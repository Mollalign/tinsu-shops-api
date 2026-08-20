from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import ActorType
from app.common.pagination import Page, PaginationParams
from app.database import get_db
from app.dependencies import AuthenticatedUser, get_current_user, require_owner
from app.inventory import service as inventory_service
from app.inventory.schemas import (
    AdjustmentRequest,
    InventoryMovementResponse,
    InventoryStatusResponse,
    RestockRequest,
)

router = APIRouter(prefix="/shops/{shop_id}", tags=["Inventory"])


@router.get(
    "/inventory",
    response_model=Page[InventoryStatusResponse],
    summary="Inventory Overview",
    description="Paginated inventory summary showing stock levels for all active products.",
)
async def get_inventory(
    shop_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
    params: Annotated[PaginationParams, Depends()],
) -> Page[InventoryStatusResponse]:
    return await inventory_service.get_inventory_overview(shop_id, current_user.id, db, params)


@router.get(
    "/inventory/low-stock",
    response_model=list[InventoryStatusResponse],
    summary="Low Stock Alert",
    description="Products at or below their low-stock threshold, sorted by lowest stock first.",
)
async def low_stock(
    shop_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[InventoryStatusResponse]:
    from app.products.service import get_low_stock_products
    products = await get_low_stock_products(shop_id, db)
    return [
        InventoryStatusResponse(
            product_id=p.id,
            product_name=p.name,
            category=p.category,
            stock_quantity=p.stock_quantity,
            low_stock_threshold=p.low_stock_threshold,
            is_low_stock=True,
            selling_price=float(p.selling_price),
        )
        for p in products
    ]


@router.post(
    "/products/{product_id}/restock",
    response_model=InventoryMovementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Restock Product",
    description="Add stock to a product. Creates a RESTOCK inventory movement.",
)
async def restock(
    shop_id: UUID,
    product_id: UUID,
    body: RestockRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InventoryMovementResponse:
    movement = await inventory_service.restock_product(
        shop_id, product_id, current_user.id, body, ActorType.OWNER, current_user.id, db
    )
    return InventoryMovementResponse.model_validate(movement)


@router.post(
    "/products/{product_id}/adjust",
    response_model=InventoryMovementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Adjust Stock",
    description="Make a manual stock adjustment (positive or negative). Negative stock is rejected.",
)
async def adjust(
    shop_id: UUID,
    product_id: UUID,
    body: AdjustmentRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InventoryMovementResponse:
    movement = await inventory_service.adjust_product_stock(
        shop_id, product_id, current_user.id, body, ActorType.OWNER, current_user.id, db
    )
    return InventoryMovementResponse.model_validate(movement)


@router.get(
    "/products/{product_id}/movements",
    response_model=Page[InventoryMovementResponse],
    summary="Product Movement History",
    description="Full inventory movement history for a specific product.",
)
async def product_movements(
    shop_id: UUID,
    product_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    params: Annotated[PaginationParams, Depends()],
) -> Page[InventoryMovementResponse]:
    return await inventory_service.list_product_movements(shop_id, product_id, db, params)
