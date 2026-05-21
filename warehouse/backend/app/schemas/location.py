from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class LocationCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=20, description="Location code e.g. A-01-03")
    aisle: str = Field(..., min_length=1, max_length=10)
    rack: str = Field(..., min_length=1, max_length=10)
    position: str = Field(..., min_length=1, max_length=10)
    zone: Optional[str] = Field(default=None, max_length=50)
    capacity: float = Field(default=0.0, ge=0)
    is_active: bool = True


class LocationUpdate(BaseModel):
    aisle: Optional[str] = Field(default=None, max_length=10)
    rack: Optional[str] = Field(default=None, max_length=10)
    position: Optional[str] = Field(default=None, max_length=10)
    zone: Optional[str] = Field(default=None, max_length=50)
    capacity: Optional[float] = Field(default=None, ge=0)
    is_active: Optional[bool] = None


class LocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    aisle: str
    rack: str
    position: str
    zone: Optional[str]
    capacity: float
    current_load: float
    is_active: bool
    created_at: datetime


class ProductLocationCreate(BaseModel):
    product_id: int
    location_id: int
    quantity: float = Field(default=0.0, ge=0)
    min_quantity: float = Field(default=0.0, ge=0)


class ProductLocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    location_id: int
    quantity: float
    min_quantity: float
    updated_at: datetime

    product_name: Optional[str] = None
    product_barcode: Optional[str] = None
    location_code: Optional[str] = None
