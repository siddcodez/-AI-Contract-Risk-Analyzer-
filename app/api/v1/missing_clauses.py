"""API endpoints for contract missing-clause detection.

Provides structured endpoints to query detected missing clauses for a contract version.
Enforces JWT authentication, tenant isolation via RLS, and consistent error handling.
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.db.session import get_db, set_tenant_context
from app.models.user import User
from app.repositories import (
    contract_repo,
    contract_version_repo,
    missing_clause_repo,
)
from app.schemas.missing_clause import MissingClauseItem, MissingClauseListResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/contracts/{contract_id}", tags=["missing-clauses"])


@router.get(
    "/missing-clauses",
    response_model=MissingClauseListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get missing clauses for a contract",
    description=(
        "Fetch the deterministic set of missing clauses identified for a specific "
        "contract version. If version_id is omitted, returns results for the latest version."
    ),
)
async def get_missing_clauses(
    contract_id: uuid.UUID,
    version_id: uuid.UUID | None = Query(
        default=None,
        description="Target contract version UUID. If omitted, uses the latest version.",
    ),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MissingClauseListResponse:
    """Retrieve missing clauses for a contract and version."""
    await set_tenant_context(session, str(current_user.org_id))

    contract = await contract_repo.get_by_id(session, contract_id)
    if contract is None:
        raise NotFoundError(f"Contract {contract_id} not found")

    versions = await contract_version_repo.list_by_contract(session, contract_id)
    if not versions:
        raise NotFoundError(f"No contract versions found for contract {contract_id}")

    target_version_id = version_id if version_id is not None else versions[-1].id

    # Verify requested version belongs to this contract
    if not any(v.id == target_version_id for v in versions):
        raise NotFoundError(f"Version {target_version_id} not found for contract {contract_id}")

    records = await missing_clause_repo.list_by_contract_and_version(
        session, contract_id, target_version_id
    )

    items = [MissingClauseItem.model_validate(r) for r in records]

    logger.info(
        "missing_clauses_fetched",
        contract_id=str(contract_id),
        version_id=str(target_version_id),
        org_id=str(current_user.org_id),
        count=len(items),
    )

    return MissingClauseListResponse(
        contract_id=contract_id,
        version_id=target_version_id,
        items=items,
        total=len(items),
    )
