"""Client portal domain — kept separate from the internal employee domain.

- Customer            : the shop/company master record (fiscal identity).
- CustomerUser        : portal login for a customer (OWNER/STAFF). NOT an Employee.
- CustomerAddress     : shipping/billing addresses (several per customer).
- CustomerChangeRequest: versioned request to change fiscal data / addresses,
  reviewed by office staff. Customers never UPDATE master data directly.
"""
import enum

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON,
    Enum as SAEnum,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class CustomerStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    PENDING = "PENDING"  # registered, awaiting office approval


class CustomerUserRole(str, enum.Enum):
    OWNER = "OWNER"   # can manage other users + request fiscal changes
    STAFF = "STAFF"   # can place orders


class AddressType(str, enum.Enum):
    SHIPPING = "SHIPPING"
    BILLING = "BILLING"


class ChangeRequestTarget(str, enum.Enum):
    FISCAL = "FISCAL"      # company_name, tax_id, contact
    ADDRESS = "ADDRESS"    # add/edit an address


class ChangeRequestStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    company_name = Column(String(255), nullable=False, index=True)
    tax_id = Column(String(50), unique=True, nullable=False, index=True)  # NIF/CIF
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    status = Column(
        SAEnum(CustomerStatus), nullable=False, default=CustomerStatus.PENDING, index=True
    )
    price_tier = Column(String(50), nullable=True)  # tariff/price list code
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    users = relationship(
        "CustomerUser", back_populates="customer", lazy="selectin",
        cascade="all, delete-orphan",
    )
    addresses = relationship(
        "CustomerAddress", back_populates="customer", lazy="selectin",
        cascade="all, delete-orphan",
    )


class CustomerUser(Base):
    __tablename__ = "customer_users"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    customer_id = Column(
        Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    role = Column(SAEnum(CustomerUserRole), nullable=False, default=CustomerUserRole.STAFF)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    customer = relationship("Customer", back_populates="users", lazy="selectin")


class CustomerAddress(Base):
    __tablename__ = "customer_addresses"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    customer_id = Column(
        Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type = Column(SAEnum(AddressType), nullable=False, default=AddressType.SHIPPING)
    label = Column(String(100), nullable=True)
    line1 = Column(String(255), nullable=False)
    line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=False)
    province = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=False)
    country = Column(String(2), nullable=False, default="ES")
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    customer = relationship("Customer", back_populates="addresses", lazy="selectin")


class CustomerChangeRequest(Base):
    """Versioned request to change fiscal data or an address (office-reviewed)."""
    __tablename__ = "customer_change_requests"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    customer_id = Column(
        Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by = Column(
        Integer, ForeignKey("customer_users.id", ondelete="SET NULL"), nullable=True
    )
    target = Column(SAEnum(ChangeRequestTarget), nullable=False)
    # Proposed changes as JSON (the new field values to apply on approval).
    payload = Column(JSON, nullable=False)
    status = Column(
        SAEnum(ChangeRequestStatus), nullable=False,
        default=ChangeRequestStatus.PENDING, index=True,
    )
    reviewer_id = Column(
        Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    review_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    customer = relationship("Customer", lazy="selectin")
