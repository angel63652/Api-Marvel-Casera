"""Analytics + ETL with Polars (off the order hot-path).

Sales are derived from COMPLETED orders' picked quantities (order confirmation
discounts stock via the cached delta, not a Movement row, so orders are the
source of truth for sales). Polars does the in-memory aggregation.
"""
import io
from datetime import datetime

import polars as pl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderLine, OrderStatus
from app.models.product import Product, ProductTierPrice


async def sales_summary(
    db: AsyncSession,
    start: datetime | None = None,
    end: datetime | None = None,
    top: int = 10,
) -> dict:
    """Aggregate units & estimated revenue per product from COMPLETED orders."""
    stmt = (
        select(
            OrderLine.product_id,
            Product.name,
            OrderLine.quantity_picked,
            Product.price_base,
        )
        .join(Order, Order.id == OrderLine.order_id)
        .join(Product, Product.id == OrderLine.product_id)
        .where(Order.status == OrderStatus.COMPLETED)
    )
    if start:
        stmt = stmt.where(Order.completed_at >= start)
    if end:
        stmt = stmt.where(Order.completed_at <= end)
    rows = (await db.execute(stmt)).all()

    if not rows:
        return {"total_units": 0.0, "total_revenue": 0.0, "lines": 0, "top_products": []}

    df = pl.DataFrame(
        {
            "product_id": [r[0] for r in rows],
            "name": [r[1] for r in rows],
            "qty": [float(r[2] or 0.0) for r in rows],
            "price_base": [float(r[3] or 0.0) for r in rows],
        }
    )
    df = df.with_columns((pl.col("qty") * pl.col("price_base")).alias("revenue"))
    grouped = (
        df.group_by("product_id", "name")
        .agg(
            pl.col("qty").sum().alias("units"),
            pl.col("revenue").sum().alias("revenue"),
        )
        .sort("units", descending=True)
    )
    top_products = [
        {
            "product_id": int(r["product_id"]),
            "name": r["name"],
            "units": round(float(r["units"]), 3),
            "revenue": round(float(r["revenue"]), 2),
        }
        for r in grouped.head(top).to_dicts()
    ]
    return {
        "total_units": round(float(df["qty"].sum()), 3),
        "total_revenue": round(float(df["revenue"].sum()), 2),
        "lines": df.height,
        "top_products": top_products,
    }


async def import_tier_prices(db: AsyncSession, csv_bytes: bytes) -> dict:
    """Bulk upsert tier prices from CSV (columns: niu, tier, price).

    Polars parses/validates; rows referencing unknown NIUs are skipped.
    """
    try:
        df = pl.read_csv(io.BytesIO(csv_bytes))
    except Exception as exc:  # noqa: BLE001
        return {"error": f"CSV inválido: {exc}", "created": 0, "updated": 0, "skipped": 0}

    required = {"niu", "tier", "price"}
    if not required.issubset({c.lower() for c in df.columns}):
        return {
            "error": f"Faltan columnas; se requieren {sorted(required)}",
            "created": 0, "updated": 0, "skipped": 0,
        }
    # Normalize column names to lowercase.
    df = df.rename({c: c.lower() for c in df.columns})

    created = updated = skipped = 0
    for row in df.to_dicts():
        niu = str(row.get("niu") or "").strip()
        tier = str(row.get("tier") or "").strip()
        try:
            price = float(row.get("price"))
        except (TypeError, ValueError):
            skipped += 1
            continue
        if not niu or not tier or price < 0:
            skipped += 1
            continue
        product = (
            await db.execute(select(Product).where(Product.niu == niu))
        ).scalar_one_or_none()
        if product is None:
            skipped += 1
            continue
        existing = (
            await db.execute(
                select(ProductTierPrice).where(
                    ProductTierPrice.product_id == product.id,
                    ProductTierPrice.tier == tier,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(ProductTierPrice(product_id=product.id, tier=tier, price=price))
            created += 1
        else:
            existing.price = price
            updated += 1
    await db.flush()
    return {"created": created, "updated": updated, "skipped": skipped}
