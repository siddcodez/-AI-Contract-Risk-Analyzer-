"""Repository for ContractChunk DB operations.

contract_chunks table HAS RLS enabled — all queries are subject to the
tenant_isolation policy (org_id must match the current session's app.current_org_id setting).
"""

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract_chunk import ContractChunk


async def bulk_create(
    session: AsyncSession,
    *,
    chunks_data: list[dict[str, Any]],
) -> list[ContractChunk]:
    """Bulk create contract chunk records.

    Subject to RLS WITH CHECK — caller must ensure org_id matches current tenant.
    """
    chunks = [ContractChunk(**data) for data in chunks_data]
    session.add_all(chunks)
    await session.flush()
    return chunks


async def delete_by_contract_and_version(
    session: AsyncSession,
    contract_id: uuid.UUID,
    version_id: uuid.UUID,
) -> None:
    """Delete all existing chunks for a specific contract version.

    Used to ensure idempotency when retrying a contract processing job.
    Subject to RLS.
    """
    await session.execute(
        delete(ContractChunk).where(
            ContractChunk.contract_id == contract_id,
            ContractChunk.version_id == version_id,
        )
    )
    await session.flush()


async def list_by_contract(
    session: AsyncSession,
    contract_id: uuid.UUID,
) -> list[ContractChunk]:
    """Fetch all chunks for a contract, ordered by chunk_index.

    Subject to RLS — caller must set tenant context first.
    """
    result = await session.execute(
        select(ContractChunk)
        .where(ContractChunk.contract_id == contract_id)
        .order_by(ContractChunk.chunk_index.asc())
    )
    return list(result.scalars().all())


async def similarity_search(
    session: AsyncSession,
    query_vector: list[float],
    *,
    contract_id: uuid.UUID | None = None,
    version_id: uuid.UUID | None = None,
    top_k: int = 8,
    min_score: float = 0.20,
    distance_metric: str = "cosine",
) -> list[tuple[ContractChunk, float]]:
    """Perform pgvector similarity search on contract chunks with hybrid filtering.

    Args:
        session: Active database session.
        query_vector: Vector embedding of search query.
        contract_id: Optional filter for contract ID.
        version_id: Optional filter for version ID.
        top_k: Max results to return (>= 1).
        min_score: Minimum similarity score threshold (0.0 to 1.0).
        distance_metric: Distance metric ('cosine', 'l2', 'inner_product').

    Returns:
        List of tuples (ContractChunk, similarity_score) sorted by score descending.

    Raises:
        ValueError: If input parameters or distance_metric are invalid.
    """
    from app.core.config import get_settings

    settings = get_settings()

    if len(query_vector) != settings.EMBEDDING_DIMENSION:
        raise ValueError(
            f"Query vector dimension ({len(query_vector)}) does not match "
            f"expected dimension ({settings.EMBEDDING_DIMENSION})"
        )
    if top_k < 1:
        raise ValueError("top_k must be at least 1")
    if not (0.0 <= min_score <= 1.0):
        raise ValueError("min_score must be between 0.0 and 1.0")

    metric_lower = distance_metric.lower()
    if metric_lower == "cosine":
        dist_expr = ContractChunk.embedding.cosine_distance(query_vector)
    elif metric_lower == "l2":
        dist_expr = ContractChunk.embedding.l2_distance(query_vector)
    elif metric_lower == "inner_product":
        dist_expr = ContractChunk.embedding.max_inner_product(query_vector)
    else:
        raise ValueError(f"Unsupported distance metric: '{distance_metric}'")

    # Score calculation: for cosine distance d, similarity score = 1.0 - d
    score_expr = 1.0 - dist_expr

    query = (
        select(ContractChunk, score_expr.label("score"))
        .where(ContractChunk.embedding.is_not(None))
        .where(score_expr >= min_score)
    )

    if contract_id is not None:
        query = query.where(ContractChunk.contract_id == contract_id)
    if version_id is not None:
        query = query.where(ContractChunk.version_id == version_id)

    query = query.order_by(dist_expr.asc()).limit(top_k)

    result = await session.execute(query)
    rows = result.all()
    return [(row[0], float(row[1])) for row in rows]
