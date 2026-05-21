from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class ReplenishmentStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ReplenishmentPriority(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Replenishment(Base):
    __tablename__ = "replenishments"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    status = Column(
        SAEnum(ReplenishmentStatus),
        nullable=False,
        default=ReplenishmentStatus.PENDING,
        index=True,
    )
    priority = Column(
        SAEnum(ReplenishmentPriority),
        nullable=False,
        default=ReplenishmentPriority.MEDIUM,
    )
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)

    created_by_employee = relationship("Employee", back_populates="replenishments", lazy="selectin")
    lines = relationship(
        "ReplenishmentLine",
        back_populates="replenishment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ReplenishmentLine(Base):
    __tablename__ = "replenishment_lines"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    replenishment_id = Column(
        Integer, ForeignKey("replenishments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="RESTRICT"), nullable=True)
    current_qty = Column(Float, nullable=False, default=0.0)
    min_qty = Column(Float, nullable=False, default=0.0)
    requested_qty = Column(Float, nullable=False)
    received_qty = Column(Float, nullable=False, default=0.0)

    replenishment = relationship("Replenishment", back_populates="lines", lazy="selectin")
    product = relationship("Product", back_populates="replenishment_lines", lazy="selectin")
    location = relationship("Location", back_populates="replenishment_lines", lazy="selectin")
