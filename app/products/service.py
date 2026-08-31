from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.categories.models import Category
from app.common.enums import ActorType, InventoryMovementType
from app.common.exceptions import CategoryNotFoundError, ProductNotFoundError
from app.common.pagination import Page, PaginationParams
from app.inventory.models import InventoryMovement
from app.products.models import Product
from app.products.schemas import ProductCreate, ProductUpdate
from app.shops.service import get_shop_for_owner


def _product_query():
    """Base select with category eagerly joined."""
    return select(Product).options(joinedload(Product.category_obj))


async def _get_product(shop_id: UUID, product_id: UUID, db: AsyncSession) -> Product:
    result = await db.execute(
        _product_query()
        .where(Product.id == product_id, Product.shop_id == shop_id)
        .execution_options(populate_existing=True)
    )
    product = result.unique().scalar_one_or_none()
    if not product:
        raise ProductNotFoundError()
    return product


async def _validate_category(shop_id: UUID, category_id: UUID, db: AsyncSession) -> None:
    """Reject cross-shop category assignments."""
    result = await db.execute(
        select(Category).where(
            Category.id == category_id, Category.shop_id == shop_id
        )
    )
    if result.scalar_one_or_none() is None:
        raise CategoryNotFoundError()


async def list_products(
    shop_id: UUID,
    db: AsyncSession,
    params: PaginationParams,
    active_only: bool = True,
    category_id: UUID | None = None,
) -> Page[Product]:
    base_q = _product_query().where(Product.shop_id == shop_id)
    if active_only:
        base_q = base_q.where(Product.is_active == True)  # noqa: E712
    if category_id is not None:
        base_q = base_q.where(Product.category_id == category_id)

    count_result = await db.execute(
        select(func.count()).select_from(base_q.subquery())
    )
    total = count_result.scalar_one()

    result = await db.execute(
        base_q.order_by(Product.name.asc()).offset(params.offset).limit(params.limit)
    )
    return Page.create(list(result.unique().scalars().all()), total, params)


async def create_product(
    shop_id: UUID,
    owner_id: UUID,
    data: ProductCreate,
    actor_type: ActorType,
    actor_id: UUID,
    db: AsyncSession,
) -> Product:
    await get_shop_for_owner(shop_id, owner_id, db)

    if data.category_id is not None:
        await _validate_category(shop_id, data.category_id, db)

    async with db.begin_nested():
        product = Product(
            shop_id=shop_id,
            name=data.name,
            selling_price=data.selling_price,
            stock_quantity=data.initial_stock,
            low_stock_threshold=data.low_stock_threshold,
            category_id=data.category_id,
            photo_url=data.photo_url,
        )
        db.add(product)
        await db.flush()

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
    return await _get_product(shop_id, product.id, db)


async def get_product_for_shop(
    shop_id: UUID, product_id: UUID, db: AsyncSession
) -> Product:
    return await _get_product(shop_id, product_id, db)


async def update_product(
    shop_id: UUID,
    product_id: UUID,
    owner_id: UUID,
    data: ProductUpdate,
    db: AsyncSession,
) -> Product:
    await get_shop_for_owner(shop_id, owner_id, db)
    product = await _get_product(shop_id, product_id, db)

    update_data = data.model_dump(exclude_unset=True)

    # Validate new category belongs to same shop (but allow explicit null to clear)
    if "category_id" in update_data and update_data["category_id"] is not None:
        await _validate_category(shop_id, update_data["category_id"], db)

    for field, value in update_data.items():
        setattr(product, field, value)

    await db.commit()
    return await _get_product(shop_id, product.id, db)


async def deactivate_product(
    shop_id: UUID, product_id: UUID, owner_id: UUID, db: AsyncSession
) -> Product:
    await get_shop_for_owner(shop_id, owner_id, db)
    product = await _get_product(shop_id, product_id, db)
    product.is_active = False
    await db.commit()
    return await _get_product(shop_id, product.id, db)


async def search_products(
    shop_id: UUID,
    query: str,
    db: AsyncSession,
    limit: int = 20,
    category_id: UUID | None = None,
) -> list[Product]:
    base_q = (
        _product_query()
        .where(
            Product.shop_id == shop_id,
            Product.is_active == True,  # noqa: E712
            Product.name.ilike(f"%{query}%"),
        )
    )
    if category_id is not None:
        base_q = base_q.where(Product.category_id == category_id)

    result = await db.execute(base_q.order_by(Product.name.asc()).limit(limit))
    return list(result.unique().scalars().all())


async def get_low_stock_products(shop_id: UUID, db: AsyncSession) -> list[Product]:
    result = await db.execute(
        _product_query()
        .where(
            Product.shop_id == shop_id,
            Product.is_active == True,  # noqa: E712
            Product.stock_quantity <= Product.low_stock_threshold,
        )
        .order_by(Product.stock_quantity.asc())
    )
    return list(result.unique().scalars().all())
