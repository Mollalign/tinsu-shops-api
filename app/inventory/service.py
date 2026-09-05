from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

from app.common.enums import ActorType, InventoryMovementType
from app.common.exceptions import NegativeStockError, ProductNotFoundError
from app.common.pagination import Page, PaginationParams
from app.inventory.models import InventoryMovement
from app.inventory.schemas import AdjustmentRequest, InventoryMovementResponse, InventoryStatusResponse, RestockRequest
from app.products.models import Product
from app.shops.service import get_shop_for_owner


async def get_inventory_overview(
    shop_id: UUID,
    owner_id: UUID,
    db: AsyncSession,
    params: PaginationParams,
) -> Page[InventoryStatusResponse]:
    await get_shop_for_owner(shop_id, owner_id, db)

    count_result = await db.execute(
        select(func.count()).select_from(Product).where(
            Product.shop_id == shop_id, Product.is_active == True
        )
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(Product)
        .where(Product.shop_id == shop_id, Product.is_active == True)
        .order_by(Product.name.asc())
        .offset(params.offset)
        .limit(params.limit)
    )
    products = result.scalars().all()

    items = [
        InventoryStatusResponse(
            product_id=p.id,
            product_name=p.name,
            category=p.category,
            stock_quantity=p.stock_quantity,
            low_stock_threshold=p.low_stock_threshold,
            is_low_stock=p.stock_quantity <= p.low_stock_threshold,
            selling_price=float(p.selling_price),
        )
        for p in products
    ]
    return Page.create(items, total, params)


async def restock_product(
    shop_id: UUID,
    product_id: UUID,
    owner_id: UUID,
    data: RestockRequest,
    actor_type: ActorType,
    actor_id: UUID,
    db: AsyncSession,
) -> InventoryMovement:
    await get_shop_for_owner(shop_id, owner_id, db)

    result = await db.execute(
        select(Product)
        .where(Product.id == product_id, Product.shop_id == shop_id)
        .options(noload(Product.category_obj))
        .with_for_update()
    )
    product = result.scalar_one_or_none()
    if not product:
        raise ProductNotFoundError()

    product.stock_quantity += data.quantity

    movement = InventoryMovement(
        shop_id=shop_id,
        product_id=product_id,
        type=InventoryMovementType.RESTOCK,
        quantity=data.quantity,
        reason=data.reason,
        created_by_type=actor_type,
        created_by_id=actor_id,
    )
    db.add(movement)
    await db.commit()
    await db.refresh(movement)
    return movement


async def adjust_product_stock(
    shop_id: UUID,
    product_id: UUID,
    owner_id: UUID,
    data: AdjustmentRequest,
    actor_type: ActorType,
    actor_id: UUID,
    db: AsyncSession,
) -> InventoryMovement:
    await get_shop_for_owner(shop_id, owner_id, db)

    result = await db.execute(
        select(Product)
        .where(Product.id == product_id, Product.shop_id == shop_id)
        .options(noload(Product.category_obj))
        .with_for_update()
    )
    product = result.scalar_one_or_none()
    if not product:
        raise ProductNotFoundError()

    new_quantity = product.stock_quantity + data.quantity
    if new_quantity < 0:
        raise NegativeStockError(product.name)

    product.stock_quantity = new_quantity

    movement = InventoryMovement(
        shop_id=shop_id,
        product_id=product_id,
        type=InventoryMovementType.ADJUSTMENT,
        quantity=data.quantity,
        reason=data.reason,
        created_by_type=actor_type,
        created_by_id=actor_id,
    )
    db.add(movement)
    await db.commit()
    await db.refresh(movement)
    return movement


async def list_product_movements(
    shop_id: UUID,
    product_id: UUID,
    db: AsyncSession,
    params: PaginationParams,
) -> Page[InventoryMovementResponse]:
    count_result = await db.execute(
        select(func.count()).select_from(InventoryMovement).where(
            InventoryMovement.shop_id == shop_id,
            InventoryMovement.product_id == product_id,
        )
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(InventoryMovement)
        .where(
            InventoryMovement.shop_id == shop_id,
            InventoryMovement.product_id == product_id,
        )
        .order_by(InventoryMovement.created_at.desc())
        .offset(params.offset)
        .limit(params.limit)
    )
    movements = [InventoryMovementResponse.model_validate(m) for m in result.scalars().all()]
    return Page.create(movements, total, params)
