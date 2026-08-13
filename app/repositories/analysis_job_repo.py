"""Repository for AnalysisJob DB operations.

analysis_jobs table HAS RLS enabled — all queries are subject to tenant_isolation policy.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis_job import AnalysisJob, AnalysisJobStatus


async def create(
    session: AsyncSession,
    *,
    contract_id: uuid.UUID,
    version_id: uuid.UUID,
    org_id: uuid.UUID,
) -> AnalysisJob:
    """Create a new AnalysisJob in queued status.

    Subject to RLS WITH CHECK — caller must set tenant context first.
    """
    job = AnalysisJob(
        id=uuid.uuid4(),
        contract_id=contract_id,
        version_id=version_id,
        org_id=org_id,
        status=AnalysisJobStatus.queued,
    )
    session.add(job)
    await session.flush()
    return job


async def get_by_id(
    session: AsyncSession,
    job_id: uuid.UUID,
) -> AnalysisJob | None:
    """Fetch an analysis job by primary key.

    Subject to RLS — caller must set tenant context first.
    """
    result = await session.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    return result.scalars().first()


async def get_latest_by_contract(
    session: AsyncSession,
    contract_id: uuid.UUID,
) -> AnalysisJob | None:
    """Fetch the latest analysis job for a contract.

    Subject to RLS — caller must set tenant context first.
    """
    result = await session.execute(
        select(AnalysisJob)
        .where(AnalysisJob.contract_id == contract_id)
        .order_by(AnalysisJob.created_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def update_status(
    session: AsyncSession,
    job_id: uuid.UUID,
    status: AnalysisJobStatus,
    *,
    error_message: str | None = None,
    findings_count: int | None = None,
) -> AnalysisJob | None:
    """Update the status, error message, and findings count of an analysis job.

    Subject to RLS — caller must set tenant context first.
    """
    job = await get_by_id(session, job_id)
    if job is None:
        return None

    job.status = status
    if error_message is not None:
        job.error_message = error_message
    if findings_count is not None:
        job.findings_count = findings_count

    await session.flush()
    return job
