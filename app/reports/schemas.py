from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class TodayReportResponse(BaseModel):
    date: date
    total_sales: Decimal
    number_of_sales: int
    items_sold: int
    low_stock_count: int


class WorkerTodayResponse(BaseModel):
    total_sales: Decimal
    number_of_sales: int
    items_sold: int


class ShopDailySummary(BaseModel):
    shop_id: UUID
    shop_name: str
    today_sales: Decimal
    number_of_sales: int


class OwnerDashboardResponse(BaseModel):
    shops: list[ShopDailySummary]
    total_today_sales: Decimal
