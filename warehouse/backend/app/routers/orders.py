from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select, or_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime, timezone

from app.database import get_db
from app.models.order import Order, OrderLine, OrderStatus, OrderLineStatus
from app.models.product import Product
from app.models.employee import Employee
from app.schemas.order import (
    OrderCreate,
    OrderResponse,
    OrderLineResponse,
    PickingUpdate,
    ObservationRequest,
    ConformityRequest,
    ReturnRequest,
    StartPickingRequest,
    PickingListItem,
)
from app.auth import get_current_employee, require_role
from app.services import picking_service, stock_service, reservation_service

router = APIRouter(prefix="/orders", tags=["Órdenes"])


def _serialize_line(line: OrderLine) -> OrderLineResponse:
    return OrderLineResponse(
        id=line.id,
        order_id=line.order_id,
        product_id=line.product_id,
        quantity_requested=line.quantity_requested,
        quantity_picked=line.quantity_picked,
        location_id=line.location_id,
        status=line.status,
        observations=line.observations,
        picked_by=line.picked_by,
        picked_at=line.picked_at,
        product_name=line.product.name if line.product else None,
        product_barcode=line.product.barcode if line.product else None,
        product_niu=line.product.niu if line.product else None,
        location_code=line.location.code if line.location else None,
        picker_name=(
            f"{line.picker.name} {line.picker.surname}" if line.picker else None
        ),
    )


def _serialize(order: Order) -> OrderResponse:
    lines = [_serialize_line(l) for l in order.lines]
    return OrderResponse(
        id=order.id,
        order_number=order.order_number,
        customer_name=order.customer_name,
        customer_id=order.customer_id,
        status=order.status,
        notes=order.notes,
        buyer_id=order.buyer_id,
        conformity_signed=order.conformity_signed,
        conformity_at=order.conformity_at,
        conformity_notes=order.conformity_notes,
        return_reason=order.return_reason,
        created_at=order.created_at,
        completed_at=order.completed_at,
        delivered_at=order.delivered_at,
        lines=lines,
        buyer_name=(
            f"{order.buyer.name} {order.buyer.surname}" if order.buyer else None
        ),
        total_lines=len(lines),
        lines_picked=sum(1 for l in order.lines if l.status == OrderLineStatus.PICKED),
        lines_missing=sum(1 for l in order.lines if l.status == OrderLineStatus.MISSING),
    )


@router.get("", response_model=list[OrderResponse])
async def list_orders(
    response: Response,
    status: Optional[OrderStatus] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    customer: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Order)
    if status:
        stmt = stmt.where(Order.status == status)
    if start_date:
        stmt = stmt.where(Order.created_at >= start_date)
    if end_date:
        stmt = stmt.where(Order.created_at <= end_date)
    if customer:
        like = f"%{customer}%"
        stmt = stmt.where(
            or_(Order.customer_name.ilike(like), Order.customer_id.ilike(like))
        )
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    response.headers["X-Total-Count"] = str(total or 0)
    stmt = stmt.order_by(Order.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return [_serialize(o) for o in result.scalars().all()]


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: int, db: AsyncSession = Depends(get_db)):
    order = await db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    return _serialize(order)


@router.get("/{order_id}/picking-list", response_model=list[PickingListItem])
async def picking_list(order_id: int, db: AsyncSession = Depends(get_db)):
    order = await db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    items = await picking_service.get_picking_list(order_id, db)
    return [PickingListItem(**item) for item in items]


@router.post("", response_model=OrderResponse, status_code=201)
async def create_order(
    payload: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current: Employee = Depends(require_role("OFFICE", "MANAGER")),
):
    # Assign a sequential order number, retrying on the rare unique-collision
    # race (two requests reading the same max at once). Savepoints keep the
    # outer transaction intact between attempts.
    order = None
    for _ in range(5):
        candidate = await picking_service.generate_order_number(db)
        try:
            async with db.begin_nested():
                order = Order(
                    order_number=candidate,
                    customer_name=payload.customer_name,
                    customer_id=payload.customer_id,
                    notes=payload.notes,
                    status=OrderStatus.PENDING,
                )
                db.add(order)
                await db.flush()
            break
        except IntegrityError:
            order = None
    if order is None:
        raise HTTPException(
            status_code=500, detail="No se pudo asignar un número de orden único"
        )
    for line_in in payload.lines:
        product = await db.get(Product, line_in.product_id)
        if product is None:
            raise HTTPException(
                status_code=404, detail=f"Producto {line_in.product_id} no encontrado"
            )
        # Default the pick location to the product's first assigned location.
        location_id = line_in.location_id
        if location_id is None and product.locations:
            location_id = product.locations[0].location_id
        db.add(
            OrderLine(
                order_id=order.id,
                product_id=line_in.product_id,
                quantity_requested=line_in.quantity_requested,
                location_id=location_id,
                status=OrderLineStatus.PENDING,
            )
        )
    await db.flush()
    # Hold stock for each line (available = current_stock - reserved_stock).
    for line_in in payload.lines:
        await reservation_service.reserve(
            db, line_in.product_id, line_in.quantity_requested, order_id=order.id
        )
    await db.refresh(order)
    return _serialize(order)


@router.put("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: int,
    status: OrderStatus,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("OFFICE", "MANAGER")),
):
    order = await db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    order.status = status
    # Cancelling/returning frees the order's stock holds.
    if status in (OrderStatus.CANCELLED, OrderStatus.RETURNED):
        await reservation_service.release_for_order(db, order_id)
    await db.flush()
    await db.refresh(order)
    return _serialize(order)


@router.post("/{order_id}/start-picking", response_model=OrderResponse)
async def start_picking(
    order_id: int,
    payload: StartPickingRequest,
    db: AsyncSession = Depends(get_db),
    current: Employee = Depends(require_role("PICKER", "MANAGER", "OFFICE")),
):
    order = await db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    if order.status in (OrderStatus.COMPLETED, OrderStatus.CANCELLED):
        raise HTTPException(status_code=400, detail="La orden ya está cerrada")
    picker = await db.get(Employee, payload.picker_id)
    if picker is None:
        raise HTTPException(status_code=404, detail="Operario (picker) no encontrado")
    order.buyer_id = payload.picker_id
    order.status = OrderStatus.PICKING
    await db.flush()
    await db.refresh(order)
    return _serialize(order)


@router.post("/{order_id}/lines/{line_id}/pick", response_model=OrderLineResponse)
async def pick_line(
    order_id: int,
    line_id: int,
    payload: PickingUpdate,
    db: AsyncSession = Depends(get_db),
    current: Employee = Depends(require_role("PICKER", "MANAGER", "OFFICE")),
):
    line = await db.get(OrderLine, line_id)
    if line is None or line.order_id != order_id:
        raise HTTPException(status_code=404, detail="Línea de orden no encontrada")

    # Validate scanned barcode against the expected product.
    if payload.barcode_scanned:
        ok = await picking_service.validate_barcode(
            payload.barcode_scanned, line.product_id, db
        )
        if not ok:
            raise HTTPException(
                status_code=400,
                detail="El código escaneado no coincide con el producto de esta línea",
            )

    line.quantity_picked = payload.quantity_picked
    if payload.location_id:
        line.location_id = payload.location_id
    if payload.observation:
        line.observations = payload.observation

    if payload.quantity_picked >= line.quantity_requested:
        line.status = OrderLineStatus.PICKED
    elif payload.quantity_picked > 0:
        line.status = OrderLineStatus.PARTIAL
    else:
        line.status = OrderLineStatus.PENDING

    line.picked_by = current.id
    line.picked_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(line)
    return _serialize_line(line)


@router.post("/{order_id}/lines/{line_id}/observe", response_model=OrderLineResponse)
async def observe_line(
    order_id: int,
    line_id: int,
    payload: ObservationRequest,
    db: AsyncSession = Depends(get_db),
    current: Employee = Depends(require_role("PICKER", "MANAGER", "OFFICE")),
):
    """Record an observation: product missing, location error, etc."""
    line = await db.get(OrderLine, line_id)
    if line is None or line.order_id != order_id:
        raise HTTPException(status_code=404, detail="Línea de orden no encontrada")
    line.observations = payload.observation
    line.status = payload.status or OrderLineStatus.MISSING
    line.picked_by = current.id
    line.picked_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(line)
    return _serialize_line(line)


@router.post("/{order_id}/confirm", response_model=OrderResponse)
async def confirm_order(
    order_id: int,
    payload: ConformityRequest,
    db: AsyncSession = Depends(get_db),
    current: Employee = Depends(get_current_employee),
):
    """Sign off conformity once every line has been processed.

    Allowed for the assigned picker, or any MANAGER/ADMIN.
    """
    order = await db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    role = current.role.value if hasattr(current.role, "value") else current.role
    is_authorized = role in ("ADMIN", "MANAGER") or order.buyer_id == current.id
    if not is_authorized:
        raise HTTPException(
            status_code=403,
            detail="Solo el operario asignado o un responsable puede dar conformidad",
        )

    pending = [l for l in order.lines if l.status == OrderLineStatus.PENDING]
    if pending:
        raise HTTPException(
            status_code=400,
            detail=f"Quedan {len(pending)} líneas pendientes de procesar",
        )

    # Discount picked quantities from stock (EXIT effect on cached stock).
    for line in order.lines:
        if line.quantity_picked > 0:
            await stock_service.apply_movement_delta(
                line.product_id, -line.quantity_picked, db
            )
            if line.location_id:
                await stock_service.update_location_load(
                    line.location_id, -line.quantity_picked, db
                )
                await stock_service.update_product_location_qty(
                    line.product_id, line.location_id, -line.quantity_picked, db
                )

    # Stock has physically left: free this order's holds (CONSUMED).
    await reservation_service.consume_for_order(db, order_id)

    order.conformity_signed = True
    order.conformity_at = datetime.now(timezone.utc)
    order.conformity_notes = payload.conformity_notes
    order.status = OrderStatus.COMPLETED
    order.completed_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(order)
    return _serialize(order)


@router.post("/{order_id}/return", response_model=OrderResponse)
async def return_order(
    order_id: int,
    payload: ReturnRequest,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("OFFICE", "MANAGER", "DRIVER")),
):
    order = await db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    order.status = OrderStatus.RETURNED
    order.return_reason = payload.return_reason
    # Free any remaining holds for this order.
    await reservation_service.release_for_order(db, order_id)
    await db.flush()
    await db.refresh(order)
    return _serialize(order)
