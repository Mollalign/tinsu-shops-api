from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import Page, PaginationParams
from app.database import get_db
from app.dependencies import AuthenticatedUser, require_owner
from app.workers import service as worker_service
from app.workers.schemas import (
    WorkerCreateResponse,
    WorkerResetPin,
    WorkerResponse,
    WorkerCreate,
    WorkerUpdate,
)

router = APIRouter(prefix="/shops/{shop_id}/workers", tags=["Workers"])


@router.get(
    "",
    response_model=Page[WorkerResponse],
    summary="List Workers",
    description="List all workers for a shop. Owner only.",
)
async def list_workers(
    shop_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
    params: Annotated[PaginationParams, Depends()],
) -> Page[WorkerResponse]:
    page = await worker_service.list_workers(shop_id, current_user.id, db, params)
    return Page[WorkerResponse](
        items=[WorkerResponse.model_validate(w) for w in page.items],
        page=page.page,
        page_size=page.page_size,
        total=page.total,
        total_pages=page.total_pages,
    )


@router.post(
    "",
    response_model=WorkerCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Worker",
    description="Add a new worker to the shop. PIN is generated automatically if not provided. "
                "The plain-text PIN is returned ONLY in this response.",
)
async def create_worker(
    shop_id: UUID,
    body: WorkerCreate,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkerCreateResponse:
    return await worker_service.create_worker(shop_id, current_user.id, body, db)


@router.get(
    "/{worker_id}",
    response_model=WorkerResponse,
    summary="Get Worker",
    description="Return a specific worker belonging to the shop.",
)
async def get_worker(
    shop_id: UUID,
    worker_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkerResponse:
    worker = await worker_service.get_worker(shop_id, worker_id, current_user.id, db)
    return WorkerResponse.model_validate(worker)


@router.patch(
    "/{worker_id}",
    response_model=WorkerResponse,
    summary="Update Worker",
    description="Update worker details.",
)
async def update_worker(
    shop_id: UUID,
    worker_id: UUID,
    body: WorkerUpdate,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkerResponse:
    worker = await worker_service.update_worker(shop_id, worker_id, current_user.id, body, db)
    return WorkerResponse.model_validate(worker)


@router.post(
    "/{worker_id}/reset-pin",
    summary="Reset Worker PIN",
    description="Reset a worker's PIN. Returns the new plain-text PIN (shown once only).",
)
async def reset_pin(
    shop_id: UUID,
    worker_id: UUID,
    body: WorkerResetPin,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    new_pin = await worker_service.reset_worker_pin(
        shop_id, worker_id, current_user.id, body, db
    )
    return {"message": "PIN reset successfully.", "pin": new_pin}


@router.post(
    "/{worker_id}/disable",
    response_model=WorkerResponse,
    summary="Disable Worker",
    description="Disable a worker account. They can no longer log in.",
)
async def disable_worker(
    shop_id: UUID,
    worker_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkerResponse:
    worker = await worker_service.disable_worker(shop_id, worker_id, current_user.id, db)
    return WorkerResponse.model_validate(worker)
