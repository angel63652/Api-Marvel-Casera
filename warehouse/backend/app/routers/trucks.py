from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime, timezone
from collections import defaultdict

from app.database import get_db
from app.models.truck import (
    Truck,
    TruckSchedule,
    TruckReturn,
    ScheduleType,
    ScheduleStatus,
)
from app.models.employee import Employee
from app.schemas.truck import (
    TruckCreate,
    TruckUpdate,
    TruckResponse,
    TruckScheduleCreate,
    TruckScheduleUpdate,
    TruckScheduleResponse,
    TruckScheduleComplete,
    TruckReturnCreate,
    TruckReturnResponse,
    TruckCalendarDay,
)
from app.auth import require_role, get_current_employee

router = APIRouter(prefix="/trucks", tags=["Camiones"])


def _truck_resp(t: Truck) -> TruckResponse:
    return TruckResponse(
        id=t.id,
        plate=t.plate,
        brand=t.brand,
        model_name=t.model,
        capacity_kg=t.capacity_kg,
        capacity_m3=t.capacity_m3,
        driver_id=t.driver_id,
        driver_name=(f"{t.driver.name} {t.driver.surname}" if t.driver else None),
        is_active=t.is_active,
        notes=t.notes,
    )


def _sched_resp(s: TruckSchedule) -> TruckScheduleResponse:
    return TruckScheduleResponse(
        id=s.id,
        truck_id=s.truck_id,
        truck_plate=s.truck.plate if s.truck else None,
        driver_id=s.driver_id,
        driver_name=(f"{s.driver.name} {s.driver.surname}" if s.driver else None),
        date=s.date,
        schedule_type=s.schedule_type,
        route_description=s.route_description,
        estimated_cost=s.estimated_cost,
        actual_cost=s.actual_cost,
        departure_time=s.departure_time,
        return_time=s.return_time,
        status=s.status,
        orders_assigned=s.orders_assigned or [],
        notes=s.notes,
        created_by=s.created_by,
    )


# ---- Fleet -----------------------------------------------------------------
@router.get("", response_model=list[TruckResponse])
async def list_trucks(active_only: bool = False, db: AsyncSession = Depends(get_db)):
    stmt = select(Truck)
    if active_only:
        stmt = stmt.where(Truck.is_active.is_(True))
    stmt = stmt.order_by(Truck.plate)
    result = await db.execute(stmt)
    return [_truck_resp(t) for t in result.scalars().all()]


@router.post("", response_model=TruckResponse, status_code=201)
async def create_truck(
    payload: TruckCreate,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("MANAGER")),
):
    existing = await db.execute(select(Truck).where(Truck.plate == payload.plate))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="Ya existe un camión con esa matrícula")
    truck = Truck(
        plate=payload.plate,
        brand=payload.brand,
        model=payload.model_name,
        capacity_kg=payload.capacity_kg,
        capacity_m3=payload.capacity_m3,
        driver_id=payload.driver_id,
        is_active=payload.is_active,
        notes=payload.notes,
    )
    db.add(truck)
    await db.flush()
    await db.refresh(truck)
    return _truck_resp(truck)


# ---- Schedules (declared before /{truck_id} to avoid route shadowing) ------
@router.get("/schedules", response_model=list[TruckScheduleResponse])
async def list_schedules(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    truck_id: Optional[int] = None,
    status: Optional[ScheduleStatus] = None,
    schedule_type: Optional[ScheduleType] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(TruckSchedule)
    if start_date:
        stmt = stmt.where(TruckSchedule.date >= start_date)
    if end_date:
        stmt = stmt.where(TruckSchedule.date <= end_date)
    if truck_id:
        stmt = stmt.where(TruckSchedule.truck_id == truck_id)
    if status:
        stmt = stmt.where(TruckSchedule.status == status)
    if schedule_type:
        stmt = stmt.where(TruckSchedule.schedule_type == schedule_type)
    stmt = stmt.order_by(TruckSchedule.date)
    result = await db.execute(stmt)
    return [_sched_resp(s) for s in result.scalars().all()]


@router.get("/schedules/calendar", response_model=list[TruckCalendarDay])
async def schedules_calendar(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(TruckSchedule)
    if start_date:
        stmt = stmt.where(TruckSchedule.date >= start_date)
    if end_date:
        stmt = stmt.where(TruckSchedule.date <= end_date)
    stmt = stmt.order_by(TruckSchedule.date)
    result = await db.execute(stmt)
    grouped: dict[str, list] = defaultdict(list)
    for s in result.scalars().all():
        key = s.date.date().isoformat()
        grouped[key].append(_sched_resp(s))
    return [TruckCalendarDay(date=k, schedules=v) for k, v in sorted(grouped.items())]


@router.get("/schedules/history")
async def schedules_history(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(TruckSchedule).where(
        TruckSchedule.status == ScheduleStatus.COMPLETED
    )
    if start_date:
        stmt = stmt.where(TruckSchedule.date >= start_date)
    if end_date:
        stmt = stmt.where(TruckSchedule.date <= end_date)
    stmt = stmt.order_by(TruckSchedule.date.desc())
    result = await db.execute(stmt)
    schedules = result.scalars().all()

    total_trips = len(schedules)
    total_cost = sum((s.actual_cost or 0.0) for s in schedules)
    total_estimated = sum((s.estimated_cost or 0.0) for s in schedules)
    avg_cost = (total_cost / total_trips) if total_trips else 0.0

    return {
        "stats": {
            "total_trips": total_trips,
            "total_cost": round(total_cost, 2),
            "total_estimated": round(total_estimated, 2),
            "avg_cost_per_trip": round(avg_cost, 2),
            "cost_deviation": round(total_cost - total_estimated, 2),
        },
        "schedules": [_sched_resp(s) for s in schedules],
    }


@router.get("/schedules/{schedule_id}", response_model=TruckScheduleResponse)
async def get_schedule(schedule_id: int, db: AsyncSession = Depends(get_db)):
    s = await db.get(TruckSchedule, schedule_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Programación no encontrada")
    return _sched_resp(s)


@router.post("/schedules", response_model=TruckScheduleResponse, status_code=201)
async def create_schedule(
    payload: TruckScheduleCreate,
    db: AsyncSession = Depends(get_db),
    current: Employee = Depends(require_role("MANAGER", "OFFICE")),
):
    truck = await db.get(Truck, payload.truck_id)
    if truck is None:
        raise HTTPException(status_code=404, detail="Camión no encontrado")
    s = TruckSchedule(
        truck_id=payload.truck_id,
        driver_id=payload.driver_id or truck.driver_id,
        date=payload.date,
        schedule_type=payload.schedule_type,
        route_description=payload.route_description,
        estimated_cost=payload.estimated_cost,
        departure_time=payload.departure_time,
        return_time=payload.return_time,
        orders_assigned=payload.orders_assigned or [],
        notes=payload.notes,
        created_by=current.id,
        status=ScheduleStatus.SCHEDULED,
    )
    db.add(s)
    await db.flush()
    await db.refresh(s)
    return _sched_resp(s)


@router.put("/schedules/{schedule_id}", response_model=TruckScheduleResponse)
async def update_schedule(
    schedule_id: int,
    payload: TruckScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("MANAGER", "OFFICE")),
):
    s = await db.get(TruckSchedule, schedule_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Programación no encontrada")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    await db.flush()
    await db.refresh(s)
    return _sched_resp(s)


@router.post("/schedules/{schedule_id}/complete", response_model=TruckScheduleResponse)
async def complete_schedule(
    schedule_id: int,
    payload: TruckScheduleComplete,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("MANAGER", "OFFICE", "DRIVER")),
):
    s = await db.get(TruckSchedule, schedule_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Programación no encontrada")
    s.status = ScheduleStatus.COMPLETED
    if payload.actual_cost is not None:
        s.actual_cost = payload.actual_cost
    if payload.notes:
        s.notes = payload.notes
    s.return_time = payload.return_time or datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(s)
    return _sched_resp(s)


@router.post("/schedules/{schedule_id}/returns", response_model=TruckReturnResponse, status_code=201)
async def register_return(
    schedule_id: int,
    payload: TruckReturnCreate,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("MANAGER", "OFFICE", "DRIVER")),
):
    s = await db.get(TruckSchedule, schedule_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Programación no encontrada")
    ret = TruckReturn(
        truck_schedule_id=schedule_id,
        order_id=payload.order_id,
        product_id=payload.product_id,
        quantity=payload.quantity,
        reason=payload.reason,
    )
    db.add(ret)
    await db.flush()
    await db.refresh(ret)
    return TruckReturnResponse(
        id=ret.id,
        truck_schedule_id=ret.truck_schedule_id,
        order_id=ret.order_id,
        product_id=ret.product_id,
        product_name=ret.product.name if ret.product else None,
        quantity=ret.quantity,
        reason=ret.reason,
        processed_at=ret.processed_at,
    )


# ---- Truck by id (kept last so it doesn't shadow /schedules) ---------------
@router.get("/{truck_id}", response_model=TruckResponse)
async def get_truck(truck_id: int, db: AsyncSession = Depends(get_db)):
    truck = await db.get(Truck, truck_id)
    if truck is None:
        raise HTTPException(status_code=404, detail="Camión no encontrado")
    return _truck_resp(truck)


@router.put("/{truck_id}", response_model=TruckResponse)
async def update_truck(
    truck_id: int,
    payload: TruckUpdate,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("MANAGER")),
):
    truck = await db.get(Truck, truck_id)
    if truck is None:
        raise HTTPException(status_code=404, detail="Camión no encontrado")
    data = payload.model_dump(exclude_unset=True)
    if "model_name" in data:
        truck.model = data.pop("model_name")
    for field, value in data.items():
        setattr(truck, field, value)
    await db.flush()
    await db.refresh(truck)
    return _truck_resp(truck)
