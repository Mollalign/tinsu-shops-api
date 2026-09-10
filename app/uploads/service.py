from __future__ import annotations

import asyncio
import re
from pathlib import Path
from uuid import UUID, uuid4

import aiofiles
from fastapi import Request, UploadFile

from app.common.exceptions import (
    EmptyImageError,
    ImageStorageError,
    ImageTooLargeError,
    InvalidImageTypeError,
)
from app.config import settings
from app.shops.service import get_shop_for_owner
from app.uploads import r2 as r2_storage

# Magic-byte signatures — never trust the client filename or Content-Type alone.
_JPEG = b"\xff\xd8\xff"
_PNG = b"\x89PNG\r\n\x1a\n"

_SAFE_FILENAME = re.compile(
    r"^product-image-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(jpg|png|webp)$"
)

_EXT_CONTENT_TYPE = {
    "jpg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}


def products_dir() -> Path:
    return Path(settings.UPLOAD_DIR).resolve() / "products"


def detect_image_ext(data: bytes) -> str | None:
    if len(data) < 12:
        return None
    if data.startswith(_JPEG):
        return "jpg"
    if data.startswith(_PNG):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def is_safe_filename(filename: str) -> bool:
    return bool(_SAFE_FILENAME.fullmatch(filename))


def content_type_for(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    return _EXT_CONTENT_TYPE.get(ext, "application/octet-stream")


def public_image_url(filename: str, request: Request | None = None) -> str:
    """Build a client-reachable URL. Never return a filesystem path."""
    if settings.r2_enabled:
        return r2_storage.r2_public_url(filename)
    base = (settings.PUBLIC_BASE_URL or "").rstrip("/")
    if not base and request is not None:
        base = str(request.base_url).rstrip("/")
    if not base:
        base = "http://localhost:8000"
    return f"{base}/media/products/{filename}"


def resolve_stored_path(filename: str) -> Path | None:
    """Return the file path only if *filename* is a safe basename under products/."""
    if not is_safe_filename(filename):
        return None
    root = products_dir()
    path = (root / filename).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    return path


async def _read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ImageTooLargeError()
        chunks.append(chunk)
    return b"".join(chunks)


async def save_product_image(
    shop_id: UUID,
    owner_id: UUID,
    upload: UploadFile,
    db,
    request: Request | None = None,
) -> str:
    """Validate and store an image. Returns a public URL. Owner-only."""
    await get_shop_for_owner(shop_id, owner_id, db)

    data = await _read_limited(upload, settings.MAX_UPLOAD_BYTES)
    await upload.close()

    if not data:
        raise EmptyImageError()

    ext = detect_image_ext(data)
    if ext is None:
        raise InvalidImageTypeError()

    filename = f"product-image-{uuid4()}.{ext}"
    content_type = content_type_for(filename)

    try:
        if settings.r2_enabled:
            await _save_to_r2(filename, data, content_type)
        else:
            await _save_to_disk(filename, data)
    except (*r2_storage.r2_storage_errors(), OSError) as exc:
        raise ImageStorageError() from exc

    return public_image_url(filename, request)


async def _save_to_r2(filename: str, data: bytes, content_type: str) -> None:
    await asyncio.to_thread(r2_storage.put_product_image, filename, data, content_type)


async def _save_to_disk(filename: str, data: bytes) -> None:
    dest_dir = products_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    async with aiofiles.open(dest, "wb") as f:
        await f.write(data)
