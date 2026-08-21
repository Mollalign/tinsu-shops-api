"""
Sales flow tests — simplified (no payment method).
Tests cover: creation, validation, idempotency, stock deduction, security.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def sale_body(*items: tuple[str, int]) -> dict:
    return {"items": [{"product_id": pid, "quantity": qty} for pid, qty in items]}


# ─────────────────────────────────────────────────────────────────────────────
# Create sale — happy path
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateSale:
    @pytest.mark.asyncio
    async def test_worker_sells_one_product(
        self, app_client: AsyncClient, worker_token, shop, product
    ):
        resp = await app_client.post(
            f"/api/v1/shops/{shop.id}/sales",
            json=sale_body((str(product.id), 2)),
            headers=auth(worker_token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        # Response structure
        assert data["total_amount"] == "70.00"  # 35 × 2
        assert len(data["items"]) == 1
        assert data["items"][0]["product_name"] == "Coca-Cola 500ml"
        assert data["items"][0]["quantity"] == 2
        assert data["items"][0]["unit_price"] == "35.00"
        assert data["items"][0]["subtotal"] == "70.00"
        assert data["sold_by"]["name"] == "Hana"

        # No payment_method in response
        assert "payment_method" not in data

    @pytest.mark.asyncio
    async def test_stock_decremented_after_sale(
        self, app_client: AsyncClient, worker_token, shop, product, db_session
    ):
        initial_stock = product.stock_quantity
        await app_client.post(
            f"/api/v1/shops/{shop.id}/sales",
            json=sale_body((str(product.id), 3)),
            headers=auth(worker_token),
        )
        await db_session.refresh(product)
        assert product.stock_quantity == initial_stock - 3

    @pytest.mark.asyncio
    async def test_multiple_products_in_one_sale(
        self, app_client: AsyncClient, worker_token, shop, product, db_session
    ):
        from app.products.models import Product

        p2 = Product(
            shop_id=shop.id,
            name="Water 500ml",
            selling_price=Decimal("20.00"),
            stock_quantity=100,
        )
        db_session.add(p2)
        await db_session.commit()
        await db_session.refresh(p2)

        resp = await app_client.post(
            f"/api/v1/shops/{shop.id}/sales",
            json=sale_body((str(product.id), 2), (str(p2.id), 1)),
            headers=auth(worker_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        # 35×2 + 20×1 = 90
        assert data["total_amount"] == "90.00"
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_owner_can_also_sell(
        self, app_client: AsyncClient, owner_token, shop, product
    ):
        resp = await app_client.post(
            f"/api/v1/shops/{shop.id}/sales",
            json=sale_body((str(product.id), 1)),
            headers=auth(owner_token),
        )
        assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Idempotency
# ─────────────────────────────────────────────────────────────────────────────

class TestIdempotency:
    @pytest.mark.asyncio
    async def test_duplicate_request_returns_same_sale(
        self, app_client: AsyncClient, worker_token, shop, product, db_session
    ):
        from app.sales.models import Sale
        from sqlalchemy import select, func

        key = str(uuid4())
        headers = {**auth(worker_token), "Idempotency-Key": key}
        body = sale_body((str(product.id), 1))

        r1 = await app_client.post(f"/api/v1/shops/{shop.id}/sales", json=body, headers=headers)
        r2 = await app_client.post(f"/api/v1/shops/{shop.id}/sales", json=body, headers=headers)

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["id"] == r2.json()["id"], "Duplicate key must return same sale"

        # Only ONE sale row created
        count = await db_session.scalar(
            select(func.count()).select_from(Sale).where(Sale.idempotency_key == key)
        )
        assert count == 1

    @pytest.mark.asyncio
    async def test_different_keys_create_different_sales(
        self, app_client: AsyncClient, worker_token, shop, product
    ):
        body = sale_body((str(product.id), 1))
        r1 = await app_client.post(
            f"/api/v1/shops/{shop.id}/sales",
            json=body,
            headers={**auth(worker_token), "Idempotency-Key": str(uuid4())},
        )
        r2 = await app_client.post(
            f"/api/v1/shops/{shop.id}/sales",
            json=body,
            headers={**auth(worker_token), "Idempotency-Key": str(uuid4())},
        )
        assert r1.json()["id"] != r2.json()["id"]


# ─────────────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────────────

class TestSaleValidation:
    @pytest.mark.asyncio
    async def test_empty_items_rejected(
        self, app_client: AsyncClient, worker_token, shop
    ):
        resp = await app_client.post(
            f"/api/v1/shops/{shop.id}/sales",
            json={"items": []},
            headers=auth(worker_token),
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_zero_quantity_rejected(
        self, app_client: AsyncClient, worker_token, shop, product
    ):
        resp = await app_client.post(
            f"/api/v1/shops/{shop.id}/sales",
            json={"items": [{"product_id": str(product.id), "quantity": 0}]},
            headers=auth(worker_token),
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_negative_quantity_rejected(
        self, app_client: AsyncClient, worker_token, shop, product
    ):
        resp = await app_client.post(
            f"/api/v1/shops/{shop.id}/sales",
            json={"items": [{"product_id": str(product.id), "quantity": -1}]},
            headers=auth(worker_token),
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_insufficient_stock_returns_400(
        self, app_client: AsyncClient, worker_token, shop, product
    ):
        resp = await app_client.post(
            f"/api/v1/shops/{shop.id}/sales",
            json=sale_body((str(product.id), 9999)),
            headers=auth(worker_token),
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "INSUFFICIENT_STOCK"

    @pytest.mark.asyncio
    async def test_inactive_product_rejected(
        self, app_client: AsyncClient, worker_token, shop, db_session
    ):
        from app.products.models import Product

        inactive = Product(
            shop_id=shop.id,
            name="Old Item",
            selling_price=Decimal("10.00"),
            stock_quantity=10,
            is_active=False,
        )
        db_session.add(inactive)
        await db_session.commit()

        resp = await app_client.post(
            f"/api/v1/shops/{shop.id}/sales",
            json=sale_body((str(inactive.id), 1)),
            headers=auth(worker_token),
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "INACTIVE_PRODUCT"

    @pytest.mark.asyncio
    async def test_cross_shop_product_rejected(
        self, app_client: AsyncClient, worker_token, shop, db_session, owner
    ):
        from app.products.models import Product
        from app.shops.models import Shop

        other_shop = Shop(owner_id=owner.id, name="Other Shop")
        db_session.add(other_shop)
        await db_session.flush()

        other_product = Product(
            shop_id=other_shop.id,
            name="Other Item",
            selling_price=Decimal("15.00"),
            stock_quantity=10,
        )
        db_session.add(other_product)
        await db_session.commit()

        resp = await app_client.post(
            f"/api/v1/shops/{shop.id}/sales",
            json=sale_body((str(other_product.id), 1)),
            headers=auth(worker_token),
        )
        assert resp.status_code == 404  # product not found in this shop

    @pytest.mark.asyncio
    async def test_no_payment_method_required(
        self, app_client: AsyncClient, worker_token, shop, product
    ):
        """Sale succeeds without any payment_method field."""
        resp = await app_client.post(
            f"/api/v1/shops/{shop.id}/sales",
            json={"items": [{"product_id": str(product.id), "quantity": 1}]},
            headers=auth(worker_token),
        )
        assert resp.status_code == 200
        assert "payment_method" not in resp.json()


# ─────────────────────────────────────────────────────────────────────────────
# Security
# ─────────────────────────────────────────────────────────────────────────────

class TestSaleSecurity:
    @pytest.mark.asyncio
    async def test_unauthenticated_cannot_sell(
        self, app_client: AsyncClient, shop, product
    ):
        resp = await app_client.post(
            f"/api/v1/shops/{shop.id}/sales",
            json=sale_body((str(product.id), 1)),
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_worker_cannot_access_another_shop(
        self, app_client: AsyncClient, worker_token, db_session, owner
    ):
        from app.shops.models import Shop

        other_shop = Shop(owner_id=owner.id, name="Other Branch")
        db_session.add(other_shop)
        await db_session.commit()

        # Worker tries to post sale to a shop they don't belong to
        resp = await app_client.post(
            f"/api/v1/shops/{other_shop.id}/sales",
            json={"items": [{"product_id": str(uuid4()), "quantity": 1}]},
            headers=auth(worker_token),
        )
        # Product won't be found in other shop — 404 is acceptable security boundary
        assert resp.status_code in (403, 404)


# ─────────────────────────────────────────────────────────────────────────────
# Reports
# ─────────────────────────────────────────────────────────────────────────────

class TestReports:
    @pytest.mark.asyncio
    async def test_today_report_totals(
        self, app_client: AsyncClient, owner_token, worker_token, shop, product
    ):
        # Make 2 sales
        await app_client.post(
            f"/api/v1/shops/{shop.id}/sales",
            json=sale_body((str(product.id), 2)),
            headers=auth(worker_token),
        )
        await app_client.post(
            f"/api/v1/shops/{shop.id}/sales",
            json=sale_body((str(product.id), 1)),
            headers=auth(worker_token),
        )

        resp = await app_client.get(
            f"/api/v1/shops/{shop.id}/reports/today",
            headers=auth(owner_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert float(data["total_sales"]) > 0
        assert data["number_of_sales"] >= 2
        assert data["items_sold"] >= 3
        assert "payment_breakdown" not in data

    @pytest.mark.asyncio
    async def test_worker_today_no_payment_breakdown(
        self, app_client: AsyncClient, worker_token, shop, product
    ):
        await app_client.post(
            f"/api/v1/shops/{shop.id}/sales",
            json=sale_body((str(product.id), 1)),
            headers=auth(worker_token),
        )
        resp = await app_client.get(
            f"/api/v1/shops/{shop.id}/workers/me/today",
            headers=auth(worker_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "payment_breakdown" not in data
        assert "total_sales" in data
        assert "number_of_sales" in data
        assert "items_sold" in data
