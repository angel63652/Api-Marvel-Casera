from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models.movement import Movement, MovementLine, MovementType
from app.models.product import Product
from app.models.employee import Employee
from app.schemas.movement import (
    MovementCreate, MovementResponse, MovementLineResponse, StockAdjustmentRequest,
)
from app.auth import require_role, get_current_employee, verify_password
from app.services import stock_service, reservation_service

router = APIRouter(prefix="/movements", tags=["Movimientos"])

INBOUND = {MovementType.ENTRY, MovementType.REPLENISHMENT, MovementType.RETURN}


def _serialize_line(line: MovementLine) -> MovementLineResponse:
    return MovementLineResponse(
        id=line.id,
        movement_id=line.movement_id,
        product_id=line.product_id,
        location_id=line.location_id,
        quantity=line.quantity,
        unit_price=line.unit_price,
        lot=line.lot,
        expiry_date=line.expiry_date,
        product_name=line.product.name if line.product else None,
        product_barcode=line.product.barcode if line.product else None,
        location_code=line.location.code if line.location else None,
    )


def _serialize(movement: Movement) -> MovementResponse:
    return MovementResponse(
        id=movement.id,
        type=movement.type,
        reference=movement.reference,
        date=movement.date,
        notes=movement.notes,
        supplier=movement.supplier,
        user_id=movement.user_id,
        created_at=movement.created_at,
        lines=[_serialize_line(l) for l in movement.lines],
        user_name=(
            f"{movement.user.name} {movement.user.surname}"
            if movement.user
            else None
        ),
    )


@router.get("", response_model=list[MovementResponse])
async def list_movements(
    response: Response,
    type: Optional[MovementType] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    product_id: Optional[int] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Movement)
    count_stmt = select(func.count(func.distinct(Movement.id)))
    if type:
        stmt = stmt.where(Movement.type == type)
        count_stmt = count_stmt.where(Movement.type == type)
    if start_date:
        stmt = stmt.where(Movement.date >= start_date)
        count_stmt = count_stmt.where(Movement.date >= start_date)
    if end_date:
        stmt = stmt.where(Movement.date <= end_date)
        count_stmt = count_stmt.where(Movement.date <= end_date)
    if product_id:
        stmt = stmt.join(MovementLine).where(MovementLine.product_id == product_id)
        count_stmt = count_stmt.join(MovementLine).where(
            MovementLine.product_id == product_id
        )
    total = await db.scalar(count_stmt)
    response.headers["X-Total-Count"] = str(total or 0)
    stmt = stmt.order_by(Movement.date.desc()).distinct().limit(limit).offset(offset)
    result = await db.execute(stmt)
    return [_serialize(m) for m in result.scalars().unique().all()]


@router.get("/report/summary")
async def movement_summary(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(
            Movement.type,
            func.count(func.distinct(Movement.id)),
            func.coalesce(func.sum(MovementLine.quantity), 0.0),
            func.coalesce(
                func.sum(MovementLine.quantity * func.coalesce(MovementLine.unit_price, 0.0)),
                0.0,
            ),
        )
        .join(MovementLine, MovementLine.movement_id == Movement.id)
    )
    if start_date:
        stmt = stmt.where(Movement.date >= start_date)
    if end_date:
        stmt = stmt.where(Movement.date <= end_date)
    stmt = stmt.group_by(Movement.type)
    result = await db.execute(stmt)
    items = []
    for mtype, count, qty, value in result.all():
        items.append(
            {
                "type": mtype.value if hasattr(mtype, "value") else mtype,
                "count": count,
                "total_quantity": float(qty or 0.0),
                "total_value": float(value or 0.0),
            }
        )
    return {"summary": items, "start_date": start_date, "end_date": end_date}


@router.get("/{movement_id}", response_model=MovementResponse)
async def get_movement(movement_id: int, db: AsyncSession = Depends(get_db)):
    movement = await db.get(Movement, movement_id)
    if movement is None:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    return _serialize(movement)


@router.post("", response_model=MovementResponse, status_code=201)
async def create_movement(
    payload: MovementCreate,
    db: AsyncSession = Depends(get_db),
    current: Employee = Depends(require_role("MANAGER", "OFFICE", "PICKER")),
):
    if payload.type == MovementType.ADJUSTMENT:
        raise HTTPException(
            status_code=403,
            detail="Los ajustes de stock requieren aprobación: usa POST /movements/adjustment",
        )
    movement = Movement(
        type=payload.type,
        reference=payload.reference,
        date=payload.date or datetime.utcnow(),
        notes=payload.notes,
        supplier=payload.supplier,
        user_id=payload.user_id or current.id,
    )
    db.add(movement)
    await db.flush()

    sign = 1.0 if payload.type in INBOUND else -1.0
    for line_in in payload.lines:
        product = await db.get(Product, line_in.product_id)
        if product is None:
            raise HTTPException(
                status_code=404,
                detail=f"Producto {line_in.product_id} no encontrado",
            )
        line = MovementLine(
            movement_id=movement.id,
            product_id=line_in.product_id,
            location_id=line_in.location_id,
            quantity=line_in.quantity,
            unit_price=line_in.unit_price,
            lot=line_in.lot,
            expiry_date=line_in.expiry_date,
        )
        db.add(line)

        delta = sign * line_in.quantity
        if payload.type == MovementType.ADJUSTMENT:
            # Adjustments set an explicit signed delta via quantity.
            delta = line_in.quantity
        await stock_service.apply_movement_delta(line_in.product_id, delta, db)
        if line_in.location_id:
            await stock_service.update_location_load(line_in.location_id, delta, db)
            await stock_service.update_product_location_qty(
                line_in.product_id, line_in.location_id, delta, db
            )

    await db.flush()
    # Real-time: stock changed for the affected products.
    for pid in {line.product_id for line in payload.lines}:
        await reservation_service.notify_available(db, pid)
    # Re-select so selectin loaders populate lines + their product/location within
    # the async context (avoids a lazy load during sync serialization).
    movement = (
        await db.execute(select(Movement).where(Movement.id == movement.id))
    ).scalar_one()
    return _serialize(movement)


@router.post("/adjustment", response_model=MovementResponse, status_code=201)
async def create_stock_adjustment(
    payload: StockAdjustmentRequest,
    db: AsyncSession = Depends(get_db),
    current: Employee = Depends(require_role("MANAGER")),
):
    """Manual stock correction (ADJUSTMENT) gated by manager password re-auth.

    Sensitive: it sets an arbitrary signed delta on stock, so we re-verify the
    caller's password before applying it. Routed here instead of the generic
    movements endpoint, which rejects ADJUSTMENT.
    """
    if not verify_password(payload.password, current.hashed_password):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    if payload.quantity == 0:
        raise HTTPException(status_code=400, detail="El ajuste no puede ser 0")

    product = await db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    movement = Movement(
        type=MovementType.ADJUSTMENT,
        reference="ADJUSTMENT",
        date=datetime.utcnow(),
        notes=payload.reason,
        user_id=current.id,
    )
    db.add(movement)
    await db.flush()
    db.add(MovementLine(
        movement_id=movement.id,
        product_id=payload.product_id,
        location_id=payload.location_id,
        quantity=payload.quantity,  # signed
    ))
    # ADJUSTMENT delta carries its own sign.
    await stock_service.apply_movement_delta(payload.product_id, payload.quantity, db)
    if payload.location_id:
        await stock_service.update_location_load(payload.location_id, payload.quantity, db)
        await stock_service.update_product_location_qty(
            payload.product_id, payload.location_id, payload.quantity, db
        )
    await db.flush()
    await reservation_service.notify_available(db, payload.product_id)
    movement = (
        await db.execute(select(Movement).where(Movement.id == movement.id))
    ).scalar_one()
    return _serialize(movement)
