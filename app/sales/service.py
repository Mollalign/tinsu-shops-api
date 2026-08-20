from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.enums import ActorType, InventoryMovementType, PaymentMethod
from app.common.exceptions import (
    EmptySaleError,
    InactiveProductError,
    InsufficientStockError,
    ProductNotFoundError,
    SaleNotFoundError,
    UnauthorizedShopAccessError,
)
from app.common.pagination import Page, PaginationParams
from app.inventory.models import InventoryMovement
from app.owners.models import Owner
from app.products.models import Product
from app.sales.models import Sale, SaleItem
from app.sales.schemas import SaleItemResponse, SaleRequest, SaleResponse, SoldByResponse
from app.shops.service import get_shop_for_owner
from app.workers.models import Worker


async def create_sale(
    shop_id: UUID,
    data: SaleRequest,
    actor_type: ActorType,
    actor_id: UUID,
    db: AsyncSession,
) -> SaleResponse:
    if not data.items:
        raise EmptySaleError()

    # Load all requested products with row-level locks for concurrency safety
    product_ids = [item.product_id for item in data.items]

    locked_result = await db.execute(
        select(Product)
        .where(Product.id.in_(product_ids), Product.shop_id == shop_id)
        .with_for_update()
    )
    products_map: dict[UUID, Product] = {p.id: p for p in locked_result.scalars().all()}

    # Validate all products
    for item in data.items:
        product = products_map.get(item.product_id)
        if not product:
            raise ProductNotFoundError()
        if not product.is_active:
            raise InactiveProductError(product.name)
        if product.stock_quantity < item.quantity:
            raise InsufficientStockError(product.name, product.stock_quantity)

    # Calculate totals server-side
    total_amount = Decimal("0")
    sale_items_data = []
    for item in data.items:
        product = products_map[item.product_id]
        unit_price = product.selling_price
        subtotal = unit_price * item.quantity
        total_amount += subtotal
        sale_items_data.append((product, item.quantity, unit_price, subtotal))

    # Create sale
    sale = Sale(
        shop_id=shop_id,
        sold_by_type=actor_type,
        sold_by_id=actor_id,
        payment_method=data.payment_method,
        total_amount=total_amount,
    )
    db.add(sale)
    await db.flush()

    # Create sale items, decrement stock, create inventory movements
    response_items = []
    for product, qty, unit_price, subtotal in sale_items_data:
        sale_item = SaleItem(
            sale_id=sale.id,
            product_id=product.id,
            quantity=qty,
            unit_price=unit_price,
            subtotal=subtotal,
        )
        db.add(sale_item)

        product.stock_quantity -= qty

        movement = InventoryMovement(
            shop_id=shop_id,
            product_id=product.id,
            type=InventoryMovementType.SALE,
            quantity=-qty,
            reason=f"Sale #{sale.id}",
            created_by_type=actor_type,
            created_by_id=actor_id,
        )
        db.add(movement)

        response_items.append(
            SaleItemResponse(
                product_id=product.id,
                product_name=product.name,
                quantity=qty,
                unit_price=unit_price,
                subtotal=subtotal,
            )
        )

    await db.commit()
    await db.refresh(sale)

    # Resolve actor name
    actor_name = await _resolve_actor_name(actor_type, actor_id, db)

    return SaleResponse(
        id=sale.id,
        shop_id=sale.shop_id,
        payment_method=sale.payment_method,
        total_amount=sale.total_amount,
        items=response_items,
        sold_by=SoldByResponse(
            type=actor_type,
            id=actor_id,
            name=actor_name,
        ),
        created_at=sale.created_at,
    )


async def _resolve_actor_name(
    actor_type: ActorType, actor_id: UUID, db: AsyncSession
) -> str:
    if actor_type == ActorType.OWNER:
        result = await db.execute(select(Owner.name).where(Owner.id == actor_id))
    else:
        result = await db.execute(select(Worker.name).where(Worker.id == actor_id))
    name = result.scalar_one_or_none()
    return name or "Unknown"


async def list_sales(
    shop_id: UUID,
    db: AsyncSession,
    params: PaginationParams,
    date_from: date | None = None,
    date_to: date | None = None,
    payment_method: PaymentMethod | None = None,
    worker_id: UUID | None = None,
) -> Page[Sale]:
    query = select(Sale).where(Sale.shop_id == shop_id)

    if date_from:
        query = query.where(Sale.created_at >= datetime(date_from.year, date_from.month, date_from.day, tzinfo=UTC))
    if date_to:
        end = datetime(date_to.year, date_to.month, date_to.day, tzinfo=UTC) + timedelta(days=1)
        query = query.where(Sale.created_at < end)
    if payment_method:
        query = query.where(Sale.payment_method == payment_method)
    if worker_id:
        query = query.where(
            Sale.sold_by_type == ActorType.WORKER,
            Sale.sold_by_id == worker_id,
        )

    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar_one()

    result = await db.execute(
        query.order_by(Sale.created_at.desc()).offset(params.offset).limit(params.limit)
    )
    return Page.create(list(result.scalars().all()), total, params)


async def get_sale_detail(shop_id: UUID, sale_id: UUID, db: AsyncSession) -> SaleResponse:
    result = await db.execute(
        select(Sale)
        .where(Sale.id == sale_id, Sale.shop_id == shop_id)
        .options(selectinload(Sale.items).selectinload(SaleItem.product))
    )
    sale = result.scalar_one_or_none()
    if not sale:
        raise SaleNotFoundError()

    actor_name = await _resolve_actor_name(sale.sold_by_type, sale.sold_by_id, db)

    return SaleResponse(
        id=sale.id,
        shop_id=sale.shop_id,
        payment_method=sale.payment_method,
        total_amount=sale.total_amount,
        items=[
            SaleItemResponse(
                product_id=item.product_id,
                product_name=item.product.name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                subtotal=item.subtotal,
            )
            for item in sale.items
        ],
        sold_by=SoldByResponse(
            type=sale.sold_by_type,
            id=sale.sold_by_id,
            name=actor_name,
        ),
        created_at=sale.created_at,
    )
