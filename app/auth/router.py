from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service as auth_service
from app.auth.schemas import OwnerLoginRequest, TokenResponse, WorkerLoginRequest
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/owner/login",
    response_model=TokenResponse,
    summary="Owner Login",
    description="Authenticate as an owner using phone and PIN. Returns a JWT access token.",
)
async def owner_login(
    body: OwnerLoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    return await auth_service.owner_login(body.phone, body.pin, db)


@router.post(
    "/worker/login",
    response_model=TokenResponse,
    summary="Worker Login",
    description="Authenticate as a worker using shop_id, worker_id, and PIN. Token is shop-scoped.",
)
async def worker_login(
    body: WorkerLoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    return await auth_service.worker_login(
        body.shop_id, body.worker_id, body.pin, db
    )
