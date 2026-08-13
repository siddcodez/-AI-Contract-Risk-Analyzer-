"""Contract async processing service.

Orchestrates contract text extraction, chunking, embedding generation,
and DB persistence for an async ProcessingJob. Transitions status through:
queued → processing → completed | failed.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.db.session import set_tenant_context
from app.models.contract import ContractStatus
from app.models.processing_job import JobStatus, ProcessingJob
from app.repositories import (
    contract_chunk_repo,
    contract_repo,
    contract_version_repo,
    processing_job_repo,
)
from app.services import chunking_service, document_extractor, embedding_service, storage_service

logger = get_logger(__name__)


async def process_contract(session: AsyncSession, job_id: uuid.UUID) -> ProcessingJob:
    """Execute the contract processing pipeline for a given job ID.

    Flow:
        1. Load ProcessingJob and set tenant context.
        2. Guard against duplicate execution (if completed).
        3. Mark job & contract as processing.
        4. Download file from MinIO.
        5. Extract plain text.
        6. Split text into overlapping chunks.
        7. Generate vector embeddings for all chunks.
        8. Clear existing chunks (if retrying) and bulk insert new chunks.
        9. Mark job & contract as completed.

    On error:
        - Roll back chunk creation.
        - Mark job & contract as failed with safe error message.

    Args:
        session: Active database session.
        job_id: UUID of the ProcessingJob.

    Returns:
        Updated ProcessingJob record.

    Raises:
        NotFoundError: If the job or associated contract is missing.
    """
    # 1. Fetch job directly (worker bypasses tenant filter initially to read job's org_id)
    job = await processing_job_repo.get_by_id(session, job_id)
    if job is None:
        raise NotFoundError(f"ProcessingJob {job_id} not found")

    # Set RLS tenant context for this session
    await set_tenant_context(session, str(job.org_id))

    # 2. Idempotency check: if already completed, do nothing
    if job.status == JobStatus.completed:
        logger.info("Job already completed, skipping execution", job_id=str(job_id))
        return job

    # 3. Transition to processing
    now = datetime.now(UTC)
    await processing_job_repo.update_status(session, job_id, JobStatus.processing)
    job.started_at = now
    await contract_repo.update_status(session, job.contract_id, ContractStatus.processing)
    await session.commit()

    # Re-set tenant context after commit
    await set_tenant_context(session, str(job.org_id))

    try:
        # 4. Fetch contract and version
        contract = await contract_repo.get_by_id(session, job.contract_id)
        if contract is None:
            raise NotFoundError(f"Contract {job.contract_id} not found")

        versions = await contract_version_repo.list_by_contract(session, contract.id)
        if not versions:
            raise NotFoundError(f"No contract versions found for contract {contract.id}")
        latest_version = versions[-1]

        # 5. Download file from storage
        file_bytes = storage_service.download_file(contract.storage_key)

        # 6. Extract text
        extracted_text = document_extractor.extract_text(
            file_bytes,
            contract.content_type,
            contract.file_name,
        )

        # 7. Chunk text
        chunks = chunking_service.chunk_text(extracted_text)

        # 8. Generate embeddings
        embeddings = embedding_service.embed_texts(chunks)

        # 9. Clear old chunks (for idempotency) and bulk insert new chunks
        await contract_chunk_repo.delete_by_contract_and_version(
            session, contract.id, latest_version.id
        )

        chunks_data = [
            {
                "id": uuid.uuid4(),
                "contract_id": contract.id,
                "version_id": latest_version.id,
                "org_id": job.org_id,
                "chunk_index": idx,
                "content": chunk_text_content,
                "token_count": len(chunk_text_content.split()),
                "embedding": embeddings[idx],
            }
            for idx, chunk_text_content in enumerate(chunks)
        ]

        await contract_chunk_repo.bulk_create(session, chunks_data=chunks_data)

        # 10. Mark completed
        finish_time = datetime.now(UTC)
        job.status = JobStatus.completed
        job.completed_at = finish_time
        job.error_message = None

        await contract_repo.update_status(session, contract.id, ContractStatus.completed)
        await session.commit()

        logger.info(
            "Contract processing completed successfully",
            job_id=str(job_id),
            contract_id=str(contract.id),
            chunks_count=len(chunks),
        )
        return job

    except Exception as exc:
        logger.error("Processing job failed", job_id=str(job_id), exc_info=exc)
        await session.rollback()

        # Update status to failed safely
        await set_tenant_context(session, str(job.org_id))
        safe_error = _format_safe_error(exc)

        await processing_job_repo.update_status(
            session, job_id, JobStatus.failed, error_message=safe_error
        )
        await contract_repo.update_status(session, job.contract_id, ContractStatus.failed)
        await session.commit()

        raise


def _format_safe_error(exc: Exception) -> str:
    """Format an exception into a safe human-readable string for clients."""
    err_str = str(exc)
    # Strip potential secret leaks
    if "key" in err_str.lower() or "token" in err_str.lower() or "password" in err_str.lower():
        return f"{exc.__class__.__name__}: Processing encountered an internal error"
    return f"{exc.__class__.__name__}: {err_str}" if err_str else exc.__class__.__name__
