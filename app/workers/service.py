from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import UnauthorizedShopAccessError, WorkerNotFoundError
from app.common.pagination import Page, PaginationParams
from app.common.security import generate_pin, hash_pin
from app.shops.service import get_shop_for_owner
from app.workers.models import Worker
from app.workers.schemas import WorkerCreate, WorkerCreateResponse, WorkerResetPin, WorkerUpdate


async def list_workers(
    shop_id: UUID,
    owner_id: UUID,
    db: AsyncSession,
    params: PaginationParams,
) -> Page[Worker]:
    await get_shop_for_owner(shop_id, owner_id, db)

    count_result = await db.execute(
        select(func.count()).select_from(Worker).where(Worker.shop_id == shop_id)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(Worker)
        .where(Worker.shop_id == shop_id)
        .order_by(Worker.created_at.asc())
        .offset(params.offset)
        .limit(params.limit)
    )
    workers = list(result.scalars().all())
    return Page.create(workers, total, params)


async def create_worker(
    shop_id: UUID, owner_id: UUID, data: WorkerCreate, db: AsyncSession
) -> WorkerCreateResponse:
    await get_shop_for_owner(shop_id, owner_id, db)

    plain_pin = data.pin or generate_pin(6)
    worker = Worker(
        shop_id=shop_id,
        name=data.name,
        pin_hash=hash_pin(plain_pin),
    )
    db.add(worker)
    await db.commit()
    await db.refresh(worker)

    return WorkerCreateResponse(
        id=worker.id,
        shop_id=worker.shop_id,
        name=worker.name,
        is_active=worker.is_active,
        created_at=worker.created_at,
        updated_at=worker.updated_at,
        pin=plain_pin,
    )


async def get_worker(
    shop_id: UUID, worker_id: UUID, owner_id: UUID, db: AsyncSession
) -> Worker:
    await get_shop_for_owner(shop_id, owner_id, db)
    result = await db.execute(
        select(Worker).where(Worker.id == worker_id, Worker.shop_id == shop_id)
    )
    worker = result.scalar_one_or_none()
    if not worker:
        raise WorkerNotFoundError()
    return worker


async def update_worker(
    shop_id: UUID, worker_id: UUID, owner_id: UUID, data: WorkerUpdate, db: AsyncSession
) -> Worker:
    worker = await get_worker(shop_id, worker_id, owner_id, db)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(worker, field, value)
    await db.commit()
    await db.refresh(worker)
    return worker


async def reset_worker_pin(
    shop_id: UUID, worker_id: UUID, owner_id: UUID, data: WorkerResetPin, db: AsyncSession
) -> str:
    """Returns the new plain-text PIN (shown once only)."""
    worker = await get_worker(shop_id, worker_id, owner_id, db)
    plain_pin = data.new_pin or generate_pin(6)
    worker.pin_hash = hash_pin(plain_pin)
    await db.commit()
    return plain_pin


async def disable_worker(
    shop_id: UUID, worker_id: UUID, owner_id: UUID, db: AsyncSession
) -> Worker:
    worker = await get_worker(shop_id, worker_id, owner_id, db)
    worker.is_active = False
    await db.commit()
    await db.refresh(worker)
    return worker
