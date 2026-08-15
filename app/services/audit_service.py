"""Audit logging service for tracking security, processing, and review events.

Appends structured events to the audit_logs table. Never logs sensitive text.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.audit_log import AuditActionType, AuditLog
from app.repositories import audit_log_repo

logger = get_logger(__name__)


async def log_audit_event(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    action: AuditActionType | str,
    entity_type: str,
    user_id: uuid.UUID | None = None,
    user_email: str | None = None,
    entity_id: uuid.UUID | None = None,
    metadata_json: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Record an immutable audit log entry in the active database transaction."""
    action_str = action.value if isinstance(action, AuditActionType) else str(action)
    safe_meta = metadata_json or {}

    log_entry = await audit_log_repo.create(
        session,
        org_id=org_id,
        action=action_str,
        entity_type=entity_type,
        user_id=user_id,
        user_email=user_email,
        entity_id=entity_id,
        metadata_json=safe_meta,
        ip_address=ip_address,
    )

    logger.info(
        "audit_event_recorded",
        action=action_str,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else None,
        org_id=str(org_id),
        user_email=user_email,
    )

    return log_entry
