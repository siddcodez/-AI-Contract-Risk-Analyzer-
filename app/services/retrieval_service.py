"""Semantic retrieval and RAG context building service (M5).

Provides vector similarity search over contract text chunks using existing
embedding service abstractions and pgvector similarity search, and constructs
RAG context windows bounded by character and chunk budgets.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.repositories import contract_chunk_repo
from app.services import embedding_service

logger = get_logger(__name__)


async def search_chunks(
    session: AsyncSession,
    query: str,
    *,
    contract_id: uuid.UUID | None = None,
    version_id: uuid.UUID | None = None,
    top_k: int | None = None,
    min_score: float | None = None,
    distance_metric: str | None = None,
) -> list[dict[str, Any]]:
    """Execute semantic similarity search for a query string over contract chunks.

    Args:
        session: Active database session (subject to RLS tenant context).
        query: Free-text search query.
        contract_id: Optional contract UUID filter.
        version_id: Optional version UUID filter.
        top_k: Max chunks to retrieve (defaults to settings.RETRIEVAL_TOP_K).
        min_score: Minimum similarity score (defaults to settings.RETRIEVAL_MIN_SCORE).
        distance_metric: Metric ('cosine', 'l2', 'inner_product').

    Returns:
        List of result dictionaries containing chunk metadata and similarity scores.
    """
    settings = get_settings()
    k = top_k if top_k is not None else settings.RETRIEVAL_TOP_K
    score_threshold = min_score if min_score is not None else settings.RETRIEVAL_MIN_SCORE
    metric = distance_metric if distance_metric is not None else settings.VECTOR_DISTANCE_METRIC

    if not query or not query.strip():
        return []

    # 1. Generate query vector using existing embedding provider
    query_vectors = embedding_service.embed_texts([query])
    if not query_vectors:
        return []
    query_vector = query_vectors[0]

    # 2. Perform pgvector similarity search in repository
    raw_results = await contract_chunk_repo.similarity_search(
        session,
        query_vector,
        contract_id=contract_id,
        version_id=version_id,
        top_k=k,
        min_score=score_threshold,
        distance_metric=metric,
    )

    # 3. Format structured results
    results: list[dict[str, Any]] = [
        {
            "chunk_id": chunk.id,
            "contract_id": chunk.contract_id,
            "version_id": chunk.version_id,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "similarity_score": round(score, 4),
        }
        for chunk, score in raw_results
    ]

    logger.info(
        "Completed semantic chunk search",
        contract_id=str(contract_id) if contract_id else None,
        query_length=len(query),
        results_count=len(results),
    )
    return results


async def build_rag_context(
    session: AsyncSession,
    query: str,
    *,
    contract_id: uuid.UUID | None = None,
    version_id: uuid.UUID | None = None,
    top_k: int | None = None,
    min_score: float | None = None,
    max_chunks: int | None = None,
    max_chars: int | None = None,
    distance_metric: str | None = None,
) -> dict[str, Any]:
    """Build a structured RAG context string bounded by chunk and character budgets.

    Args:
        session: Active database session (subject to RLS tenant context).
        query: User or analysis query topic.
        contract_id: Optional contract UUID filter.
        version_id: Optional version UUID filter.
        top_k: Candidate retrieval limit.
        min_score: Minimum similarity score threshold.
        max_chunks: Max chunks allowed in final context (defaults to
            settings.MAX_RAG_CONTEXT_CHUNKS).
        max_chars: Character budget for context (defaults to settings.RAG_CONTEXT_MAX_CHARS).
        distance_metric: Distance metric string.

    Returns:
        Dictionary containing formatted context_text, chunks_count, total_chars, and items.
    """
    settings = get_settings()
    chunk_limit = max_chunks if max_chunks is not None else settings.MAX_RAG_CONTEXT_CHUNKS
    char_budget = max_chars if max_chars is not None else settings.RAG_CONTEXT_MAX_CHARS
    search_k = top_k if top_k is not None else max(chunk_limit, settings.RETRIEVAL_TOP_K)

    items = await search_chunks(
        session,
        query,
        contract_id=contract_id,
        version_id=version_id,
        top_k=search_k,
        min_score=min_score,
        distance_metric=distance_metric,
    )

    context_blocks: list[str] = []
    included_items: list[dict[str, Any]] = []
    current_chars = 0

    for item in items[:chunk_limit]:
        header = f"[Chunk {item['chunk_index']} | similarity={item['similarity_score']:.2f}]\n"
        content = item["content"]
        block = f"{header}{content}\n\n"

        if current_chars + len(block) > char_budget:
            remaining_chars = char_budget - current_chars - len(header) - 4
            if remaining_chars > 20:
                truncated_content = content[:remaining_chars] + "..."
                block = f"{header}{truncated_content}\n\n"
                context_blocks.append(block)
                included_items.append(item)
                current_chars += len(block)
            break

        context_blocks.append(block)
        included_items.append(item)
        current_chars += len(block)

    context_text = "".join(context_blocks).strip()

    return {
        "context_text": context_text,
        "chunks_count": len(included_items),
        "total_chars": len(context_text),
        "items": included_items,
    }
