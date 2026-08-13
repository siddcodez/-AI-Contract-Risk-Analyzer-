"""Repository for ProcessingJob operations.

processing_jobs has RLS enabled — all queries are filtered by
the tenant_isolation policy.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.processing_job import JobStatus, ProcessingJob


async def create(
    session: AsyncSession,
    *,
    contract_id: uuid.UUID,
    org_id: uuid.UUID,
) -> ProcessingJob:
    """Create a new processing job in queued status.

    Subject to RLS WITH CHECK — caller must set tenant context first.
    """
    job = ProcessingJob(
        id=uuid.uuid4(),
        contract_id=contract_id,
        status=JobStatus.queued,
        org_id=org_id,
    )
    session.add(job)
    await session.flush()
    return job


async def get_by_id(
    session: AsyncSession,
    job_id: uuid.UUID,
) -> ProcessingJob | None:
    """Fetch a processing job by primary key.

    Subject to RLS — caller must set tenant context first.
    """
    result = await session.execute(select(ProcessingJob).where(ProcessingJob.id == job_id))
    return result.scalars().first()


async def get_by_contract_id(
    session: AsyncSession,
    contract_id: uuid.UUID,
) -> ProcessingJob | None:
    """Fetch the latest processing job for a contract.

    Returns the most recently created job for the given contract.
    Subject to RLS — caller must set tenant context first.
    """
    result = await session.execute(
        select(ProcessingJob)
        .where(ProcessingJob.contract_id == contract_id)
        .order_by(ProcessingJob.created_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def update_status(
    session: AsyncSession,
    job_id: uuid.UUID,
    status: JobStatus,
    *,
    error_message: str | None = None,
) -> ProcessingJob | None:
    """Update the status of a processing job.

    Subject to RLS — caller must set tenant context first.
    """
    job = await get_by_id(session, job_id)
    if job is None:
        return None
    job.status = status
    if error_message is not None:
        job.error_message = error_message
    await session.flush()
    return job
