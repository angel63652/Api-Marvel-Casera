"""Client portal authentication (separate realm from employees).

Tokens carry aud="portal" + type="customer"; employee endpoints reject them and
vice versa. Tenancy is enforced in `get_current_customer_user` (token's
customer_id must match the user's).
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.limiter import limiter
from app.auth import (
    hash_password, verify_password, create_customer_token, get_current_customer_user,
)
from app.models.customer import (
    Customer, CustomerUser, CustomerStatus, CustomerUserRole,
)
from app.schemas.portal import (
    PortalRegisterRequest, PortalLoginRequest, PortalTokenResponse,
    CustomerUserResponse, CustomerSummary,
)

router = APIRouter(prefix="/api/portal/auth", tags=["Portal · Auth"])


def _token_response(user: CustomerUser, customer: Customer) -> PortalTokenResponse:
    role = user.role.value if hasattr(user.role, "value") else user.role
    status_v = customer.status.value if hasattr(customer.status, "value") else customer.status
    return PortalTokenResponse(
        access_token=create_customer_token(user.id, user.customer_id),
        token_type="bearer",
        user=CustomerUserResponse(
            id=user.id, customer_id=user.customer_id, email=user.email,
            name=user.name, role=role, is_active=user.is_active,
        ),
        customer=CustomerSummary(
            id=customer.id, company_name=customer.company_name,
            tax_id=customer.tax_id, status=status_v,
        ),
    )


@router.post("/register", response_model=PortalTokenResponse, status_code=201)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def register(
    request: Request, payload: PortalRegisterRequest, db: AsyncSession = Depends(get_db)
):
    """Self-registration: creates a PENDING customer + an OWNER user.

    The account can sign in immediately but stays PENDING until office staff
    approve it (ordering is gated on ACTIVE in the portal API).
    """
    dup = await db.execute(
        select(Customer).where(Customer.tax_id == payload.tax_id)
    )
    if dup.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="Ya existe un cliente con ese NIF/CIF")
    dup_u = await db.execute(
        select(CustomerUser).where(CustomerUser.email == payload.email)
    )
    if dup_u.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="Ese email ya está registrado")

    customer = Customer(
        company_name=payload.company_name,
        tax_id=payload.tax_id,
        contact_email=payload.email,
        contact_phone=payload.phone,
        status=CustomerStatus.PENDING,
    )
    db.add(customer)
    await db.flush()
    user = CustomerUser(
        customer_id=customer.id,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        name=payload.name,
        role=CustomerUserRole.OWNER,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return _token_response(user, customer)


@router.post("/login", response_model=PortalTokenResponse)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def login(
    request: Request, payload: PortalLoginRequest, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(CustomerUser).where(CustomerUser.email == payload.email)
    )
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Usuario inactivo")
    customer = await db.get(Customer, user.customer_id)
    if customer is None or customer.status == CustomerStatus.SUSPENDED:
        raise HTTPException(status_code=403, detail="Cuenta suspendida")
    return _token_response(user, customer)


@router.get("/me", response_model=PortalTokenResponse)
async def me(
    user: CustomerUser = Depends(get_current_customer_user),
    db: AsyncSession = Depends(get_db),
):
    customer = await db.get(Customer, user.customer_id)
    return _token_response(user, customer)
