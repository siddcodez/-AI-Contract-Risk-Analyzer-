"""Repository for ReportJob database operations.

report_jobs table HAS RLS enabled — all queries are subject to the
tenant_isolation policy.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report_job import ReportJob, ReportJobStatus


async def create(
    session: AsyncSession,
    *,
    contract_id: uuid.UUID,
    version_id: uuid.UUID,
    org_id: uuid.UUID,
) -> ReportJob:
    """Create a new report generation job record.

    Subject to RLS WITH CHECK.
    """
    job = ReportJob(
        id=uuid.uuid4(),
        contract_id=contract_id,
        version_id=version_id,
        org_id=org_id,
        status=ReportJobStatus.queued,
    )
    session.add(job)
    await session.flush()
    return job


async def get_by_id(
    session: AsyncSession,
    job_id: uuid.UUID,
) -> ReportJob | None:
    """Fetch a report job by ID.

    Subject to RLS.
    """
    result = await session.execute(select(ReportJob).where(ReportJob.id == job_id))
    return result.scalars().first()


async def get_latest_by_contract_and_version(
    session: AsyncSession,
    contract_id: uuid.UUID,
    version_id: uuid.UUID,
) -> ReportJob | None:
    """Fetch the latest report generation job for a contract version.

    Subject to RLS.
    """
    result = await session.execute(
        select(ReportJob)
        .where(
            ReportJob.contract_id == contract_id,
            ReportJob.version_id == version_id,
        )
        .order_by(ReportJob.created_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def update_status(
    session: AsyncSession,
    job: ReportJob,
    status: str | ReportJobStatus,
    *,
    storage_key: str | None = None,
    file_size: int | None = None,
    error_message: str | None = None,
) -> ReportJob:
    """Update job lifecycle status and artifact storage details.

    Subject to RLS.
    """
    status_str = status.value if isinstance(status, ReportJobStatus) else str(status)
    job.status = status_str

    if status_str == ReportJobStatus.processing and not job.started_at:
        job.started_at = datetime.now(UTC)
    elif status_str in (ReportJobStatus.completed, ReportJobStatus.failed):
        job.completed_at = datetime.now(UTC)

    if storage_key is not None:
        job.storage_key = storage_key
    if file_size is not None:
        job.file_size = file_size
    if error_message is not None:
        job.error_message = error_message

    await session.flush()
    return job
