from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.common.enums import ActorType


class SaleItemRequest(BaseModel):
    product_id: UUID
    quantity: int = Field(..., gt=0, description="Must be at least 1")


class SaleRequest(BaseModel):
    """
    Simple sale request — items only.
    The server owns all pricing, stock validation, and total calculation.
    Payment method is not part of the sale flow anymore.
    """
    items: list[SaleItemRequest] = Field(..., min_length=1)


class SaleItemResponse(BaseModel):
    product_id: UUID
    product_name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class SoldByResponse(BaseModel):
    type: ActorType
    id: UUID
    name: str


class SaleResponse(BaseModel):
    id: UUID
    shop_id: UUID
    total_amount: Decimal
    items: list[SaleItemResponse]
    sold_by: SoldByResponse
    created_at: datetime

    model_config = {"from_attributes": True}


class SaleListResponse(BaseModel):
    """Lightweight sale row for list/history views."""
    id: UUID
    shop_id: UUID
    total_amount: Decimal
    items_count: int
    sold_by_name: str
    created_at: datetime

    model_config = {"from_attributes": True}
