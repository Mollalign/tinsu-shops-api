from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ShopCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    location: str | None = Field(None, max_length=500)
    phone: str | None = Field(None, max_length=20)


class ShopUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    location: str | None = Field(None, max_length=500)
    phone: str | None = Field(None, max_length=20)
    is_active: bool | None = None


class ShopResponse(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    location: str | None
    phone: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
