from functools import lru_cache

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    APP_NAME: str = "Tinsu Shops API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://neondb_owner:npg_TvZAhdsjm37U@ep-fancy-sound-ax5cs0qq-pooler.c-4.us-east-2.aws.neon.tech/neondb?ssl=true"

    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production-use-a-long-random-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30 days

    # Timezone
    BUSINESS_TIMEZONE: str = "Africa/Addis_Ababa"

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # Image uploads. When R2 is configured, files go to Cloudflare R2.
    # Otherwise they are stored on local disk (tests / offline development).
    UPLOAD_DIR: str = "uploads"
    PUBLIC_BASE_URL: str = ""
    MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024  # 5 MB

    # Cloudflare R2 (S3-compatible). Leave empty to keep local disk storage.
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = ""
    # Public URL prefix, e.g. https://pub-xxxxx.r2.dev or https://images.yourdomain.com
    R2_PUBLIC_BASE_URL: str = ""
    R2_ENDPOINT_URL: str = ""

    @property
    def r2_enabled(self) -> bool:
        return bool(
            self.R2_ACCOUNT_ID
            and self.R2_ACCESS_KEY_ID
            and self.R2_SECRET_ACCESS_KEY
            and self.R2_BUCKET_NAME
            and self.R2_PUBLIC_BASE_URL
        )

    @property
    def r2_endpoint_url(self) -> str:
        if self.R2_ENDPOINT_URL:
            return self.R2_ENDPOINT_URL.rstrip("/")
        return f"https://{self.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
