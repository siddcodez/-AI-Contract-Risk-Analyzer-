"""Contract Risk Analysis API endpoints (M4).

GET  /api/v1/contracts/{id}/analysis         — Get analysis status & findings count
GET  /api/v1/contracts/{id}/findings         — List risk findings (paginated, filterable)
GET  /api/v1/contracts/{id}/findings/summary — Get risk summary counts by severity
POST /api/v1/contracts/{id}/analyze          — Trigger / re-run risk analysis

All endpoints require authentication.  Triggering analysis requires reviewer or admin role.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_reviewer_or_above
from app.core.exceptions import NotFoundError
from app.core.rate_limit import rate_limit_analysis
from app.db.session import get_db
from app.models.risk_finding import RiskCategory, RiskSeverity
from app.models.user import User
from app.repositories import analysis_job_repo, contract_repo, risk_finding_repo
from app.schemas.analysis import AnalysisStatusResponse
from app.schemas.risk_finding import (
    RiskFindingListResponse,
    RiskFindingResponse,
    RiskSummaryResponse,
)
from app.services import analysis_service

router = APIRouter(prefix="/contracts", tags=["analysis"])


@router.get(
    "/{contract_id}/analysis",
    response_model=AnalysisStatusResponse,
    summary="Get contract risk analysis status",
)
async def get_analysis_status(
    contract_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AnalysisStatusResponse:
    """Retrieve the current risk analysis status and findings count for a contract.

    RLS ensures the contract belongs to the user's organization.
    """
    _ = user  # RLS context
    contract = await contract_repo.get_by_id(session, contract_id)
    if contract is None:
        raise NotFoundError("Contract not found")

    job = await analysis_job_repo.get_latest_by_contract(session, contract_id)
    if job is None:
        raise NotFoundError("No analysis job found for contract")

    return AnalysisStatusResponse(
        contract_id=contract.id,
        analysis_job_id=job.id,
        status=job.status,
        findings_count=job.findings_count,
        error_message=job.error_message,
    )


@router.get(
    "/{contract_id}/findings",
    response_model=RiskFindingListResponse,
    summary="List risk findings for a contract",
)
async def list_findings(
    contract_id: uuid.UUID,
    category: RiskCategory | None = Query(default=None, description="Filter by risk category"),
    severity: RiskSeverity | None = Query(default=None, description="Filter by risk severity"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> RiskFindingListResponse:
    """List risk findings detected in a contract document with filtering and pagination.

    RLS ensures the contract and findings belong to the user's organization.
    """
    _ = user  # RLS context
    contract = await contract_repo.get_by_id(session, contract_id)
    if contract is None:
        raise NotFoundError("Contract not found")

    findings = await risk_finding_repo.list_by_contract(
        session,
        contract_id,
        category=category,
        severity=severity,
        skip=skip,
        limit=limit,
    )
    total = await risk_finding_repo.count_by_contract(
        session,
        contract_id,
        category=category,
        severity=severity,
    )

    return RiskFindingListResponse(
        items=[RiskFindingResponse.model_validate(f) for f in findings],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{contract_id}/findings/summary",
    response_model=RiskSummaryResponse,
    summary="Get risk severity summary for a contract",
)
async def get_findings_summary(
    contract_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> RiskSummaryResponse:
    """Retrieve summary counts of risk findings categorized by severity.

    RLS ensures the contract belongs to the user's organization.
    """
    _ = user  # RLS context
    contract = await contract_repo.get_by_id(session, contract_id)
    if contract is None:
        raise NotFoundError("Contract not found")

    summary_data = await risk_finding_repo.get_summary_by_contract(session, contract_id)
    return RiskSummaryResponse(**summary_data)


@router.post(
    "/{contract_id}/analyze",
    response_model=AnalysisStatusResponse,
    status_code=202,
    summary="Trigger or re-run risk analysis on a contract",
    dependencies=[Depends(rate_limit_analysis())],
)
async def trigger_analysis(
    contract_id: uuid.UUID,
    user: User = Depends(require_reviewer_or_above),
    session: AsyncSession = Depends(get_db),
) -> AnalysisStatusResponse:
    """Trigger or re-run AI risk analysis on an uploaded contract.

    Requires Reviewer or Admin role. RLS context enforced.
    """
    contract = await contract_repo.get_by_id(session, contract_id)
    if contract is None:
        raise NotFoundError("Contract not found")

    job = await analysis_service.trigger_analysis(
        session,
        contract_id=contract.id,
        org_id=user.org_id,
    )

    return AnalysisStatusResponse(
        contract_id=contract.id,
        analysis_job_id=job.id,
        status=job.status,
        findings_count=job.findings_count,
        error_message=job.error_message,
    )
