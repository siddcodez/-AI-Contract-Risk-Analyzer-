"""Integration tests for M4/M5 RAG grounding integration.

Verifies that risk analysis findings are grounded with vector similarity search
metadata (chunk_id, chunk_index, similarity_score) without altering original evidence.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.models.analysis_job import AnalysisJobStatus
from app.services import analysis_service


@pytest.fixture
def grounding_ids() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    return (uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4())


class TestRAGGrounding:
    @patch("app.services.analysis_service.retrieval_service.search_chunks", new_callable=AsyncMock)
    @patch("app.services.analysis_service.risk_finding_repo.bulk_create", new_callable=AsyncMock)
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
    async def test_risk_findings_are_grounded_with_retrieval_metadata(
        self,
        mock_set_ctx: AsyncMock,
        mock_get_job: AsyncMock,
        mock_update_job_status: AsyncMock,
        mock_list_chunks: AsyncMock,
        mock_delete_findings: AsyncMock,
        mock_bulk_create: AsyncMock,
        mock_search_chunks: AsyncMock,
        grounding_ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID],
    ) -> None:
        job_id, contract_id, version_id, org_id = grounding_ids

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

        # Grounding match return
        matched_chunk_id = uuid.uuid4()
        mock_search_chunks.return_value = [
            {
                "chunk_id": matched_chunk_id,
                "contract_id": contract_id,
                "version_id": version_id,
                "chunk_index": 0,
                "content": "Uncapped liability clause in agreement.",
                "similarity_score": 0.94,
            }
        ]

        mock_session = AsyncMock()

        res_job = await analysis_service.analyze_contract(mock_session, job_id)

        assert res_job.status == AnalysisJobStatus.completed
        mock_bulk_create.assert_called_once()

        created_findings = mock_bulk_create.call_args[1]["findings_data"]
        assert len(created_findings) > 0

        first_finding = created_findings[0]
        assert first_finding["chunk_id"] == matched_chunk_id
        assert "grounding" in first_finding["metadata_json"]
        grounding_info = first_finding["metadata_json"]["grounding"]
        assert grounding_info["chunk_id"] == str(matched_chunk_id)
        assert grounding_info["chunk_index"] == 0
        assert grounding_info["similarity_score"] == 0.94
