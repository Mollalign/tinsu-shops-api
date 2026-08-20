from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.common.enums import ActorType, PaymentMethod


class SaleItemRequest(BaseModel):
    product_id: UUID
    quantity: int = Field(..., gt=0, description="Must be at least 1")


class SaleRequest(BaseModel):
    payment_method: PaymentMethod
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
    payment_method: PaymentMethod
    total_amount: Decimal
    items: list[SaleItemResponse]
    sold_by: SoldByResponse
    created_at: datetime

    model_config = {"from_attributes": True}


class SaleListResponse(BaseModel):
    """Lightweight sale row for list views."""
    id: UUID
    shop_id: UUID
    payment_method: PaymentMethod
    total_amount: Decimal
    sold_by_type: ActorType
    sold_by_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}
