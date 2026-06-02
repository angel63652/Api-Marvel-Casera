"""Client portal API: catalog, orders, profile, change requests.

All endpoints require a portal token and are scoped to the caller's customer
(tenancy). Portal orders never oversell: stock is reserved atomically with an
availability check (`reserve_if_available`).
"""
import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.events import broker

from app.database import get_db
from app.auth import get_current_customer_user
from app.models.customer import (
    Customer, CustomerUser, CustomerAddress, CustomerChangeRequest,
    ChangeRequestTarget, ChangeRequestStatus,
)
from app.models.product import Product
from app.models.order import Order, OrderLine, OrderStatus, OrderLineStatus
from app.schemas.portal import (
    CatalogItem, PortalOrderCreate, PortalOrderResponse, PortalOrderLine,
    ProfileResponse, CustomerSummary, AddressResponse,
    ChangeRequestCreate, ChangeRequestResponse,
)
from app.services import reservation_service, picking_service, pricing_service

router = APIRouter(prefix="/api/portal", tags=["Portal · Cliente"])


def _customer_ref(customer_id: int) -> str:
    return f"CUST-{customer_id}"


# ---- Catalog ---------------------------------------------------------------
@router.get("/catalog", response_model=list[CatalogItem])
async def catalog(
    response: Response,
    user: CustomerUser = Depends(get_current_customer_user),
    search: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    customer = await db.get(Customer, user.customer_id)
    tier = customer.price_tier if customer else None

    stmt = select(Product).where(Product.active.is_(True))
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            (Product.name.ilike(like)) | (Product.niu.ilike(like)) | (Product.barcode.ilike(like))
        )
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    response.headers["X-Total-Count"] = str(total or 0)
    stmt = stmt.order_by(Product.name).limit(limit).offset(offset)
    products = (await db.execute(stmt)).scalars().all()

    items = []
    for p in products:
        available = (p.current_stock or 0.0) - (p.reserved_stock or 0.0)
        items.append(
            CatalogItem(
                id=p.id, niu=p.niu, barcode=p.barcode, name=p.name,
                category=p.category,
                unit=p.unit.value if hasattr(p.unit, "value") else p.unit,
                available_stock=available,
                price=pricing_service.resolve_price_from_loaded(p, tier),
            )
        )
    return items


@router.get("/catalog/stream")
async def catalog_stream(
    user: CustomerUser = Depends(get_current_customer_user),
):
    """Server-Sent Events stream of stock-availability changes (real-time).

    Emits `event: stock` with `{product_id, available_stock}` whenever stock
    changes, plus periodic heartbeats to keep the connection alive.
    """
    async def event_gen():
        # Immediate comment so the client knows it's connected.
        yield ": connected\n\n"
        async with broker.subscribe() as q:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"event: {event.get('type','message')}\ndata: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"  # heartbeat

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---- Orders ----------------------------------------------------------------
async def _build_order_response(order: Order, tier: str | None, db: AsyncSession) -> PortalOrderResponse:
    lines = []
    total = 0.0
    has_price = False
    for line in order.lines:
        # Use the frozen price captured at order time; fall back to live pricing
        # for legacy lines created before C14.
        price = line.unit_price
        if price is None:
            price = await pricing_service.resolve_price(db, line.product_id, tier)
        line_total = (price * line.quantity_requested) if price is not None else None
        if line_total is not None:
            total += line_total
            has_price = True
        lines.append(PortalOrderLine(
            product_id=line.product_id,
            product_name=line.product.name if line.product else None,
            quantity=line.quantity_requested,
            unit_price=price,
            line_total=line_total,
        ))
    return PortalOrderResponse(
        id=order.id,
        order_number=order.order_number,
        status=order.status.value if hasattr(order.status, "value") else order.status,
        created_at=order.created_at.isoformat() if order.created_at else None,
        notes=order.notes,
        lines=lines,
        total=round(total, 2) if has_price else None,
    )


@router.post("/orders", response_model=PortalOrderResponse, status_code=201)
async def create_portal_order(
    payload: PortalOrderCreate,
    user: CustomerUser = Depends(get_current_customer_user),
    db: AsyncSession = Depends(get_db),
):
    customer = await db.get(Customer, user.customer_id)
    if customer is None or customer.status.value != "ACTIVE":
        raise HTTPException(
            status_code=403,
            detail="La cuenta debe estar aprobada (ACTIVE) para realizar pedidos",
        )

    # Validate products exist & are active before creating the order.
    products: dict[int, Product] = {}
    for item in payload.items:
        p = await db.get(Product, item.product_id)
        if p is None or not p.active:
            raise HTTPException(status_code=404, detail=f"Producto {item.product_id} no disponible")
        products[item.product_id] = p

    # Create the internal Order (unique number with savepoint retry).
    order = None
    for _ in range(5):
        candidate = await picking_service.generate_order_number(db)
        try:
            async with db.begin_nested():
                order = Order(
                    order_number=candidate,
                    customer_name=customer.company_name,
                    customer_id=_customer_ref(customer.id),
                    notes=payload.notes,
                    status=OrderStatus.PENDING,
                )
                db.add(order)
                await db.flush()
            break
        except IntegrityError:
            order = None
    if order is None:
        raise HTTPException(status_code=500, detail="No se pudo asignar número de orden")

    # Reserve atomically (no overselling); add order lines.
    for item in payload.items:
        product = products[item.product_id]
        res = await reservation_service.reserve_if_available(
            db, item.product_id, item.quantity, order_id=order.id, source="PORTAL"
        )
        if res is None:
            available = await reservation_service.get_available(db, item.product_id)
            raise HTTPException(
                status_code=409,
                detail=f"Stock insuficiente de '{product.name}': disponible {available}, solicitado {item.quantity}",
            )
        location_id = product.locations[0].location_id if product.locations else None
        # Freeze the sale price at order time (tier price → base).
        unit_price = pricing_service.resolve_price_from_loaded(product, customer.price_tier)
        db.add(OrderLine(
            order_id=order.id,
            product_id=item.product_id,
            quantity_requested=item.quantity,
            location_id=location_id,
            unit_price=unit_price,
            status=OrderLineStatus.PENDING,
        ))
    await db.flush()
    # Real-time: availability dropped for the ordered products.
    for pid in {item.product_id for item in payload.items}:
        await reservation_service.notify_available(db, pid)
    order = (await db.execute(select(Order).where(Order.id == order.id))).scalar_one()
    return await _build_order_response(order, customer.price_tier, db)


@router.get("/orders", response_model=list[PortalOrderResponse])
async def list_portal_orders(
    user: CustomerUser = Depends(get_current_customer_user),
    db: AsyncSession = Depends(get_db),
):
    customer = await db.get(Customer, user.customer_id)
    ref = _customer_ref(user.customer_id)
    stmt = (
        select(Order).where(Order.customer_id == ref).order_by(Order.created_at.desc())
    )
    orders = (await db.execute(stmt)).scalars().all()
    return [await _build_order_response(o, customer.price_tier if customer else None, db) for o in orders]


@router.get("/orders/{order_id}", response_model=PortalOrderResponse)
async def get_portal_order(
    order_id: int,
    user: CustomerUser = Depends(get_current_customer_user),
    db: AsyncSession = Depends(get_db),
):
    order = await db.get(Order, order_id)
    if order is None or order.customer_id != _customer_ref(user.customer_id):
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    customer = await db.get(Customer, user.customer_id)
    return await _build_order_response(order, customer.price_tier if customer else None, db)


# ---- Profile / addresses ---------------------------------------------------
def _addr_resp(a: CustomerAddress) -> AddressResponse:
    return AddressResponse(
        id=a.id,
        type=a.type.value if hasattr(a.type, "value") else a.type,
        label=a.label, line1=a.line1, line2=a.line2, city=a.city,
        province=a.province, postal_code=a.postal_code, country=a.country,
        is_default=a.is_default,
    )


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(
    user: CustomerUser = Depends(get_current_customer_user),
    db: AsyncSession = Depends(get_db),
):
    customer = await db.get(Customer, user.customer_id)
    return ProfileResponse(
        customer=CustomerSummary(
            id=customer.id, company_name=customer.company_name,
            tax_id=customer.tax_id,
            status=customer.status.value if hasattr(customer.status, "value") else customer.status,
        ),
        contact_email=customer.contact_email,
        contact_phone=customer.contact_phone,
        price_tier=customer.price_tier,
        addresses=[_addr_resp(a) for a in customer.addresses],
    )


@router.get("/addresses", response_model=list[AddressResponse])
async def list_addresses(
    user: CustomerUser = Depends(get_current_customer_user),
    db: AsyncSession = Depends(get_db),
):
    customer = await db.get(Customer, user.customer_id)
    return [_addr_resp(a) for a in customer.addresses]


# ---- Change requests (fiscal data / addresses go through approval) ----------
@router.post("/profile/change-request", response_model=ChangeRequestResponse, status_code=201)
async def create_change_request(
    payload: ChangeRequestCreate,
    user: CustomerUser = Depends(get_current_customer_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        target = ChangeRequestTarget(payload.target)
    except ValueError:
        raise HTTPException(status_code=400, detail="target debe ser FISCAL o ADDRESS")
    cr = CustomerChangeRequest(
        customer_id=user.customer_id,
        requested_by=user.id,
        target=target,
        payload=payload.payload,
        status=ChangeRequestStatus.PENDING,
    )
    db.add(cr)
    await db.flush()
    return ChangeRequestResponse(
        id=cr.id, target=cr.target.value, status=cr.status.value, payload=cr.payload
    )


@router.get("/profile/change-requests", response_model=list[ChangeRequestResponse])
async def list_my_change_requests(
    user: CustomerUser = Depends(get_current_customer_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(CustomerChangeRequest).where(
        CustomerChangeRequest.customer_id == user.customer_id
    ).order_by(CustomerChangeRequest.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [
        ChangeRequestResponse(
            id=r.id, target=r.target.value, status=r.status.value, payload=r.payload
        )
        for r in rows
    ]
