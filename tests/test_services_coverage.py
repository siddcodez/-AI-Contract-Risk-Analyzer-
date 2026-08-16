"""Targeted tests for processing_service and auth_service edge and failure branches."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.models.contract import Contract, ContractStatus
from app.models.contract_version import ContractVersion
from app.models.processing_job import JobStatus, ProcessingJob
from app.models.user import User, UserRole
from app.schemas.auth import RegisterRequest
from app.services import auth_service, processing_service

# ---------------------------------------------------------------------------
# Processing Service Branch Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_contract_job_not_found_raises() -> None:
    session = AsyncMock()
    with patch(
        "app.repositories.processing_job_repo.get_by_id", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = None
        with pytest.raises(NotFoundError, match=r"ProcessingJob .* not found"):
            await processing_service.process_contract(session, uuid.uuid4())


@pytest.mark.asyncio
async def test_process_contract_already_completed_idempotent() -> None:
    session = AsyncMock()
    job = ProcessingJob(
        id=uuid.uuid4(),
        contract_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        status=JobStatus.completed,
    )
    with (
        patch("app.repositories.processing_job_repo.get_by_id", new_callable=AsyncMock) as mock_get,
        patch("app.services.processing_service.set_tenant_context", new_callable=AsyncMock),
    ):
        mock_get.return_value = job
        res = await processing_service.process_contract(session, job.id)
        assert res.status == JobStatus.completed


@pytest.mark.asyncio
async def test_process_contract_missing_contract_or_version_fails_cleanly() -> None:
    session = AsyncMock()
    job = ProcessingJob(
        id=uuid.uuid4(),
        contract_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        status=JobStatus.queued,
    )

    with (
        patch("app.repositories.processing_job_repo.get_by_id", new_callable=AsyncMock) as mock_get,
        patch("app.services.processing_service.set_tenant_context", new_callable=AsyncMock),
        patch("app.repositories.processing_job_repo.update_status", new_callable=AsyncMock),
        patch("app.repositories.contract_repo.update_status", new_callable=AsyncMock),
        patch("app.repositories.contract_repo.get_by_id", new_callable=AsyncMock) as mock_c_get,
        patch("app.services.websocket_manager.ws_manager.broadcast_event", new_callable=AsyncMock),
    ):
        mock_get.return_value = job
        mock_c_get.return_value = None

        with pytest.raises(NotFoundError, match=r"Contract .* not found"):
            await processing_service.process_contract(session, job.id)


@pytest.mark.asyncio
async def test_process_contract_end_to_end_success_with_broadcast() -> None:
    session = AsyncMock()
    job = ProcessingJob(
        id=uuid.uuid4(),
        contract_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        status=JobStatus.queued,
    )
    contract = Contract(
        id=job.contract_id,
        title="Agreement.pdf",
        file_name="agreement.pdf",
        file_size=2048,
        content_type="application/pdf",
        storage_key="contracts/agreement.pdf",
        status=ContractStatus.processing,
        org_id=job.org_id,
        uploaded_by=uuid.uuid4(),
    )
    version = ContractVersion(
        id=uuid.uuid4(),
        contract_id=contract.id,
        version_number=1,
        file_name=contract.file_name,
        file_size=contract.file_size,
        content_type=contract.content_type,
        storage_key=contract.storage_key,
        org_id=job.org_id,
    )

    mock_analysis_job = MagicMock(id=uuid.uuid4())
    with (
        patch(
            "app.repositories.processing_job_repo.get_by_id", new_callable=AsyncMock
        ) as mock_j_get,
        patch("app.services.processing_service.set_tenant_context", new_callable=AsyncMock),
        patch("app.repositories.processing_job_repo.update_status", new_callable=AsyncMock),
        patch("app.repositories.contract_repo.update_status", new_callable=AsyncMock),
        patch("app.repositories.contract_repo.get_by_id", new_callable=AsyncMock) as mock_c_get,
        patch(
            "app.repositories.contract_version_repo.list_by_contract", new_callable=AsyncMock
        ) as mock_v_list,
        patch("app.services.storage_service.download_file", return_value=b"PDF bytes content"),
        patch(
            "app.services.document_extractor.extract_text", return_value="Extracted text chunkable"
        ),
        patch("app.services.chunking_service.chunk_text", return_value=["Chunk 1", "Chunk 2"]),
        patch(
            "app.services.embedding_service.embed_texts", return_value=[[0.1] * 1536, [0.2] * 1536]
        ),
        patch(
            "app.repositories.contract_chunk_repo.delete_by_contract_and_version",
            new_callable=AsyncMock,
        ),
        patch("app.repositories.contract_chunk_repo.bulk_create", new_callable=AsyncMock),
        patch(
            "app.repositories.analysis_job_repo.create",
            new_callable=AsyncMock,
            return_value=mock_analysis_job,
        ),
        patch("app.workers.tasks.analyze_contract_job.delay"),
        patch(
            "app.services.websocket_manager.ws_manager.broadcast_event", new_callable=AsyncMock
        ) as mock_bc,
    ):
        mock_j_get.return_value = job
        mock_c_get.return_value = contract
        mock_v_list.return_value = [version]

        res = await processing_service.process_contract(session, job.id)
        assert res.id == job.id
        mock_bc.assert_awaited()


# ---------------------------------------------------------------------------
# Auth Service Branch Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_duplicate_email_conflict() -> None:
    session = AsyncMock()
    req = RegisterRequest(
        email="existing@example.com",
        password="ValidPassword123!",
        full_name="Existing User",
        org_name="New Corp",
    )
    with patch("app.repositories.user_repo.email_exists", new_callable=AsyncMock) as mock_exists:
        mock_exists.return_value = True
        with pytest.raises(ConflictError, match="A user with this email already exists"):
            await auth_service.register_user(session, req)


@pytest.mark.asyncio
async def test_authenticate_invalid_email_or_password_raises() -> None:
    session = AsyncMock()
    with patch(
        "app.repositories.user_repo.get_by_email_for_auth", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = None
        with pytest.raises(AuthenticationError, match="Invalid email or password"):
            await auth_service.authenticate_user(session, "none@example.com", "wrongpass")


@pytest.mark.asyncio
async def test_authenticate_inactive_user_deactivated() -> None:
    session = AsyncMock()
    user = User(
        id=uuid.uuid4(),
        email="inactive@example.com",
        password_hash=auth_service.hash_password("ValidPass123!"),
        full_name="Inactive User",
        role=UserRole.viewer,
        org_id=uuid.uuid4(),
        is_active=False,
    )
    with patch(
        "app.repositories.user_repo.get_by_email_for_auth", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = user
        with pytest.raises(AuthenticationError, match="Account is deactivated"):
            await auth_service.authenticate_user(session, "inactive@example.com", "ValidPass123!")
