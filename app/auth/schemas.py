from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.common.enums import UserRole


class OwnerLoginRequest(BaseModel):
    phone: str = Field(..., description="Owner phone number")
    pin: str = Field(..., min_length=4, description="Owner PIN")


class WorkerLoginRequest(BaseModel):
    shop_id: UUID = Field(..., description="The shop this worker belongs to")
    worker_id: UUID = Field(..., description="Worker ID")
    pin: str = Field(..., min_length=4, description="Worker PIN")


class TokenUserInfo(BaseModel):
    id: UUID
    role: UserRole
    name: str
    shop_id: UUID | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: TokenUserInfo
