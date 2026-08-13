"""Unit tests for retrieval service and RAG context builder (M5).

Tests vector similarity search logic, score thresholds, top_k bounds,
invalid input validations, and RAG context character limit clipping.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from app.core.config import get_settings
from app.models.contract_chunk import ContractChunk
from app.repositories import contract_chunk_repo
from app.services import retrieval_service


@pytest.fixture
def sample_uuids() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    return (uuid.uuid4(), uuid.uuid4(), uuid.uuid4())


class TestRetrievalService:
    @patch(
        "app.services.retrieval_service.contract_chunk_repo.similarity_search",
        new_callable=AsyncMock,
    )
    async def test_search_chunks_successful(
        self,
        mock_repo_search: AsyncMock,
        sample_uuids: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
    ) -> None:
        contract_id, version_id, org_id = sample_uuids

        chunk = ContractChunk(
            id=uuid.uuid4(),
            contract_id=contract_id,
            version_id=version_id,
            org_id=org_id,
            chunk_index=0,
            content="The Customer may terminate this Agreement upon 30 days notice.",
            embedding=[0.1] * 1536,
        )

        mock_repo_search.return_value = [(chunk, 0.8851)]

        mock_session = AsyncMock()
        results = await retrieval_service.search_chunks(
            mock_session,
            "termination obligations",
            contract_id=contract_id,
            top_k=5,
            min_score=0.25,
        )

        assert len(results) == 1
        assert results[0]["chunk_id"] == chunk.id
        assert results[0]["similarity_score"] == 0.8851
        mock_repo_search.assert_called_once()

    async def test_search_chunks_empty_query(self) -> None:
        mock_session = AsyncMock()
        results = await retrieval_service.search_chunks(mock_session, "   ")
        assert results == []

    @patch("app.services.retrieval_service.search_chunks", new_callable=AsyncMock)
    async def test_build_rag_context_bounds(
        self,
        mock_search: AsyncMock,
        sample_uuids: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
    ) -> None:
        contract_id, version_id, _org_id = sample_uuids

        items = [
            {
                "chunk_id": uuid.uuid4(),
                "contract_id": contract_id,
                "version_id": version_id,
                "chunk_index": 0,
                "content": "Clause 1: Scope of Work and Deliverables." * 5,
                "similarity_score": 0.92,
            },
            {
                "chunk_id": uuid.uuid4(),
                "contract_id": contract_id,
                "version_id": version_id,
                "chunk_index": 1,
                "content": "Clause 2: Payment and Fee Terms." * 5,
                "similarity_score": 0.85,
            },
        ]
        mock_search.return_value = items

        mock_session = AsyncMock()
        rag = await retrieval_service.build_rag_context(
            mock_session,
            "payment terms",
            contract_id=contract_id,
            max_chunks=2,
            max_chars=100,
        )

        assert rag["chunks_count"] <= 2
        assert rag["total_chars"] <= 100
        assert "similarity=0.92" in rag["context_text"]


class TestContractChunkRepoValidations:
    async def test_invalid_query_vector_dimension(self) -> None:
        mock_session = AsyncMock()
        bad_vector = [0.1, 0.2]  # wrong dimension

        with pytest.raises(ValueError, match="Query vector dimension"):
            await contract_chunk_repo.similarity_search(mock_session, bad_vector)

    async def test_invalid_top_k(self) -> None:
        mock_session = AsyncMock()
        dimension = get_settings().EMBEDDING_DIMENSION
        valid_vec = [0.1] * dimension

        with pytest.raises(ValueError, match="top_k must be at least 1"):
            await contract_chunk_repo.similarity_search(mock_session, valid_vec, top_k=0)

    async def test_invalid_min_score(self) -> None:
        mock_session = AsyncMock()
        dimension = get_settings().EMBEDDING_DIMENSION
        valid_vec = [0.1] * dimension

        with pytest.raises(ValueError, match=r"min_score must be between 0\.0 and 1\.0"):
            await contract_chunk_repo.similarity_search(mock_session, valid_vec, min_score=1.5)

    async def test_unsupported_distance_metric(self) -> None:
        mock_session = AsyncMock()
        dimension = get_settings().EMBEDDING_DIMENSION
        valid_vec = [0.1] * dimension

        with pytest.raises(ValueError, match="Unsupported distance metric"):
            await contract_chunk_repo.similarity_search(
                mock_session, valid_vec, distance_metric="euclidean_unsupported"
            )

