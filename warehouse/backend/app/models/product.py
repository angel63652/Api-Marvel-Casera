from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class UnitType(str, enum.Enum):
    KG = "kg"
    UNIT = "unit"
    BOX = "box"
    PALLET = "pallet"


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    niu = Column(String(50), unique=True, nullable=False, index=True)
    barcode = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True, index=True)
    unit = Column(SAEnum(UnitType), nullable=False, default=UnitType.UNIT)
    min_stock = Column(Float, nullable=False, default=0.0)
    current_stock = Column(Float, nullable=False, default=0.0)
    weight = Column(Float, nullable=True)
    price_cost = Column(Float, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    locations = relationship(
        "ProductLocation",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    movement_lines = relationship(
        "MovementLine",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    order_lines = relationship(
        "OrderLine",
        back_populates="product",
        lazy="selectin",
    )
    replenishment_lines = relationship(
        "ReplenishmentLine",
        back_populates="product",
        lazy="selectin",
    )
