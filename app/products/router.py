from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import ActorType
from app.common.pagination import Page, PaginationParams
from app.database import get_db
from app.dependencies import AuthenticatedUser, get_current_user, require_owner
from app.products import service as product_service
from app.products.schemas import (
    ProductCreate,
    ProductResponse,
    ProductSearchResponse,
    ProductUpdate,
)

router = APIRouter(prefix="/shops/{shop_id}/products", tags=["Products"])


@router.get(
    "",
    response_model=Page[ProductResponse],
    summary="List Products",
    description="List all active products in a shop. Accessible by both owners and workers.",
)
async def list_products(
    shop_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    params: Annotated[PaginationParams, Depends()],
) -> Page[ProductResponse]:
    page = await product_service.list_products(shop_id, db, params)
    return Page[ProductResponse](
        items=[ProductResponse.model_validate(p) for p in page.items],
        page=page.page,
        page_size=page.page_size,
        total=page.total,
        total_pages=page.total_pages,
    )


@router.get(
    "/search",
    response_model=list[ProductSearchResponse],
    summary="Search Products",
    description="Case-insensitive product search by name or category. Accessible to workers and owners.",
)
async def search_products(
    shop_id: UUID,
    q: str = Query(..., min_length=1, max_length=100, description="Search query"),
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> list[ProductSearchResponse]:
    products = await product_service.search_products(shop_id, q, db)
    return [ProductSearchResponse.model_validate(p) for p in products]


@router.get(
    "/low-stock",
    response_model=list[ProductResponse],
    summary="Low Stock Products",
    description="Return products where stock is at or below the threshold. Owner only.",
)
async def low_stock_products(
    shop_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ProductResponse]:
    products = await product_service.get_low_stock_products(shop_id, db)
    return [ProductResponse.model_validate(p) for p in products]


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Product",
    description="Create a new product with optional initial stock. "
                "All operations are atomic — product creation and inventory movement happen together.",
)
async def create_product(
    shop_id: UUID,
    body: ProductCreate,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductResponse:
    product = await product_service.create_product(
        shop_id=shop_id,
        owner_id=current_user.id,
        data=body,
        actor_type=ActorType.OWNER,
        actor_id=current_user.id,
        db=db,
    )
    return ProductResponse.model_validate(product)


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Get Product",
    description="Get a single product by ID.",
)
async def get_product(
    shop_id: UUID,
    product_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductResponse:
    product = await product_service.get_product_for_shop(shop_id, product_id, db)
    return ProductResponse.model_validate(product)


@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Update Product",
    description="Update product details (price, threshold, etc.). Owner only.",
)
async def update_product(
    shop_id: UUID,
    product_id: UUID,
    body: ProductUpdate,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductResponse:
    product = await product_service.update_product(shop_id, product_id, current_user.id, body, db)
    return ProductResponse.model_validate(product)


@router.delete(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Deactivate Product",
    description="Soft-delete a product (sets is_active=false). Historical sales are preserved.",
)
async def deactivate_product(
    shop_id: UUID,
    product_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductResponse:
    product = await product_service.deactivate_product(shop_id, product_id, current_user.id, db)
    return ProductResponse.model_validate(product)
