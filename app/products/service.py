from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import ActorType, InventoryMovementType
from app.common.exceptions import ProductNotFoundError, UnauthorizedShopAccessError
from app.common.pagination import Page, PaginationParams
from app.inventory.models import InventoryMovement
from app.products.models import Product
from app.products.schemas import ProductCreate, ProductUpdate
from app.shops.service import get_shop_for_owner


async def list_products(
    shop_id: UUID,
    db: AsyncSession,
    params: PaginationParams,
    active_only: bool = True,
) -> Page[Product]:
    base_q = select(Product).where(Product.shop_id == shop_id)
    if active_only:
        base_q = base_q.where(Product.is_active == True)

    count_result = await db.execute(
        select(func.count()).select_from(base_q.subquery())
    )
    total = count_result.scalar_one()

    result = await db.execute(
        base_q.order_by(Product.name.asc()).offset(params.offset).limit(params.limit)
    )
    return Page.create(list(result.scalars().all()), total, params)


async def create_product(
    shop_id: UUID,
    owner_id: UUID,
    data: ProductCreate,
    actor_type: ActorType,
    actor_id: UUID,
    db: AsyncSession,
) -> Product:
    await get_shop_for_owner(shop_id, owner_id, db)

    async with db.begin_nested():
        product = Product(
            shop_id=shop_id,
            name=data.name,
            selling_price=data.selling_price,
            stock_quantity=data.initial_stock,
            low_stock_threshold=data.low_stock_threshold,
            category=data.category,
            photo_url=data.photo_url,
        )
        db.add(product)
        await db.flush()  # Get product.id

        if data.initial_stock > 0:
            movement = InventoryMovement(
                shop_id=shop_id,
                product_id=product.id,
                type=InventoryMovementType.INITIAL,
                quantity=data.initial_stock,
                reason="Initial stock",
                created_by_type=actor_type,
                created_by_id=actor_id,
            )
            db.add(movement)

    await db.commit()
    await db.refresh(product)
    return product


async def get_product_for_shop(
    shop_id: UUID, product_id: UUID, db: AsyncSession
) -> Product:
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.shop_id == shop_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise ProductNotFoundError()
    return product


async def update_product(
    shop_id: UUID,
    product_id: UUID,
    owner_id: UUID,
    data: ProductUpdate,
    db: AsyncSession,
) -> Product:
    await get_shop_for_owner(shop_id, owner_id, db)
    product = await get_product_for_shop(shop_id, product_id, db)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)
    await db.commit()
    await db.refresh(product)
    return product


async def deactivate_product(
    shop_id: UUID, product_id: UUID, owner_id: UUID, db: AsyncSession
) -> Product:
    await get_shop_for_owner(shop_id, owner_id, db)
    product = await get_product_for_shop(shop_id, product_id, db)
    product.is_active = False
    await db.commit()
    await db.refresh(product)
    return product


async def search_products(
    shop_id: UUID, query: str, db: AsyncSession, limit: int = 20
) -> list[Product]:
    result = await db.execute(
        select(Product)
        .where(
            Product.shop_id == shop_id,
            Product.is_active == True,
            or_(
                Product.name.ilike(f"%{query}%"),
                Product.category.ilike(f"%{query}%"),
            ),
        )
        .order_by(Product.name.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_low_stock_products(shop_id: UUID, db: AsyncSession) -> list[Product]:
    result = await db.execute(
        select(Product)
        .where(
            Product.shop_id == shop_id,
            Product.is_active == True,
            Product.stock_quantity <= Product.low_stock_threshold,
        )
        .order_by(Product.stock_quantity.asc())
    )
    return list(result.scalars().all())
