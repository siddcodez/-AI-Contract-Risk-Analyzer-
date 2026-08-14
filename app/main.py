"""FastAPI application entry point.

Defines the app instance, lifespan (startup/shutdown), middleware, and
registers all routers and exception handlers.

Architecture rules enforced here:
- All expensive/blocking work (OCR, LLM, embeddings) happens in Celery workers.
- The HTTP layer only validates, enqueues, and reads pre-computed results.
- Request IDs are injected at the middleware level so every log line is correlated.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import boto3
import redis.asyncio as aioredis
from botocore.exceptions import ClientError
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_v1_router
from app.api.v1.health import router as health_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.db.session import close_db, init_db
from app.middleware.request_id import RequestIDMiddleware

# Configure structured logging before anything else logs
configure_logging()

logger = get_logger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Application lifespan — startup + shutdown
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown resources."""
    logger.info(
        "Starting AI Contract Risk Analyzer",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )

    # 1. Initialise database connection pool
    init_db()

    # 2. Verify Redis connectivity
    try:
        redis_client = aioredis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=5)
        await redis_client.ping()
        await redis_client.aclose()
        logger.info("Redis connection verified")
    except Exception as exc:
        logger.error("Redis connection failed at startup", exc_info=exc)
        raise

    # 3. Ensure MinIO bucket exists (create if absent — idempotent)
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=settings.MINIO_ENDPOINT,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name="us-east-1",
        )
        try:
            s3.head_bucket(Bucket=settings.MINIO_BUCKET_NAME)
            logger.info("Object storage bucket verified", bucket=settings.MINIO_BUCKET_NAME)
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchBucket"):
                s3.create_bucket(Bucket=settings.MINIO_BUCKET_NAME)
                logger.info("Object storage bucket created", bucket=settings.MINIO_BUCKET_NAME)
            else:
                raise
    except Exception as exc:
        logger.error("Object storage check failed at startup", exc_info=exc)
        raise

    logger.info("Startup complete — ready to serve requests")

    yield  # ← application runs here

    # Shutdown
    logger.info("Shutting down — releasing resources")
    await close_db()
    logger.info("Shutdown complete")


# ---------------------------------------------------------------------------
# FastAPI app instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Contract Risk Analyzer",
    description=(
        "Multi-tenant AI-powered contract analysis platform. "
        "Upload contracts, automatically detect risk clauses, evaluate against "
        "your organisation's playbook, and receive structured risk reports."
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan,
    # Disable default /docs in production to reduce attack surface
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestIDMiddleware)


# ---------------------------------------------------------------------------
# Routers & exception handlers
# ---------------------------------------------------------------------------

app.include_router(health_router)
app.include_router(api_v1_router)
register_exception_handlers(app)

# ---------------------------------------------------------------------------
# Static files & root UI route
# ---------------------------------------------------------------------------
_static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/", include_in_schema=False)
async def serve_frontend() -> FileResponse:
    """Serve the frontend SPA at the root URL."""
    return FileResponse(str(_static_dir / "index.html"))
