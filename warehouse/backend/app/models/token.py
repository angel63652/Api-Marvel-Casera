"""Refresh token store for revocable, long-lived sessions.

The access token stays a stateless short-lived JWT. Each login also issues a
refresh JWT whose `jti` is recorded here so it can be revoked server-side
(logout, deactivation, rotation).
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    jti = Column(String(64), unique=True, nullable=False, index=True)
    employee_id = Column(
        Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    employee = relationship("Employee", lazy="selectin")


class CustomerRefreshToken(Base):
    """Refresh token store for the client portal (isolated from employees)."""
    __tablename__ = "customer_refresh_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    jti = Column(String(64), unique=True, nullable=False, index=True)
    customer_user_id = Column(
        Integer, ForeignKey("customer_users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
