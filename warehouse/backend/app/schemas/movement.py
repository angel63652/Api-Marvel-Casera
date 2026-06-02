from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime, date
from app.models.movement import MovementType


class MovementLineCreate(BaseModel):
    product_id: int
    location_id: Optional[int] = None
    quantity: float = Field(..., gt=0)
    unit_price: Optional[float] = Field(default=None, ge=0)
    lot: Optional[str] = Field(default=None, max_length=100)
    expiry_date: Optional[date] = None


class MovementCreate(BaseModel):
    type: MovementType
    reference: Optional[str] = Field(default=None, max_length=100)
    date: Optional[datetime] = None
    notes: Optional[str] = None
    supplier: Optional[str] = Field(default=None, max_length=255)
    user_id: Optional[int] = None
    lines: list[MovementLineCreate] = Field(..., min_length=1)


class StockAdjustmentRequest(BaseModel):
    """Sensitive manual stock correction — requires manager password re-auth."""
    product_id: int
    location_id: Optional[int] = None
    quantity: float = Field(..., description="Signed delta (+/-) to apply to stock")
    reason: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., description="Caller's password, re-verified")


class MovementLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    movement_id: int
    product_id: int
    location_id: Optional[int]
    quantity: float
    unit_price: Optional[float]
    lot: Optional[str]
    expiry_date: Optional[date]
    product_name: Optional[str] = None
    product_barcode: Optional[str] = None
    location_code: Optional[str] = None


class MovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: MovementType
    reference: Optional[str]
    date: datetime
    notes: Optional[str]
    supplier: Optional[str]
    user_id: Optional[int]
    created_at: datetime
    lines: list[MovementLineResponse] = []

    user_name: Optional[str] = None


class MovementReportItem(BaseModel):
    """Summary item for movement reports."""
    type: MovementType
    count: int
    total_quantity: float
    total_value: Optional[float]
    period_start: datetime
    period_end: datetime
