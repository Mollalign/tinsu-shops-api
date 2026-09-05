from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.enums import ActorType, InventoryMovementType
from app.common.exceptions import (
    EmptySaleError,
    InactiveProductError,
    InsufficientStockError,
    ProductNotFoundError,
    SaleNotFoundError,
)
from app.common.pagination import Page, PaginationParams
from app.inventory.models import InventoryMovement
from app.owners.models import Owner
from app.products.models import Product
from app.sales.models import Sale, SaleItem
from app.sales.schemas import SaleItemResponse, SaleRequest, SaleResponse, SoldByResponse
from app.workers.models import Worker


async def create_sale(
    shop_id: UUID,
    data: SaleRequest,
    actor_type: ActorType,
    actor_id: UUID,
    db: AsyncSession,
    idempotency_key: str | None = None,
) -> SaleResponse:
    """
    Atomic sale creation.

    Steps:
    1. Check idempotency — return existing sale if key already used.
    2. Lock product rows (prevents oversell under concurrency).
    3. Validate every product (active, in-shop, sufficient stock).
    4. Calculate all prices and totals server-side.
    5. Create Sale + SaleItems + deduct stock + InventoryMovements in one transaction.
    """
    if not data.items:
        raise EmptySaleError()

    # ── Idempotency check ──────────────────────────────────────────────────
    if idempotency_key:
        existing = await _find_by_idempotency_key(idempotency_key, shop_id, db)
        if existing:
            return existing

    # ── Lock product rows for concurrency safety ───────────────────────────
    # Lock ONLY the products table — PostgreSQL forbids FOR UPDATE when a
    # LEFT OUTER JOIN is present (nullable side). We lock just the IDs first,
    # then fetch the full objects in a separate query.
    product_ids = [item.product_id for item in data.items]

    await db.execute(
        select(Product.id)
        .where(Product.id.in_(product_ids), Product.shop_id == shop_id)
        .with_for_update()
    )

    # Now fetch the full product rows (no lock needed — rows are already held).
    fetched = await db.execute(
        select(Product)
        .where(Product.id.in_(product_ids), Product.shop_id == shop_id)
    )
    products_map: dict[UUID, Product] = {p.id: p for p in fetched.scalars().all()}

    # ── Validate all products ──────────────────────────────────────────────
    for item in data.items:
        product = products_map.get(item.product_id)
        if not product:
            raise ProductNotFoundError()
        if not product.is_active:
            raise InactiveProductError(product.name)
        if product.stock_quantity < item.quantity:
            raise InsufficientStockError(product.name, product.stock_quantity)

    # ── Server-side price calculation ──────────────────────────────────────
    total_amount = Decimal("0")
    sale_items_data = []
    for item in data.items:
        product = products_map[item.product_id]
        unit_price = product.selling_price  # always reads current DB price
        subtotal = unit_price * item.quantity
        total_amount += subtotal
        sale_items_data.append((product, item.quantity, unit_price, subtotal))

    # ── Create sale ────────────────────────────────────────────────────────
    sale = Sale(
        shop_id=shop_id,
        sold_by_type=actor_type,
        sold_by_id=actor_id,
        total_amount=total_amount,
        idempotency_key=idempotency_key,
        # Set in Python so SQLite (second-precision CURRENT_TIMESTAMP) still
        # distinguishes sales that complete in the same second.
        created_at=datetime.now(UTC),
    )
    db.add(sale)
    await db.flush()

    # ── Create items + deduct stock + record movements ────────────────────
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

    try:
        await db.commit()
    except IntegrityError:
        # Race condition on idempotency_key unique constraint — return existing sale
        await db.rollback()
        if idempotency_key:
            existing = await _find_by_idempotency_key(idempotency_key, shop_id, db)
            if existing:
                return existing
        raise

    await db.refresh(sale)

    actor_name = await _resolve_actor_name(actor_type, actor_id, db)

    return SaleResponse(
        id=sale.id,
        shop_id=sale.shop_id,
        total_amount=sale.total_amount,
        items=response_items,
        sold_by=SoldByResponse(
            type=actor_type,
            id=actor_id,
            name=actor_name,
        ),
        created_at=sale.created_at,
    )


async def _find_by_idempotency_key(
    key: str, shop_id: UUID, db: AsyncSession
) -> SaleResponse | None:
    """Return a completed sale if this idempotency key was already used."""
    result = await db.execute(
        select(Sale)
        .where(Sale.idempotency_key == key, Sale.shop_id == shop_id)
        .options(selectinload(Sale.items).selectinload(SaleItem.product))
    )
    sale = result.scalar_one_or_none()
    if not sale:
        return None

    actor_name = await _resolve_actor_name(sale.sold_by_type, sale.sold_by_id, db)
    return SaleResponse(
        id=sale.id,
        shop_id=sale.shop_id,
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
    worker_id: UUID | None = None,
) -> Page:
    """
    Return lightweight sale list rows with items_count and sold_by_name.
    No payment filter — payment method is no longer part of the workflow.
    """
    query = (
        select(
            Sale,
            func.count(SaleItem.id).label("items_count"),
        )
        .outerjoin(SaleItem, SaleItem.sale_id == Sale.id)
        .where(Sale.shop_id == shop_id)
        .group_by(Sale.id)
    )

    if date_from:
        query = query.where(
            Sale.created_at >= datetime(date_from.year, date_from.month, date_from.day, tzinfo=UTC)
        )
    if date_to:
        end = datetime(date_to.year, date_to.month, date_to.day, tzinfo=UTC) + timedelta(days=1)
        query = query.where(Sale.created_at < end)
    if worker_id:
        query = query.where(
            Sale.sold_by_type == ActorType.WORKER,
            Sale.sold_by_id == worker_id,
        )

    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar_one()

    rows = await db.execute(
        query.order_by(Sale.created_at.desc()).offset(params.offset).limit(params.limit)
    )

    # Build list items with sold_by_name resolved
    from app.sales.schemas import SaleListResponse
    items = []
    for sale, items_count in rows.all():
        actor_name = await _resolve_actor_name(sale.sold_by_type, sale.sold_by_id, db)
        items.append(
            SaleListResponse(
                id=sale.id,
                shop_id=sale.shop_id,
                total_amount=sale.total_amount,
                items_count=items_count,
                sold_by_name=actor_name,
                created_at=sale.created_at,
            )
        )

    return Page.create(items, total, params)


async def get_recent_products(
    shop_id: UUID,
    worker_id: UUID,
    limit: int,
    db: AsyncSession,
) -> list[Product]:
    """
    Return up to ``limit`` unique active products most recently sold by
    ``worker_id`` in ``shop_id``, ordered by most-recently-sold first.

    Query strategy:
    1. Subquery – for each product the worker sold in this shop, compute
       MAX(sale.created_at) so duplicates collapse to a single row.
    2. Outer query – join Products on that subquery, filter active only,
       sort DESC on the max timestamp, apply the limit.

    No full sale-history download: a single efficient GROUP BY query.
    """
    subq = (
        select(
            SaleItem.product_id,
            func.max(Sale.created_at).label("last_sold_at"),
        )
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(
            Sale.shop_id == shop_id,
            Sale.sold_by_type == ActorType.WORKER,
            Sale.sold_by_id == worker_id,
        )
        .group_by(SaleItem.product_id)
        .subquery()
    )

    result = await db.execute(
        select(Product)
        .join(subq, Product.id == subq.c.product_id)
        .where(Product.is_active.is_(True))
        .order_by(subq.c.last_sold_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


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
