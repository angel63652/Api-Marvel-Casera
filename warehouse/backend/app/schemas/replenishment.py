from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from app.models.replenishment import ReplenishmentStatus, ReplenishmentPriority


class ReplenishmentLineCreate(BaseModel):
    product_id: int
    location_id: Optional[int] = None
    current_qty: float = Field(default=0.0, ge=0)
    min_qty: float = Field(default=0.0, ge=0)
    requested_qty: float = Field(..., gt=0)


class ReplenishmentCreate(BaseModel):
    priority: ReplenishmentPriority = ReplenishmentPriority.MEDIUM
    notes: Optional[str] = None
    created_by: Optional[int] = None
    lines: list[ReplenishmentLineCreate] = Field(..., min_length=1)


class ReplenishmentStatusUpdate(BaseModel):
    status: ReplenishmentStatus
    notes: Optional[str] = None


class ReplenishmentLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    replenishment_id: int
    product_id: int
    location_id: Optional[int]
    current_qty: float
    min_qty: float
    requested_qty: float
    received_qty: float
    product_name: Optional[str] = None
    product_barcode: Optional[str] = None
    location_code: Optional[str] = None


class ReplenishmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: ReplenishmentStatus
    priority: ReplenishmentPriority
    notes: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    created_by: Optional[int]
    lines: list[ReplenishmentLineResponse] = []

    created_by_name: Optional[str] = None


class ReplenishmentCompleteRequest(BaseModel):
    """Used when marking a replenishment as complete with received quantities."""
    received_quantities: dict[int, float] = Field(
        ..., description="Map of line_id -> received_qty"
    )
    notes: Optional[str] = None
