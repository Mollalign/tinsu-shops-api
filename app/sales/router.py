from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import ActorType, PaymentMethod
from app.common.pagination import Page, PaginationParams
from app.database import get_db
from app.dependencies import AuthenticatedUser, get_current_user, require_owner
from app.sales import service as sales_service
from app.sales.schemas import SaleListResponse, SaleRequest, SaleResponse

router = APIRouter(prefix="/shops/{shop_id}/sales", tags=["Sales"])


@router.post(
    "",
    response_model=SaleResponse,
    summary="Create Sale",
    description=(
        "Process a sale transaction. The backend: validates stock, reads current prices, "
        "calculates all totals server-side, decrements stock, and records inventory movements — "
        "all in one atomic database transaction."
    ),
)
async def create_sale(
    shop_id: UUID,
    body: SaleRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SaleResponse:
    actor_type = ActorType.OWNER if current_user.role.value == "owner" else ActorType.WORKER
    return await sales_service.create_sale(shop_id, body, actor_type, current_user.id, db)


@router.get(
    "",
    response_model=Page[SaleListResponse],
    summary="List Sales",
    description="Paginated list of sales. Supports filtering by date range, payment method, and worker.",
)
async def list_sales(
    shop_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    params: Annotated[PaginationParams, Depends()],
    date_from: date | None = Query(None, description="Filter sales from this date (inclusive)"),
    date_to: date | None = Query(None, description="Filter sales up to this date (inclusive)"),
    payment_method: PaymentMethod | None = Query(None),
    worker_id: UUID | None = Query(None),
) -> Page[SaleListResponse]:
    page = await sales_service.list_sales(
        shop_id, db, params, date_from, date_to, payment_method, worker_id
    )
    return Page[SaleListResponse](
        items=[SaleListResponse.model_validate(s) for s in page.items],
        page=page.page,
        page_size=page.page_size,
        total=page.total,
        total_pages=page.total_pages,
    )


@router.get(
    "/{sale_id}",
    response_model=SaleResponse,
    summary="Get Sale Detail",
    description="Detailed view of a single sale, including all line items and seller info.",
)
async def get_sale(
    shop_id: UUID,
    sale_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SaleResponse:
    return await sales_service.get_sale_detail(shop_id, sale_id, db)
