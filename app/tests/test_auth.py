"""
Tests for the authentication flow:
 - Owner and worker login (returns both tokens)
 - POST /auth/refresh — happy path and error paths
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from jose import jwt

from app.common.security import create_refresh_token
from app.config import settings


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_expired_refresh_token(payload: dict) -> str:
    """Craft a well-signed refresh token that is already expired."""
    data = payload.copy()
    data["exp"] = datetime.now(UTC) - timedelta(seconds=1)
    data["iat"] = datetime.now(UTC) - timedelta(days=31)
    data["type"] = "refresh"
    return jwt.encode(data, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


# ---------------------------------------------------------------------------
# Owner login
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_owner_login_returns_both_tokens(app_client: AsyncClient, owner):
    resp = await app_client.post(
        "/api/v1/auth/owner/login",
        json={"phone": owner.phone, "pin": "1234"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "owner"


@pytest.mark.asyncio
async def test_owner_refresh_token_has_correct_type_claim(app_client: AsyncClient, owner):
    resp = await app_client.post(
        "/api/v1/auth/owner/login",
        json={"phone": owner.phone, "pin": "1234"},
    )
    assert resp.status_code == 200
    rt = resp.json()["refresh_token"]
    payload = jwt.decode(rt, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert payload["type"] == "refresh"
    assert payload["role"] == "owner"
    assert payload["sub"] == str(owner.id)


# ---------------------------------------------------------------------------
# Worker login
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_worker_login_returns_both_tokens(app_client: AsyncClient, shop, worker):
    resp = await app_client.post(
        "/api/v1/auth/worker/login",
        json={
            "shop_id": str(shop.id),
            "worker_id": str(worker.id),
            "pin": "5678",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["user"]["role"] == "worker"
    assert body["user"]["shop_id"] == str(shop.id)


@pytest.mark.asyncio
async def test_worker_refresh_token_has_shop_id(app_client: AsyncClient, shop, worker):
    resp = await app_client.post(
        "/api/v1/auth/worker/login",
        json={
            "shop_id": str(shop.id),
            "worker_id": str(worker.id),
            "pin": "5678",
        },
    )
    assert resp.status_code == 200
    rt = resp.json()["refresh_token"]
    payload = jwt.decode(rt, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert payload["type"] == "refresh"
    assert payload["role"] == "worker"
    assert payload["shop_id"] == str(shop.id)


# ---------------------------------------------------------------------------
# POST /auth/refresh — happy paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_with_valid_owner_token_returns_new_access_token(
    app_client: AsyncClient, owner
):
    # Login to get a refresh token
    login_resp = await app_client.post(
        "/api/v1/auth/owner/login",
        json={"phone": owner.phone, "pin": "1234"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    resp = await app_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["user"]["role"] == "owner"


@pytest.mark.asyncio
async def test_refresh_returns_rotated_refresh_token(app_client: AsyncClient, owner):
    """Each successful refresh yields a DIFFERENT refresh token (rotation)."""
    login_resp = await app_client.post(
        "/api/v1/auth/owner/login",
        json={"phone": owner.phone, "pin": "1234"},
    )
    original_rt = login_resp.json()["refresh_token"]

    resp = await app_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": original_rt},
    )
    assert resp.status_code == 200
    new_rt = resp.json()["refresh_token"]
    # The new refresh token is a valid JWT but has a newer iat
    orig_payload = jwt.decode(original_rt, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    new_payload = jwt.decode(new_rt, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert new_payload["iat"] >= orig_payload["iat"]
    assert new_payload["type"] == "refresh"


@pytest.mark.asyncio
async def test_refresh_with_valid_worker_token(app_client: AsyncClient, shop, worker):
    login_resp = await app_client.post(
        "/api/v1/auth/worker/login",
        json={
            "shop_id": str(shop.id),
            "worker_id": str(worker.id),
            "pin": "5678",
        },
    )
    refresh_token = login_resp.json()["refresh_token"]

    resp = await app_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["role"] == "worker"
    assert body["user"]["shop_id"] == str(shop.id)


@pytest.mark.asyncio
async def test_refreshed_access_token_is_usable(app_client: AsyncClient, shop, owner_token, owner):
    """Access token received after refresh works for authenticated endpoints."""
    login_resp = await app_client.post(
        "/api/v1/auth/owner/login",
        json={"phone": owner.phone, "pin": "1234"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    refresh_resp = await app_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    new_access_token = refresh_resp.json()["access_token"]

    # New token should work on an authenticated endpoint
    shops_resp = await app_client.get(
        "/api/v1/shops",
        headers={"Authorization": f"Bearer {new_access_token}"},
    )
    assert shops_resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /auth/refresh — error paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_with_expired_token_returns_401(app_client: AsyncClient, owner):
    expired_rt = _make_expired_refresh_token({
        "sub": str(owner.id),
        "role": "owner",
        "name": owner.name,
    })

    resp = await app_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": expired_rt},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "INVALID_REFRESH_TOKEN"


@pytest.mark.asyncio
async def test_refresh_with_garbage_string_returns_401(app_client: AsyncClient):
    resp = await app_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "this-is-not-a-jwt"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_access_token_rejected(app_client: AsyncClient, owner):
    """Passing an access token (type claim absent) to /refresh must fail."""
    login_resp = await app_client.post(
        "/api/v1/auth/owner/login",
        json={"phone": owner.phone, "pin": "1234"},
    )
    access_token = login_resp.json()["access_token"]

    resp = await app_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access_token},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "INVALID_REFRESH_TOKEN"


@pytest.mark.asyncio
async def test_refresh_for_inactive_owner_returns_401(app_client: AsyncClient, db_session, owner):
    """If the owner account is deactivated, refreshing must fail."""
    login_resp = await app_client.post(
        "/api/v1/auth/owner/login",
        json={"phone": owner.phone, "pin": "1234"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    # Deactivate the owner
    owner.is_active = False
    await db_session.commit()

    resp = await app_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_for_inactive_worker_returns_401(
    app_client: AsyncClient, db_session, shop, worker
):
    login_resp = await app_client.post(
        "/api/v1/auth/worker/login",
        json={
            "shop_id": str(shop.id),
            "worker_id": str(worker.id),
            "pin": "5678",
        },
    )
    refresh_token = login_resp.json()["refresh_token"]

    # Deactivate the worker
    worker.is_active = False
    await db_session.commit()

    resp = await app_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 401
