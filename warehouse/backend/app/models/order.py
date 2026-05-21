from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    PICKING = "PICKING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    RETURNED = "RETURNED"


class OrderLineStatus(str, enum.Enum):
    PENDING = "PENDING"
    PICKED = "PICKED"
    MISSING = "MISSING"
    PARTIAL = "PARTIAL"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    order_number = Column(String(50), unique=True, nullable=False, index=True)
    customer_name = Column(String(255), nullable=False)
    customer_id = Column(String(100), nullable=True, index=True)
    status = Column(SAEnum(OrderStatus), nullable=False, default=OrderStatus.PENDING, index=True)
    notes = Column(Text, nullable=True)
    buyer_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    conformity_signed = Column(Boolean, nullable=False, default=False)
    conformity_at = Column(DateTime(timezone=True), nullable=True)
    conformity_notes = Column(Text, nullable=True)
    return_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)

    buyer = relationship("Employee", back_populates="orders_picked", lazy="selectin")
    lines = relationship(
        "OrderLine",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class OrderLine(Base):
    __tablename__ = "order_lines"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity_requested = Column(Float, nullable=False)
    quantity_picked = Column(Float, nullable=False, default=0.0)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    status = Column(SAEnum(OrderLineStatus), nullable=False, default=OrderLineStatus.PENDING)
    observations = Column(Text, nullable=True)
    picked_by = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    picked_at = Column(DateTime(timezone=True), nullable=True)

    order = relationship("Order", back_populates="lines", lazy="selectin")
    product = relationship("Product", back_populates="order_lines", lazy="selectin")
    location = relationship("Location", back_populates="order_lines", lazy="selectin")
    picker = relationship(
        "Employee",
        foreign_keys=[picked_by],
        back_populates="lines_picked",
        lazy="selectin",
    )
