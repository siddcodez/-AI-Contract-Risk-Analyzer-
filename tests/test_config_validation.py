"""Tests for production configuration validation and environment checks."""

import pytest
from app.core.config import Settings
from pydantic import ValidationError


def test_development_config_valid() -> None:
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="development",
        SECRET_KEY="min-length-32-chars-dev-secret-key-12345",
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/testdb",
        REDIS_URL="redis://localhost:6379/0",
        SUPABASE_URL="https://test-project.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="test-service-role-key-12345",
    )
    assert settings.is_development
    assert not settings.is_production
    assert settings.SUPABASE_STORAGE_BUCKET == "contract-documents"
    assert settings.CELERY_BROKER_URL == "redis://localhost:6379/0"
    assert settings.CELERY_RESULT_BACKEND == "redis://localhost:6379/0"


def test_jwt_secret_alias_resolution() -> None:
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="development",
        JWT_SECRET="min-length-32-chars-jwt-secret-from-render-12345",
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/testdb",
        REDIS_URL="redis://localhost:6379/0",
        SUPABASE_URL="https://test-project.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="test-service-role-key-12345",
    )
    assert settings.SECRET_KEY == "min-length-32-chars-jwt-secret-from-render-12345"


def test_database_url_normalization() -> None:
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="development",
        SECRET_KEY="min-length-32-chars-dev-secret-key-12345",
        DATABASE_URL="postgres://neon_user:neon_pass@ep-xyz.aws.neon.tech/neondb",
        REDIS_URL="redis://localhost:6379/0",
        SUPABASE_URL="https://test-project.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="test-service-role-key-12345",
    )
    assert settings.DATABASE_URL.startswith("postgresql+asyncpg://")
    assert "neon_user:neon_pass" in settings.DATABASE_URL


def test_celery_defaults_to_redis_url() -> None:
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="development",
        SECRET_KEY="min-length-32-chars-dev-secret-key-12345",
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/testdb",
        REDIS_URL="rediss://default:upstashpass@global-upstash.io:6379",
        SUPABASE_URL="https://test-project.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="test-service-role-key-12345",
    )
    assert settings.CELERY_BROKER_URL == "rediss://default:upstashpass@global-upstash.io:6379"
    assert settings.CELERY_RESULT_BACKEND == "rediss://default:upstashpass@global-upstash.io:6379"


def test_production_config_rejects_insecure_secret_key() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            SECRET_KEY="change-me-to-a-random-64-char-hex-string",
            DATABASE_URL="postgresql+asyncpg://produser:prodpass@db.prod:5432/proddb",
            REDIS_URL="redis://redis.prod:6379/0",
            SUPABASE_URL="https://prod.supabase.co",
            SUPABASE_SERVICE_ROLE_KEY="supabase-prod-service-role-key-99999",
        )
    assert "Insecure SECRET_KEY" in str(exc_info.value)


def test_production_config_rejects_default_db_credentials() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            SECRET_KEY="super-secure-production-random-jwt-key-99999",
            DATABASE_URL="postgresql+asyncpg://postgres:postgres@db.prod:5432/proddb",
            REDIS_URL="redis://redis.prod:6379/0",
            SUPABASE_URL="https://prod.supabase.co",
            SUPABASE_SERVICE_ROLE_KEY="supabase-prod-service-role-key-99999",
        )
    assert "Default database credentials" in str(exc_info.value)


def test_production_config_rejects_insecure_supabase_key() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            SECRET_KEY="super-secure-production-random-jwt-key-99999",
            DATABASE_URL="postgresql+asyncpg://produser:prodpass@db.prod:5432/proddb",
            REDIS_URL="redis://redis.prod:6379/0",
            SUPABASE_URL="https://prod.supabase.co",
            SUPABASE_SERVICE_ROLE_KEY="default-secret-change-me",
        )
    assert "Insecure SUPABASE_SERVICE_ROLE_KEY" in str(exc_info.value)


def test_production_config_requires_llm_api_key_when_not_mock() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            SECRET_KEY="super-secure-production-random-jwt-key-99999",
            DATABASE_URL="postgresql+asyncpg://produser:prodpass@db.prod:5432/proddb",
            REDIS_URL="redis://redis.prod:6379/0",
            SUPABASE_URL="https://prod.supabase.co",
            SUPABASE_SERVICE_ROLE_KEY="supabase-prod-service-role-key-99999",
            LLM_PROVIDER="openai",
            LLM_API_KEY=None,
            GROQ_API_KEY=None,
        )
    assert "LLM API key must be configured" in str(exc_info.value)
