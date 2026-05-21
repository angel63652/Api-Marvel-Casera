from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey,
    Enum as SAEnum, Date
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class MovementType(str, enum.Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    REPLENISHMENT = "REPLENISHMENT"
    RETURN = "RETURN"
    ADJUSTMENT = "ADJUSTMENT"


class Movement(Base):
    __tablename__ = "movements"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    type = Column(SAEnum(MovementType), nullable=False, index=True)
    reference = Column(String(100), nullable=True, index=True)
    date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    notes = Column(Text, nullable=True)
    supplier = Column(String(255), nullable=True)
    user_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("Employee", back_populates="movements", lazy="selectin")
    lines = relationship(
        "MovementLine",
        back_populates="movement",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class MovementLine(Base):
    __tablename__ = "movement_lines"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    movement_id = Column(Integer, ForeignKey("movements.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="RESTRICT"), nullable=True)
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=True)
    lot = Column(String(100), nullable=True)
    expiry_date = Column(Date, nullable=True)

    movement = relationship("Movement", back_populates="lines", lazy="selectin")
    product = relationship("Product", back_populates="movement_lines", lazy="selectin")
    location = relationship("Location", back_populates="movement_lines", lazy="selectin")
