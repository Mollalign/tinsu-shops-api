from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import AuthenticatedUser, get_current_user, require_owner
from app.reports import service as reports_service
from app.reports.schemas import OwnerDashboardResponse, TodayReportResponse, WorkerTodayResponse
from app.sales import service as sales_service
from app.sales.schemas import RecentProductsResponse, RecentProductItem

router = APIRouter(tags=["Reports"])


@router.get(
    "/shops/{shop_id}/reports/today",
    response_model=TodayReportResponse,
    summary="Today's Shop Report",
    description=(
        "Aggregated daily report for the mobile dashboard: total sales, item count, "
        "payment breakdown, and low-stock count — all in one request. "
        "Times calculated in Africa/Addis_Ababa timezone."
    ),
)
async def today_report(
    shop_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TodayReportResponse:
    return await reports_service.get_today_report(shop_id, current_user.id, db)


@router.get(
    "/shops/{shop_id}/workers/me/today",
    response_model=WorkerTodayResponse,
    summary="Worker Today's Performance",
    description="The authenticated worker's own sales summary for today.",
)
async def worker_today(
    shop_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkerTodayResponse:
    from app.common.exceptions import UnauthorizedShopAccessError
    from app.common.enums import UserRole

    if current_user.role == UserRole.WORKER and current_user.shop_id != shop_id:
        raise UnauthorizedShopAccessError()

    return await reports_service.get_worker_today(shop_id, current_user.id, db)


@router.get(
    "/shops/{shop_id}/workers/me/recent-products",
    response_model=RecentProductsResponse,
    summary="Worker Recent Products",
    description=(
        "Return the products most recently sold by the authenticated worker "
        "inside the given shop, ordered by most-recently-sold first. "
        "Duplicate products are collapsed — each product appears at most once. "
        "Inactive products are excluded. Workers can only query their own shop."
    ),
)
async def worker_recent_products(
    shop_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(8, ge=1, le=20, description="Max products to return (1–20)"),
) -> RecentProductsResponse:
    from app.common.exceptions import UnauthorizedShopAccessError
    from app.common.enums import UserRole

    # Workers may only query their own shop
    if current_user.role == UserRole.WORKER and current_user.shop_id != shop_id:
        raise UnauthorizedShopAccessError()

    products = await sales_service.get_recent_products(
        shop_id=shop_id,
        worker_id=current_user.id,
        limit=limit,
        db=db,
    )
    return RecentProductsResponse(
        items=[RecentProductItem.model_validate(p) for p in products]
    )


@router.get(
    "/owner/dashboard",
    response_model=OwnerDashboardResponse,
    summary="Owner Multi-Shop Dashboard",
    description="Aggregated daily summary across ALL of the owner's shops.",
)
async def owner_dashboard(
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OwnerDashboardResponse:
    return await reports_service.get_owner_dashboard(current_user.id, db)
