from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import ShopNotFoundError, UnauthorizedShopAccessError
from app.shops.models import Shop
from app.shops.schemas import ShopCreate, ShopUpdate


async def get_owner_shops(owner_id: UUID, db: AsyncSession) -> list[Shop]:
    result = await db.execute(
        select(Shop).where(Shop.owner_id == owner_id).order_by(Shop.created_at.asc())
    )
    return list(result.scalars().all())


async def create_shop(owner_id: UUID, data: ShopCreate, db: AsyncSession) -> Shop:
    shop = Shop(
        owner_id=owner_id,
        name=data.name,
        location=data.location,
        phone=data.phone,
    )
    db.add(shop)
    await db.commit()
    await db.refresh(shop)
    return shop


async def get_shop_for_owner(shop_id: UUID, owner_id: UUID, db: AsyncSession) -> Shop:
    """Fetch a shop and verify it belongs to the owner."""
    result = await db.execute(select(Shop).where(Shop.id == shop_id))
    shop = result.scalar_one_or_none()
    if not shop:
        raise ShopNotFoundError()
    if shop.owner_id != owner_id:
        raise UnauthorizedShopAccessError()
    return shop


async def update_shop(
    shop_id: UUID, owner_id: UUID, data: ShopUpdate, db: AsyncSession
) -> Shop:
    shop = await get_shop_for_owner(shop_id, owner_id, db)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(shop, field, value)
    await db.commit()
    await db.refresh(shop)
    return shop
