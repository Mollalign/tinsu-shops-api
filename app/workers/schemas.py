from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class WorkerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    pin: str | None = Field(
        None, min_length=4, max_length=20, description="Leave null to auto-generate a PIN"
    )


class WorkerUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)


class WorkerResetPin(BaseModel):
    new_pin: str | None = Field(
        None, min_length=4, max_length=20, description="Leave null to auto-generate"
    )


class WorkerResponse(BaseModel):
    id: UUID
    shop_id: UUID
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkerCreateResponse(WorkerResponse):
    """Returned only on creation — includes the temporary PIN once."""
    pin: str | None = Field(None, description="Temporary PIN (shown once, never stored)")
