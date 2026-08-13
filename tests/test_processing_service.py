"""Unit tests for Processing Service pipeline.

Tests the state transitions (queued → processing → completed / failed),
idempotency, and error handling with mocked storage and DB sessions.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.exceptions import NotFoundError
from app.models.processing_job import JobStatus
from app.services import processing_service


@pytest.fixture
def sample_ids() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    return (uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

    @patch(
        "app.workers.tasks.analyze_contract_job.delay",
    )
    @patch(
        "app.services.processing_service.analysis_job_repo.create",
        new_callable=AsyncMock,
    )
    @patch("app.services.processing_service.storage_service.download_file")
    @patch(
        "app.services.processing_service.contract_chunk_repo.bulk_create",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.processing_service.contract_chunk_repo.delete_by_contract_and_version",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.processing_service.contract_version_repo.list_by_contract",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.processing_service.contract_repo.get_by_id",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.processing_service.contract_repo.update_status",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.processing_service.processing_job_repo.update_status",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.processing_service.processing_job_repo.get_by_id",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.processing_service.set_tenant_context",
        new_callable=AsyncMock,
    )
    async def test_successful_processing_pipeline(
        self,
        mock_set_ctx: AsyncMock,
        mock_get_job: AsyncMock,
        mock_update_job_status: AsyncMock,
        mock_update_contract_status: AsyncMock,
        mock_get_contract: AsyncMock,
        mock_list_versions: AsyncMock,
        mock_delete_chunks: AsyncMock,
        mock_bulk_create_chunks: AsyncMock,
        mock_download: MagicMock,
        mock_create_analysis_job: AsyncMock,
        mock_task_delay: MagicMock,
        sample_ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID],
    ) -> None:
        job_id, contract_id, version_id, org_id = sample_ids

        # Setup mock job
        mock_job = MagicMock()
        mock_job.id = job_id
        mock_job.contract_id = contract_id
        mock_job.org_id = org_id
        mock_job.status = JobStatus.queued
        mock_get_job.return_value = mock_job

        # Setup mock contract
        mock_contract = MagicMock()
        mock_contract.id = contract_id
        mock_contract.storage_key = f"{org_id}/{contract_id}/contract.txt"
        mock_contract.content_type = "text/plain"
        mock_contract.file_name = "contract.txt"
        mock_get_contract.return_value = mock_contract

        # Setup mock version
        mock_version = MagicMock()
        mock_version.id = version_id
        mock_list_versions.return_value = [mock_version]

        # Setup mock analysis job
        mock_analysis_job = MagicMock()
        mock_analysis_job.id = uuid.uuid4()
        mock_create_analysis_job.return_value = mock_analysis_job

        # Setup mock file content
        mock_download.return_value = b"Master Services Agreement\n\nClause 1: Scope of Work."

        # Mock AsyncSession
        mock_session = AsyncMock()

        res_job = await processing_service.process_contract(mock_session, job_id)

        assert res_job.status == JobStatus.completed
        mock_download.assert_called_once_with(mock_contract.storage_key)
        mock_bulk_create_chunks.assert_called_once()
        mock_create_analysis_job.assert_called_once()
        mock_task_delay.assert_called_once_with(str(mock_analysis_job.id))
        assert mock_session.commit.call_count >= 2

    @patch(
        "app.workers.tasks.analyze_contract_job.delay",
        side_effect=Exception("Broker connection error"),
    )
    @patch(
        "app.services.processing_service.analysis_job_repo.create",
        new_callable=AsyncMock,
    )
    @patch("app.services.processing_service.storage_service.download_file")
    @patch(
        "app.services.processing_service.contract_chunk_repo.bulk_create",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.processing_service.contract_chunk_repo.delete_by_contract_and_version",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.processing_service.contract_version_repo.list_by_contract",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.processing_service.contract_repo.get_by_id",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.processing_service.contract_repo.update_status",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.processing_service.processing_job_repo.update_status",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.processing_service.processing_job_repo.get_by_id",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.processing_service.set_tenant_context",
        new_callable=AsyncMock,
    )
    async def test_enqueue_failure_does_not_fail_completed_processing(
        self,
        mock_set_ctx: AsyncMock,
        mock_get_job: AsyncMock,
        mock_update_job_status: AsyncMock,
        mock_update_contract_status: AsyncMock,
        mock_get_contract: AsyncMock,
        mock_list_versions: AsyncMock,
        mock_delete_chunks: AsyncMock,
        mock_bulk_create_chunks: AsyncMock,
        mock_download: MagicMock,
        mock_create_analysis_job: AsyncMock,
        mock_task_delay: MagicMock,
        sample_ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID],
    ) -> None:
        job_id, contract_id, version_id, org_id = sample_ids

        mock_job = MagicMock()
        mock_job.id = job_id
        mock_job.contract_id = contract_id
        mock_job.org_id = org_id
        mock_job.status = JobStatus.queued
        mock_get_job.return_value = mock_job

        mock_contract = MagicMock()
        mock_contract.id = contract_id
        mock_contract.storage_key = f"{org_id}/{contract_id}/contract.txt"
        mock_contract.content_type = "text/plain"
        mock_contract.file_name = "contract.txt"
        mock_get_contract.return_value = mock_contract

        mock_version = MagicMock()
        mock_version.id = version_id
        mock_list_versions.return_value = [mock_version]

        mock_analysis_job = MagicMock()
        mock_analysis_job.id = uuid.uuid4()
        mock_create_analysis_job.return_value = mock_analysis_job

        mock_download.return_value = b"Master Services Agreement"
        mock_session = AsyncMock()

        res_job = await processing_service.process_contract(mock_session, job_id)

        assert res_job.status == JobStatus.completed
        mock_create_analysis_job.assert_called_once()
        mock_task_delay.assert_called_once()

    @patch("app.services.processing_service.processing_job_repo.get_by_id", new_callable=AsyncMock)
    @patch("app.services.processing_service.set_tenant_context", new_callable=AsyncMock)
    async def test_idempotent_completed_job_skipped(
        self,
        mock_set_ctx: AsyncMock,
        mock_get_job: AsyncMock,
        sample_ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID],
    ) -> None:
        job_id, _contract_id, _version_id, org_id = sample_ids

        mock_job = MagicMock()
        mock_job.id = job_id
        mock_job.org_id = org_id
        mock_job.status = JobStatus.completed
        mock_get_job.return_value = mock_job

        mock_session = AsyncMock()
        res_job = await processing_service.process_contract(mock_session, job_id)

        assert res_job.status == JobStatus.completed
        # Commit should not be called since job was skipped
        mock_session.commit.assert_not_called()

    @patch("app.services.processing_service.processing_job_repo.get_by_id", new_callable=AsyncMock)
    async def test_job_not_found_raises(self, mock_get_job: AsyncMock) -> None:
        mock_get_job.return_value = None
        mock_session = AsyncMock()

        with pytest.raises(NotFoundError, match="ProcessingJob"):
            await processing_service.process_contract(mock_session, uuid.uuid4())

    @patch("app.services.processing_service.storage_service.download_file")
    @patch(
        "app.services.processing_service.contract_version_repo.list_by_contract",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.processing_service.contract_repo.get_by_id",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.processing_service.contract_repo.update_status",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.processing_service.processing_job_repo.update_status",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.processing_service.processing_job_repo.get_by_id",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.processing_service.set_tenant_context",
        new_callable=AsyncMock,
    )
    async def test_processing_failure_updates_status(
        self,
        mock_set_ctx: AsyncMock,
        mock_get_job: AsyncMock,
        mock_update_job_status: AsyncMock,
        mock_update_contract_status: AsyncMock,
        mock_get_contract: AsyncMock,
        mock_list_versions: AsyncMock,
        mock_download: MagicMock,
        sample_ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID],
    ) -> None:
        job_id, contract_id, version_id, org_id = sample_ids

        mock_job = MagicMock()
        mock_job.id = job_id
        mock_job.contract_id = contract_id
        mock_job.org_id = org_id
        mock_job.status = JobStatus.queued
        mock_get_job.return_value = mock_job

        mock_contract = MagicMock()
        mock_contract.id = contract_id
        mock_contract.storage_key = f"{org_id}/{contract_id}/bad.pdf"
        mock_contract.content_type = "application/pdf"
        mock_contract.file_name = "bad.pdf"
        mock_get_contract.return_value = mock_contract

        mock_version = MagicMock()
        mock_version.id = version_id
        mock_list_versions.return_value = [mock_version]

        # Simulate corrupt file error on download/extract
        mock_download.side_effect = Exception("Storage read failure")

        mock_session = AsyncMock()

        with pytest.raises(Exception, match="Storage read failure"):
            await processing_service.process_contract(mock_session, job_id)

        # Verify rollback and failure status updates
        mock_session.rollback.assert_called_once()
        mock_update_job_status.assert_called_with(
            mock_session,
            job_id,
            JobStatus.failed,
            error_message="Exception: Storage read failure",
        )
