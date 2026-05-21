from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey,
    Enum as SAEnum, JSON, Time
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class ScheduleType(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class ScheduleStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    IN_ROUTE = "IN_ROUTE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Truck(Base):
    __tablename__ = "trucks"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    plate = Column(String(20), unique=True, nullable=False, index=True)
    brand = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)
    capacity_kg = Column(Float, nullable=True)
    capacity_m3 = Column(Float, nullable=True)
    driver_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    driver = relationship("Employee", back_populates="trucks_driven", lazy="selectin")
    schedules = relationship(
        "TruckSchedule",
        back_populates="truck",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    calendar_events = relationship(
        "CalendarEvent",
        back_populates="truck",
        lazy="selectin",
    )


class TruckSchedule(Base):
    __tablename__ = "truck_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    truck_id = Column(Integer, ForeignKey("trucks.id", ondelete="CASCADE"), nullable=False, index=True)
    driver_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    schedule_type = Column(SAEnum(ScheduleType), nullable=False, default=ScheduleType.DAILY)
    route_description = Column(Text, nullable=True)
    estimated_cost = Column(Float, nullable=True)
    actual_cost = Column(Float, nullable=True)
    departure_time = Column(DateTime(timezone=True), nullable=True)
    return_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(SAEnum(ScheduleStatus), nullable=False, default=ScheduleStatus.SCHEDULED, index=True)
    orders_assigned = Column(JSON, nullable=True, default=list)
    notes = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    truck = relationship("Truck", back_populates="schedules", lazy="selectin")
    driver = relationship(
        "Employee",
        foreign_keys=[driver_id],
        back_populates="schedules_driven",
        lazy="selectin",
    )
    creator = relationship(
        "Employee",
        foreign_keys=[created_by],
        back_populates="schedules_created",
        lazy="selectin",
    )
    returns = relationship(
        "TruckReturn",
        back_populates="truck_schedule",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class TruckReturn(Base):
    __tablename__ = "truck_returns"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    truck_schedule_id = Column(
        Integer, ForeignKey("truck_schedules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    reason = Column(Text, nullable=True)
    processed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    truck_schedule = relationship("TruckSchedule", back_populates="returns", lazy="selectin")
    order = relationship("Order", lazy="selectin")
    product = relationship("Product", lazy="selectin")
