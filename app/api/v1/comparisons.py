"""Contract version comparison API endpoints (M8).

GET /api/v1/contracts/{contract_id}/compare
    ?from_version_id={UUID}&to_version_id={UUID}&refresh={bool}
    Computes/retrieves deterministic clause diffs (added/removed/modified/unchanged)
    and risk score deltas between two versions of the same contract.
    Subject to Postgres RLS tenant isolation.

POST /api/v1/contracts/{contract_id}/compare/explain-clause
    On-demand endpoint to generate a plain-English AI summary of modifications
    for a specific modified clause. Keeps LLM execution isolated and on-demand.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.logging import get_logger
from app.core.rate_limit import rate_limit_ask, rate_limit_search
from app.db.session import get_db
from app.models.user import User
from app.schemas.comparison import (
    ClauseExplanationRequest,
    ClauseExplanationResponse,
    ContractComparisonResponse,
)
from app.services import comparison_service, llm_service

logger = get_logger(__name__)

router = APIRouter(prefix="/contracts", tags=["comparisons"])


@router.get(
    "/{contract_id}/compare",
    response_model=ContractComparisonResponse,
    summary="Compare two contract versions deterministically",
    dependencies=[Depends(rate_limit_search())],
)
async def compare_contract_versions(
    contract_id: uuid.UUID,
    from_version_id: uuid.UUID = Query(..., description="Baseline version UUID"),
    to_version_id: uuid.UUID = Query(..., description="Target version UUID to compare against"),
    refresh: bool = Query(False, description="Whether to force recomputation of comparison"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ContractComparisonResponse:
    """Compare two versions of the same contract deterministically.

    Identifies added, removed, modified, and unchanged clauses, calculates
    risk score delta, and persists results for caching.
    Enforces PostgreSQL Row-Level Security (RLS) tenant isolation.
    """
    _ = user  # RLS context active
    return await comparison_service.compare_contract_versions(
        session,
        contract_id=contract_id,
        from_version_id=from_version_id,
        to_version_id=to_version_id,
        org_id=user.org_id,
        refresh=refresh,
    )


@router.post(
    "/{contract_id}/compare/explain-clause",
    response_model=ClauseExplanationResponse,
    summary="Generate on-demand AI explanation for a modified clause",
    dependencies=[Depends(rate_limit_ask())],
)
async def explain_modified_clause(
    contract_id: uuid.UUID,
    payload: ClauseExplanationRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ClauseExplanationResponse:
    """Generate an on-demand, non-authoritative AI explanation of clause differences.

    Keeps heavy LLM generation isolated to explicit on-demand user clicks in the UI.
    """
    _ = (user, session)
    context = f"ORIGINAL CLAUSE:\n{payload.from_text}\n\nREVISED CLAUSE:\n{payload.to_text}"
    sources = [
        {"chunk_id": uuid.uuid4(), "chunk_index": 0, "content": context, "similarity_score": 0.95}
    ]
    try:
        query_text = (
            f"Summarize key differences between these two versions of "
            f"the {payload.clause_type} clause."
        )
        grounded = await llm_service.generate_grounded_answer(
            query_text,
            context,
            sources,
        )
        explanation = grounded.answer
    except Exception as exc:
        logger.warning(
            "clause_explanation_fallback",
            contract_id=str(contract_id),
            clause_type=payload.clause_type,
            exc_info=exc,
        )
        explanation = (
            "Unable to generate AI explanation. Please review the highlighted text diff directly."
        )

    return ClauseExplanationResponse(
        clause_type=payload.clause_type,
        explanation=explanation.strip() if explanation else "Text modified between versions.",
        is_ai_generated=True,
    )
