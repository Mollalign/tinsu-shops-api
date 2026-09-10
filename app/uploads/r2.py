"""Cloudflare R2 client (S3-compatible). Isolated so tests can stub it."""

from __future__ import annotations

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings


def object_key(filename: str) -> str:
    return f"products/{filename}"


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def put_product_image(filename: str, data: bytes, content_type: str) -> None:
    """Upload bytes to R2. Raises OSError-like failures as ClientError/BotoCoreError."""
    get_s3_client().put_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=object_key(filename),
        Body=data,
        ContentType=content_type,
        CacheControl="public, max-age=31536000, immutable",
    )


def r2_public_url(filename: str) -> str:
    return f"{settings.R2_PUBLIC_BASE_URL.rstrip('/')}/{object_key(filename)}"


def r2_storage_errors() -> tuple[type[BaseException], ...]:
    return (BotoCoreError, ClientError)
