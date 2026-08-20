from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.common.enums import ActorType, InventoryMovementType


class RestockRequest(BaseModel):
    quantity: int = Field(..., gt=0, description="Number of units to add")
    reason: str | None = Field(None, max_length=500)


class AdjustmentRequest(BaseModel):
    quantity: int = Field(..., description="Positive or negative adjustment")
    reason: str | None = Field(None, max_length=500, description="Required for negative adjustments")


class InventoryMovementResponse(BaseModel):
    id: UUID
    shop_id: UUID
    product_id: UUID
    type: InventoryMovementType
    quantity: int
    reason: str | None
    created_by_type: ActorType
    created_by_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InventoryStatusResponse(BaseModel):
    """Compact product inventory row for the inventory overview."""
    product_id: UUID
    product_name: str
    category: str | None
    stock_quantity: int
    low_stock_threshold: int
    is_low_stock: bool
    selling_price: float
