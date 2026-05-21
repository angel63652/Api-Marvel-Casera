"""Reading Orders API endpoints."""

import re
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Path

from marvel_metadata.api.deps import get_db
from marvel_metadata.api.models.reading_order import (
    ReadingOrderCreate,
    ReadingOrderDetail,
    ReadingOrderSummary,
)
from marvel_metadata.data.repository import ReadingOrderRepository

router = APIRouter()


def _slug_from_name(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug.strip("-")[:80]


@router.get("", response_model=list[ReadingOrderSummary])
async def list_reading_orders(
    db: sqlite3.Connection = Depends(get_db),
) -> list[ReadingOrderSummary]:
    """List all reading orders (curated and user-created)."""
    repo = ReadingOrderRepository(db)
    orders = repo.list_all()
    return [
        ReadingOrderSummary(
            id=o["id"],
            slug=o["slug"],
            name=o["name"],
            description=o["description"] or "",
            is_curated=bool(o["is_curated"]),
            item_count=o["item_count"],
            created_at=o["created_at"],
        )
        for o in orders
    ]


@router.get("/{slug}", response_model=ReadingOrderDetail)
async def get_reading_order(
    slug: str = Path(..., description="Reading order slug"),
    db: sqlite3.Connection = Depends(get_db),
) -> ReadingOrderDetail:
    """Get a reading order with all its items."""
    repo = ReadingOrderRepository(db)
    order = repo.get_by_slug(slug)
    if not order:
        raise HTTPException(status_code=404, detail=f"Reading order '{slug}' not found")
    return ReadingOrderDetail(**{**order, "is_curated": bool(order["is_curated"])})


@router.post("", response_model=ReadingOrderDetail, status_code=201)
async def create_reading_order(
    body: ReadingOrderCreate,
    db: sqlite3.Connection = Depends(get_db),
) -> ReadingOrderDetail:
    """Create a new custom reading order."""
    repo = ReadingOrderRepository(db)
    slug = _slug_from_name(body.name)

    # Ensure unique slug
    base_slug = slug
    suffix = 1
    while repo.get_by_slug(slug):
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    items = [i.model_dump() for i in body.items]
    order = repo.create(
        slug=slug,
        name=body.name,
        description=body.description,
        is_curated=False,
        items=items,
    )
    return ReadingOrderDetail(**{**order, "is_curated": bool(order["is_curated"])})


@router.delete("/{slug}", status_code=204)
async def delete_reading_order(
    slug: str = Path(..., description="Reading order slug"),
    db: sqlite3.Connection = Depends(get_db),
) -> None:
    """Delete a user-created reading order (curated orders cannot be deleted)."""
    repo = ReadingOrderRepository(db)
    order = repo.get_by_slug(slug)
    if not order:
        raise HTTPException(status_code=404, detail=f"Reading order '{slug}' not found")
    if order["is_curated"]:
        raise HTTPException(status_code=403, detail="Curated reading orders cannot be deleted")
    repo.delete(slug)
