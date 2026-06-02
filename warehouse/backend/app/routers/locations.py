from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database import get_db
from app.models.location import Location, ProductLocation
from app.models.product import Product
from app.models.employee import Employee
from app.schemas.location import (
    LocationCreate,
    LocationUpdate,
    LocationResponse,
    ProductLocationCreate,
    ProductLocationResponse,
)
from app.auth import require_role

router = APIRouter(prefix="/locations", tags=["Ubicaciones"])


@router.get("", response_model=list[LocationResponse])
async def list_locations(
    response: Response,
    aisle: Optional[str] = None,
    active_only: bool = True,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Location)
    if active_only:
        stmt = stmt.where(Location.is_active.is_(True))
    if aisle:
        stmt = stmt.where(Location.aisle == aisle)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    response.headers["X-Total-Count"] = str(total or 0)
    stmt = (
        stmt.order_by(Location.aisle, Location.rack, Location.position)
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/aisle/{aisle}", response_model=list[LocationResponse])
async def locations_in_aisle(aisle: str, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Location)
        .where(Location.aisle == aisle)
        .order_by(Location.rack, Location.position)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{location_id}")
async def get_location(location_id: int, db: AsyncSession = Depends(get_db)):
    location = await db.get(Location, location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="Ubicación no encontrada")
    products = []
    for pl in location.product_locations:
        products.append(
            {
                "product_location_id": pl.id,
                "product_id": pl.product_id,
                "product_name": pl.product.name if pl.product else None,
                "product_barcode": pl.product.barcode if pl.product else None,
                "quantity": pl.quantity,
                "min_quantity": pl.min_quantity,
            }
        )
    return {
        "id": location.id,
        "code": location.code,
        "aisle": location.aisle,
        "rack": location.rack,
        "position": location.position,
        "zone": location.zone,
        "capacity": location.capacity,
        "current_load": location.current_load,
        "is_active": location.is_active,
        "products": products,
    }


@router.post("", response_model=LocationResponse, status_code=201)
async def create_location(
    payload: LocationCreate,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("MANAGER")),
):
    existing = await db.execute(select(Location).where(Location.code == payload.code))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="Ya existe una ubicación con ese código")
    location = Location(**payload.model_dump())
    db.add(location)
    await db.flush()
    await db.refresh(location)
    return location


@router.put("/{location_id}", response_model=LocationResponse)
async def update_location(
    location_id: int,
    payload: LocationUpdate,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("MANAGER")),
):
    location = await db.get(Location, location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="Ubicación no encontrada")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(location, field, value)
    await db.flush()
    await db.refresh(location)
    return location


@router.post("/{location_id}/assign-product", response_model=ProductLocationResponse, status_code=201)
async def assign_product(
    location_id: int,
    payload: ProductLocationCreate,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("MANAGER", "OFFICE")),
):
    location = await db.get(Location, location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="Ubicación no encontrada")
    product = await db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    existing = await db.execute(
        select(ProductLocation).where(
            ProductLocation.product_id == payload.product_id,
            ProductLocation.location_id == location_id,
        )
    )
    pl = existing.scalar_one_or_none()
    if pl is not None:
        pl.quantity = payload.quantity
        pl.min_quantity = payload.min_quantity
    else:
        pl = ProductLocation(
            product_id=payload.product_id,
            location_id=location_id,
            quantity=payload.quantity,
            min_quantity=payload.min_quantity,
        )
        db.add(pl)
    await db.flush()
    await db.refresh(pl)
    return ProductLocationResponse(
        id=pl.id,
        product_id=pl.product_id,
        location_id=pl.location_id,
        quantity=pl.quantity,
        min_quantity=pl.min_quantity,
        updated_at=pl.updated_at,
        product_name=product.name,
        product_barcode=product.barcode,
        location_code=location.code,
    )


@router.delete("/{location_id}/products/{product_id}")
async def unassign_product(
    location_id: int,
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("MANAGER")),
):
    result = await db.execute(
        select(ProductLocation).where(
            ProductLocation.product_id == product_id,
            ProductLocation.location_id == location_id,
        )
    )
    pl = result.scalar_one_or_none()
    if pl is None:
        raise HTTPException(status_code=404, detail="Asignación no encontrada")
    await db.delete(pl)
    return {"detail": "Producto desasignado de la ubicación"}
