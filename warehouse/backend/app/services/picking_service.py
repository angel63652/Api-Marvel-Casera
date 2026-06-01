"""Picking helpers: barcode validation, ordered picking lists, completion checks."""
import random
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.order import Order, OrderLine, OrderLineStatus


async def validate_barcode(
    scanned_barcode: str, expected_product_id: int, db: AsyncSession
) -> bool:
    """Return True if the scanned barcode matches the expected product.

    Accepts either the product barcode or its NIU (some scanners read NIU labels).
    """
    if not scanned_barcode:
        return False
    product = await db.get(Product, expected_product_id)
    if product is None:
        return False
    scanned = scanned_barcode.strip()
    return scanned == product.barcode or scanned == product.niu


async def find_product_by_code(code: str, db: AsyncSession) -> Product | None:
    """Resolve a scanned code to a product by barcode first, then NIU."""
    code = (code or "").strip()
    if not code:
        return None
    result = await db.execute(select(Product).where(Product.barcode == code))
    product = result.scalar_one_or_none()
    if product is None:
        result = await db.execute(select(Product).where(Product.niu == code))
        product = result.scalar_one_or_none()
    return product


def _location_sort_key(line: OrderLine):
    """Sort picking lines by aisle -> rack -> position for an efficient route."""
    loc = line.location
    if loc is None:
        # Lines without a location go last.
        return ("zzz", "zzz", "zzz")
    return (loc.aisle or "zzz", loc.rack or "zzz", loc.position or "zzz")


async def get_picking_list(order_id: int, db: AsyncSession) -> list[dict]:
    """Return the order's lines formatted and sorted for efficient picking."""
    order = await db.get(Order, order_id)
    if order is None:
        return []

    sorted_lines = sorted(order.lines, key=_location_sort_key)
    items = []
    for line in sorted_lines:
        loc = line.location
        product = line.product
        items.append(
            {
                "line_id": line.id,
                "product_id": line.product_id,
                "product_name": product.name if product else "",
                "product_barcode": product.barcode if product else "",
                "product_niu": product.niu if product else "",
                "location_id": line.location_id,
                "location_code": loc.code if loc else None,
                "aisle": loc.aisle if loc else None,
                "rack": loc.rack if loc else None,
                "position": loc.position if loc else None,
                "quantity_requested": line.quantity_requested,
                "quantity_picked": line.quantity_picked,
                "status": line.status.value
                if hasattr(line.status, "value")
                else line.status,
                "observations": line.observations,
            }
        )
    return items


async def check_order_completion(order_id: int, db: AsyncSession) -> bool:
    """True when no order line is still PENDING (all picked/missing/partial)."""
    order = await db.get(Order, order_id)
    if order is None or not order.lines:
        return False
    return all(line.status != OrderLineStatus.PENDING for line in order.lines)


async def summarize_picking(order_id: int, db: AsyncSession) -> dict:
    """Counts used for progress bars and conformity screens."""
    order = await db.get(Order, order_id)
    if order is None:
        return {"total": 0, "picked": 0, "missing": 0, "partial": 0, "pending": 0}
    total = len(order.lines)
    picked = sum(1 for l in order.lines if l.status == OrderLineStatus.PICKED)
    missing = sum(1 for l in order.lines if l.status == OrderLineStatus.MISSING)
    partial = sum(1 for l in order.lines if l.status == OrderLineStatus.PARTIAL)
    pending = sum(1 for l in order.lines if l.status == OrderLineStatus.PENDING)
    return {
        "total": total,
        "picked": picked,
        "missing": missing,
        "partial": partial,
        "pending": pending,
    }


def generate_order_number() -> str:
    """Generate an order number like ORD-2025-483920."""
    year = datetime.now(timezone.utc).year
    suffix = random.randint(100000, 999999)
    return f"ORD-{year}-{suffix}"
