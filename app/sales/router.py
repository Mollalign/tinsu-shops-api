from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import ActorType
from app.common.pagination import Page, PaginationParams
from app.database import get_db
from app.dependencies import AuthenticatedUser, get_current_user
from app.sales import service as sales_service
from app.sales.schemas import SaleListResponse, SaleRequest, SaleResponse

router = APIRouter(prefix="/shops/{shop_id}/sales", tags=["Sales"])


@router.post(
    "",
    response_model=SaleResponse,
    summary="Create Sale",
    description=(
        "Complete a sale. The server validates stock, reads current prices, "
        "calculates all totals, decrements stock, and records inventory movements "
        "atomically. No payment method required.\n\n"
        "**Idempotency:** Supply `Idempotency-Key: <uuid>` to safely retry without "
        "creating duplicate sales."
    ),
)
async def create_sale(
    shop_id: UUID,
    body: SaleRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> SaleResponse:
    actor_type = ActorType.OWNER if current_user.role.value == "owner" else ActorType.WORKER
    return await sales_service.create_sale(
        shop_id, body, actor_type, current_user.id, db, idempotency_key
    )


@router.get(
    "",
    response_model=Page[SaleListResponse],
    summary="List Sales",
    description="Paginated list of sales. Supports optional date range and worker filter.",
)
async def list_sales(
    shop_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    params: Annotated[PaginationParams, Depends()],
    date_from: date | None = Query(None, description="Filter from this date (inclusive)"),
    date_to: date | None = Query(None, description="Filter up to this date (inclusive)"),
    worker_id: UUID | None = Query(None),
) -> Page[SaleListResponse]:
    return await sales_service.list_sales(shop_id, db, params, date_from, date_to, worker_id)


@router.get(
    "/{sale_id}",
    response_model=SaleResponse,
    summary="Get Sale Detail",
    description="Detailed view of a single sale including all line items and seller info.",
)
async def get_sale(
    shop_id: UUID,
    sale_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SaleResponse:
    return await sales_service.get_sale_detail(shop_id, sale_id, db)
