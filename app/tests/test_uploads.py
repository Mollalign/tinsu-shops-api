"""
Tests for product image upload, storage, authorization, and photo_url
integration on product create/update.
"""
from __future__ import annotations

import base64
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

# 1×1 PNG
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
# Valid JPEG magic bytes (body is not a full JPEG; we validate signatures only)
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x00\x00" + b"\x00" * 32


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def upload_url(shop_id) -> str:
    return f"/api/v1/shops/{shop_id}/uploads/images"


@pytest.fixture(autouse=True)
def isolated_upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "http://test")
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 5 * 1024 * 1024)
    # Never hit real R2 during default tests
    monkeypatch.setattr(settings, "R2_ACCOUNT_ID", "")
    monkeypatch.setattr(settings, "R2_ACCESS_KEY_ID", "")
    monkeypatch.setattr(settings, "R2_SECRET_ACCESS_KEY", "")
    monkeypatch.setattr(settings, "R2_BUCKET_NAME", "")
    monkeypatch.setattr(settings, "R2_PUBLIC_BASE_URL", "")
    (tmp_path / "uploads" / "products").mkdir(parents=True)


# ---------------------------------------------------------------------------
# Valid upload
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_valid_png(app_client: AsyncClient, owner_token, shop):
    resp = await app_client.post(
        upload_url(shop.id),
        files={"file": ("ignored-name.exe", PNG_1X1, "application/octet-stream")},
        headers=auth(owner_token),
    )
    assert resp.status_code == 201, resp.text
    url = resp.json()["url"]
    assert url.startswith("http://test/media/products/product-image-")
    assert url.endswith(".png")
    assert "/uploads/" not in url
    assert ".." not in url


@pytest.mark.asyncio
async def test_upload_valid_jpeg(app_client: AsyncClient, owner_token, shop):
    resp = await app_client.post(
        upload_url(shop.id),
        files={"file": ("photo.jpg", JPEG_BYTES, "image/jpeg")},
        headers=auth(owner_token),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["url"].endswith(".jpg")


@pytest.mark.asyncio
async def test_returned_url_is_fetchable(app_client: AsyncClient, owner_token, shop):
    upload = await app_client.post(
        upload_url(shop.id),
        files={"file": ("a.png", PNG_1X1, "image/png")},
        headers=auth(owner_token),
    )
    assert upload.status_code == 201
    url = upload.json()["url"]
    path = url.removeprefix("http://test")
    media = await app_client.get(path)
    assert media.status_code == 200
    assert media.headers["content-type"].startswith("image/")
    assert media.content == PNG_1X1


# ---------------------------------------------------------------------------
# Invalid / empty / oversized
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_invalid_file_rejected(app_client: AsyncClient, owner_token, shop):
    resp = await app_client.post(
        upload_url(shop.id),
        files={"file": ("notes.txt", b"not an image", "text/plain")},
        headers=auth(owner_token),
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "INVALID_IMAGE_TYPE"


@pytest.mark.asyncio
async def test_upload_empty_file_rejected(app_client: AsyncClient, owner_token, shop):
    resp = await app_client.post(
        upload_url(shop.id),
        files={"file": ("empty.jpg", b"", "image/jpeg")},
        headers=auth(owner_token),
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "EMPTY_IMAGE"


@pytest.mark.asyncio
async def test_upload_missing_file_rejected(app_client: AsyncClient, owner_token, shop):
    resp = await app_client.post(
        upload_url(shop.id),
        headers=auth(owner_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_upload_oversized_rejected(
    app_client: AsyncClient, owner_token, shop, monkeypatch
):
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 50)
    huge = PNG_1X1 + b"\x00" * 100
    resp = await app_client.post(
        upload_url(shop.id),
        files={"file": ("big.png", huge, "image/png")},
        headers=auth(owner_token),
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "IMAGE_TOO_LARGE"


@pytest.mark.asyncio
async def test_upload_ignores_original_filename(
    app_client: AsyncClient, owner_token, shop
):
    resp = await app_client.post(
        upload_url(shop.id),
        files={"file": ("../../etc/passwd.png", PNG_1X1, "image/png")},
        headers=auth(owner_token),
    )
    assert resp.status_code == 201
    url = resp.json()["url"]
    assert "passwd" not in url
    assert ".." not in url
    assert "/etc/" not in url


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthenticated_upload_rejected(app_client: AsyncClient, shop):
    resp = await app_client.post(
        upload_url(shop.id),
        files={"file": ("a.png", PNG_1X1, "image/png")},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_worker_cannot_upload(
    app_client: AsyncClient, worker_token, shop
):
    resp = await app_client.post(
        upload_url(shop.id),
        files={"file": ("a.png", PNG_1X1, "image/png")},
        headers=auth(worker_token),
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "OWNER_ONLY"


@pytest.mark.asyncio
async def test_owner_cannot_upload_to_another_shop(
    app_client: AsyncClient, db_session: AsyncSession, owner_token, shop
):
    from app.common.security import hash_pin
    from app.owners.models import Owner
    from app.shops.models import Shop

    other_owner = Owner(
        name="Other", phone=f"092{uuid4().hex[:7]}", pin_hash=hash_pin("9999")
    )
    db_session.add(other_owner)
    await db_session.commit()
    await db_session.refresh(other_owner)

    other_shop = Shop(owner_id=other_owner.id, name="Other Shop")
    db_session.add(other_shop)
    await db_session.commit()
    await db_session.refresh(other_shop)

    resp = await app_client.post(
        upload_url(other_shop.id),
        files={"file": ("a.png", PNG_1X1, "image/png")},
        headers=auth(owner_token),
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "UNAUTHORIZED_SHOP_ACCESS"


# ---------------------------------------------------------------------------
# Media serving safety
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_media_path_traversal_rejected(app_client: AsyncClient):
    resp = await app_client.get("/media/products/../../etc/passwd")
    assert resp.status_code in (404, 422)


@pytest.mark.asyncio
async def test_media_unknown_file_404(app_client: AsyncClient):
    resp = await app_client.get(
        "/media/products/product-image-00000000-0000-0000-0000-000000000000.png"
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Product photo_url integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_product_saves_photo_url(
    app_client: AsyncClient, owner_token, shop
):
    upload = await app_client.post(
        upload_url(shop.id),
        files={"file": ("a.png", PNG_1X1, "image/png")},
        headers=auth(owner_token),
    )
    photo_url = upload.json()["url"]

    resp = await app_client.post(
        f"/api/v1/shops/{shop.id}/products",
        json={
            "name": "Coca-Cola",
            "selling_price": 35,
            "initial_stock": 50,
            "photo_url": photo_url,
        },
        headers=auth(owner_token),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["photo_url"] == photo_url
    assert data["name"] == "Coca-Cola"


@pytest.mark.asyncio
async def test_create_product_without_image(app_client: AsyncClient, owner_token, shop):
    resp = await app_client.post(
        f"/api/v1/shops/{shop.id}/products",
        json={"name": "Water", "selling_price": 15, "initial_stock": 10},
        headers=auth(owner_token),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["photo_url"] is None


@pytest.mark.asyncio
async def test_update_product_replaces_photo_url(
    app_client: AsyncClient, owner_token, shop, product
):
    upload = await app_client.post(
        upload_url(shop.id),
        files={"file": ("a.png", PNG_1X1, "image/png")},
        headers=auth(owner_token),
    )
    photo_url = upload.json()["url"]

    resp = await app_client.patch(
        f"/api/v1/shops/{shop.id}/products/{product.id}",
        json={"photo_url": photo_url},
        headers=auth(owner_token),
    )
    assert resp.status_code == 200
    assert resp.json()["photo_url"] == photo_url


@pytest.mark.asyncio
async def test_update_product_clears_photo_url(
    app_client: AsyncClient, owner_token, shop, product
):
    await app_client.patch(
        f"/api/v1/shops/{shop.id}/products/{product.id}",
        json={"photo_url": "http://test/media/products/old.png"},
        headers=auth(owner_token),
    )
    resp = await app_client.patch(
        f"/api/v1/shops/{shop.id}/products/{product.id}",
        json={"photo_url": None},
        headers=auth(owner_token),
    )
    assert resp.status_code == 200
    assert resp.json()["photo_url"] is None


# ---------------------------------------------------------------------------
# Cloudflare R2
# ---------------------------------------------------------------------------

def _enable_r2(monkeypatch) -> list[dict]:
    monkeypatch.setattr(settings, "R2_ACCOUNT_ID", "acc123")
    monkeypatch.setattr(settings, "R2_ACCESS_KEY_ID", "key")
    monkeypatch.setattr(settings, "R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setattr(settings, "R2_BUCKET_NAME", "tinsu-product-images")
    monkeypatch.setattr(settings, "R2_PUBLIC_BASE_URL", "https://images.example.com")
    puts: list[dict] = []

    def fake_put(filename: str, data: bytes, content_type: str) -> None:
        puts.append(
            {"filename": filename, "data": data, "content_type": content_type}
        )

    monkeypatch.setattr("app.uploads.r2.put_product_image", fake_put)
    return puts


@pytest.mark.asyncio
async def test_upload_uses_r2_when_configured(
    app_client: AsyncClient, owner_token, shop, monkeypatch
):
    puts = _enable_r2(monkeypatch)
    resp = await app_client.post(
        upload_url(shop.id),
        files={"file": ("a.png", PNG_1X1, "image/png")},
        headers=auth(owner_token),
    )
    assert resp.status_code == 201, resp.text
    url = resp.json()["url"]
    assert url.startswith("https://images.example.com/products/product-image-")
    assert url.endswith(".png")
    assert "/media/" not in url
    assert len(puts) == 1
    assert puts[0]["data"] == PNG_1X1
    assert puts[0]["content_type"] == "image/png"


@pytest.mark.asyncio
async def test_r2_upload_does_not_write_local_disk(
    app_client: AsyncClient, owner_token, shop, monkeypatch, tmp_path
):
    _enable_r2(monkeypatch)
    await app_client.post(
        upload_url(shop.id),
        files={"file": ("a.png", PNG_1X1, "image/png")},
        headers=auth(owner_token),
    )
    products = tmp_path / "uploads" / "products"
    assert list(products.iterdir()) == []


@pytest.mark.asyncio
async def test_r2_failure_returns_storage_error(
    app_client: AsyncClient, owner_token, shop, monkeypatch
):
    from botocore.exceptions import ClientError

    _enable_r2(monkeypatch)

    def boom(filename: str, data: bytes, content_type: str) -> None:
        raise ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}},
            "PutObject",
        )

    monkeypatch.setattr("app.uploads.r2.put_product_image", boom)
    resp = await app_client.post(
        upload_url(shop.id),
        files={"file": ("a.png", PNG_1X1, "image/png")},
        headers=auth(owner_token),
    )
    assert resp.status_code == 500
    assert resp.json()["detail"]["code"] == "IMAGE_STORAGE_ERROR"
