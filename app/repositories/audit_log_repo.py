"""Repository for AuditLog database operations.

audit_logs table HAS RLS enabled — all queries are subject to the
tenant_isolation policy.
"""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def create(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    action: str,
    entity_type: str,
    user_id: uuid.UUID | None = None,
    user_email: str | None = None,
    entity_id: uuid.UUID | None = None,
    metadata_json: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Append a new audit trail record.

    Subject to RLS WITH CHECK.
    """
    log = AuditLog(
        id=uuid.uuid4(),
        org_id=org_id,
        user_id=user_id,
        user_email=user_email,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=metadata_json or {},
        ip_address=ip_address,
    )
    session.add(log)
    await session.flush()
    return log


async def list_audit_logs(
    session: AsyncSession,
    *,
    action: str | None = None,
    entity_type: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[AuditLog]:
    """Fetch paginated audit logs for the current tenant.

    Subject to RLS.
    """
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)

    stmt = stmt.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_audit_logs(
    session: AsyncSession,
    *,
    action: str | None = None,
    entity_type: str | None = None,
) -> int:
    """Count total audit logs for current tenant matching optional filters."""
    stmt = select(func.count()).select_from(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)

    result = await session.execute(stmt)
    count = result.scalar()
    return count if count is not None else 0
