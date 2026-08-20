from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import (
    InactiveAccountError,
    InvalidCredentialsError,
    ShopNotFoundError,
    WorkerNotFoundError,
)
from app.common.security import create_access_token, verify_pin
from app.owners.models import Owner
from app.shops.models import Shop
from app.workers.models import Worker
from app.auth.schemas import TokenResponse, TokenUserInfo
from app.common.enums import UserRole


async def owner_login(phone: str, pin: str, db: AsyncSession) -> TokenResponse:
    result = await db.execute(select(Owner).where(Owner.phone == phone))
    owner = result.scalar_one_or_none()

    if not owner or not verify_pin(pin, owner.pin_hash):
        raise InvalidCredentialsError("Invalid phone or PIN.")

    if not owner.is_active:
        raise InactiveAccountError()

    token = create_access_token({
        "sub": str(owner.id),
        "role": UserRole.OWNER.value,
        "name": owner.name,
        "is_active": owner.is_active,
    })

    return TokenResponse(
        access_token=token,
        user=TokenUserInfo(
            id=owner.id,
            role=UserRole.OWNER,
            name=owner.name,
        ),
    )


async def worker_login(
    shop_id: str, worker_id: str, pin: str, db: AsyncSession
) -> TokenResponse:
    # Verify shop exists
    shop_result = await db.execute(select(Shop).where(Shop.id == shop_id, Shop.is_active == True))
    shop = shop_result.scalar_one_or_none()
    if not shop:
        raise ShopNotFoundError()

    # Verify worker belongs to this shop
    worker_result = await db.execute(
        select(Worker).where(Worker.id == worker_id, Worker.shop_id == shop_id)
    )
    worker = worker_result.scalar_one_or_none()
    if not worker:
        raise WorkerNotFoundError()

    if not verify_pin(pin, worker.pin_hash):
        raise InvalidCredentialsError("Invalid PIN.")

    if not worker.is_active:
        raise InactiveAccountError()

    token = create_access_token({
        "sub": str(worker.id),
        "role": UserRole.WORKER.value,
        "name": worker.name,
        "shop_id": str(shop_id),
        "is_active": worker.is_active,
    })

    return TokenResponse(
        access_token=token,
        user=TokenUserInfo(
            id=worker.id,
            role=UserRole.WORKER,
            name=worker.name,
            shop_id=shop.id,
        ),
    )
