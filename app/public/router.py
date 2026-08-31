"""
Public endpoints — no authentication required.
Used by workers before they have a JWT (e.g. selecting their shop / their own name).
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.shops.models import Shop
from app.shops.schemas import ShopResponse
from app.workers.models import Worker
from app.workers.schemas import WorkerResponse

router = APIRouter(prefix="/public", tags=["Public"])


@router.get(
    "/shops",
    response_model=list[ShopResponse],
    summary="List All Shops (Public)",
    description="Return all shops. No authentication required. Used by workers at login.",
)
async def list_public_shops(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ShopResponse]:
    result = await db.execute(select(Shop).order_by(Shop.name.asc()))
    shops = list(result.scalars().all())
    return [ShopResponse.model_validate(s) for s in shops]


@router.get(
    "/shops/{shop_id}/workers",
    response_model=list[WorkerResponse],
    summary="List Active Workers (Public)",
    description=(
        "Return active workers for a shop. No authentication required. "
        "Used by workers at login to pick their own name before entering their PIN."
    ),
)
async def list_public_workers(
    shop_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[WorkerResponse]:
    result = await db.execute(
        select(Worker)
        .where(Worker.shop_id == shop_id, Worker.is_active.is_(True))
        .order_by(Worker.name.asc())
    )
    workers = list(result.scalars().all())
    return [WorkerResponse.model_validate(w) for w in workers]
