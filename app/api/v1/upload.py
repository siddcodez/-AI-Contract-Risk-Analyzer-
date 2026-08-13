"""Contract upload and management endpoints (M2).

POST /api/v1/contracts/upload           — Upload a contract file
GET  /api/v1/contracts/list             — List contracts (paginated)
GET  /api/v1/contracts/{id}/details     — Get contract details
GET  /api/v1/contracts/{id}/status      — Get processing status

All endpoints require authentication.  Upload requires reviewer
or admin role.  Read endpoints are available to any authenticated user.
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_reviewer_or_above
from app.db.session import get_db
from app.models.user import User
from app.schemas.contract import (
    ContractListResponse,
    ContractResponse,
    ContractStatusResponse,
    ContractUploadResponse,
)
from app.services import contract_service
from app.services.file_validator import validate_file

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.post(
    "/upload",
    response_model=ContractUploadResponse,
    status_code=201,
    summary="Upload a contract document",
)
async def upload_contract(
    file: UploadFile = File(..., description="Contract file (PDF, DOCX, or TXT)"),
    title: str = Form(default="", description="Optional display title for the contract"),
    user: User = Depends(require_reviewer_or_above),
    session: AsyncSession = Depends(get_db),
) -> ContractUploadResponse:
    """Upload a contract file for processing.

    The file is validated (type, size, magic bytes), stored in object
    storage, and a processing job is created in queued status.

    Returns the contract_id and job_id for tracking.
    """
    # Read file content
    file_data = await file.read()

    # Validate file
    validated = validate_file(
        filename=file.filename,
        content_type=file.content_type,
        file_data=file_data,
    )

    # Orchestrate upload (creates contract, version, and job in session)
    response = await contract_service.upload_contract(
        session,
        user=user,
        file_data=file_data,
        validated=validated,
        title=title if title else None,
    )

    # Commit transaction to PostgreSQL before enqueuing Celery task
    await session.commit()

    # Enqueue processing task safely post-commit
    try:
        from app.workers.tasks import process_contract_job

        process_contract_job.delay(str(response.job_id))
    except Exception as exc:
        # Non-fatal if Redis/Celery is offline in local dev — job remains queued in DB
        from app.core.logging import get_logger

        get_logger(__name__).warning(
            "Failed to enqueue Celery task post-commit",
            job_id=str(response.job_id),
            exc_info=exc,
        )

    return response


@router.get(
    "/list",
    response_model=ContractListResponse,
    summary="List contracts for the current organization",
)
async def list_contracts(
    skip: int = 0,
    limit: int = 20,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ContractListResponse:
    """List contracts belonging to the current user's organization.

    Supports pagination via skip and limit query parameters.
    """
    return await contract_service.list_contracts(
        session,
        user.org_id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{contract_id}/details",
    response_model=ContractResponse,
    summary="Get contract details",
)
async def get_contract(
    contract_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ContractResponse:
    """Retrieve details of a specific contract.

    RLS ensures the contract belongs to the user's organization.
    """
    _ = user  # Used by get_current_user for auth + RLS context
    return await contract_service.get_contract(session, contract_id)


@router.get(
    "/{contract_id}/status",
    response_model=ContractStatusResponse,
    summary="Get contract processing status",
)
async def get_contract_status(
    contract_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ContractStatusResponse:
    """Check the processing status of a contract and its associated job.

    RLS ensures the contract belongs to the user's organization.
    """
    _ = user  # Used by get_current_user for auth + RLS context
    return await contract_service.get_contract_status(session, contract_id)
