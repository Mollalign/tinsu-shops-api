from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytz
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import ActorType, PaymentMethod
from app.config import settings
from app.inventory.models import InventoryMovement
from app.products.models import Product
from app.reports.schemas import (
    OwnerDashboardResponse,
    PaymentBreakdown,
    ShopDailySummary,
    TodayReportResponse,
    WorkerTodayResponse,
)
from app.sales.models import Sale, SaleItem
from app.shops.models import Shop
from app.shops.service import get_shop_for_owner


def _today_utc_range() -> tuple[datetime, datetime]:
    """Return UTC start/end for 'today' in Ethiopian local time."""
    tz = pytz.timezone(settings.BUSINESS_TIMEZONE)
    local_now = datetime.now(tz)
    local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    local_end = local_start + timedelta(days=1)
    return local_start.astimezone(UTC), local_end.astimezone(UTC)


async def get_today_report(
    shop_id: UUID, owner_id: UUID, db: AsyncSession
) -> TodayReportResponse:
    await get_shop_for_owner(shop_id, owner_id, db)

    start, end = _today_utc_range()

    # Aggregate sales
    sales_result = await db.execute(
        select(
            func.sum(Sale.total_amount).label("total_sales"),
            func.count(Sale.id).label("num_sales"),
        ).where(
            Sale.shop_id == shop_id,
            Sale.created_at >= start,
            Sale.created_at < end,
        )
    )
    row = sales_result.one()
    total_sales = row.total_sales or Decimal("0")
    num_sales = row.num_sales or 0

    # Items sold
    items_result = await db.execute(
        select(func.sum(SaleItem.quantity)).select_from(SaleItem).join(Sale).where(
            Sale.shop_id == shop_id,
            Sale.created_at >= start,
            Sale.created_at < end,
        )
    )
    items_sold = items_result.scalar_one() or 0

    # Payment breakdown
    breakdown = await _payment_breakdown(shop_id, start, end, db)

    # Low stock count
    low_stock_result = await db.execute(
        select(func.count()).select_from(Product).where(
            Product.shop_id == shop_id,
            Product.is_active == True,
            Product.stock_quantity <= Product.low_stock_threshold,
        )
    )
    low_stock_count = low_stock_result.scalar_one()

    return TodayReportResponse(
        date=date.today(),
        total_sales=total_sales,
        number_of_sales=num_sales,
        items_sold=items_sold,
        payment_breakdown=breakdown,
        low_stock_count=low_stock_count,
    )


async def get_worker_today(
    shop_id: UUID, worker_id: UUID, db: AsyncSession
) -> WorkerTodayResponse:
    start, end = _today_utc_range()

    sales_result = await db.execute(
        select(
            func.sum(Sale.total_amount).label("total_sales"),
            func.count(Sale.id).label("num_sales"),
        ).where(
            Sale.shop_id == shop_id,
            Sale.sold_by_type == ActorType.WORKER,
            Sale.sold_by_id == worker_id,
            Sale.created_at >= start,
            Sale.created_at < end,
        )
    )
    row = sales_result.one()

    items_result = await db.execute(
        select(func.sum(SaleItem.quantity)).select_from(SaleItem).join(Sale).where(
            Sale.shop_id == shop_id,
            Sale.sold_by_type == ActorType.WORKER,
            Sale.sold_by_id == worker_id,
            Sale.created_at >= start,
            Sale.created_at < end,
        )
    )

    breakdown = await _payment_breakdown(shop_id, start, end, db, worker_id=worker_id)

    return WorkerTodayResponse(
        total_sales=row.total_sales or Decimal("0"),
        number_of_sales=row.num_sales or 0,
        items_sold=items_result.scalar_one() or 0,
        payment_breakdown=breakdown,
    )


async def get_owner_dashboard(owner_id: UUID, db: AsyncSession) -> OwnerDashboardResponse:
    start, end = _today_utc_range()

    shops_result = await db.execute(
        select(Shop).where(Shop.owner_id == owner_id, Shop.is_active == True)
    )
    shops = shops_result.scalars().all()

    shop_summaries = []
    total_today = Decimal("0")

    for shop in shops:
        result = await db.execute(
            select(
                func.sum(Sale.total_amount).label("today_sales"),
                func.count(Sale.id).label("num_sales"),
            ).where(
                Sale.shop_id == shop.id,
                Sale.created_at >= start,
                Sale.created_at < end,
            )
        )
        row = result.one()
        shop_total = row.today_sales or Decimal("0")
        total_today += shop_total
        shop_summaries.append(
            ShopDailySummary(
                shop_id=shop.id,
                shop_name=shop.name,
                today_sales=shop_total,
                number_of_sales=row.num_sales or 0,
            )
        )

    return OwnerDashboardResponse(shops=shop_summaries, total_today_sales=total_today)


async def _payment_breakdown(
    shop_id: UUID,
    start: datetime,
    end: datetime,
    db: AsyncSession,
    worker_id: UUID | None = None,
) -> PaymentBreakdown:
    query = select(Sale.payment_method, func.sum(Sale.total_amount)).where(
        Sale.shop_id == shop_id,
        Sale.created_at >= start,
        Sale.created_at < end,
    )
    if worker_id:
        query = query.where(
            Sale.sold_by_type == ActorType.WORKER, Sale.sold_by_id == worker_id
        )
    query = query.group_by(Sale.payment_method)

    result = await db.execute(query)
    rows = result.all()

    breakdown = PaymentBreakdown()
    for method, total in rows:
        if method == PaymentMethod.CASH:
            breakdown.cash = total or Decimal("0")
        elif method == PaymentMethod.TELEBIRR:
            breakdown.telebirr = total or Decimal("0")
        elif method == PaymentMethod.CBE_BIRR:
            breakdown.cbe_birr = total or Decimal("0")
        elif method == PaymentMethod.OTHER:
            breakdown.other = total or Decimal("0")
    return breakdown
