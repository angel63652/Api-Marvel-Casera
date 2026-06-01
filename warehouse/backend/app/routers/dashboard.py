from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta

from app.database import get_db
from app.models.product import Product
from app.models.location import Location
from app.models.order import Order, OrderStatus
from app.models.movement import Movement
from app.models.truck import TruckSchedule, ScheduleStatus
from app.services import stock_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats")
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    total_products = (
        await db.execute(
            select(func.count(Product.id)).where(Product.active.is_(True))
        )
    ).scalar() or 0

    total_locations = (
        await db.execute(
            select(func.count(Location.id)).where(Location.is_active.is_(True))
        )
    ).scalar() or 0

    orders_today = (
        await db.execute(
            select(func.count(Order.id)).where(
                Order.created_at >= today_start, Order.created_at < today_end
            )
        )
    ).scalar() or 0

    orders_pending = (
        await db.execute(
            select(func.count(Order.id)).where(Order.status == OrderStatus.PENDING)
        )
    ).scalar() or 0

    orders_picking = (
        await db.execute(
            select(func.count(Order.id)).where(Order.status == OrderStatus.PICKING)
        )
    ).scalar() or 0

    trucks_today = (
        await db.execute(
            select(func.count(TruckSchedule.id)).where(
                TruckSchedule.date >= today_start, TruckSchedule.date < today_end
            )
        )
    ).scalar() or 0

    trucks_scheduled = (
        await db.execute(
            select(func.count(TruckSchedule.id)).where(
                TruckSchedule.status == ScheduleStatus.SCHEDULED
            )
        )
    ).scalar() or 0

    low_stock = await stock_service.check_low_stock(db)

    # Recent movements (last 10)
    recent_mov_result = await db.execute(
        select(Movement).order_by(Movement.date.desc()).limit(10)
    )
    recent_movements = [
        {
            "id": m.id,
            "type": m.type.value if hasattr(m.type, "value") else m.type,
            "reference": m.reference,
            "date": m.date.isoformat() if m.date else None,
            "supplier": m.supplier,
            "line_count": len(m.lines),
        }
        for m in recent_mov_result.scalars().all()
    ]

    # Recent orders (last 5)
    recent_ord_result = await db.execute(
        select(Order).order_by(Order.created_at.desc()).limit(5)
    )
    recent_orders = [
        {
            "id": o.id,
            "order_number": o.order_number,
            "customer_name": o.customer_name,
            "status": o.status.value if hasattr(o.status, "value") else o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "total_lines": len(o.lines),
        }
        for o in recent_ord_result.scalars().all()
    ]

    # Today's truck schedule
    today_trucks_result = await db.execute(
        select(TruckSchedule)
        .where(TruckSchedule.date >= today_start, TruckSchedule.date < today_end)
        .order_by(TruckSchedule.departure_time.nullslast())
    )
    today_trucks = [
        {
            "id": s.id,
            "truck_plate": s.truck.plate if s.truck else None,
            "driver_name": (
                f"{s.driver.name} {s.driver.surname}" if s.driver else None
            ),
            "route_description": s.route_description,
            "status": s.status.value if hasattr(s.status, "value") else s.status,
            "departure_time": s.departure_time.isoformat()
            if s.departure_time
            else None,
        }
        for s in today_trucks_result.scalars().all()
    ]

    return {
        "total_products": total_products,
        "total_locations": total_locations,
        "low_stock_count": len(low_stock),
        "orders_today": orders_today,
        "orders_pending": orders_pending,
        "orders_picking": orders_picking,
        "trucks_today": trucks_today,
        "trucks_scheduled": trucks_scheduled,
        "recent_movements": recent_movements,
        "recent_orders": recent_orders,
        "low_stock_products": low_stock[:10],
        "today_trucks": today_trucks,
    }
