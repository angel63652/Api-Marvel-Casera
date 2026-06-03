from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import Response as FastAPIResponse
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database import get_db
from app.models.product import Product
from app.models.employee import Employee
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductWithStock,
)
from app.auth import get_current_employee, require_role
from app.services import stock_service
from app.services.barcode_service import generate_label
from app.services.excel_service import build_xlsx, XLSX_MEDIA, xlsx_headers

router = APIRouter(prefix="/products", tags=["Productos"])


def _serialize(product: Product) -> dict:
    return {
        "id": product.id,
        "niu": product.niu,
        "barcode": product.barcode,
        "name": product.name,
        "description": product.description,
        "category": product.category,
        "unit": product.unit,
        "min_stock": product.min_stock,
        "current_stock": product.current_stock,
        "reserved_stock": product.reserved_stock or 0.0,
        "available_stock": (product.current_stock or 0.0) - (product.reserved_stock or 0.0),
        "weight": product.weight,
        "price_cost": product.price_cost,
        "price_base": product.price_base,
        "active": product.active,
        "created_at": product.created_at,
        "updated_at": product.updated_at,
    }


@router.get("", response_model=list[ProductResponse])
async def list_products(
    response: Response,
    search: Optional[str] = None,
    category: Optional[str] = None,
    low_stock: bool = False,
    active_only: bool = True,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Product)
    if active_only:
        stmt = stmt.where(Product.active.is_(True))
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                Product.name.ilike(like),
                Product.niu.ilike(like),
                Product.barcode.ilike(like),
            )
        )
    if category:
        stmt = stmt.where(Product.category == category)
    if low_stock:
        stmt = stmt.where(Product.current_stock < Product.min_stock)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    response.headers["X-Total-Count"] = str(total or 0)
    stmt = stmt.order_by(Product.name).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return [ProductResponse.model_validate(_serialize(p)) for p in result.scalars().all()]


@router.get("/export")
async def export_products_xlsx(
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("MANAGER", "OFFICE")),
):
    """Download full active product catalog as XLSX."""
    result = await db.execute(select(Product).where(Product.active.is_(True)).order_by(Product.name))
    products = result.scalars().all()
    headers = ["ID", "NIU", "Código barras", "Nombre", "Categoría", "Unidad",
               "Stock mín.", "Stock actual", "Stock reservado", "Stock disponible",
               "Coste (€)", "PVP base (€)", "Activo"]
    rows = [
        [
            p.id, p.niu, p.barcode, p.name, p.category, p.unit,
            p.min_stock, p.current_stock or 0,
            p.reserved_stock or 0,
            (p.current_stock or 0) - (p.reserved_stock or 0),
            p.price_cost, p.price_base, "Sí" if p.active else "No",
        ]
        for p in products
    ]
    content = build_xlsx("Productos", headers, rows)
    return FastAPIResponse(content=content, media_type=XLSX_MEDIA,
                           headers=xlsx_headers("productos.xlsx"))


@router.get("/low-stock")
async def low_stock_products(db: AsyncSession = Depends(get_db)):
    return await stock_service.check_low_stock(db)


@router.get("/barcode/{barcode}", response_model=ProductResponse)
async def get_by_barcode(barcode: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.barcode == barcode))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado por código de barras")
    return ProductResponse.model_validate(_serialize(product))


@router.get("/niu/{niu}", response_model=ProductResponse)
async def get_by_niu(niu: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.niu == niu))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado por NIU")
    return ProductResponse.model_validate(_serialize(product))


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return ProductResponse.model_validate(_serialize(product))


@router.get("/{product_id}/stock", response_model=ProductWithStock)
async def get_product_stock(product_id: int, db: AsyncSession = Depends(get_db)):
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    breakdown = await stock_service.get_stock_by_location(product_id, db)
    data = _serialize(product)
    data["stock_by_location"] = breakdown
    data["is_low_stock"] = product.current_stock < product.min_stock
    return ProductWithStock.model_validate(data)


@router.get("/{product_id}/label")
async def get_product_label(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(get_current_employee),
):
    """Return a printable PNG barcode label for the product."""
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    barcode_val = product.barcode or product.niu
    if not barcode_val:
        raise HTTPException(status_code=422, detail="El producto no tiene código de barras ni NIU")
    png_bytes = generate_label(barcode_val, product.name or "", product.niu or "")
    return FastAPIResponse(
        content=png_bytes,
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="label_{product_id}.png"'},
    )


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    payload: ProductCreate,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("MANAGER", "OFFICE")),
):
    existing = await db.execute(
        select(Product).where(
            or_(Product.niu == payload.niu, Product.barcode == payload.barcode)
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="Ya existe un producto con ese NIU o código de barras")
    product = Product(**payload.model_dump())
    db.add(product)
    await db.flush()
    await db.refresh(product)
    return ProductResponse.model_validate(_serialize(product))


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("MANAGER", "OFFICE")),
):
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    await db.flush()
    await db.refresh(product)
    return ProductResponse.model_validate(_serialize(product))


@router.put("/{product_id}/tier-prices", status_code=200)
async def set_tier_price(
    product_id: int,
    tier: str = Query(..., min_length=1, max_length=50),
    price: float = Query(..., ge=0),
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("MANAGER", "OFFICE")),
):
    """Set (upsert) the sale price of a product for a given price tier."""
    from app.models.product import ProductTierPrice

    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    existing = await db.execute(
        select(ProductTierPrice).where(
            ProductTierPrice.product_id == product_id,
            ProductTierPrice.tier == tier,
        )
    )
    tp = existing.scalar_one_or_none()
    if tp is None:
        tp = ProductTierPrice(product_id=product_id, tier=tier, price=price)
        db.add(tp)
    else:
        tp.price = price
    await db.flush()
    return {"product_id": product_id, "tier": tier, "price": price}


@router.delete("/{product_id}", status_code=200)
async def deactivate_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("ADMIN")),
):
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    product.active = False
    await db.flush()
    return {"detail": "Producto desactivado", "id": product_id}
