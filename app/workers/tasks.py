"""Celery tasks for async contract processing.

All task definitions live here. Celery tasks create their own database
sessions (independent of FastAPI request scope) and call domain services.
"""

import asyncio
import uuid
from typing import Any

from celery import Task
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.exceptions import StorageError, ValidationError
from app.core.logging import get_logger
from app.services import processing_service
from app.services.document_extractor import DocumentExtractionError
from app.workers.celery_app import celery_app

logger = get_logger(__name__)

# Transient error tuple for Celery retries
TRANSIENT_ERRORS = (StorageError, ConnectionError, TimeoutError, OSError)


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="app.workers.tasks.process_contract_job",
    max_retries=3,
    default_retry_delay=5,
)
def process_contract_job(self: Task, job_id: str) -> dict[str, Any]:
    """Celery worker task to process an uploaded contract document.

    Args:
        job_id: String representation of the ProcessingJob UUID.

    Returns:
        Summary dict of task execution.
    """
    logger.info("Starting process_contract_job task", job_id=job_id)
    job_uuid = uuid.UUID(job_id)
    settings = get_settings()

    async def _run() -> None:
        engine = create_async_engine(settings.DATABASE_URL)
        async_session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session_factory() as session:
            await processing_service.process_contract(session, job_uuid)
        await engine.dispose()

    try:
        asyncio.run(_run())
        logger.info("Completed process_contract_job task", job_id=job_id)
        return {"job_id": job_id, "status": "completed"}
    except TRANSIENT_ERRORS as exc:
        logger.warning(
            "Transient error during process_contract_job, scheduling retry",
            job_id=job_id,
            attempt=self.request.retries + 1,
            exc_info=exc,
        )
        try:
            raise self.retry(exc=exc, countdown=5 * (2**self.request.retries))
        except self.MaxRetriesExceededError:
            logger.error(
                "Max retries exceeded for process_contract_job",
                job_id=job_id,
                exc_info=exc,
            )
            return {"job_id": job_id, "status": "failed", "error": str(exc)}
    except (DocumentExtractionError, ValidationError) as exc:
        # Permanent validation error — handled and marked failed in processing_service
        logger.error(
            "Permanent validation error in process_contract_job (no retry)",
            job_id=job_id,
            exc_info=exc,
        )
        return {"job_id": job_id, "status": "failed", "error": str(exc)}
    except Exception as exc:
        logger.error(
            "Unexpected error in process_contract_job",
            job_id=job_id,
            exc_info=exc,
        )
        return {"job_id": job_id, "status": "failed", "error": str(exc)}
