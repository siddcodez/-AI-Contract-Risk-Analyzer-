"""Audit Logs API endpoints (Phase 11).

GET /api/v1/audit-logs — List immutable tenant audit logs (ADMIN only, paginated).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.user import User
from app.repositories import audit_log_repo
from app.schemas.review import AuditLogListResponse, AuditLogResponse

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get(
    "",
    response_model=AuditLogListResponse,
    summary="List tenant audit logs (Admin only)",
)
async def list_audit_logs(
    action: str | None = Query(None, description="Filter by AuditActionType"),
    entity_type: str | None = Query(None, description="Filter by entity type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    admin_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """Retrieve paginated, immutable audit trail records for the organization.

    Requires Admin role. Subject to PostgreSQL Row-Level Security (RLS) tenant isolation.
    """
    _ = admin_user  # RLS context active
    logs = await audit_log_repo.list_audit_logs(
        session,
        action=action,
        entity_type=entity_type,
        skip=skip,
        limit=limit,
    )
    total = await audit_log_repo.count_audit_logs(
        session,
        action=action,
        entity_type=entity_type,
    )

    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(log) for log in logs],
        total=total,
        skip=skip,
        limit=limit,
    )
