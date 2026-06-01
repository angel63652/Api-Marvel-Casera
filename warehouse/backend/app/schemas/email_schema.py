from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.email_model import EmailPriority


class EmailClientCreate(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=255)
    customer_email: str = Field(..., max_length=255)
    folder_name: Optional[str] = Field(default=None, max_length=100)
    gmail_label: Optional[str] = Field(default=None, max_length=100)
    is_active: bool = True
    auto_filter: bool = True
    ai_category: Optional[str] = None


class EmailClientUpdate(BaseModel):
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    folder_name: Optional[str] = None
    gmail_label: Optional[str] = None
    is_active: Optional[bool] = None
    auto_filter: Optional[bool] = None
    ai_category: Optional[str] = None


class EmailClientResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    customer_name: str
    customer_email: str
    folder_name: Optional[str]
    gmail_label: Optional[str]
    is_active: bool
    auto_filter: bool
    ai_category: Optional[str]
    created_at: datetime
    message_count: int = 0


class EmailMessageResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    gmail_message_id: str
    from_email: str
    to_email: Optional[str]
    subject: Optional[str]
    body_preview: Optional[str]
    received_at: Optional[datetime]
    ai_category: Optional[str]
    ai_summary: Optional[str]
    ai_priority: Optional[EmailPriority]
    customer_id: Optional[int]
    folder_assigned: Optional[str]
    is_read: bool
    is_notified: bool
    office_notified_at: Optional[datetime]

    customer_name: Optional[str] = None


class EmailFilterRequest(BaseModel):
    subject: str
    body: str
    from_email: str


class EmailFilterResponse(BaseModel):
    category: str
    summary: str
    priority: str
    matched_customer_id: Optional[int] = None
    matched_customer_name: Optional[str] = None
    suggested_folder: Optional[str] = None


class NotifyOfficeRequest(BaseModel):
    staff_emails: List[str] = Field(..., min_length=1)
    note: Optional[str] = None


class EmailSyncResponse(BaseModel):
    synced_count: int = 0
    classified_count: int = 0
    errors: List[str] = Field(default_factory=list)
