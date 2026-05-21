from app.schemas.product import (
    ProductBase, ProductCreate, ProductUpdate, ProductResponse, ProductWithStock
)
from app.schemas.location import (
    LocationCreate, LocationUpdate, LocationResponse, ProductLocationCreate, ProductLocationResponse
)
from app.schemas.movement import (
    MovementLineCreate, MovementCreate, MovementLineResponse, MovementResponse, MovementReportItem
)
from app.schemas.replenishment import (
    ReplenishmentLineCreate, ReplenishmentCreate, ReplenishmentLineResponse, ReplenishmentResponse
)
from app.schemas.order import (
    OrderLineCreate, OrderCreate, OrderLineResponse, OrderResponse,
    PickingUpdate, ConformityRequest, ReturnRequest, PickingListItem
)
from app.schemas.truck import (
    TruckCreate, TruckUpdate, TruckResponse,
    TruckScheduleCreate, TruckScheduleUpdate, TruckScheduleResponse,
    TruckReturnCreate, TruckReturnResponse,
    TruckScheduleComplete, TruckCalendarDay
)
from app.schemas.employee import (
    EmployeeCreate, EmployeeUpdate, EmployeeResponse,
    PayrollCreate, PayrollResponse,
    CalendarEventCreate, CalendarEventUpdate, CalendarEventResponse
)
from app.schemas.email_schema import (
    EmailClientCreate, EmailClientUpdate, EmailClientResponse,
    EmailMessageResponse, EmailFilterRequest, EmailFilterResponse,
    NotifyOfficeRequest
)

__all__ = [
    "ProductBase", "ProductCreate", "ProductUpdate", "ProductResponse", "ProductWithStock",
    "LocationCreate", "LocationUpdate", "LocationResponse",
    "ProductLocationCreate", "ProductLocationResponse",
    "MovementLineCreate", "MovementCreate", "MovementLineResponse", "MovementResponse", "MovementReportItem",
    "ReplenishmentLineCreate", "ReplenishmentCreate", "ReplenishmentLineResponse", "ReplenishmentResponse",
    "OrderLineCreate", "OrderCreate", "OrderLineResponse", "OrderResponse",
    "PickingUpdate", "ConformityRequest", "ReturnRequest", "PickingListItem",
    "TruckCreate", "TruckUpdate", "TruckResponse",
    "TruckScheduleCreate", "TruckScheduleUpdate", "TruckScheduleResponse",
    "TruckReturnCreate", "TruckReturnResponse", "TruckScheduleComplete", "TruckCalendarDay",
    "EmployeeCreate", "EmployeeUpdate", "EmployeeResponse",
    "PayrollCreate", "PayrollResponse",
    "CalendarEventCreate", "CalendarEventUpdate", "CalendarEventResponse",
    "EmailClientCreate", "EmailClientUpdate", "EmailClientResponse",
    "EmailMessageResponse", "EmailFilterRequest", "EmailFilterResponse", "NotifyOfficeRequest",
]
