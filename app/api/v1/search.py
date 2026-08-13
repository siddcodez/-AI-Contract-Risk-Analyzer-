"""Semantic Search and Retrieval API endpoints (M5).

POST /api/v1/contracts/{id}/search    — Semantic vector search across contract chunks
POST /api/v1/contracts/{id}/retrieval — Grounded RAG context generation

All endpoints require authentication. RLS enforces tenant isolation.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.user import User
from app.repositories import contract_repo
from app.schemas.search import (
    ChunkSearchResultItem,
    ContractSearchRequest,
    ContractSearchResponse,
    RAGContextRequest,
    RAGContextResponse,
)
from app.services import retrieval_service

router = APIRouter(prefix="/contracts", tags=["search"])


@router.post(
    "/{contract_id}/search",
    response_model=ContractSearchResponse,
    summary="Semantic vector search across contract chunks",
)
async def search_contract_chunks(
    contract_id: uuid.UUID,
    payload: ContractSearchRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ContractSearchResponse:
    """Execute pgvector semantic similarity search over text chunks of a contract document.

    Subject to RLS — tenant context enforced via authentication dependency.
    """
    _ = user  # RLS context active
    contract = await contract_repo.get_by_id(session, contract_id)
    if contract is None:
        raise NotFoundError("Contract not found")

    results = await retrieval_service.search_chunks(
        session,
        payload.query,
        contract_id=contract.id,
        version_id=payload.version_id,
        top_k=payload.top_k,
        min_score=payload.min_score,
    )

    items = [ChunkSearchResultItem.model_validate(r) for r in results]

    return ContractSearchResponse(
        contract_id=contract.id,
        query=payload.query,
        total_results=len(items),
        items=items,
    )


@router.post(
    "/{contract_id}/retrieval",
    response_model=RAGContextResponse,
    summary="Generate grounded RAG context for a query",
)
async def get_rag_context(
    contract_id: uuid.UUID,
    payload: RAGContextRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> RAGContextResponse:
    """Generate a structured, bounded RAG context window grounded in matching contract text chunks.

    Subject to RLS — tenant context enforced via authentication dependency.
    """
    _ = user  # RLS context active
    contract = await contract_repo.get_by_id(session, contract_id)
    if contract is None:
        raise NotFoundError("Contract not found")

    rag_res = await retrieval_service.build_rag_context(
        session,
        payload.query,
        contract_id=contract.id,
        version_id=payload.version_id,
        top_k=payload.top_k,
        min_score=payload.min_score,
        max_chunks=payload.max_chunks,
        max_chars=payload.max_chars,
    )

    items = [ChunkSearchResultItem.model_validate(r) for r in rag_res["items"]]

    return RAGContextResponse(
        contract_id=contract.id,
        query=payload.query,
        context_text=rag_res["context_text"],
        chunks_count=rag_res["chunks_count"],
        total_chars=rag_res["total_chars"],
        items=items,
    )
