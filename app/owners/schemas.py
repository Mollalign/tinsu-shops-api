from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class OwnerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    phone: str = Field(..., min_length=6, max_length=20)
    pin: str = Field(..., min_length=4, max_length=20)


class OwnerResponse(BaseModel):
    id: UUID
    name: str
    phone: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
