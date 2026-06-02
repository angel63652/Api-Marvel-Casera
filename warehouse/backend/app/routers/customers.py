"""Office-side customer management (employee-gated).

Approve registrations (PENDING -> ACTIVE), suspend, set price tier. Customers
self-register via the portal (PENDING) and office activates them here.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import require_role
from app.models.employee import Employee
from app.models.customer import Customer, CustomerStatus

router = APIRouter(prefix="/customers", tags=["Clientes"])


def _serialize(c: Customer) -> dict:
    return {
        "id": c.id,
        "company_name": c.company_name,
        "tax_id": c.tax_id,
        "contact_email": c.contact_email,
        "contact_phone": c.contact_phone,
        "status": c.status.value if hasattr(c.status, "value") else c.status,
        "price_tier": c.price_tier,
        "created_at": c.created_at,
    }


@router.get("")
async def list_customers(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("OFFICE", "MANAGER")),
):
    stmt = select(Customer)
    if status:
        stmt = stmt.where(Customer.status == status)
    stmt = stmt.order_by(Customer.company_name)
    return [_serialize(c) for c in (await db.execute(stmt)).scalars().all()]


@router.get("/{customer_id}")
async def get_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("OFFICE", "MANAGER")),
):
    c = await db.get(Customer, customer_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return _serialize(c)


@router.post("/{customer_id}/approve")
async def approve_customer(
    customer_id: int,
    price_tier: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("OFFICE", "MANAGER")),
):
    c = await db.get(Customer, customer_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    c.status = CustomerStatus.ACTIVE
    if price_tier is not None:
        c.price_tier = price_tier
    await db.flush()
    return _serialize(c)


@router.post("/{customer_id}/suspend")
async def suspend_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("OFFICE", "MANAGER")),
):
    c = await db.get(Customer, customer_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    c.status = CustomerStatus.SUSPENDED
    await db.flush()
    return _serialize(c)


@router.put("/{customer_id}/price-tier")
async def set_price_tier(
    customer_id: int,
    tier: str = Query(..., min_length=1, max_length=50),
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("OFFICE", "MANAGER")),
):
    c = await db.get(Customer, customer_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    c.price_tier = tier
    await db.flush()
    return _serialize(c)
