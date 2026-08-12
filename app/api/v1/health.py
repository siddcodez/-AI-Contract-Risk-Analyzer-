"""Health check endpoint.

GET /api/v1/health

Pings all backing services (DB, Redis, MinIO) and returns per-service status.
The endpoint itself returns 200 even when a dependency is degraded — operators
can see *which* service is down without the load balancer removing the app
instance from rotation when it's the DB that's at fault.

Response schema:
    {
        "status": "ok" | "degraded",
        "version": "0.1.0",
        "environment": "development",
        "services": {
            "db": "ok" | "error",
            "redis": "ok" | "error",
            "storage": "ok" | "error"
        }
    }
"""

import boto3
import redis.asyncio as aioredis
from botocore.exceptions import ClientError
from fastapi import APIRouter
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
        # 404 means the bucket doesn't exist yet — still reachable
        if error_code == "404":
            return True
        logger.warning("Storage health check failed", exc_info=exc)
        return False
    except Exception as exc:
        logger.warning("Storage health check failed", exc_info=exc)
        return False


@router.get(
    "/health",
    summary="Health check",
    description=(
        "Returns the operational status of the application and all backing services. "
        "Always returns HTTP 200; inspect `status` and `services` fields for detail."
    ),
    response_description="Health status of the application and its dependencies",
)
async def health_check() -> JSONResponse:
    """Check the health of all backing services."""
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

    logger.info("Health check", status=overall, **services)

    return JSONResponse(
        status_code=200,  # always 200 — see module docstring
        content={
            "status": overall,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "services": services,
        },
    )
