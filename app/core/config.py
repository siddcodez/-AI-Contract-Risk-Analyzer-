"""Application configuration via Pydantic Settings.

All secrets and environment-specific values are read from environment variables
(or a .env file in development). No hardcoded values anywhere except safe defaults
for non-secret settings.

Usage:
    from app.core.config import get_settings
    settings = get_settings()
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings — sourced exclusively from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # silently ignore unknown env vars (e.g. system vars)
    )

    # ---- Application -------------------------------------------------------
    APP_VERSION: str = Field(default="0.1.0")
    ENVIRONMENT: Literal["development", "staging", "production"] = Field(default="development")
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    SECRET_KEY: str = Field(min_length=32)

    # ---- PostgreSQL ---------------------------------------------------------
    DATABASE_URL: str = Field(
        description="Async SQLAlchemy URL: postgresql+asyncpg://user:pass@host:port/db"
    )

    # ---- Redis --------------------------------------------------------------
    REDIS_URL: str = Field(description="Redis connection URL: redis://host:port/db")

    # ---- MinIO / S3 ---------------------------------------------------------
    MINIO_ENDPOINT: str = Field(description="Full URL including scheme: http://host:port")
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET_NAME: str = Field(default="contract-documents")
    MINIO_USE_SSL: bool = Field(default=False)

    # ---- Celery -------------------------------------------------------------
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/2")

    # ---- File Upload & Chunking ---------------------------------------------
    MAX_FILE_SIZE_MB: int = Field(default=50, ge=1, description="Maximum upload file size in MB")
    CHUNK_SIZE: int = Field(default=1000, ge=100, description="Chunk size in characters")
    CHUNK_OVERLAP: int = Field(default=200, ge=0, description="Chunk overlap in characters")

    # ---- Embeddings ---------------------------------------------------------
    EMBEDDING_DIMENSION: int = Field(
        default=1536, ge=1, description="Vector dimension for embeddings"
    )
    EMBEDDING_PROVIDER: str = Field(
        default="mock", description="Embedding provider (mock, openai, etc.)"
    )

    # ---- JWT / Security -----------------------------------------------------
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, ge=5)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1)

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must use the postgresql+asyncpg:// scheme for async support"
            )
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton Settings instance (cached after first call).

    Using lru_cache means we only parse env vars once at startup.
    In tests, call get_settings.cache_clear() before overriding.
    """
    return Settings()
