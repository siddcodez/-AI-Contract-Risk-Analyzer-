"""Contract PDF Reports API endpoints (Phase 12).

POST /api/v1/contracts/{contract_id}/reports/generate
    ?version_id={UUID}
    Triggers an async Celery task to generate an annotated PDF report.
    Returns 202 Accepted. Deduplicates active jobs per (contract_id, version_id).

GET /api/v1/contracts/{contract_id}/reports/latest
    ?version_id={UUID}
    Returns status and storage info for the latest report.

GET /api/v1/contracts/{contract_id}/reports/download
    ?version_id={UUID}
    Streams/downloads the generated PDF file from object storage.
"""

import io
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_reviewer_or_above
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.rate_limit import rate_limit_upload
from app.db.session import get_db
from app.models.report_job import ReportJobStatus
from app.models.user import User
from app.repositories import contract_repo, contract_version_repo, report_job_repo
from app.schemas.report import ReportGenerateResponse, ReportStatusResponse
from app.services import report_service, storage_service

logger = get_logger(__name__)

router = APIRouter(prefix="/contracts", tags=["reports"])


@router.post(
    "/{contract_id}/reports/generate",
    response_model=ReportGenerateResponse,
    status_code=202,
    summary="Trigger async PDF report generation",
    dependencies=[Depends(rate_limit_upload())],
)
async def generate_report(
    contract_id: uuid.UUID,
    version_id: uuid.UUID | None = Query(
        None, description="Target version UUID (defaults to latest)"
    ),
    user: User = Depends(require_reviewer_or_above),
    session: AsyncSession = Depends(get_db),
) -> ReportGenerateResponse:
    """Trigger background generation of an annotated PDF risk report.

    Requires Reviewer or Admin role. Returns 202 Accepted with job info.
    """
    job = await report_service.trigger_report_generation(
        session,
        contract_id=contract_id,
        version_id=version_id,
        org_id=user.org_id,
    )

    # Dispatch Celery background task if newly queued
    if job.status == ReportJobStatus.queued:
        from app.workers.tasks import generate_contract_report_job

        generate_contract_report_job.delay(
            str(job.id),
            user_id=str(user.id),
            user_email=user.email,
        )

    return ReportGenerateResponse(
        contract_id=job.contract_id,
        version_id=job.version_id,
        job_id=job.id,
        status=job.status,
        message="Report generation initiated in the background",
    )


@router.get(
    "/{contract_id}/reports/latest",
    response_model=ReportStatusResponse,
    summary="Get status of latest contract report",
)
async def get_latest_report_status(
    contract_id: uuid.UUID,
    version_id: uuid.UUID | None = Query(
        None, description="Target version UUID (defaults to latest)"
    ),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ReportStatusResponse:
    """Retrieve the latest report status for a contract version.

    Accessible to all authenticated tenant roles (Admin, Reviewer, Viewer).
    """
    _ = user  # RLS active
    contract = await contract_repo.get_by_id(session, contract_id)
    if contract is None:
        raise NotFoundError("Contract not found")

    target_version_id: uuid.UUID
    if version_id is None:
        latest_ver = await contract_version_repo.get_latest_by_contract(session, contract_id)
        if latest_ver is None:
            raise NotFoundError("No versions found for contract")
        target_version_id = latest_ver.id
    else:
        target_version_id = version_id

    job = await report_job_repo.get_latest_by_contract_and_version(
        session, contract_id, target_version_id
    )
    if job is None:
        raise NotFoundError("No report found for this contract version")

    download_url = (
        f"/api/v1/contracts/{contract_id}/reports/download?version_id={target_version_id}"
        if job.status == ReportJobStatus.completed
        else None
    )

    return ReportStatusResponse(
        id=job.id,
        contract_id=job.contract_id,
        version_id=job.version_id,
        status=job.status,
        storage_key=job.storage_key,
        file_size=job.file_size,
        error_message=job.error_message,
        download_url=download_url,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


@router.get(
    "/{contract_id}/reports/download",
    summary="Download generated PDF report",
)
async def download_report(
    contract_id: uuid.UUID,
    version_id: uuid.UUID | None = Query(
        None, description="Target version UUID (defaults to latest)"
    ),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Download the completed annotated PDF report file from object storage.

    Accessible to all authenticated tenant roles (Admin, Reviewer, Viewer).
    """
    _ = user  # RLS active
    contract = await contract_repo.get_by_id(session, contract_id)
    if contract is None:
        raise NotFoundError("Contract not found")

    target_version_id: uuid.UUID
    if version_id is None:
        latest_ver = await contract_version_repo.get_latest_by_contract(session, contract_id)
        if latest_ver is None:
            raise NotFoundError("No versions found for contract")
        target_version_id = latest_ver.id
    else:
        target_version_id = version_id

    job = await report_job_repo.get_latest_by_contract_and_version(
        session, contract_id, target_version_id
    )
    if job is None or job.status != ReportJobStatus.completed or not job.storage_key:
        raise NotFoundError("Report PDF is not available or has not finished generating")

    file_bytes = storage_service.download_file(key=job.storage_key)
    filename = f"ContractIQ_Report_{contract.title.replace(' ', '_')}.pdf"

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
