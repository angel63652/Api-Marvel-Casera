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
    create_customer_refresh_token, decode_customer_refresh_token,
)
from app.models.customer import (
    Customer, CustomerUser, CustomerStatus, CustomerUserRole,
)
from app.models.token import CustomerRefreshToken
from app.schemas.portal import (
    PortalRegisterRequest, PortalLoginRequest, PortalTokenResponse,
    PortalRefreshRequest, PortalAccessTokenResponse,
    CustomerUserResponse, CustomerSummary,
)

router = APIRouter(prefix="/api/portal/auth", tags=["Portal · Auth"])


async def _issue_customer_refresh(customer_user_id: int, db: AsyncSession) -> str:
    token, jti, expires_at = create_customer_refresh_token(customer_user_id)
    db.add(CustomerRefreshToken(
        jti=jti, customer_user_id=customer_user_id, expires_at=expires_at
    ))
    await db.flush()
    return token


def _token_response(
    user: CustomerUser, customer: Customer, refresh: str | None = None
) -> PortalTokenResponse:
    role = user.role.value if hasattr(user.role, "value") else user.role
    status_v = customer.status.value if hasattr(customer.status, "value") else customer.status
    return PortalTokenResponse(
        access_token=create_customer_token(user.id, user.customer_id),
        refresh_token=refresh,
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
    refresh = await _issue_customer_refresh(user.id, db)
    return _token_response(user, customer, refresh)


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
    refresh = await _issue_customer_refresh(user.id, db)
    return _token_response(user, customer, refresh)


@router.post("/refresh", response_model=PortalAccessTokenResponse)
async def refresh_token(payload: PortalRefreshRequest, db: AsyncSession = Depends(get_db)):
    """Exchange a valid, non-revoked portal refresh token for a new access token."""
    data = decode_customer_refresh_token(payload.refresh_token)
    jti = data.get("jti")
    user_id = data.get("sub")
    if not jti or not user_id:
        raise HTTPException(status_code=401, detail="Token de refresco inválido")

    stored = (
        await db.execute(select(CustomerRefreshToken).where(CustomerRefreshToken.jti == jti))
    ).scalar_one_or_none()
    if stored is None or stored.revoked:
        raise HTTPException(status_code=401, detail="Sesión revocada o inexistente")

    user = await db.get(CustomerUser, int(user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo")
    customer = await db.get(Customer, user.customer_id)
    if customer is None or customer.status == CustomerStatus.SUSPENDED:
        raise HTTPException(status_code=403, detail="Cuenta suspendida")

    return PortalAccessTokenResponse(
        access_token=create_customer_token(user.id, user.customer_id), token_type="bearer"
    )


@router.post("/logout")
async def logout(payload: PortalRefreshRequest, db: AsyncSession = Depends(get_db)):
    """Revoke a portal refresh token (idempotent)."""
    try:
        data = decode_customer_refresh_token(payload.refresh_token)
    except HTTPException:
        return {"detail": "Sesión cerrada"}
    jti = data.get("jti")
    if jti:
        stored = (
            await db.execute(select(CustomerRefreshToken).where(CustomerRefreshToken.jti == jti))
        ).scalar_one_or_none()
        if stored is not None:
            stored.revoked = True
            await db.flush()
    return {"detail": "Sesión cerrada"}


@router.get("/me", response_model=PortalTokenResponse)
async def me(
    user: CustomerUser = Depends(get_current_customer_user),
    db: AsyncSession = Depends(get_db),
):
    customer = await db.get(Customer, user.customer_id)
    return _token_response(user, customer)
