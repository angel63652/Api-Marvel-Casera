"""Office-side review of customer change requests (employee-gated).

Approving a FISCAL request applies the payload to the Customer master record;
an ADDRESS request creates/updates an address. Customers never mutate master
data directly — this is the controlled path.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import require_role
from app.models.employee import Employee
from app.models.customer import (
    Customer, CustomerAddress, CustomerChangeRequest,
    ChangeRequestTarget, ChangeRequestStatus, AddressType,
)

router = APIRouter(prefix="/customer-requests", tags=["Clientes · Solicitudes"])

_FISCAL_FIELDS = {"company_name", "tax_id", "contact_email", "contact_phone"}


def _serialize(cr: CustomerChangeRequest) -> dict:
    return {
        "id": cr.id,
        "customer_id": cr.customer_id,
        "target": cr.target.value if hasattr(cr.target, "value") else cr.target,
        "status": cr.status.value if hasattr(cr.status, "value") else cr.status,
        "payload": cr.payload,
        "review_notes": cr.review_notes,
        "created_at": cr.created_at,
        "reviewed_at": cr.reviewed_at,
    }


@router.get("")
async def list_requests(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: Employee = Depends(require_role("OFFICE", "MANAGER")),
):
    stmt = select(CustomerChangeRequest)
    if status:
        stmt = stmt.where(CustomerChangeRequest.status == status)
    stmt = stmt.order_by(CustomerChangeRequest.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [_serialize(r) for r in rows]


@router.post("/{request_id}/approve")
async def approve_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current: Employee = Depends(require_role("OFFICE", "MANAGER")),
):
    cr = await db.get(CustomerChangeRequest, request_id)
    if cr is None:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    if cr.status != ChangeRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="La solicitud ya fue revisada")

    payload = cr.payload or {}
    if cr.target == ChangeRequestTarget.FISCAL:
        customer = await db.get(Customer, cr.customer_id)
        if customer is None:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        for field, value in payload.items():
            if field in _FISCAL_FIELDS:
                setattr(customer, field, value)
    elif cr.target == ChangeRequestTarget.ADDRESS:
        addr_id = payload.get("id")
        if addr_id:  # edit existing
            addr = await db.get(CustomerAddress, addr_id)
            if addr is None or addr.customer_id != cr.customer_id:
                raise HTTPException(status_code=404, detail="Dirección no encontrada")
            for field in ("label", "line1", "line2", "city", "province", "postal_code", "country"):
                if field in payload:
                    setattr(addr, field, payload[field])
        else:  # add new
            db.add(CustomerAddress(
                customer_id=cr.customer_id,
                type=AddressType(payload.get("type", "SHIPPING")),
                label=payload.get("label"),
                line1=payload.get("line1", ""),
                line2=payload.get("line2"),
                city=payload.get("city", ""),
                province=payload.get("province"),
                postal_code=payload.get("postal_code", ""),
                country=payload.get("country", "ES"),
                is_default=bool(payload.get("is_default", False)),
            ))

    cr.status = ChangeRequestStatus.APPROVED
    cr.reviewer_id = current.id
    cr.reviewed_at = datetime.now(timezone.utc)
    await db.flush()
    return _serialize(cr)


@router.post("/{request_id}/reject")
async def reject_request(
    request_id: int,
    notes: str | None = None,
    db: AsyncSession = Depends(get_db),
    current: Employee = Depends(require_role("OFFICE", "MANAGER")),
):
    cr = await db.get(CustomerChangeRequest, request_id)
    if cr is None:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    if cr.status != ChangeRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="La solicitud ya fue revisada")
    cr.status = ChangeRequestStatus.REJECTED
    cr.reviewer_id = current.id
    cr.review_notes = notes
    cr.reviewed_at = datetime.now(timezone.utc)
    await db.flush()
    return _serialize(cr)
