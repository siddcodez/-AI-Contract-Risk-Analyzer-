"""Precedent search service — surfaces similar reviewed clauses across tenant contracts.

Uses pgvector semantic similarity search on existing clause embeddings,
filtered strictly by organization tenant context and excluding the query contract
(across all its versions).
"""

import hashlib
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.repositories import contract_chunk_repo
from app.schemas.precedent import PrecedentItem, PrecedentSearchResponse
from app.services import embedding_service

logger = get_logger(__name__)

# Tenant-safe in-memory cache for query embedding vectors: (org_id, query_hash) -> vector
_QUERY_VECTOR_CACHE: dict[tuple[uuid.UUID, str], list[float]] = {}


def _get_tenant_cache_key(org_id: uuid.UUID, query: str) -> tuple[uuid.UUID, str]:
    """Generate a tenant-isolated cache key for clause query embeddings."""
    norm_query = query.strip().lower()
    q_hash = hashlib.sha256(norm_query.encode("utf-8")).hexdigest()
    return (org_id, q_hash)


def get_cached_query_vector(org_id: uuid.UUID, query: str) -> list[float] | None:
    """Retrieve cached embedding vector for this organization and query."""
    key = _get_tenant_cache_key(org_id, query)
    return _QUERY_VECTOR_CACHE.get(key)


def set_cached_query_vector(org_id: uuid.UUID, query: str, vector: list[float]) -> None:
    """Store embedding vector into tenant-isolated cache (capped size)."""
    if len(_QUERY_VECTOR_CACHE) > 5000:
        _QUERY_VECTOR_CACHE.clear()
    key = _get_tenant_cache_key(org_id, query)
    _QUERY_VECTOR_CACHE[key] = vector


async def find_similar_precedents(
    session: AsyncSession,
    *,
    contract_id: uuid.UUID,
    org_id: uuid.UUID,
    query: str,
    top_k: int = 5,
    min_score: float = 0.50,
) -> PrecedentSearchResponse:
    """Search for similar reviewed clauses across the organization's other contracts.

    Excludes all chunks belonging to contract_id (across all versions).
    Subject to Postgres RLS tenant isolation.

    Args:
        session: Active database session with tenant context set.
        contract_id: UUID of the current contract (to exclude from precedent pool).
        org_id: UUID of the calling organization (for tenant cache isolation).
        query: Clause text or query to find precedents for.
        top_k: Maximum number of precedent clauses to return.
        min_score: Minimum cosine similarity score threshold (0.0 to 1.0).

    Returns:
        PrecedentSearchResponse containing ranked precedent items and disclaimer.
    """
    clean_query = query.strip()
    if not clean_query:
        return PrecedentSearchResponse(
            query_contract_id=contract_id,
            query=query,
            total_results=0,
            items=[],
        )

    settings = get_settings()

    # 1. Retrieve or compute query embedding vector (tenant-cached)
    cached_vec = get_cached_query_vector(org_id, clean_query)
    if cached_vec is not None:
        query_vector = cached_vec
    else:
        vectors = embedding_service.embed_texts([clean_query])
        if not vectors:
            return PrecedentSearchResponse(
                query_contract_id=contract_id,
                query=query,
                total_results=0,
                items=[],
            )
        query_vector = vectors[0]
        set_cached_query_vector(org_id, clean_query, query_vector)

    # 2. Execute pgvector search excluding the current contract across all versions
    raw_results = await contract_chunk_repo.search_precedent_chunks(
        session,
        query_vector,
        exclude_contract_id=contract_id,
        top_k=top_k,
        min_score=min_score,
        distance_metric=settings.VECTOR_DISTANCE_METRIC,
    )

    items: list[PrecedentItem] = []
    for chunk, c_title, c_filename, score in raw_results:
        items.append(
            PrecedentItem(
                chunk_id=chunk.id,
                contract_id=chunk.contract_id,
                version_id=chunk.version_id,
                contract_title=c_title or c_filename,
                file_name=c_filename,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                similarity_score=round(score, 4),
                created_at=chunk.created_at,
                metadata_json=None,
            )
        )

    logger.info(
        "precedent_search_completed",
        contract_id=str(contract_id),
        org_id=str(org_id),
        results_count=len(items),
    )

    return PrecedentSearchResponse(
        query_contract_id=contract_id,
        query=query,
        total_results=len(items),
        items=items,
    )
