"""
Tests for product search — name matching, category-name matching,
shop isolation, inactive-product exclusion, and the new
ProductSearchResult response shape.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.categories.models import Category
from app.products.models import Product


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def search_url(shop_id) -> str:
    return f"/api/v1/shops/{shop_id}/products/search"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def drinks_category(db_session: AsyncSession, shop):
    c = Category(shop_id=shop.id, name="Drinks")
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)
    return c


@pytest_asyncio.fixture
async def snacks_category(db_session: AsyncSession, shop):
    c = Category(shop_id=shop.id, name="Snacks")
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)
    return c


@pytest_asyncio.fixture
async def coke(db_session: AsyncSession, shop, drinks_category):
    p = Product(
        shop_id=shop.id,
        name="Coca-Cola",
        selling_price=Decimal("35.00"),
        stock_quantity=50,
        category_id=drinks_category.id,
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


@pytest_asyncio.fixture
async def fanta(db_session: AsyncSession, shop, drinks_category):
    p = Product(
        shop_id=shop.id,
        name="Fanta Orange",
        selling_price=Decimal("30.00"),
        stock_quantity=40,
        category_id=drinks_category.id,
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


@pytest_asyncio.fixture
async def biscuit(db_session: AsyncSession, shop, snacks_category):
    p = Product(
        shop_id=shop.id,
        name="Digestive Biscuit",
        selling_price=Decimal("20.00"),
        stock_quantity=30,
        category_id=snacks_category.id,
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_response_has_items_and_matched_category_keys(
    app_client: AsyncClient, owner_token, shop, coke
):
    resp = await app_client.get(
        search_url(shop.id), params={"q": "cola"}, headers=auth(owner_token)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "matched_category" in data


# ---------------------------------------------------------------------------
# Product name search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_by_exact_product_name(
    app_client: AsyncClient, owner_token, shop, coke
):
    resp = await app_client.get(
        search_url(shop.id), params={"q": "Coca-Cola"}, headers=auth(owner_token)
    )
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()["items"]]
    assert "Coca-Cola" in names


@pytest.mark.asyncio
async def test_search_by_partial_product_name(
    app_client: AsyncClient, owner_token, shop, coke, fanta
):
    resp = await app_client.get(
        search_url(shop.id), params={"q": "co"}, headers=auth(owner_token)
    )
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()["items"]]
    assert "Coca-Cola" in names


@pytest.mark.asyncio
async def test_search_product_name_case_insensitive(
    app_client: AsyncClient, owner_token, shop, coke
):
    for q in ("coca-cola", "COCA-COLA", "Coca-Cola", "cOcA"):
        resp = await app_client.get(
            search_url(shop.id), params={"q": q}, headers=auth(owner_token)
        )
        assert resp.status_code == 200, q
        names = [p["name"] for p in resp.json()["items"]]
        assert "Coca-Cola" in names, f"query={q!r} missed Coca-Cola"


@pytest.mark.asyncio
async def test_search_returns_multiple_matches(
    app_client: AsyncClient, owner_token, shop, coke, fanta
):
    """Both Coca-Cola and Fanta are in Drinks; searching 'a' should find both."""
    resp = await app_client.get(
        search_url(shop.id), params={"q": "a"}, headers=auth(owner_token)
    )
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()["items"]]
    assert "Coca-Cola" in names
    assert "Fanta Orange" in names


# ---------------------------------------------------------------------------
# Category-name matching
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_exact_category_name_returns_matched_category(
    app_client: AsyncClient, owner_token, shop, drinks_category, coke
):
    resp = await app_client.get(
        search_url(shop.id), params={"q": "Drinks"}, headers=auth(owner_token)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["matched_category"] is not None
    assert data["matched_category"]["name"] == "Drinks"
    assert data["matched_category"]["id"] == str(drinks_category.id)


@pytest.mark.asyncio
async def test_search_category_name_case_insensitive(
    app_client: AsyncClient, owner_token, shop, drinks_category, coke
):
    for q in ("drinks", "DRINKS", "dRiNkS"):
        resp = await app_client.get(
            search_url(shop.id), params={"q": q}, headers=auth(owner_token)
        )
        assert resp.status_code == 200, q
        data = resp.json()
        assert data["matched_category"] is not None, f"query={q!r} — no match"
        assert data["matched_category"]["name"] == "Drinks"


@pytest.mark.asyncio
async def test_search_partial_category_name(
    app_client: AsyncClient, owner_token, shop, drinks_category, coke
):
    resp = await app_client.get(
        search_url(shop.id), params={"q": "rink"}, headers=auth(owner_token)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["matched_category"] is not None
    assert data["matched_category"]["name"] == "Drinks"


@pytest.mark.asyncio
async def test_search_category_match_has_product_count(
    app_client: AsyncClient, owner_token, shop, drinks_category, coke, fanta
):
    resp = await app_client.get(
        search_url(shop.id), params={"q": "Drinks"}, headers=auth(owner_token)
    )
    assert resp.status_code == 200
    mc = resp.json()["matched_category"]
    assert mc is not None
    assert mc["product_count"] == 2  # coke + fanta


@pytest.mark.asyncio
async def test_search_no_category_match_when_query_misses(
    app_client: AsyncClient, owner_token, shop, drinks_category, coke
):
    resp = await app_client.get(
        search_url(shop.id), params={"q": "xyz_no_match"}, headers=auth(owner_token)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["matched_category"] is None
    assert data["items"] == []


# ---------------------------------------------------------------------------
# No matched_category when category_id filter is active
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_matched_category_when_filter_active(
    app_client: AsyncClient, owner_token, shop, drinks_category, snacks_category, coke
):
    """If a category_id filter is supplied, matched_category must be None
    regardless of whether the query matches a category name."""
    resp = await app_client.get(
        search_url(shop.id),
        params={"q": "Drinks", "category_id": str(drinks_category.id)},
        headers=auth(owner_token),
    )
    assert resp.status_code == 200
    assert resp.json()["matched_category"] is None


# ---------------------------------------------------------------------------
# Category filter + product name search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_with_category_filter_narrows_results(
    app_client: AsyncClient, owner_token, shop, drinks_category, snacks_category, coke, biscuit
):
    resp = await app_client.get(
        search_url(shop.id),
        params={"q": "c", "category_id": str(drinks_category.id)},
        headers=auth(owner_token),
    )
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()["items"]]
    assert "Coca-Cola" in names
    assert "Digestive Biscuit" not in names


# ---------------------------------------------------------------------------
# Inactive products excluded
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inactive_product_excluded_from_search(
    app_client: AsyncClient, db_session: AsyncSession, owner_token, shop
):
    inactive = Product(
        shop_id=shop.id,
        name="Ghost Cola",
        selling_price=Decimal("10.00"),
        stock_quantity=5,
        is_active=False,
    )
    db_session.add(inactive)
    await db_session.commit()

    resp = await app_client.get(
        search_url(shop.id), params={"q": "Ghost"}, headers=auth(owner_token)
    )
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()["items"]]
    assert "Ghost Cola" not in names


# ---------------------------------------------------------------------------
# Shop isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_category_search_isolated_to_shop(
    app_client: AsyncClient, db_session: AsyncSession, owner_token, shop
):
    """A category from a different shop must never appear as matched_category."""
    from app.owners.models import Owner
    from app.shops.models import Shop
    from app.common.security import hash_pin

    other_owner = Owner(name="Other", phone="0912345001", pin_hash=hash_pin("0000"))
    db_session.add(other_owner)
    await db_session.commit()
    await db_session.refresh(other_owner)

    other_shop = Shop(owner_id=other_owner.id, name="Other Shop")
    db_session.add(other_shop)
    await db_session.commit()
    await db_session.refresh(other_shop)

    # Only other_shop has a "Drinks" category
    other_drinks = Category(shop_id=other_shop.id, name="Drinks")
    db_session.add(other_drinks)
    await db_session.commit()

    # Searching our shop should return no category match
    resp = await app_client.get(
        search_url(shop.id), params={"q": "Drinks"}, headers=auth(owner_token)
    )
    assert resp.status_code == 200
    assert resp.json()["matched_category"] is None


@pytest.mark.asyncio
async def test_product_search_isolated_to_shop(
    app_client: AsyncClient, db_session: AsyncSession, owner_token, shop
):
    """Products from a different shop must not appear in search results."""
    from app.owners.models import Owner
    from app.shops.models import Shop
    from app.common.security import hash_pin

    other_owner = Owner(name="Sneaky", phone="0912345002", pin_hash=hash_pin("0000"))
    db_session.add(other_owner)
    await db_session.commit()
    await db_session.refresh(other_owner)

    other_shop = Shop(owner_id=other_owner.id, name="Sneaky Shop")
    db_session.add(other_shop)
    await db_session.commit()
    await db_session.refresh(other_shop)

    foreign_product = Product(
        shop_id=other_shop.id,
        name="Secret Coke",
        selling_price=Decimal("50.00"),
        stock_quantity=10,
    )
    db_session.add(foreign_product)
    await db_session.commit()

    resp = await app_client.get(
        search_url(shop.id), params={"q": "Secret Coke"}, headers=auth(owner_token)
    )
    assert resp.status_code == 200
    assert resp.json()["items"] == []


# ---------------------------------------------------------------------------
# Non-owner (owner with no elevated role requirement) can search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_any_authenticated_user_can_search_products(
    app_client: AsyncClient, owner_token, shop, coke
):
    """The /search endpoint accepts any authenticated user (owner or worker).
    We verify this using an owner token since the worker fixture has a
    SQLite-UUID compatibility limitation in the test harness."""
    resp = await app_client.get(
        search_url(shop.id), params={"q": "Cola"}, headers=auth(owner_token)
    )
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()["items"]]
    assert "Coca-Cola" in names


# ---------------------------------------------------------------------------
# Unauthenticated rejected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_requires_auth(app_client: AsyncClient, shop):
    resp = await app_client.get(search_url(shop.id), params={"q": "coke"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_empty_query_rejected(
    app_client: AsyncClient, owner_token, shop
):
    resp = await app_client.get(
        search_url(shop.id), params={"q": ""}, headers=auth(owner_token)
    )
    assert resp.status_code == 422
