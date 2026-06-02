"""Client portal schemas (auth + profile)."""
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class PortalRegisterRequest(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=255)
    tax_id: str = Field(..., min_length=4, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: Optional[str] = None
    phone: Optional[str] = None


class PortalLoginRequest(BaseModel):
    email: EmailStr
    password: str


class CustomerSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    company_name: str
    tax_id: str
    status: str


class CustomerUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    customer_id: int
    email: EmailStr
    name: Optional[str] = None
    role: str
    is_active: bool


class PortalTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: CustomerUserResponse
    customer: CustomerSummary


# ---- Catalog ---------------------------------------------------------------
class CatalogItem(BaseModel):
    id: int
    niu: str
    barcode: str
    name: str
    category: Optional[str] = None
    unit: str
    available_stock: float
    price: Optional[float] = None  # resolved for the customer's tier


# ---- Orders ----------------------------------------------------------------
class PortalOrderItem(BaseModel):
    product_id: int
    quantity: float = Field(..., gt=0)


class PortalOrderCreate(BaseModel):
    items: list[PortalOrderItem] = Field(..., min_length=1)
    shipping_address_id: Optional[int] = None
    notes: Optional[str] = None


class PortalOrderLine(BaseModel):
    product_id: int
    product_name: Optional[str] = None
    quantity: float
    unit_price: Optional[float] = None
    line_total: Optional[float] = None


class PortalOrderResponse(BaseModel):
    id: int
    order_number: str
    status: str
    created_at: Optional[str] = None
    notes: Optional[str] = None
    lines: list[PortalOrderLine] = []
    total: Optional[float] = None


# ---- Profile / addresses / change requests ---------------------------------
class AddressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: str
    label: Optional[str] = None
    line1: str
    line2: Optional[str] = None
    city: str
    province: Optional[str] = None
    postal_code: str
    country: str
    is_default: bool


class ProfileResponse(BaseModel):
    customer: CustomerSummary
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    price_tier: Optional[str] = None
    addresses: list[AddressResponse] = []


class ChangeRequestCreate(BaseModel):
    target: str = Field(..., description="FISCAL or ADDRESS")
    payload: dict = Field(..., description="Proposed new values")


class ChangeRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    target: str
    status: str
    payload: dict
