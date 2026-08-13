"""Contract management service — upload orchestration and retrieval.

Orchestrates file validation, object storage, and database operations
for contract upload and management.  Controllers call this service;
this service calls repositories and other services.

No HTTP or FastAPI types appear here — only domain objects and schemas.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.contract import Contract
from app.models.user import User
from app.repositories import contract_repo, contract_version_repo, processing_job_repo
from app.schemas.contract import (
    ContractListResponse,
    ContractResponse,
    ContractStatusResponse,
    ContractUploadResponse,
)
from app.services import storage_service
from app.services.file_validator import ValidatedFile

logger = get_logger(__name__)


async def upload_contract(
    session: AsyncSession,
    *,
    user: User,
    file_data: bytes,
    validated: ValidatedFile,
    title: str | None = None,
) -> ContractUploadResponse:
    """Upload a contract: store in MinIO, create DB records.

    Flow:
        1. Generate a safe object key.
        2. Upload file to MinIO.
        3. Create Contract record (status=pending).
        4. Create ContractVersion (version 1).
        5. Create ProcessingJob (status=queued).
        6. Return upload response.

    Args:
        session: Database session (tenant context already set).
        user: Authenticated user performing the upload.
        file_data: Raw validated file bytes.
        validated: Validated file metadata.
        title: Optional display title (defaults to filename).

    Returns:
        ContractUploadResponse with contract_id and job_id.
    """
    contract_id = uuid.uuid4()
    display_title = title or validated.sanitized_name

    # 1. Generate storage key: {org_id}/{contract_id}/{filename}
    storage_key = f"{user.org_id}/{contract_id}/{validated.sanitized_name}"

    # 2. Upload to MinIO
    storage_service.upload_file(
        file_data=file_data,
        key=storage_key,
        content_type=validated.content_type,
    )

    # 3. Create Contract record
    contract = await contract_repo.create(
        session,
        title=display_title,
        file_name=validated.sanitized_name,
        file_size=validated.file_size,
        content_type=validated.content_type,
        storage_key=storage_key,
        org_id=user.org_id,
        uploaded_by=user.id,
    )
    # Use the repo-generated ID
    contract_id = contract.id

    # 4. Create ContractVersion (version 1)
    await contract_version_repo.create(
        session,
        contract_id=contract_id,
        version_number=1,
        file_name=validated.sanitized_name,
        file_size=validated.file_size,
        content_type=validated.content_type,
        storage_key=storage_key,
        org_id=user.org_id,
    )

    # 5. Create ProcessingJob
    job = await processing_job_repo.create(
        session,
        contract_id=contract_id,
        org_id=user.org_id,
    )

    logger.info(
        "Contract uploaded",
        contract_id=str(contract_id),
        job_id=str(job.id),
        file_name=validated.sanitized_name,
        file_size=validated.file_size,
        org_id=str(user.org_id),
    )

    return ContractUploadResponse(
        contract_id=contract_id,
        job_id=job.id,
        status=job.status.value,
        file_name=validated.sanitized_name,
        file_size=validated.file_size,
        content_type=validated.content_type,
        created_at=contract.created_at,
    )


async def get_contract(
    session: AsyncSession,
    contract_id: uuid.UUID,
) -> ContractResponse:
    """Fetch a single contract by ID.

    Subject to RLS — caller must set tenant context first.

    Raises:
        NotFoundError: If the contract does not exist.
    """
    contract = await contract_repo.get_by_id(session, contract_id)
    if contract is None:
        raise NotFoundError("Contract not found")
    return _contract_to_response(contract)


async def list_contracts(
    session: AsyncSession,
    org_id: uuid.UUID,
    *,
    skip: int = 0,
    limit: int = 20,
) -> ContractListResponse:
    """List contracts for the current organization with pagination.

    Subject to RLS — caller must set tenant context first.
    """
    contracts = await contract_repo.list_by_org(session, org_id, skip=skip, limit=limit)
    total = await contract_repo.count_by_org(session, org_id)
    return ContractListResponse(
        contracts=[_contract_to_response(c) for c in contracts],
        total=total,
        skip=skip,
        limit=limit,
    )


async def get_contract_status(
    session: AsyncSession,
    contract_id: uuid.UUID,
) -> ContractStatusResponse:
    """Get the processing status of a contract.

    Subject to RLS — caller must set tenant context first.

    Raises:
        NotFoundError: If the contract does not exist.
    """
    contract = await contract_repo.get_by_id(session, contract_id)
    if contract is None:
        raise NotFoundError("Contract not found")

    job = await processing_job_repo.get_by_contract_id(session, contract_id)

    return ContractStatusResponse(
        contract_id=contract.id,
        contract_status=contract.status.value,
        job_id=job.id if job else None,
        job_status=job.status.value if job else None,
        error_message=job.error_message if job else None,
    )


def _contract_to_response(contract: Contract) -> ContractResponse:
    """Map a Contract ORM model to its API response schema."""
    return ContractResponse(
        id=contract.id,
        title=contract.title,
        file_name=contract.file_name,
        file_size=contract.file_size,
        content_type=contract.content_type,
        status=contract.status.value,
        org_id=contract.org_id,
        uploaded_by=contract.uploaded_by,
        created_at=contract.created_at,
        updated_at=contract.updated_at,
    )
