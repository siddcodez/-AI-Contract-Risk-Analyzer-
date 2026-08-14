"""Unit tests for Analysis Service pipeline.

Tests AnalysisJob lifecycle execution (queued → processing → completed / failed),
idempotency, and error handling with mocked repositories.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.exceptions import NotFoundError
from app.models.analysis_job import AnalysisJobStatus
from app.services import analysis_service


@pytest.fixture
def sample_analysis_ids() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    return (uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4())


class TestAnalysisService:
    @patch("app.workers.tasks.analyze_contract_job.delay")
    @patch("app.services.analysis_service.analysis_job_repo.create", new_callable=AsyncMock)
    @patch(
        "app.services.analysis_service.contract_version_repo.list_by_contract",
        new_callable=AsyncMock,
    )
    async def test_trigger_analysis_creates_job_and_dispatches_task(
        self,
        mock_list_versions: AsyncMock,
        mock_create_job: AsyncMock,
        mock_task_delay: MagicMock,
        sample_analysis_ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID],
    ) -> None:
        _job_id, contract_id, version_id, org_id = sample_analysis_ids

        mock_version = MagicMock()
        mock_version.id = version_id
        mock_list_versions.return_value = [mock_version]

        mock_job = MagicMock()
        mock_job.id = uuid.uuid4()
        mock_create_job.return_value = mock_job

        mock_session = AsyncMock()

        res_job = await analysis_service.trigger_analysis(
            mock_session, contract_id=contract_id, org_id=org_id
        )

        assert res_job == mock_job
        mock_create_job.assert_called_once_with(
            mock_session,
            contract_id=contract_id,
            version_id=version_id,
            org_id=org_id,
        )
        mock_session.commit.assert_called_once()
        assert mock_task_delay.call_args[0][0] == str(mock_job.id)

    @patch("app.services.analysis_service.missing_clause_service.detect_missing_clauses", new_callable=AsyncMock)
    @patch("app.services.analysis_service.contract_repo.get_by_id", new_callable=AsyncMock)
    @patch("app.services.analysis_service.retrieval_service.search_chunks", new_callable=AsyncMock)
    @patch(
        "app.services.analysis_service.risk_finding_repo.bulk_create",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.analysis_service.risk_finding_repo.delete_by_contract_and_version",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.analysis_service.contract_chunk_repo.list_by_contract",
        new_callable=AsyncMock,
    )
    @patch("app.services.analysis_service.analysis_job_repo.update_status", new_callable=AsyncMock)
    @patch("app.services.analysis_service.analysis_job_repo.get_by_id", new_callable=AsyncMock)
    @patch("app.services.analysis_service.set_tenant_context", new_callable=AsyncMock)
    async def test_successful_analysis_run(
        self,
        mock_set_ctx: AsyncMock,
        mock_get_job: AsyncMock,
        mock_update_job_status: AsyncMock,
        mock_list_chunks: AsyncMock,
        mock_delete_findings: AsyncMock,
        mock_bulk_create_findings: AsyncMock,
        mock_search_chunks: AsyncMock,
        mock_get_contract: AsyncMock,
        mock_detect_missing: AsyncMock,
        sample_analysis_ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID],
    ) -> None:
        mock_search_chunks.return_value = []
        job_id, contract_id, version_id, org_id = sample_analysis_ids

        mock_job = MagicMock()
        mock_job.id = job_id
        mock_job.contract_id = contract_id
        mock_job.version_id = version_id
        mock_job.org_id = org_id
        mock_job.status = AnalysisJobStatus.queued
        mock_get_job.return_value = mock_job

        mock_chunk = MagicMock()
        mock_chunk.id = uuid.uuid4()
        mock_chunk.chunk_index = 0
        mock_chunk.content = "Uncapped liability clause in agreement."
        mock_list_chunks.return_value = [mock_chunk]

        mock_session = AsyncMock()

        res_job = await analysis_service.analyze_contract(mock_session, job_id)

        assert res_job.status == AnalysisJobStatus.completed
        mock_delete_findings.assert_called_once_with(mock_session, contract_id, version_id)
        mock_bulk_create_findings.assert_called_once()
        assert mock_session.commit.call_count >= 2

    @patch(
        "app.services.analysis_service.contract_chunk_repo.list_by_contract",
        new_callable=AsyncMock,
    )
    @patch("app.services.analysis_service.analysis_job_repo.get_by_id", new_callable=AsyncMock)
    @patch("app.services.analysis_service.set_tenant_context", new_callable=AsyncMock)
    async def test_run_analysis_alias_compatibility(
        self,
        mock_set_ctx: AsyncMock,
        mock_get_job: AsyncMock,
        mock_list_chunks: AsyncMock,
        sample_analysis_ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID],
    ) -> None:
        job_id, contract_id, version_id, org_id = sample_analysis_ids
        mock_job = MagicMock()
        mock_job.id = job_id
        mock_job.contract_id = contract_id
        mock_job.version_id = version_id
        mock_job.org_id = org_id
        mock_job.status = AnalysisJobStatus.completed
        mock_get_job.return_value = mock_job

        mock_session = AsyncMock()
        res = await analysis_service.run_analysis(mock_session, job_id)
        assert res.status == AnalysisJobStatus.completed

    @patch("app.services.analysis_service.analysis_job_repo.get_by_id", new_callable=AsyncMock)
    @patch("app.services.analysis_service.set_tenant_context", new_callable=AsyncMock)
    async def test_idempotent_completed_job_skipped(
        self,
        mock_set_ctx: AsyncMock,
        mock_get_job: AsyncMock,
        sample_analysis_ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID],
    ) -> None:
        job_id, _contract_id, _version_id, org_id = sample_analysis_ids

        mock_job = MagicMock()
        mock_job.id = job_id
        mock_job.org_id = org_id
        mock_job.status = AnalysisJobStatus.completed
        mock_get_job.return_value = mock_job

        mock_session = AsyncMock()
        res_job = await analysis_service.analyze_contract(mock_session, job_id)

        assert res_job.status == AnalysisJobStatus.completed
        mock_session.commit.assert_not_called()

    @patch("app.services.analysis_service.analysis_job_repo.get_by_id", new_callable=AsyncMock)
    async def test_job_not_found_raises(self, mock_get_job: AsyncMock) -> None:
        mock_get_job.return_value = None
        mock_session = AsyncMock()

        with pytest.raises(NotFoundError, match="AnalysisJob"):
            await analysis_service.analyze_contract(mock_session, uuid.uuid4())

    @patch(
        "app.services.analysis_service.contract_chunk_repo.list_by_contract",
        side_effect=Exception("Database failure"),
    )
    @patch("app.services.analysis_service.analysis_job_repo.update_status", new_callable=AsyncMock)
    @patch("app.services.analysis_service.analysis_job_repo.get_by_id", new_callable=AsyncMock)
    @patch("app.services.analysis_service.set_tenant_context", new_callable=AsyncMock)
    async def test_analysis_failure_updates_status_with_safe_error(
        self,
        mock_set_ctx: AsyncMock,
        mock_get_job: AsyncMock,
        mock_update_job_status: AsyncMock,
        mock_list_chunks: AsyncMock,
        sample_analysis_ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID],
    ) -> None:
        job_id, contract_id, version_id, org_id = sample_analysis_ids

        mock_job = MagicMock()
        mock_job.id = job_id
        mock_job.contract_id = contract_id
        mock_job.version_id = version_id
        mock_job.org_id = org_id
        mock_job.status = AnalysisJobStatus.queued
        mock_get_job.return_value = mock_job

        mock_session = AsyncMock()

        with pytest.raises(Exception, match="Database failure"):
            await analysis_service.analyze_contract(mock_session, job_id)

        mock_session.rollback.assert_called_once()
        mock_update_job_status.assert_any_call(
            mock_session,
            job_id,
            AnalysisJobStatus.failed,
            error_message="Exception: Database failure",
        )
