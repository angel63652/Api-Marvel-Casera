from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime, timezone

from app.database import get_db
from app.models.replenishment import (
    Replenishment,
    ReplenishmentLine,
    ReplenishmentStatus,
    ReplenishmentPriority,
)
from app.models.product import Product
from app.models.movement import Movement, MovementLine, MovementType
from app.models.employee import Employee
from app.schemas.replenishment import (
    ReplenishmentCreate,
    ReplenishmentResponse,
    ReplenishmentLineResponse,
    ReplenishmentStatusUpdate,
)
from app.auth import require_role, get_current_employee
from app.services import stock_service

router = APIRouter(prefix="/replenishments", tags=["Reposiciones"])


def _serialize_line(line: ReplenishmentLine) -> ReplenishmentLineResponse:
    return ReplenishmentLineResponse(
        id=line.id,
        replenishment_id=line.replenishment_id,
        product_id=line.product_id,
        location_id=line.location_id,
        current_qty=line.current_qty,
        min_qty=line.min_qty,
        requested_qty=line.requested_qty,
        received_qty=line.received_qty,
        product_name=line.product.name if line.product else None,
        product_barcode=line.product.barcode if line.product else None,
        location_code=line.location.code if line.location else None,
    )


def _serialize(rep: Replenishment) -> ReplenishmentResponse:
    return ReplenishmentResponse(
        id=rep.id,
        status=rep.status,
        priority=rep.priority,
        notes=rep.notes,
        created_at=rep.created_at,
        completed_at=rep.completed_at,
        created_by=rep.created_by,
        lines=[_serialize_line(l) for l in rep.lines],
        created_by_name=(
            f"{rep.created_by_employee.name} {rep.created_by_employee.surname}"
            if rep.created_by_employee
            else None
        ),
    )


@router.get("", response_model=list[ReplenishmentResponse])
async def list_replenishments(
    status: Optional[ReplenishmentStatus] = None,
    priority: Optional[ReplenishmentPriority] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Replenishment)
    if status:
        stmt = stmt.where(Replenishment.status == status)
    if priority:
        stmt = stmt.where(Replenishment.priority == priority)
    stmt = stmt.order_by(Replenishment.created_at.desc())
    result = await db.execute(stmt)
    return [_serialize(r) for r in result.scalars().all()]


@router.get("/{replenishment_id}", response_model=ReplenishmentResponse)
async def get_replenishment(replenishment_id: int, db: AsyncSession = Depends(get_db)):
    rep = await db.get(Replenishment, replenishment_id)
    if rep is None:
        raise HTTPException(status_code=404, detail="Reposición no encontrada")
    return _serialize(rep)


@router.post("", response_model=ReplenishmentResponse, status_code=201)
async def create_replenishment(
    payload: ReplenishmentCreate,
    db: AsyncSession = Depends(get_db),
    current: Employee = Depends(require_role("MANAGER", "OFFICE")),
):
    rep = Replenishment(
        priority=payload.priority,
        notes=payload.notes,
        created_by=payload.created_by or current.id,
    )
    db.add(rep)
    await db.flush()
    for line_in in payload.lines:
        db.add(
            ReplenishmentLine(
                replenishment_id=rep.id,
                product_id=line_in.product_id,
                location_id=line_in.location_id,
                current_qty=line_in.current_qty,
                min_qty=line_in.min_qty,
                requested_qty=line_in.requested_qty,
            )
        )
    await db.flush()
    await db.refresh(rep)
    return _serialize(rep)


@router.post("/auto-generate", response_model=ReplenishmentResponse, status_code=201)
async def auto_generate(
    db: AsyncSession = Depends(get_db),
    current: Employee = Depends(require_role("MANAGER", "OFFICE")),
):
    """Scan all low-stock products and create a single replenishment order."""
    low = await stock_service.check_low_stock(db)
    if not low:
        raise HTTPException(status_code=400, detail="No hay productos bajo el mínimo de stock")

    rep = Replenishment(
        priority=ReplenishmentPriority.HIGH,
        notes="Generada automáticamente desde stock bajo",
        created_by=current.id,
    )
    db.add(rep)
    await db.flush()
    for item in low:
        db.add(
            ReplenishmentLine(
                replenishment_id=rep.id,
                product_id=item["product_id"],
                location_id=None,
                current_qty=item["current_stock"],
                min_qty=item["min_stock"],
                requested_qty=max(item["deficit"], item["min_stock"]),
            )
        )
    await db.flush()
    await db.refresh(rep)
    return _serialize(rep)


@router.put("/{replenishment_id}/status", response_model=ReplenishmentResponse)
async def update_status(
    replenishment_id: int,
    payload: ReplenishmentStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("MANAGER", "OFFICE")),
):
    rep = await db.get(Replenishment, replenishment_id)
    if rep is None:
        raise HTTPException(status_code=404, detail="Reposición no encontrada")
    rep.status = payload.status
    if payload.notes:
        rep.notes = payload.notes
    if payload.status == ReplenishmentStatus.COMPLETED:
        rep.completed_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(rep)
    return _serialize(rep)


@router.post("/{replenishment_id}/lines/{line_id}/receive", response_model=ReplenishmentResponse)
async def receive_line(
    replenishment_id: int,
    line_id: int,
    received_qty: float,
    db: AsyncSession = Depends(get_db),
    current: Employee = Depends(require_role("MANAGER", "OFFICE", "PICKER")),
):
    """Mark a replenishment line as received, generating a stock movement."""
    line = await db.get(ReplenishmentLine, line_id)
    if line is None or line.replenishment_id != replenishment_id:
        raise HTTPException(status_code=404, detail="Línea de reposición no encontrada")

    line.received_qty = (line.received_qty or 0.0) + received_qty

    # Register the incoming stock as a REPLENISHMENT movement.
    movement = Movement(
        type=MovementType.REPLENISHMENT,
        reference=f"REP-{replenishment_id}",
        notes=f"Recepción reposición #{replenishment_id}",
        user_id=current.id,
    )
    db.add(movement)
    await db.flush()
    db.add(
        MovementLine(
            movement_id=movement.id,
            product_id=line.product_id,
            location_id=line.location_id,
            quantity=received_qty,
        )
    )
    await stock_service.apply_movement_delta(line.product_id, received_qty, db)
    if line.location_id:
        await stock_service.update_location_load(line.location_id, received_qty, db)
        await stock_service.update_product_location_qty(
            line.product_id, line.location_id, received_qty, db
        )

    # Auto-complete when every line is fully received.
    rep = await db.get(Replenishment, replenishment_id)
    if all((l.received_qty or 0.0) >= l.requested_qty for l in rep.lines):
        rep.status = ReplenishmentStatus.COMPLETED
        rep.completed_at = datetime.now(timezone.utc)
    else:
        rep.status = ReplenishmentStatus.IN_PROGRESS

    await db.flush()
    await db.refresh(rep)
    return _serialize(rep)
