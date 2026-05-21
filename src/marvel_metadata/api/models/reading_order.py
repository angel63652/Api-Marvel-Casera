"""Reading order response and request models."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class ReadingOrderItemResponse(BaseModel):
    id: int
    position: int
    issue_id: Optional[int] = None
    issue_title: str
    note: str = ""
    detail_url: Optional[str] = None
    cover_path: Optional[str] = None
    cover_extension: Optional[str] = None
    series_name: Optional[str] = None
    on_sale_date: Optional[str] = None


class ReadingOrderSummary(BaseModel):
    id: int
    slug: str
    name: str
    description: str = ""
    is_curated: bool
    item_count: int
    created_at: str


class ReadingOrderDetail(BaseModel):
    id: int
    slug: str
    name: str
    description: str = ""
    is_curated: bool
    created_at: str
    items: list[ReadingOrderItemResponse] = Field(default_factory=list)


class ReadingOrderItemCreate(BaseModel):
    issue_id: Optional[int] = None
    issue_title: str = Field(..., min_length=1)
    note: str = ""


class ReadingOrderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    items: list[ReadingOrderItemCreate] = Field(default_factory=list)
