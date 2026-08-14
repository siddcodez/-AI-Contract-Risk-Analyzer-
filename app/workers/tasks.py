"""Celery tasks for async contract processing.

All task definitions live here. Celery tasks create their own database
sessions (independent of FastAPI request scope) and call domain services.
"""

import asyncio
import os
import uuid
from typing import Any

from celery import Task
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.exceptions import StorageError, ValidationError
from app.core.logging import (
    clear_correlation_context,
    get_logger,
    set_correlation_context,
)
from app.services import analysis_service, processing_service
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
def process_contract_job(self: Task, job_id: str, request_id: str | None = None) -> dict[str, Any]:
    """Celery worker task to process an uploaded contract document.

    Args:
        job_id: String representation of the ProcessingJob UUID.
        request_id: Optional HTTP correlation request ID.

    Returns:
        Summary dict of task execution.
    """
    task_id = getattr(getattr(self, "request", None), "id", None) or str(uuid.uuid4())
    _ = set_correlation_context(
        request_id=request_id,
        job_id=job_id,
    )
    logger.info("Starting process_contract_job task", job_id=job_id, task_id=task_id)
    job_uuid = uuid.UUID(job_id)
    settings = get_settings()

    async def _run() -> None:
        db_url = os.environ.get("MIGRATION_DATABASE_URL") or settings.DATABASE_URL
        engine = create_async_engine(db_url)
        async_session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session_factory() as session:
            await processing_service.process_contract(session, job_uuid)
        await engine.dispose()

    retries = getattr(getattr(self, "request", None), "retries", 0)
    try:
        try:
            asyncio.run(_run())
            logger.info("Completed process_contract_job task", job_id=job_id, task_id=task_id)
            return {"job_id": job_id, "task_id": task_id, "status": "completed"}
        except TRANSIENT_ERRORS as exc:
            logger.warning(
                "Transient error during process_contract_job, scheduling retry",
                job_id=job_id,
                task_id=task_id,
                attempt=retries + 1,
                exc_info=exc,
            )
            try:
                retry_fn = getattr(self, "retry", None)
                if retry_fn:
                    raise retry_fn(exc=exc, countdown=5 * (2**retries))
                return {
                    "job_id": job_id,
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(exc),
                }
            except getattr(self, "MaxRetriesExceededError", Exception):
                logger.error(
                    "Max retries exceeded for process_contract_job",
                    job_id=job_id,
                    task_id=task_id,
                    exc_info=exc,
                )
                return {
                    "job_id": job_id,
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(exc),
                }
        except (DocumentExtractionError, ValidationError) as exc:
            # Permanent validation error — handled and marked failed in processing_service
            logger.error(
                "Permanent validation error in process_contract_job (no retry)",
                job_id=job_id,
                task_id=task_id,
                exc_info=exc,
            )
            return {
                "job_id": job_id,
                "task_id": task_id,
                "status": "failed",
                "error": str(exc),
            }
        except Exception as exc:
            logger.error(
                "Unexpected error in process_contract_job",
                job_id=job_id,
                task_id=task_id,
                exc_info=exc,
            )
            return {
                "job_id": job_id,
                "task_id": task_id,
                "status": "failed",
                "error": str(exc),
            }
    finally:
        clear_correlation_context()


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="app.workers.tasks.analyze_contract_job",
    max_retries=3,
    default_retry_delay=5,
)
def analyze_contract_job(
    self: Task, analysis_job_id: str, request_id: str | None = None
) -> dict[str, Any]:
    """Celery worker task to execute contract risk analysis.

    Args:
        analysis_job_id: String representation of the AnalysisJob UUID.
        request_id: Optional HTTP correlation request ID.

    Returns:
        Summary dict of task execution.
    """
    task_id = getattr(getattr(self, "request", None), "id", None) or str(uuid.uuid4())
    _ = set_correlation_context(
        request_id=request_id,
        analysis_job_id=analysis_job_id,
    )
    logger.info(
        "Starting analyze_contract_job task",
        analysis_job_id=analysis_job_id,
        task_id=task_id,
    )
    job_uuid = uuid.UUID(analysis_job_id)
    settings = get_settings()

    async def _run() -> None:
        db_url = os.environ.get("MIGRATION_DATABASE_URL") or settings.DATABASE_URL
        engine = create_async_engine(db_url)
        async_session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session_factory() as session:
            await analysis_service.analyze_contract(session, job_uuid)
        await engine.dispose()

    retries = getattr(getattr(self, "request", None), "retries", 0)
    try:
        try:
            asyncio.run(_run())
            logger.info(
                "Completed analyze_contract_job task",
                analysis_job_id=analysis_job_id,
                task_id=task_id,
            )
            return {
                "analysis_job_id": analysis_job_id,
                "task_id": task_id,
                "status": "completed",
            }
        except TRANSIENT_ERRORS as exc:
            logger.warning(
                "Transient error during analyze_contract_job, scheduling retry",
                analysis_job_id=analysis_job_id,
                task_id=task_id,
                attempt=retries + 1,
                exc_info=exc,
            )
            try:
                retry_fn = getattr(self, "retry", None)
                if retry_fn:
                    raise retry_fn(exc=exc, countdown=5 * (2**retries))
                return {
                    "analysis_job_id": analysis_job_id,
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(exc),
                }
            except getattr(self, "MaxRetriesExceededError", Exception):
                logger.error(
                    "Max retries exceeded for analyze_contract_job",
                    analysis_job_id=analysis_job_id,
                    task_id=task_id,
                    exc_info=exc,
                )
                return {
                    "analysis_job_id": analysis_job_id,
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(exc),
                }
        except (DocumentExtractionError, ValidationError) as exc:
            # Permanent validation error — handled and marked failed in analysis_service
            logger.error(
                "Permanent validation error in analyze_contract_job (no retry)",
                analysis_job_id=analysis_job_id,
                task_id=task_id,
                exc_info=exc,
            )
            return {
                "analysis_job_id": analysis_job_id,
                "task_id": task_id,
                "status": "failed",
                "error": str(exc),
            }
        except Exception as exc:
            logger.error(
                "Unexpected error in analyze_contract_job",
                analysis_job_id=analysis_job_id,
                task_id=task_id,
                exc_info=exc,
            )
            return {
                "analysis_job_id": analysis_job_id,
                "task_id": task_id,
                "status": "failed",
                "error": str(exc),
            }
    finally:
        clear_correlation_context()
