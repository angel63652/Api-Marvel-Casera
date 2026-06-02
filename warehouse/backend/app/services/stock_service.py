"""Stock calculation and location-load helpers.

Stock is derived from the movement ledger so it can always be recomputed:
  ENTRY, REPLENISHMENT, RETURN  -> increase stock
  EXIT, ADJUSTMENT (negative)   -> decrease stock
"""
from sqlalchemy import select, func, update, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.location import Location, ProductLocation
from app.models.movement import Movement, MovementLine, MovementType

# Movement types that add to stock vs. remove from it.
INBOUND_TYPES = {MovementType.ENTRY, MovementType.REPLENISHMENT, MovementType.RETURN}
OUTBOUND_TYPES = {MovementType.EXIT}


async def calculate_product_stock(product_id: int, db: AsyncSession) -> float:
    """Recompute total stock for a product from the movement ledger."""
    stmt = (
        select(Movement.type, func.coalesce(func.sum(MovementLine.quantity), 0.0))
        .join(MovementLine, MovementLine.movement_id == Movement.id)
        .where(MovementLine.product_id == product_id)
        .group_by(Movement.type)
    )
    result = await db.execute(stmt)
    total = 0.0
    for mtype, qty in result.all():
        if mtype in INBOUND_TYPES:
            total += float(qty or 0.0)
        elif mtype in OUTBOUND_TYPES:
            total -= float(qty or 0.0)
        elif mtype == MovementType.ADJUSTMENT:
            # Adjustments carry their own sign in quantity.
            total += float(qty or 0.0)
    return total


async def recalculate_and_store(product_id: int, db: AsyncSession) -> float:
    """Recompute stock and persist it on the Product row."""
    total = await calculate_product_stock(product_id, db)
    product = await db.get(Product, product_id)
    if product:
        product.current_stock = total
        await db.flush()
    return total


async def apply_movement_delta(
    product_id: int, delta: float, db: AsyncSession
) -> float:
    """Apply an incremental change to a product's cached stock atomically.

    Uses a single `UPDATE ... SET current_stock = current_stock + :delta` so
    concurrent movements/picks cannot lose updates (no read-modify-write race
    → no overselling). Returns the new stock, or 0.0 if the product is gone.
    """
    result = await db.execute(
        update(Product)
        .where(Product.id == product_id)
        .values(current_stock=func.coalesce(Product.current_stock, 0.0) + delta)
        .returning(Product.current_stock)
    )
    row = result.first()
    if row is None:
        return 0.0
    # Keep the identity-mapped instance (if loaded) consistent with the DB.
    product = await db.get(Product, product_id)
    if product is not None:
        await db.refresh(product, attribute_names=["current_stock"])
    await db.flush()
    return float(row[0] or 0.0)


async def check_low_stock(db: AsyncSession) -> list[dict]:
    """Return all active products whose current_stock is below min_stock."""
    stmt = select(Product).where(
        Product.active.is_(True),
        Product.current_stock < Product.min_stock,
    )
    result = await db.execute(stmt)
    products = result.scalars().all()

    low = []
    for p in products:
        location_codes = [
            pl.location.code
            for pl in p.locations
            if pl.location is not None
        ]
        low.append(
            {
                "product_id": p.id,
                "product_name": p.name,
                "niu": p.niu,
                "barcode": p.barcode,
                "current_stock": p.current_stock,
                "min_stock": p.min_stock,
                "deficit": round(p.min_stock - p.current_stock, 3),
                "unit": p.unit.value if hasattr(p.unit, "value") else p.unit,
                "location_codes": location_codes,
            }
        )
    return low


async def update_location_load(
    location_id: int, delta: float, db: AsyncSession
) -> float:
    """Adjust a location's current_load by `delta` atomically (clamped to >= 0)."""
    new_load = func.coalesce(Location.current_load, 0.0) + delta
    result = await db.execute(
        update(Location)
        .where(Location.id == location_id)
        .values(current_load=case((new_load < 0, 0.0), else_=new_load))
        .returning(Location.current_load)
    )
    row = result.first()
    if row is None:
        return 0.0
    location = await db.get(Location, location_id)
    if location is not None:
        await db.refresh(location, attribute_names=["current_load"])
    await db.flush()
    return float(row[0] or 0.0)


async def update_product_location_qty(
    product_id: int, location_id: int, delta: float, db: AsyncSession
) -> None:
    """Adjust the ProductLocation quantity, creating the link if needed."""
    stmt = select(ProductLocation).where(
        ProductLocation.product_id == product_id,
        ProductLocation.location_id == location_id,
    )
    result = await db.execute(stmt)
    pl = result.scalar_one_or_none()
    if pl is None:
        pl = ProductLocation(
            product_id=product_id,
            location_id=location_id,
            quantity=max(0.0, delta),
            min_quantity=0.0,
        )
        db.add(pl)
    else:
        pl.quantity = max(0.0, (pl.quantity or 0.0) + delta)
    await db.flush()


async def get_stock_by_location(product_id: int, db: AsyncSession) -> list[dict]:
    """Return the per-location stock breakdown for a product."""
    stmt = (
        select(ProductLocation, Location)
        .join(Location, Location.id == ProductLocation.location_id)
        .where(ProductLocation.product_id == product_id)
    )
    result = await db.execute(stmt)
    breakdown = []
    for pl, loc in result.all():
        breakdown.append(
            {
                "location_id": loc.id,
                "location_code": loc.code,
                "aisle": loc.aisle,
                "rack": loc.rack,
                "position": loc.position,
                "quantity": pl.quantity,
                "min_quantity": pl.min_quantity,
            }
        )
    return breakdown
