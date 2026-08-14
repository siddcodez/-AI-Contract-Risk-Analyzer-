"""Tests for production configuration validation and environment checks."""

import pytest
from app.core.config import Settings
from pydantic import ValidationError


def test_development_config_valid() -> None:
    settings = Settings(
        ENVIRONMENT="development",
        SECRET_KEY="min-length-32-chars-dev-secret-key-12345",
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/testdb",
        REDIS_URL="redis://localhost:6379/0",
        MINIO_ENDPOINT="http://localhost:9000",
        MINIO_ACCESS_KEY="minioadmin",
        MINIO_SECRET_KEY="minioadmin",
    )
    assert settings.is_development
    assert not settings.is_production


def test_production_config_rejects_insecure_secret_key() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="insecure-default-secret-key-1234567890",
            DATABASE_URL="postgresql+asyncpg://produser:prodpass@db.prod:5432/proddb",
            REDIS_URL="redis://redis.prod:6379/0",
            MINIO_ENDPOINT="https://s3.amazonaws.com",
            MINIO_ACCESS_KEY="PRODACCESSKEY",
            MINIO_SECRET_KEY="PRODSECRETKEY12345",
        )
    assert "Insecure SECRET_KEY" in str(exc_info.value)


def test_production_config_rejects_default_db_credentials() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="super-secure-production-random-jwt-key-99999",
            DATABASE_URL="postgresql+asyncpg://postgres:postgres@db.prod:5432/proddb",
            REDIS_URL="redis://redis.prod:6379/0",
            MINIO_ENDPOINT="https://s3.amazonaws.com",
            MINIO_ACCESS_KEY="PRODACCESSKEY",
            MINIO_SECRET_KEY="PRODSECRETKEY12345",
        )
    assert "Default database credentials" in str(exc_info.value)


def test_production_config_rejects_default_minio_credentials() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="super-secure-production-random-jwt-key-99999",
            DATABASE_URL="postgresql+asyncpg://produser:prodpass@db.prod:5432/proddb",
            REDIS_URL="redis://redis.prod:6379/0",
            MINIO_ENDPOINT="https://s3.amazonaws.com",
            MINIO_ACCESS_KEY="minioadmin",
            MINIO_SECRET_KEY="minioadmin",
        )
    assert "Default MinIO/S3 credentials" in str(exc_info.value)


def test_production_config_requires_llm_api_key_when_not_mock() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="super-secure-production-random-jwt-key-99999",
            DATABASE_URL="postgresql+asyncpg://produser:prodpass@db.prod:5432/proddb",
            REDIS_URL="redis://redis.prod:6379/0",
            MINIO_ENDPOINT="https://s3.amazonaws.com",
            MINIO_ACCESS_KEY="PRODACCESSKEY",
            MINIO_SECRET_KEY="PRODSECRETKEY12345",
            LLM_PROVIDER="openai",
            LLM_API_KEY=None,
        )
    assert "LLM_API_KEY must be configured" in str(exc_info.value)
