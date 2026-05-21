from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from app.models.order import OrderStatus, OrderLineStatus


class OrderLineCreate(BaseModel):
    product_id: int
    quantity_requested: float = Field(..., gt=0)
    location_id: Optional[int] = None


class OrderCreate(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=255)
    customer_id: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = None
    lines: list[OrderLineCreate] = Field(..., min_length=1)


class OrderLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    product_id: int
    quantity_requested: float
    quantity_picked: float
    location_id: Optional[int]
    status: OrderLineStatus
    observations: Optional[str]
    picked_by: Optional[int]
    picked_at: Optional[datetime]

    product_name: Optional[str] = None
    product_barcode: Optional[str] = None
    product_niu: Optional[str] = None
    location_code: Optional[str] = None
    picker_name: Optional[str] = None


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_number: str
    customer_name: str
    customer_id: Optional[str]
    status: OrderStatus
    notes: Optional[str]
    buyer_id: Optional[int]
    conformity_signed: bool
    conformity_at: Optional[datetime]
    conformity_notes: Optional[str]
    return_reason: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    delivered_at: Optional[datetime]
    lines: list[OrderLineResponse] = []

    buyer_name: Optional[str] = None
    total_lines: int = 0
    lines_picked: int = 0
    lines_missing: int = 0


class PickingUpdate(BaseModel):
    """Payload for picking a single order line."""
    quantity_picked: float = Field(..., ge=0)
    location_id: Optional[int] = None
    observation: Optional[str] = None
    barcode_scanned: Optional[str] = None


class ObservationRequest(BaseModel):
    """Add observation to a line without picking."""
    observation: str = Field(..., min_length=1)
    status: Optional[OrderLineStatus] = None


class ConformityRequest(BaseModel):
    """Payload for confirming order conformity."""
    conformity_notes: Optional[str] = None
    picker_id: Optional[int] = None


class ReturnRequest(BaseModel):
    """Payload for marking an order as returned."""
    return_reason: str = Field(..., min_length=1)


class StartPickingRequest(BaseModel):
    picker_id: int


class PickingListItem(BaseModel):
    """Single item in a formatted picking list sorted for efficient picking."""
    line_id: int
    product_id: int
    product_name: str
    product_barcode: str
    product_niu: str
    location_id: Optional[int]
    location_code: Optional[str]
    aisle: Optional[str]
    rack: Optional[str]
    position: Optional[str]
    quantity_requested: float
    quantity_picked: float
    status: OrderLineStatus
    observations: Optional[str]
