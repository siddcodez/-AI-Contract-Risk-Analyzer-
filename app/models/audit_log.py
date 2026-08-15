"""AuditLog model — provides an immutable system audit trail.

Tracks security, processing, analysis, and review lifecycle events.
Never stores full sensitive contract text.
Subject to PostgreSQL Row-Level Security (RLS) tenant isolation.
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditActionType(enum.StrEnum):
    """Audit action event types."""

    CONTRACT_UPLOADED = "CONTRACT_UPLOADED"
    PROCESSING_STARTED = "PROCESSING_STARTED"
    PROCESSING_FAILED = "PROCESSING_FAILED"
    CLAUSE_REVIEWED = "CLAUSE_REVIEWED"  # Reserved: for non-decisional reviewer inspection tracking
    CLAUSE_APPROVED = "CLAUSE_APPROVED"
    CLAUSE_REJECTED = "CLAUSE_REJECTED"
    PLAYBOOK_RULE_CREATED = "PLAYBOOK_RULE_CREATED"
    PLAYBOOK_RULE_UPDATED = "PLAYBOOK_RULE_UPDATED"
    REPORT_GENERATED = "REPORT_GENERATED"


class AuditLog(Base):
    """An immutable audit trail entry.

    Attributes:
        id: Primary key (UUID).
        org_id: FK to organization (RLS tenant isolation).
        user_id: FK to actor user (optional for system jobs).
        user_email: Snapshot of actor email.
        action: AuditActionType string.
        entity_type: Target entity type (e.g. 'contract', 'risk_finding').
        entity_id: Target entity UUID.
        metadata_json: Safe metadata (no sensitive text).
        ip_address: Client IP address (optional).
        created_at: Event timestamp.
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_email: Mapped[str | None] = mapped_column(String(320), nullable=True, default=None)
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
