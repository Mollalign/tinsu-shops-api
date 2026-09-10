from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import AuthenticatedUser, require_owner
from app.owners import service as owner_service
from app.owners.schemas import OwnerChangePinRequest, OwnerCreate, OwnerResponse

router = APIRouter(prefix="/owners", tags=["Owners"])


@router.post(
    "",
    response_model=OwnerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Owner",
    description="Create a new owner account. (Public endpoint — used for onboarding.)",
)
async def register_owner(
    body: OwnerCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OwnerResponse:
    owner = await owner_service.create_owner(body, db)
    return OwnerResponse.model_validate(owner)


@router.get(
    "/me",
    response_model=OwnerResponse,
    summary="Get Current Owner",
    description="Return the authenticated owner's profile.",
)
async def get_me(
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OwnerResponse:
    owner = await owner_service.get_owner_by_id(current_user.id, db)
    return OwnerResponse.model_validate(owner)


@router.patch(
    "/me/pin",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change Owner PIN",
    description=(
        "Change the authenticated owner's PIN. "
        "The current PIN is verified before the new PIN is stored (hashed). "
        "The plain-text PIN is never logged or returned."
    ),
)
async def change_pin(
    body: OwnerChangePinRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await owner_service.change_owner_pin(
        current_user.id, body.current_pin, body.new_pin, db
    )
