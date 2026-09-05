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
    CategorySearchResult,
    ProductCreate,
    ProductResponse,
    ProductSearchResponse,
    ProductSearchResult,
    ProductUpdate,
)

router = APIRouter(prefix="/shops/{shop_id}/products", tags=["Products"])


@router.get(
    "",
    response_model=Page[ProductResponse],
    summary="List Products",
    description="List active products in a shop. Filter by category_id. Accessible by owners and workers.",
)
async def list_products(
    shop_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    params: Annotated[PaginationParams, Depends()],
    category_id: UUID | None = Query(None, description="Filter by category UUID"),
) -> Page[ProductResponse]:
    page = await product_service.list_products(
        shop_id, db, params, category_id=category_id
    )
    return Page[ProductResponse](
        items=[ProductResponse.model_validate(p) for p in page.items],
        page=page.page,
        page_size=page.page_size,
        total=page.total,
        total_pages=page.total_pages,
    )


@router.get(
    "/search",
    response_model=ProductSearchResult,
    summary="Search Products",
    description=(
        "Case-insensitive product search by name. "
        "Also returns a matched_category when the query matches a category name "
        "and no category_id filter is active. "
        "Accessible to workers and owners."
    ),
)
async def search_products(
    shop_id: UUID,
    q: str = Query(..., min_length=1, max_length=100, description="Search query"),
    category_id: UUID | None = Query(None, description="Narrow results to a category"),
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> ProductSearchResult:
    matched_cat, products = await product_service.search_products(
        shop_id, q, db, category_id=category_id
    )

    matched_category: CategorySearchResult | None = None
    if matched_cat is not None:
        count = await product_service.count_category_products(
            shop_id, matched_cat.id, db
        )
        matched_category = CategorySearchResult(
            id=matched_cat.id,
            name=matched_cat.name,
            product_count=count,
        )

    return ProductSearchResult(
        matched_category=matched_category,
        items=[ProductSearchResponse.model_validate(p) for p in products],
    )


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
    description="Create a new product with optional initial stock and category. Owner only.",
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
    description="Pass category_id=null to clear, omit to leave unchanged. Owner only.",
)
async def update_product(
    shop_id: UUID,
    product_id: UUID,
    body: ProductUpdate,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductResponse:
    product = await product_service.update_product(
        shop_id, product_id, current_user.id, body, db
    )
    return ProductResponse.model_validate(product)


@router.delete(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Deactivate Product",
)
async def deactivate_product(
    shop_id: UUID,
    product_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductResponse:
    product = await product_service.deactivate_product(
        shop_id, product_id, current_user.id, db
    )
    return ProductResponse.model_validate(product)
