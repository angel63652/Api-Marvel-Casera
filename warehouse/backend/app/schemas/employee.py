from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date, datetime
import enum


class EmployeeRoleEnum(str, enum.Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    PICKER = "PICKER"
    DRIVER = "DRIVER"
    OFFICE = "OFFICE"


class PayrollStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"


class CalendarEventTypeEnum(str, enum.Enum):
    TRUCK = "TRUCK"
    PAYROLL = "PAYROLL"
    MEETING = "MEETING"
    DELIVERY = "DELIVERY"
    OTHER = "OTHER"


class EmployeeBase(BaseModel):
    employee_number: str
    name: str
    surname: str
    dni: str
    email: str
    phone: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    hire_date: Optional[date] = None
    salary_base: float = 0.0
    is_active: bool = True
    is_driver: bool = False
    role: EmployeeRoleEnum = EmployeeRoleEnum.PICKER


class EmployeeCreate(EmployeeBase):
    password: str


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    surname: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    hire_date: Optional[date] = None
    salary_base: Optional[float] = None
    is_active: Optional[bool] = None
    is_driver: Optional[bool] = None
    role: Optional[EmployeeRoleEnum] = None
    password: Optional[str] = None


class EmployeeResponse(BaseModel):
    id: int
    employee_number: str
    name: str
    surname: str
    full_name: Optional[str] = None
    dni: str
    email: str
    phone: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    hire_date: Optional[date] = None
    salary_base: float
    is_active: bool
    is_driver: bool
    role: EmployeeRoleEnum
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    employee: EmployeeResponse


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PayrollBase(BaseModel):
    employee_id: int
    year: int
    month: int
    salary_base: float
    bonuses: float = 0.0
    deductions: float = 0.0
    notes: Optional[str] = None


class PayrollCreate(PayrollBase):
    pass


class PayrollResponse(BaseModel):
    id: int
    employee_id: int
    employee_name: Optional[str] = None
    year: int
    month: int
    month_name: Optional[str] = None
    salary_base: float
    bonuses: float
    deductions: float
    net_salary: float
    paid_at: Optional[datetime] = None
    paid_by: Optional[int] = None
    notes: Optional[str] = None
    status: PayrollStatusEnum
    created_at: datetime

    model_config = {"from_attributes": True}


class CalendarEventBase(BaseModel):
    title: str
    description: Optional[str] = None
    date: date
    time: Optional[str] = None
    type: CalendarEventTypeEnum = CalendarEventTypeEnum.OTHER
    employee_id: Optional[int] = None
    truck_id: Optional[int] = None
    all_day: bool = False
    color: Optional[str] = None


class CalendarEventCreate(CalendarEventBase):
    pass


class CalendarEventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    date: Optional[date] = None
    time: Optional[str] = None
    type: Optional[CalendarEventTypeEnum] = None
    employee_id: Optional[int] = None
    truck_id: Optional[int] = None
    all_day: Optional[bool] = None
    color: Optional[str] = None


class CalendarEventResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    date: date
    time: Optional[str] = None
    type: CalendarEventTypeEnum
    employee_id: Optional[int] = None
    truck_id: Optional[int] = None
    all_day: bool
    color: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
