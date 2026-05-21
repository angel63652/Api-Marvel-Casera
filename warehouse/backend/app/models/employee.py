from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey,
    Enum as SAEnum, Date, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class EmployeeRole(str, enum.Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    PICKER = "PICKER"
    DRIVER = "DRIVER"
    OFFICE = "OFFICE"


class PayrollStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"


class CalendarEventType(str, enum.Enum):
    TRUCK = "TRUCK"
    PAYROLL = "PAYROLL"
    MEETING = "MEETING"
    DELIVERY = "DELIVERY"
    OTHER = "OTHER"


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    employee_number = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    surname = Column(String(100), nullable=False)
    dni = Column(String(20), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), nullable=True)
    position = Column(String(100), nullable=True)
    department = Column(String(100), nullable=True)
    hire_date = Column(Date, nullable=True)
    salary_base = Column(Float, nullable=False, default=0.0)
    is_active = Column(Boolean, nullable=False, default=True)
    is_driver = Column(Boolean, nullable=False, default=False)
    role = Column(SAEnum(EmployeeRole), nullable=False, default=EmployeeRole.PICKER)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    payrolls = relationship(
        "Payroll",
        back_populates="employee",
        cascade="all, delete-orphan",
        foreign_keys="Payroll.employee_id",
        lazy="selectin",
    )
    movements = relationship("Movement", back_populates="user", lazy="selectin")
    orders_picked = relationship(
        "Order",
        back_populates="buyer",
        lazy="selectin",
    )
    lines_picked = relationship(
        "OrderLine",
        foreign_keys="OrderLine.picked_by",
        back_populates="picker",
        lazy="selectin",
    )
    trucks_driven = relationship("Truck", back_populates="driver", lazy="selectin")
    schedules_driven = relationship(
        "TruckSchedule",
        foreign_keys="TruckSchedule.driver_id",
        back_populates="driver",
        lazy="selectin",
    )
    schedules_created = relationship(
        "TruckSchedule",
        foreign_keys="TruckSchedule.created_by",
        back_populates="creator",
        lazy="selectin",
    )
    calendar_events = relationship(
        "CalendarEvent",
        back_populates="employee",
        lazy="selectin",
    )
    replenishments = relationship(
        "Replenishment",
        back_populates="created_by_employee",
        lazy="selectin",
    )


class Payroll(Base):
    __tablename__ = "payrolls"

    __table_args__ = (
        UniqueConstraint("employee_id", "year", "month", name="uq_payroll_employee_period"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    employee_id = Column(
        Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    salary_base = Column(Float, nullable=False)
    bonuses = Column(Float, nullable=False, default=0.0)
    deductions = Column(Float, nullable=False, default=0.0)
    net_salary = Column(Float, nullable=False)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    paid_by = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(SAEnum(PayrollStatus), nullable=False, default=PayrollStatus.PENDING)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    employee = relationship(
        "Employee",
        foreign_keys=[employee_id],
        back_populates="payrolls",
        lazy="selectin",
    )
    paid_by_employee = relationship(
        "Employee",
        foreign_keys=[paid_by],
        lazy="selectin",
    )


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    date = Column(Date, nullable=False, index=True)
    time = Column(String(5), nullable=True)
    type = Column(SAEnum(CalendarEventType), nullable=False, default=CalendarEventType.OTHER)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    truck_id = Column(Integer, ForeignKey("trucks.id", ondelete="SET NULL"), nullable=True)
    all_day = Column(Boolean, nullable=False, default=False)
    color = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    employee = relationship("Employee", back_populates="calendar_events", lazy="selectin")
    truck = relationship("Truck", back_populates="calendar_events", lazy="selectin")
