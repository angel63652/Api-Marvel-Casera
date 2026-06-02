"""Stock reservation service (R4).

Keeps `Product.reserved_stock` (cached) in sync with the ACTIVE rows of the
`stock_reservations` ledger via atomic UPDATEs, so availability is:

    available = current_stock - reserved_stock

Used by internal orders now; reused by the client portal later.
"""
from datetime import datetime, timezone

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.reservation import StockReservation, ReservationStatus
from app.events import publish_stock_change


async def _adjust_reserved(db: AsyncSession, product_id: int, delta: float) -> None:
    """Atomically bump the cached reserved_stock (never below 0)."""
    await db.execute(
        update(Product)
        .where(Product.id == product_id)
        .values(reserved_stock=func.coalesce(Product.reserved_stock, 0.0) + delta)
        .execution_options(synchronize_session=False)
    )


async def reserve(
    db: AsyncSession,
    product_id: int,
    quantity: float,
    *,
    order_id: int | None = None,
    source: str = "ORDER",
    expires_at: datetime | None = None,
) -> StockReservation:
    """Create an ACTIVE reservation and bump the cached reserved_stock."""
    res = StockReservation(
        product_id=product_id,
        order_id=order_id,
        quantity=quantity,
        status=ReservationStatus.ACTIVE,
        source=source,
        expires_at=expires_at,
    )
    db.add(res)
    await _adjust_reserved(db, product_id, quantity)
    await db.flush()
    return res


async def reserve_if_available(
    db: AsyncSession,
    product_id: int,
    quantity: float,
    *,
    order_id: int | None = None,
    source: str = "PORTAL",
    expires_at: datetime | None = None,
) -> StockReservation | None:
    """Atomically reserve only if available >= quantity (no overselling).

    Returns the reservation, or None if there is not enough available stock.
    The conditional UPDATE is the gate, so concurrent reservations cannot
    oversell (unlike `reserve`, which is unconditional / allows backorder).
    """
    available = func.coalesce(Product.current_stock, 0.0) - func.coalesce(
        Product.reserved_stock, 0.0
    )
    result = await db.execute(
        update(Product)
        .where(Product.id == product_id, available >= quantity)
        .values(reserved_stock=func.coalesce(Product.reserved_stock, 0.0) + quantity)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 0:
        return None
    res = StockReservation(
        product_id=product_id,
        order_id=order_id,
        quantity=quantity,
        status=ReservationStatus.ACTIVE,
        source=source,
        expires_at=expires_at,
    )
    db.add(res)
    await db.flush()
    return res


async def _close_active(
    db: AsyncSession, reservations, new_status: ReservationStatus
) -> float:
    """Mark the given ACTIVE reservations with new_status and free their hold."""
    freed = 0.0
    now = datetime.now(timezone.utc)
    for res in reservations:
        if res.status != ReservationStatus.ACTIVE:
            continue
        res.status = new_status
        res.released_at = now
        await _adjust_reserved(db, res.product_id, -res.quantity)
        freed += res.quantity
    await db.flush()
    return freed


async def _active_for_order(db: AsyncSession, order_id: int):
    result = await db.execute(
        select(StockReservation).where(
            StockReservation.order_id == order_id,
            StockReservation.status == ReservationStatus.ACTIVE,
        )
    )
    return list(result.scalars().all())


async def consume_for_order(db: AsyncSession, order_id: int) -> float:
    """Order fulfilled: stock physically left, so free the holds (CONSUMED)."""
    return await _close_active(
        db, await _active_for_order(db, order_id), ReservationStatus.CONSUMED
    )


async def release_for_order(db: AsyncSession, order_id: int) -> float:
    """Order cancelled/returned: free the holds (RELEASED)."""
    return await _close_active(
        db, await _active_for_order(db, order_id), ReservationStatus.RELEASED
    )


async def release_reservation(db: AsyncSession, reservation_id: int) -> bool:
    res = await db.get(StockReservation, reservation_id)
    if res is None or res.status != ReservationStatus.ACTIVE:
        return False
    await _close_active(db, [res], ReservationStatus.RELEASED)
    return True


async def expire_due(db: AsyncSession) -> int:
    """Expire ACTIVE reservations whose TTL elapsed; returns how many."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(StockReservation).where(
            StockReservation.status == ReservationStatus.ACTIVE,
            StockReservation.expires_at.is_not(None),
            StockReservation.expires_at < now,
        )
    )
    due = list(result.scalars().all())
    await _close_active(db, due, ReservationStatus.EXPIRED)
    return len(due)


async def notify_available(db: AsyncSession, product_id: int) -> float:
    """Publish the product's current availability to real-time subscribers."""
    available = await get_available(db, product_id)
    await publish_stock_change(product_id, available)
    return available


async def get_available(db: AsyncSession, product_id: int) -> float:
    """available = current_stock - reserved_stock."""
    row = (
        await db.execute(
            select(
                func.coalesce(Product.current_stock, 0.0),
                func.coalesce(Product.reserved_stock, 0.0),
            ).where(Product.id == product_id)
        )
    ).first()
    if row is None:
        return 0.0
    return float(row[0]) - float(row[1])
