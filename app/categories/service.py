"""Category service — CRUD with shop isolation."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.categories.models import Category
from app.categories.schemas import CategoryCreate, CategoryUpdate
from app.common.exceptions import CategoryNotFoundError, DuplicateCategoryNameError
from app.shops.service import get_shop_for_owner


async def list_categories(shop_id: UUID, db: AsyncSession) -> list[Category]:
    result = await db.execute(
        select(Category)
        .where(Category.shop_id == shop_id)
        .order_by(Category.name.asc())
    )
    return list(result.scalars().all())


async def get_category_for_shop(
    shop_id: UUID, category_id: UUID, db: AsyncSession
) -> Category:
    result = await db.execute(
        select(Category).where(
            Category.id == category_id, Category.shop_id == shop_id
        )
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise CategoryNotFoundError()
    return cat


async def create_category(
    shop_id: UUID,
    owner_id: UUID,
    data: CategoryCreate,
    db: AsyncSession,
) -> Category:
    await get_shop_for_owner(shop_id, owner_id, db)
    category = Category(shop_id=shop_id, name=data.name)
    db.add(category)
    try:
        await db.commit()
        await db.refresh(category)
    except IntegrityError:
        await db.rollback()
        raise DuplicateCategoryNameError(data.name)
    return category


async def update_category(
    shop_id: UUID,
    category_id: UUID,
    owner_id: UUID,
    data: CategoryUpdate,
    db: AsyncSession,
) -> Category:
    await get_shop_for_owner(shop_id, owner_id, db)
    category = await get_category_for_shop(shop_id, category_id, db)
    category.name = data.name
    try:
        await db.commit()
        await db.refresh(category)
    except IntegrityError:
        await db.rollback()
        raise DuplicateCategoryNameError(data.name)
    return category


async def delete_category(
    shop_id: UUID,
    category_id: UUID,
    owner_id: UUID,
    db: AsyncSession,
) -> None:
    await get_shop_for_owner(shop_id, owner_id, db)
    category = await get_category_for_shop(shop_id, category_id, db)
    await db.delete(category)
    await db.commit()
