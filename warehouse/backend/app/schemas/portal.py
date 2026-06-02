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
