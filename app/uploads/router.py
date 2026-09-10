from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import AuthenticatedUser, require_owner
from app.uploads.schemas import ImageUploadResponse
from app.uploads.service import (
    content_type_for,
    resolve_stored_path,
    save_product_image,
)

router = APIRouter(prefix="/shops/{shop_id}/uploads", tags=["Uploads"])
media_router = APIRouter(tags=["Media"])


@router.post(
    "/images",
    response_model=ImageUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Product Image",
    description=(
        "Upload a JPEG, PNG, or WebP image for the shop. "
        "Owner only. Returns a public URL to store as product photo_url."
    ),
)
async def upload_image(
    shop_id: UUID,
    request: Request,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File(description="Image file")],
) -> ImageUploadResponse:
    url = await save_product_image(
        shop_id=shop_id,
        owner_id=current_user.id,
        upload=file,
        db=db,
        request=request,
    )
    return ImageUploadResponse(url=url)


@media_router.get(
    "/media/products/{filename}",
    summary="Serve Product Image",
    description="Public image file. Filename must be a generated product-image UUID name.",
)
async def serve_product_image(filename: str) -> FileResponse:
    path = resolve_stored_path(filename)
    if path is None or not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found.",
        )
    return FileResponse(path, media_type=content_type_for(filename))
