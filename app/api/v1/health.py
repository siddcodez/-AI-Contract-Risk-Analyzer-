"""Health and readiness endpoints for observability & liveness probes.

Endpoints:
- GET /health  (Liveness probe: fast, lightweight, no DB calls)
- GET /ready   (Readiness probe: checks PostgreSQL, Redis, MinIO/S3, returns 200 or 503)
- GET /api/v1/health (Legacy M1-M5 status check endpoint)
- GET /api/v1/ready
"""

import asyncio

import boto3
import redis.asyncio as aioredis
from botocore.exceptions import ClientError
from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import check_db_connection

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


async def _check_redis() -> bool:
    """Ping Redis. Returns True on success."""
    settings = get_settings()
    try:
        client = aioredis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await client.ping()
        await client.aclose()
        return True
    except Exception as exc:
        logger.warning("Redis health check failed", exc_info=exc)
        return False


async def _check_storage() -> bool:
    """Head the MinIO/S3 bucket. Returns True on success."""
    settings = get_settings()
    try:
        client = boto3.client(
            "s3",
            endpoint_url=settings.MINIO_ENDPOINT,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name="us-east-1",
        )
        client.head_bucket(Bucket=settings.MINIO_BUCKET_NAME)
        return True
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        if error_code == "404":
            return True
        logger.warning("Storage health check failed", exc_info=exc)
        return False
    except Exception as exc:
        logger.warning("Storage health check failed", exc_info=exc)
        return False


async def _check_celery_worker() -> bool:
    """Ping Celery workers. Returns True if at least one worker responds."""
    try:
        from app.workers.celery_app import celery_app

        loop = asyncio.get_running_loop()
        responses = await loop.run_in_executor(None, lambda: celery_app.control.ping(timeout=0.5))
        return bool(responses)
    except Exception as exc:
        logger.warning("Celery worker health check failed", exc_info=exc)
        return False


@router.get(
    "/health",
    summary="Liveness probe",
    description="Lightweight liveness check. Returns HTTP 200 if process is running.",
)
async def liveness_check() -> JSONResponse:
    """Lightweight liveness probe (no external dependency checks)."""
    settings = get_settings()
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "ok",
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
        },
    )


@router.get(
    "/ready",
    summary="Readiness probe",
    description="Verifies PostgreSQL, Redis, and MinIO storage connectivity. Returns 200 or 503.",
)
async def readiness_check(
    include_workers: bool = Query(
        default=False, description="Include Celery worker ping in status"
    ),
) -> JSONResponse:
    """Readiness probe checking backing services."""
    settings = get_settings()

    db_ok = await check_db_connection()
    redis_ok = await _check_redis()
    storage_ok = await _check_storage()

    dependencies: dict[str, str] = {
        "database": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "error",
        "storage": "ok" if storage_ok else "error",
    }

    if include_workers:
        worker_ok = await _check_celery_worker()
        dependencies["workers"] = "ok" if worker_ok else "degraded"

    all_required_ok = db_ok and redis_ok and storage_ok
    overall_status = "ok" if all_required_ok else "degraded"
    status_code = status.HTTP_200_OK if all_required_ok else status.HTTP_503_SERVICE_UNAVAILABLE

    logger.info("Readiness check", status=overall_status, **dependencies)

    return JSONResponse(
        status_code=status_code,
        content={
            "status": overall_status,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "dependencies": dependencies,
        },
    )


@router.get(
    "/api/v1/health",
    include_in_schema=False,
    summary="Legacy M1-M5 health check",
)
async def legacy_health_check() -> JSONResponse:
    """Legacy endpoint for M1-M5 test backwards compatibility."""
    settings = get_settings()

    db_ok = await check_db_connection()
    redis_ok = await _check_redis()
    storage_ok = await _check_storage()

    services = {
        "db": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "error",
        "storage": "ok" if storage_ok else "error",
    }

    all_ok = all(v == "ok" for v in services.values())
    overall = "ok" if all_ok else "degraded"

    return JSONResponse(
        status_code=200,
        content={
            "status": overall,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "services": services,
        },
    )
