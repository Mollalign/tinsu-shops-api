"""Category API router — list is open to any auth, CUD is owner-only."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.categories import service as category_service
from app.categories.schemas import CategoryCreate, CategoryResponse, CategoryUpdate
from app.database import get_db
from app.dependencies import AuthenticatedUser, get_current_user, require_owner

router = APIRouter(prefix="/shops/{shop_id}/categories", tags=["Categories"])


@router.get(
    "",
    response_model=list[CategoryResponse],
    summary="List Categories",
)
async def list_categories(
    shop_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CategoryResponse]:
    cats = await category_service.list_categories(shop_id, db)
    return [CategoryResponse.model_validate(c) for c in cats]


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Category",
)
async def create_category(
    shop_id: UUID,
    body: CategoryCreate,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CategoryResponse:
    cat = await category_service.create_category(shop_id, current_user.id, body, db)
    return CategoryResponse.model_validate(cat)


@router.patch(
    "/{category_id}",
    response_model=CategoryResponse,
    summary="Rename Category",
)
async def update_category(
    shop_id: UUID,
    category_id: UUID,
    body: CategoryUpdate,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CategoryResponse:
    cat = await category_service.update_category(
        shop_id, category_id, current_user.id, body, db
    )
    return CategoryResponse.model_validate(cat)


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Category",
    description="Products in this category will have category_id set to NULL.",
)
async def delete_category(
    shop_id: UUID,
    category_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await category_service.delete_category(shop_id, category_id, current_user.id, db)
