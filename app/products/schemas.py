from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    selling_price: Decimal = Field(..., gt=0, decimal_places=2)
    initial_stock: int = Field(0, ge=0, description="Starting stock quantity")
    low_stock_threshold: int = Field(5, ge=0)
    category: str | None = Field(None, max_length=100)
    photo_url: str | None = Field(None, max_length=2048)


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    selling_price: Decimal | None = Field(None, gt=0, decimal_places=2)
    low_stock_threshold: int | None = Field(None, ge=0)
    category: str | None = None
    photo_url: str | None = None
    is_active: bool | None = None


class ProductResponse(BaseModel):
    id: UUID
    shop_id: UUID
    name: str
    photo_url: str | None
    selling_price: Decimal
    stock_quantity: int
    low_stock_threshold: int
    category: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductSearchResponse(BaseModel):
    """Lightweight product response for search results."""
    id: UUID
    name: str
    photo_url: str | None
    selling_price: Decimal
    stock_quantity: int
    category: str | None
    is_active: bool

    model_config = {"from_attributes": True}
