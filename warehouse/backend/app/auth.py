"""Authentication and role-based access control.

JWT (HS256) tokens, bcrypt password hashing, and FastAPI dependencies for
extracting the current employee and enforcing role requirements.

Role hierarchy used across the warehouse:
- ADMIN    : full control (super user / system owner)
- MANAGER  : warehouse / HR chief (stock changes, payroll, approvals)
- OFFICE   : office staff (orders, clients, emails)
- PICKER   : warehouse operator (picking)
- DRIVER   : truck driver (routes, deliveries)
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.employee import Employee

# auto_error=False so public/page routes can probe for an optional token.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/employees/login", auto_error=False
)


def hash_password(password: str) -> str:
    # bcrypt operates on at most 72 bytes; longer inputs are truncated.
    pwd_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        pwd_bytes = plain.encode("utf-8")[:72]
        return bcrypt.checkpw(pwd_bytes, hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


def create_refresh_token(employee_id: int) -> tuple[str, str, datetime]:
    """Build a refresh JWT. Returns (token, jti, expires_at).

    The `jti` is stored server-side so the token can be revoked.
    """
    jti = uuid.uuid4().hex
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    token = jwt.encode(
        {"sub": str(employee_id), "jti": jti, "type": "refresh", "exp": expires_at},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return token, jti, expires_at


def decode_refresh_token(token: str) -> dict:
    """Decode and validate a refresh JWT (signature, expiry, type)."""
    payload = verify_token(token)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de refresco inválido"
        )
    return payload


async def get_current_employee(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Employee:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = verify_token(token)
    reject_if_customer(payload)
    employee_id = payload.get("sub")
    if employee_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sin sujeto"
        )
    result = await db.execute(
        select(Employee).where(Employee.id == int(employee_id))
    )
    employee = result.scalar_one_or_none()
    if employee is None or not employee.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empleado no encontrado o inactivo",
        )
    return employee


def reject_if_customer(payload: dict) -> None:
    """Guard: an employee endpoint must never accept a portal (customer) token."""
    if payload.get("type") == "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token de cliente no válido para esta API",
        )


# ---- Client portal auth ----------------------------------------------------
def create_customer_token(customer_user_id: int, customer_id: int) -> str:
    """Access token for the client portal (separate realm via aud/type)."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.PORTAL_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode(
        {
            "sub": str(customer_user_id),
            "customer_id": customer_id,
            "type": "customer",
            "aud": "portal",
            "exp": expire,
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


async def get_current_customer_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Resolve the authenticated portal user from a customer token.

    Enforces the portal realm (type=customer) and tenancy (customer_id on token
    must match the user's customer). Returns the CustomerUser.
    """
    from app.models.customer import CustomerUser, Customer, CustomerStatus

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM],
            audience="portal",
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if payload.get("type") != "customer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token no válido")

    user_id = payload.get("sub")
    user = await db.get(CustomerUser, int(user_id)) if user_id else None
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inactivo")
    if user.customer_id != payload.get("customer_id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inconsistente")

    customer = await db.get(Customer, user.customer_id)
    if customer is None or customer.status == CustomerStatus.SUSPENDED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cuenta suspendida")
    return user


def require_role(*roles: str):
    """Dependency factory: ensures the current employee has one of `roles`.

    ADMIN always passes. Usage:
        Depends(require_role("ADMIN", "MANAGER"))
    """

    async def _checker(
        current: Employee = Depends(get_current_employee),
    ) -> Employee:
        role_value = (
            current.role.value if hasattr(current.role, "value") else current.role
        )
        if role_value == "ADMIN":
            return current
        if role_value not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Se requiere rol: {', '.join(roles)}",
            )
        return current

    return _checker
