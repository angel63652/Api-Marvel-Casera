"""Tier-based sale pricing.

Resolution: a tier-specific `ProductTierPrice` wins; otherwise the product's
`price_base`. Returns None if neither is set (caller decides how to show it).
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product, ProductTierPrice


async def resolve_price(
    db: AsyncSession, product_id: int, tier: str | None
) -> float | None:
    if tier:
        row = await db.execute(
            select(ProductTierPrice.price).where(
                ProductTierPrice.product_id == product_id,
                ProductTierPrice.tier == tier,
            )
        )
        tier_price = row.scalar_one_or_none()
        if tier_price is not None:
            return float(tier_price)
    base = await db.execute(
        select(Product.price_base).where(Product.id == product_id)
    )
    val = base.scalar_one_or_none()
    return float(val) if val is not None else None


def resolve_price_from_loaded(product: Product, tier: str | None) -> float | None:
    """Resolve price using already-loaded relationships (no extra query)."""
    if tier and product.tier_prices:
        for tp in product.tier_prices:
            if tp.tier == tier:
                return float(tp.price)
    return float(product.price_base) if product.price_base is not None else None
