from pydantic import BaseModel, Field


class ImageUploadResponse(BaseModel):
    url: str = Field(..., description="Public URL the client can load on device.")
