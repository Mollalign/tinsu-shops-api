"""
Integration tests for Worker CRUD endpoints.

Covers:
  - List workers (owner only)
  - Create worker with auto-generated PIN
  - Create worker with manual PIN
  - Get worker
  - Update worker name
  - Reset PIN (auto-generate)
  - Reset PIN (manual)
  - Disable worker
  - Authorization: worker token cannot manage workers
  - Shop scoping: owner cannot access another owner's workers
"""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def workers_url(shop_id: str) -> str:
    return f"/api/v1/shops/{shop_id}/workers"


def worker_url(shop_id: str, worker_id: str) -> str:
    return f"/api/v1/shops/{shop_id}/workers/{worker_id}"


def reset_pin_url(shop_id: str, worker_id: str) -> str:
    return f"/api/v1/shops/{shop_id}/workers/{worker_id}/reset-pin"


def disable_url(shop_id: str, worker_id: str) -> str:
    return f"/api/v1/shops/{shop_id}/workers/{worker_id}/disable"


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# List Workers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_workers_returns_existing(
    app_client: AsyncClient, shop, worker, owner_token: str
):
    resp = await app_client.get(
        workers_url(str(shop.id)),
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    ids = [w["id"] for w in data["items"]]
    assert str(worker.id) in ids


@pytest.mark.asyncio
async def test_list_workers_requires_auth(app_client: AsyncClient, shop):
    resp = await app_client.get(workers_url(str(shop.id)))
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_workers_worker_token_forbidden(
    app_client: AsyncClient, shop, worker_token: str
):
    resp = await app_client.get(
        workers_url(str(shop.id)),
        headers=auth_headers(worker_token),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Create Worker -- auto-generated PIN
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_worker_auto_pin(
    app_client: AsyncClient, shop, owner_token: str
):
    resp = await app_client.post(
        workers_url(str(shop.id)),
        json={"name": "Tigist"},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Tigist"
    assert data["is_active"] is True
    assert "pin" in data
    pin = data["pin"]
    assert pin is not None
    assert len(pin) == 4
    assert pin.isdigit(), "Auto-generated PIN must be 4 numeric digits"
    # PIN must NOT appear in a subsequent GET
    worker_id = data["id"]
    get_resp = await app_client.get(
        worker_url(str(shop.id), worker_id),
        headers=auth_headers(owner_token),
    )
    assert get_resp.status_code == 200
    assert "pin" not in get_resp.json()
    assert "pin_hash" not in get_resp.json()


# ---------------------------------------------------------------------------
# Create Worker -- manual PIN
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_worker_manual_pin(
    app_client: AsyncClient, shop, owner_token: str
):
    resp = await app_client.post(
        workers_url(str(shop.id)),
        json={"name": "Miriam", "pin": "7391"},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Miriam"
    assert data["pin"] == "7391"


@pytest.mark.asyncio
async def test_create_worker_manual_pin_too_short_rejected(
    app_client: AsyncClient, shop, owner_token: str
):
    resp = await app_client.post(
        workers_url(str(shop.id)),
        json={"name": "Yeshi", "pin": "12"},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_worker_name_required(
    app_client: AsyncClient, shop, owner_token: str
):
    resp = await app_client.post(
        workers_url(str(shop.id)),
        json={"pin": "1234"},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Get Worker
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_worker(
    app_client: AsyncClient, shop, worker, owner_token: str
):
    resp = await app_client.get(
        worker_url(str(shop.id), str(worker.id)),
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(worker.id)
    assert data["name"] == worker.name
    assert "pin_hash" not in data
    assert "pin" not in data


@pytest.mark.asyncio
async def test_get_worker_not_found(
    app_client: AsyncClient, shop, owner_token: str
):
    resp = await app_client.get(
        worker_url(str(shop.id), str(uuid.uuid4())),
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update Worker
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_worker_name(
    app_client: AsyncClient, shop, worker, owner_token: str
):
    resp = await app_client.patch(
        worker_url(str(shop.id), str(worker.id)),
        json={"name": "Hana Updated"},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Hana Updated"


# ---------------------------------------------------------------------------
# Reset PIN -- auto
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reset_pin_auto(
    app_client: AsyncClient, shop, worker, owner_token: str
):
    resp = await app_client.post(
        reset_pin_url(str(shop.id), str(worker.id)),
        json={"new_pin": None},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "pin" in data
    new_pin = data["pin"]
    assert len(new_pin) == 4
    assert new_pin.isdigit()
    # Worker can now login with the new PIN
    login_resp = await app_client.post(
        "/api/v1/auth/worker/login",
        json={
            "shop_id": str(shop.id),
            "worker_id": str(worker.id),
            "pin": new_pin,
        },
    )
    assert login_resp.status_code == 200
    # Old PIN (5678) must no longer work
    old_login = await app_client.post(
        "/api/v1/auth/worker/login",
        json={
            "shop_id": str(shop.id),
            "worker_id": str(worker.id),
            "pin": "5678",
        },
    )
    assert old_login.status_code == 401


# ---------------------------------------------------------------------------
# Reset PIN -- manual
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reset_pin_manual(
    app_client: AsyncClient, shop, worker, owner_token: str
):
    resp = await app_client.post(
        reset_pin_url(str(shop.id), str(worker.id)),
        json={"new_pin": "9999"},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 200
    assert resp.json()["pin"] == "9999"
    # Login with new PIN works
    login_resp = await app_client.post(
        "/api/v1/auth/worker/login",
        json={
            "shop_id": str(shop.id),
            "worker_id": str(worker.id),
            "pin": "9999",
        },
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_reset_pin_worker_token_forbidden(
    app_client: AsyncClient, shop, worker, worker_token: str
):
    resp = await app_client.post(
        reset_pin_url(str(shop.id), str(worker.id)),
        json={"new_pin": None},
        headers=auth_headers(worker_token),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Disable Worker
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_disable_worker(
    app_client: AsyncClient, shop, worker, owner_token: str
):
    resp = await app_client.post(
        disable_url(str(shop.id), str(worker.id)),
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_disabled_worker_cannot_login(
    app_client: AsyncClient, shop, worker, owner_token: str
):
    # Disable first
    await app_client.post(
        disable_url(str(shop.id), str(worker.id)),
        headers=auth_headers(owner_token),
    )
    # Login attempt should fail with 403
    login_resp = await app_client.post(
        "/api/v1/auth/worker/login",
        json={
            "shop_id": str(shop.id),
            "worker_id": str(worker.id),
            "pin": "5678",
        },
    )
    assert login_resp.status_code == 403


# ---------------------------------------------------------------------------
# Shop scoping -- owner cannot access another owner's shop workers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_owner_cannot_access_other_shop_workers(
    app_client: AsyncClient, db_session, shop, worker, owner_token: str
):
    from app.owners.models import Owner
    from app.shops.models import Shop
    from app.common.security import hash_pin as _hash

    # Create a second owner + shop
    other_owner = Owner(
        name="Other",
        phone=f"092{uuid.uuid4().hex[:7]}",
        pin_hash=_hash("0000"),
    )
    db_session.add(other_owner)
    await db_session.commit()
    await db_session.refresh(other_owner)

    other_shop = Shop(owner_id=other_owner.id, name="Other Shop", location="Hawassa")
    db_session.add(other_shop)
    await db_session.commit()
    await db_session.refresh(other_shop)

    # First owner's token should not list workers of other_shop
    resp = await app_client.get(
        workers_url(str(other_shop.id)),
        headers=auth_headers(owner_token),
    )
    assert resp.status_code in (403, 404)
