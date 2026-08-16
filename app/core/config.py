"""Application configuration via Pydantic Settings.

All secrets and environment-specific values are read from environment variables
(or a .env file in development). No hardcoded values anywhere except safe defaults
for non-secret settings.

Usage:
    from app.core.config import get_settings
    settings = get_settings()
"""

import urllib.parse
from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
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
    ENVIRONMENT: Literal["development", "test", "staging", "production"] = Field(
        default="development"
    )
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    SECRET_KEY: str = Field(
        validation_alias=AliasChoices("SECRET_KEY", "JWT_SECRET"),
        min_length=32,
        description="JWT Secret key (supports SECRET_KEY or JWT_SECRET)",
    )

    # ---- PostgreSQL ---------------------------------------------------------
    DATABASE_URL: str = Field(
        validation_alias=AliasChoices("DATABASE_URL", "NEON_DATABASE_URL"),
        description="Async SQLAlchemy URL: postgresql+asyncpg://user:pass@host:port/db",
    )
    MIGRATION_DATABASE_URL: str | None = Field(
        default=None,
        validation_alias=AliasChoices("MIGRATION_DATABASE_URL", "NEON_MIGRATION_DATABASE_URL"),
        description="Elevated migration connection URL used for background tasks and migrations",
    )

    # ---- Redis --------------------------------------------------------------
    REDIS_URL: str = Field(
        validation_alias=AliasChoices("REDIS_URL", "UPSTASH_REDIS_URL"),
        description="Redis connection URL: redis://host:port/db (or UPSTASH_REDIS_URL)",
    )

    # ---- CORS ---------------------------------------------------------------
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000",
        description="Allowed CORS origins, comma-separated or *",
    )

    # ---- Supabase Storage ---------------------------------------------------
    SUPABASE_URL: str = Field(description="Supabase project URL (e.g. https://xyz.supabase.co)")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(
        description="Supabase service role key for backend storage operations"
    )
    SUPABASE_STORAGE_BUCKET: str = Field(
        default="contract-documents",
        description="Supabase storage bucket name for contract documents",
    )

    # ---- Celery -------------------------------------------------------------
    CELERY_BROKER_URL: str | None = Field(
        default=None,
        description="Celery broker URL (defaults to REDIS_URL if unset)",
    )
    CELERY_RESULT_BACKEND: str | None = Field(
        default=None,
        description="Celery result backend URL (defaults to REDIS_URL if unset)",
    )

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

    # ---- LLM / Risk Analysis (M4) -------------------------------------------
    LLM_PROVIDER: str = Field(
        default="mock", description="LLM provider (mock, openai, anthropic, etc.)"
    )
    LLM_MODEL: str = Field(default="mock-risk-analyzer", description="LLM model identifier")
    LLM_API_KEY: str | None = Field(default=None, description="API key for LLM provider")
    LLM_TEMPERATURE: float = Field(
        default=0.0, ge=0.0, le=1.0, description="LLM sampling temperature"
    )
    MAX_ANALYSIS_TOKENS: int = Field(
        default=4000, ge=100, description="Max tokens per analysis request"
    )

    # ---- Groq / Grounded Q&A (M7.1) -----------------------------------------
    GROQ_API_KEY: str | None = Field(
        default=None, description="Groq API key for grounded contract Q&A"
    )
    GROQ_MODEL: str = Field(
        default="llama-3.3-70b-versatile",
        description="Default Groq model for grounded Q&A",
    )
    GROQ_BASE_URL: str = Field(
        default="https://api.groq.com/openai/v1",
        description="Groq API base URL",
    )

    # ---- Anthropic / Grounded Q&A (Optional) --------------------------------
    ANTHROPIC_API_KEY: str | None = Field(
        default=None, description="Anthropic API key for grounded contract Q&A"
    )
    ANTHROPIC_MODEL: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="Default Anthropic model for grounded Q&A",
    )

    # ---- Retrieval / RAG / Vector Search (M5) -------------------------------
    VECTOR_DISTANCE_METRIC: str = Field(
        default="cosine",
        description="Distance metric for pgvector search (cosine, l2, inner_product)",
    )
    RETRIEVAL_TOP_K: int = Field(default=8, ge=1, description="Default top K chunks to retrieve")
    RETRIEVAL_MIN_SCORE: float = Field(
        default=0.20, ge=0.0, le=1.0, description="Minimum similarity score threshold"
    )
    MAX_RAG_CONTEXT_CHUNKS: int = Field(
        default=12, ge=1, description="Maximum chunks included in RAG context"
    )
    RAG_CONTEXT_MAX_CHARS: int = Field(
        default=12000, ge=100, description="Maximum character budget for RAG context"
    )

    # ---- JWT / Security -----------------------------------------------------
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, ge=5)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1)

    # ---- Rate Limiting ------------------------------------------------------
    RATE_LIMIT_ENABLED: bool = Field(default=True)
    RATE_LIMIT_UPLOAD: str = Field(default="10/minute")
    RATE_LIMIT_SEARCH: str = Field(default="30/minute")
    RATE_LIMIT_ANALYSIS: str = Field(default="10/minute")
    RATE_LIMIT_ASK: str = Field(default="15/minute", description="Rate limit for grounded Q&A")

    # ---- Pagination Limits --------------------------------------------------
    MAX_PAGE_SIZE: int = Field(default=100, ge=1, le=500)
    DEFAULT_PAGE_SIZE: int = Field(default=20, ge=1, le=100)

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if isinstance(v, str):
            if v.startswith("postgres://"):
                v = v.replace("postgres://", "postgresql+asyncpg://", 1)
            elif v.startswith("postgresql://") and not v.startswith("postgresql+asyncpg://"):
                v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
            parsed = urllib.parse.urlsplit(v)
            if parsed.query:
                params = urllib.parse.parse_qs(parsed.query)
                needs_ssl = False
                if "sslmode" in params:
                    sslmode = params["sslmode"][0]
                    if sslmode in ("require", "verify-ca", "verify-full", "prefer"):
                        needs_ssl = True
                if "ssl" in params:
                    needs_ssl = True
                new_query = "ssl=require" if needs_ssl else ""
                v = urllib.parse.urlunsplit(
                    (parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment)
                )
        if not isinstance(v, str) or not v.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must use the postgresql+asyncpg:// scheme for async support"
            )
        return v

    @field_validator("MIGRATION_DATABASE_URL", mode="before")
    @classmethod
    def validate_migration_database_url(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            if v.startswith("postgres://"):
                v = v.replace("postgres://", "postgresql+asyncpg://", 1)
            elif v.startswith("postgresql://") and not v.startswith("postgresql+asyncpg://"):
                v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
            parsed = urllib.parse.urlsplit(v)
            if parsed.query:
                params = urllib.parse.parse_qs(parsed.query)
                needs_ssl = False
                if "sslmode" in params:
                    sslmode = params["sslmode"][0]
                    if sslmode in ("require", "verify-ca", "verify-full", "prefer"):
                        needs_ssl = True
                if "ssl" in params:
                    needs_ssl = True
                new_query = "ssl=require" if needs_ssl else ""
                v = urllib.parse.urlunsplit(
                    (parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment)
                )
        return v

    @model_validator(mode="after")
    def resolve_celery_defaults(self) -> "Settings":
        """Default Celery URLs to REDIS_URL if not explicitly set."""
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.REDIS_URL
        if not self.CELERY_RESULT_BACKEND:
            self.CELERY_RESULT_BACKEND = self.REDIS_URL
        return self

    @model_validator(mode="after")
    def validate_production_config(self) -> "Settings":
        """Validate that production environment does not use insecure default secrets."""
        if self.ENVIRONMENT == "production":
            insecure_keywords = ["change-me", "default", "example", "dummy", "test-key"]
            if (
                any(kw in self.SECRET_KEY.lower() for kw in insecure_keywords)
                or self.SECRET_KEY.lower() == "secret"
            ):
                raise ValueError("Insecure SECRET_KEY detected in production environment")
            if "postgres:postgres" in self.DATABASE_URL:
                raise ValueError("Default database credentials detected in production environment")
            if any(kw in self.SUPABASE_SERVICE_ROLE_KEY.lower() for kw in insecure_keywords):
                raise ValueError(
                    "Insecure SUPABASE_SERVICE_ROLE_KEY detected in production environment"
                )
            if (
                self.LLM_PROVIDER not in ("mock",)
                and not self.LLM_API_KEY
                and not self.GROQ_API_KEY
            ):
                raise ValueError(
                    f"LLM API key must be configured in production mode for provider "
                    f"'{self.LLM_PROVIDER}'"
                )
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        """Return parsed list of CORS origins."""
        if not self.CORS_ORIGINS or self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

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
