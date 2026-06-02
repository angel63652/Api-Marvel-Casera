"""Stock reservations (ledger).

Each row is a hold on a product's stock. `Product.reserved_stock` caches the
sum of ACTIVE reservations so availability reads are cheap:

    available = current_stock - reserved_stock

Reservations are created for internal orders today and will back the client
portal's cart holds (with TTL via `expires_at`).
"""
import enum

from sqlalchemy import (
    Column, Integer, Float, String, DateTime, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ReservationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"      # holding stock
    CONSUMED = "CONSUMED"  # fulfilled (stock physically left)
    RELEASED = "RELEASED"  # cancelled / returned -> hold freed
    EXPIRED = "EXPIRED"    # TTL elapsed -> hold freed


class StockReservation(Base):
    __tablename__ = "stock_reservations"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    product_id = Column(
        Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    order_id = Column(
        Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    quantity = Column(Float, nullable=False)
    status = Column(
        SAEnum(ReservationStatus), nullable=False, default=ReservationStatus.ACTIVE, index=True
    )
    source = Column(String(50), nullable=False, default="ORDER")  # ORDER, PORTAL_CART...
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    released_at = Column(DateTime(timezone=True), nullable=True)

    product = relationship("Product", lazy="selectin")
