from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    aisle = Column(String(10), nullable=False, index=True)
    rack = Column(String(10), nullable=False)
    position = Column(String(10), nullable=False)
    zone = Column(String(50), nullable=True)
    capacity = Column(Float, nullable=False, default=0.0)
    current_load = Column(Float, nullable=False, default=0.0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    product_locations = relationship(
        "ProductLocation",
        back_populates="location",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    movement_lines = relationship(
        "MovementLine",
        back_populates="location",
        lazy="selectin",
    )
    order_lines = relationship(
        "OrderLine",
        back_populates="location",
        lazy="selectin",
    )
    replenishment_lines = relationship(
        "ReplenishmentLine",
        back_populates="location",
        lazy="selectin",
    )


class ProductLocation(Base):
    __tablename__ = "product_locations"

    __table_args__ = (
        UniqueConstraint("product_id", "location_id", name="uq_product_location"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity = Column(Float, nullable=False, default=0.0)
    min_quantity = Column(Float, nullable=False, default=0.0)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    product = relationship("Product", back_populates="locations", lazy="selectin")
    location = relationship("Location", back_populates="product_locations", lazy="selectin")
