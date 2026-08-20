from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import Page, PaginationParams
from app.database import get_db
from app.dependencies import AuthenticatedUser, require_owner
from app.shops import service as shop_service
from app.shops.schemas import ShopCreate, ShopResponse, ShopUpdate

router = APIRouter(prefix="/shops", tags=["Shops"])


@router.get(
    "",
    response_model=list[ShopResponse],
    summary="List Owner Shops",
    description="Return all shops owned by the authenticated owner.",
)
async def list_shops(
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ShopResponse]:
    shops = await shop_service.get_owner_shops(current_user.id, db)
    return [ShopResponse.model_validate(s) for s in shops]


@router.post(
    "",
    response_model=ShopResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Shop",
    description="Create a new shop for the authenticated owner.",
)
async def create_shop(
    body: ShopCreate,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ShopResponse:
    shop = await shop_service.create_shop(current_user.id, body, db)
    return ShopResponse.model_validate(shop)


@router.get(
    "/{shop_id}",
    response_model=ShopResponse,
    summary="Get Shop",
    description="Return a specific shop. Owner must own this shop.",
)
async def get_shop(
    shop_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ShopResponse:
    shop = await shop_service.get_shop_for_owner(shop_id, current_user.id, db)
    return ShopResponse.model_validate(shop)


@router.patch(
    "/{shop_id}",
    response_model=ShopResponse,
    summary="Update Shop",
    description="Partially update a shop's details.",
)
async def update_shop(
    shop_id: UUID,
    body: ShopUpdate,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ShopResponse:
    shop = await shop_service.update_shop(shop_id, current_user.id, body, db)
    return ShopResponse.model_validate(shop)
