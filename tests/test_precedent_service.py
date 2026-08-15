"""Unit and domain tests for Precedent Service (M7.3)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from app.models.contract_chunk import ContractChunk
from app.services.precedent_service import (
    _QUERY_VECTOR_CACHE,
    find_similar_precedents,
    get_cached_query_vector,
    set_cached_query_vector,
)
from sqlalchemy.ext.asyncio import AsyncSession


class TestPrecedentService:
    """Test suite for organizational precedent clause search service."""

    def setup_method(self) -> None:
        """Clear cache before each test."""
        _QUERY_VECTOR_CACHE.clear()

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty_response(self) -> None:
        contract_id = uuid.uuid4()
        org_id = uuid.uuid4()
        session = AsyncMock(spec=AsyncSession)

        res = await find_similar_precedents(
            session,
            contract_id=contract_id,
            org_id=org_id,
            query="   ",
        )
        assert res.total_results == 0
        assert res.items == []
        assert res.query_contract_id == contract_id
        assert "not legal advice" in res.disclaimer.lower()

    @pytest.mark.asyncio
    async def test_precedent_search_excludes_current_contract_and_all_its_versions(self) -> None:
        """Verify the current contract (across all versions) is excluded from precedent results."""
        current_contract_id = uuid.uuid4()
        other_contract_id = uuid.uuid4()
        org_id = uuid.uuid4()

        now = datetime.now(UTC)
        other_chunk = ContractChunk(
            id=uuid.uuid4(),
            contract_id=other_contract_id,
            version_id=uuid.uuid4(),
            org_id=org_id,
            chunk_index=2,
            content="Vendor aggregate liability shall not exceed twelve months fees.",
            embedding=[0.1] * 1536,
            created_at=now,
        )

        mock_raw_rows = [
            (other_chunk, "Prior MSA 2025", "prior_msa.pdf", 0.88),
        ]

        session = AsyncMock(spec=AsyncSession)

        with (
            patch(
                "app.services.precedent_service.contract_chunk_repo.search_precedent_chunks",
                new_callable=AsyncMock,
                return_value=mock_raw_rows,
            ) as mock_search,
            patch(
                "app.services.precedent_service.embedding_service.embed_texts",
                return_value=[[0.1] * 1536],
            ),
        ):
            res = await find_similar_precedents(
                session,
                contract_id=current_contract_id,
                org_id=org_id,
                query="limitation of liability clause",
                top_k=5,
                min_score=0.50,
            )

            assert res.total_results == 1
            assert len(res.items) == 1
            item = res.items[0]
            assert item.contract_id == other_contract_id
            assert item.contract_title == "Prior MSA 2025"
            assert item.file_name == "prior_msa.pdf"
            assert item.similarity_score == 0.88
            assert "Vendor aggregate liability" in item.content

            # Verify repository was invoked with exclude_contract_id=current_contract_id
            mock_search.assert_called_once()
            call_kwargs = mock_search.call_args[1]
            assert call_kwargs["exclude_contract_id"] == current_contract_id

    @pytest.mark.asyncio
    async def test_precedent_ranking_order_descending_by_similarity(self) -> None:
        """Verify precedent results maintain strict descending similarity score order."""
        contract_id = uuid.uuid4()
        org_id = uuid.uuid4()
        now = datetime.now(UTC)

        chunk1 = ContractChunk(
            id=uuid.uuid4(),
            contract_id=uuid.uuid4(),
            version_id=uuid.uuid4(),
            org_id=org_id,
            chunk_index=1,
            content="Standard high similarity indemnification clause.",
            embedding=[0.1] * 1536,
            created_at=now,
        )
        chunk2 = ContractChunk(
            id=uuid.uuid4(),
            contract_id=uuid.uuid4(),
            version_id=uuid.uuid4(),
            org_id=org_id,
            chunk_index=2,
            content="Medium similarity indemnification clause.",
            embedding=[0.1] * 1536,
            created_at=now,
        )
        chunk3 = ContractChunk(
            id=uuid.uuid4(),
            contract_id=uuid.uuid4(),
            version_id=uuid.uuid4(),
            org_id=org_id,
            chunk_index=3,
            content="Moderate similarity indemnification clause.",
            embedding=[0.1] * 1536,
            created_at=now,
        )

        mock_raw_rows = [
            (chunk1, "Contract Alpha", "alpha.pdf", 0.94),
            (chunk2, "Contract Beta", "beta.pdf", 0.83),
            (chunk3, "Contract Gamma", "gamma.pdf", 0.71),
        ]

        session = AsyncMock(spec=AsyncSession)

        with (
            patch(
                "app.services.precedent_service.contract_chunk_repo.search_precedent_chunks",
                new_callable=AsyncMock,
                return_value=mock_raw_rows,
            ),
            patch(
                "app.services.precedent_service.embedding_service.embed_texts",
                return_value=[[0.1] * 1536],
            ),
        ):
            res = await find_similar_precedents(
                session,
                contract_id=contract_id,
                org_id=org_id,
                query="indemnify and hold harmless",
                top_k=5,
                min_score=0.50,
            )

            assert res.total_results == 3
            scores = [it.similarity_score for it in res.items]
            assert scores == [0.94, 0.83, 0.71]
            assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_min_score_threshold_parameter_forwarded_and_filtered(self) -> None:
        """Verify min_score threshold parameter is enforced to filter low-relevance chunks."""
        contract_id = uuid.uuid4()
        org_id = uuid.uuid4()
        session = AsyncMock(spec=AsyncSession)

        with (
            patch(
                "app.services.precedent_service.contract_chunk_repo.search_precedent_chunks",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_search,
            patch(
                "app.services.precedent_service.embedding_service.embed_texts",
                return_value=[[0.1] * 1536],
            ),
        ):
            await find_similar_precedents(
                session,
                contract_id=contract_id,
                org_id=org_id,
                query="confidentiality duration 5 years",
                top_k=10,
                min_score=0.65,
            )

            mock_search.assert_called_once()
            call_kwargs = mock_search.call_args[1]
            assert call_kwargs["min_score"] == 0.65
            assert call_kwargs["top_k"] == 10

    @pytest.mark.asyncio
    async def test_caching_layer_avoids_recomputing_query_embedding(self) -> None:
        """Verify repeated queries reuse cached query vectors and do not call embed_texts again."""
        contract_id = uuid.uuid4()
        org_id = uuid.uuid4()
        session = AsyncMock(spec=AsyncSession)
        query = "governing law in Delaware"

        with (
            patch(
                "app.services.precedent_service.contract_chunk_repo.search_precedent_chunks",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.services.precedent_service.embedding_service.embed_texts",
                return_value=[[0.15] * 1536],
            ) as mock_embed,
        ):
            # First call: computes embedding
            await find_similar_precedents(
                session,
                contract_id=contract_id,
                org_id=org_id,
                query=query,
            )
            assert mock_embed.call_count == 1

            # Second identical call: hits tenant vector cache, zero extra embed_texts calls
            await find_similar_precedents(
                session,
                contract_id=contract_id,
                org_id=org_id,
                query=query,
            )
            assert mock_embed.call_count == 1  # unchanged

    @pytest.mark.asyncio
    async def test_tenant_safe_caching_isolates_between_orgs(self) -> None:
        """Verify vector query cache keys are strictly isolated per org_id."""
        org_a = uuid.uuid4()
        org_b = uuid.uuid4()
        query = "Intellectual Property Ownership"
        vector_a = [0.2] * 1536

        set_cached_query_vector(org_a, query, vector_a)

        # Org A should find cached vector
        assert get_cached_query_vector(org_a, query) == vector_a
        # Org B querying identical string must NOT get Org A's cache entry
        assert get_cached_query_vector(org_b, query) is None
