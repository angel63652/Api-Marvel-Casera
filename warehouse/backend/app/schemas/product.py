from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from app.models.product import UnitType


class ProductBase(BaseModel):
    niu: str = Field(..., min_length=1, max_length=50, description="NIU number")
    barcode: str = Field(..., min_length=1, max_length=100, description="Barcode")
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=100)
    unit: UnitType = UnitType.UNIT
    min_stock: float = Field(default=0.0, ge=0)
    weight: Optional[float] = Field(default=None, ge=0)
    price_cost: Optional[float] = Field(default=None, ge=0)
    price_base: Optional[float] = Field(default=None, ge=0, description="Default sale price")
    active: bool = True


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=100)
    unit: Optional[UnitType] = None
    min_stock: Optional[float] = Field(default=None, ge=0)
    weight: Optional[float] = Field(default=None, ge=0)
    price_cost: Optional[float] = Field(default=None, ge=0)
    price_base: Optional[float] = Field(default=None, ge=0)
    active: Optional[bool] = None
    barcode: Optional[str] = Field(default=None, max_length=100)


class ProductResponse(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    current_stock: float
    reserved_stock: float = 0.0
    available_stock: float = 0.0
    created_at: datetime
    updated_at: datetime


class ProductWithStock(ProductResponse):
    """Product with detailed stock breakdown per location."""
    stock_by_location: list[dict] = Field(default_factory=list)
    is_low_stock: bool = False

    model_config = ConfigDict(from_attributes=True)
