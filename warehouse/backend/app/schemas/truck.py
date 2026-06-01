from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
import enum


class ScheduleTypeEnum(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class ScheduleStatusEnum(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    IN_ROUTE = "IN_ROUTE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TruckBase(BaseModel):
    plate: str
    brand: str
    model_name: str
    capacity_kg: Optional[float] = None
    capacity_m3: Optional[float] = None
    driver_id: Optional[int] = None
    is_active: bool = True
    notes: Optional[str] = None


class TruckCreate(TruckBase):
    pass


class TruckUpdate(BaseModel):
    plate: Optional[str] = None
    brand: Optional[str] = None
    model_name: Optional[str] = None
    capacity_kg: Optional[float] = None
    capacity_m3: Optional[float] = None
    driver_id: Optional[int] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class TruckResponse(BaseModel):
    id: int
    plate: str
    brand: str
    model_name: str
    capacity_kg: Optional[float] = None
    capacity_m3: Optional[float] = None
    driver_id: Optional[int] = None
    driver_name: Optional[str] = None
    is_active: bool
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class TruckScheduleBase(BaseModel):
    truck_id: int
    driver_id: Optional[int] = None
    date: datetime
    schedule_type: ScheduleTypeEnum = ScheduleTypeEnum.DAILY
    route_description: Optional[str] = None
    estimated_cost: Optional[float] = None
    departure_time: Optional[datetime] = None
    return_time: Optional[datetime] = None
    orders_assigned: Optional[List[int]] = None
    notes: Optional[str] = None


class TruckScheduleCreate(TruckScheduleBase):
    pass


class TruckScheduleUpdate(BaseModel):
    driver_id: Optional[int] = None
    date: Optional[datetime] = None
    schedule_type: Optional[ScheduleTypeEnum] = None
    route_description: Optional[str] = None
    estimated_cost: Optional[float] = None
    actual_cost: Optional[float] = None
    departure_time: Optional[datetime] = None
    return_time: Optional[datetime] = None
    status: Optional[ScheduleStatusEnum] = None
    orders_assigned: Optional[List[int]] = None
    notes: Optional[str] = None


class TruckScheduleResponse(BaseModel):
    id: int
    truck_id: int
    truck_plate: Optional[str] = None
    driver_id: Optional[int] = None
    driver_name: Optional[str] = None
    date: datetime
    schedule_type: ScheduleTypeEnum
    route_description: Optional[str] = None
    estimated_cost: Optional[float] = None
    actual_cost: Optional[float] = None
    departure_time: Optional[datetime] = None
    return_time: Optional[datetime] = None
    status: ScheduleStatusEnum
    orders_assigned: Optional[List[int]] = None
    notes: Optional[str] = None
    created_by: Optional[int] = None

    model_config = {"from_attributes": True}


class TruckScheduleComplete(BaseModel):
    actual_cost: Optional[float] = None
    notes: Optional[str] = None
    return_time: Optional[datetime] = None


class TruckCalendarDay(BaseModel):
    date: str
    schedules: List[TruckScheduleResponse]


class TruckReturnCreate(BaseModel):
    truck_schedule_id: int
    order_id: Optional[int] = None
    product_id: int
    quantity: float
    reason: Optional[str] = None


class TruckReturnResponse(BaseModel):
    id: int
    truck_schedule_id: int
    order_id: Optional[int] = None
    product_id: int
    product_name: Optional[str] = None
    quantity: float
    reason: Optional[str] = None
    processed_at: datetime

    model_config = {"from_attributes": True}
