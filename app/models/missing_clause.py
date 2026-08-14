"""MissingClause model — represents a detected missing contract clause.

Tracks expected clauses that were not identified in a specific contract version.
Includes deterministic confidence score, factual absence reason, and tenant isolation via org_id.
A unique constraint on (contract_id, version_id, clause_type) ensures idempotency.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MissingClause(Base):
    """A missing clause detected for a specific contract version.

    Attributes:
        id: Primary key (UUID).
        contract_id: FK to the parent contract.
        version_id: FK to the specific contract version.
        org_id: FK to organization (RLS tenant isolation filter).
        clause_type: Standardized type of the missing clause (e.g., 'data_protection').
        confidence: Confidence score in the absence determination (0.0 to 1.0).
        reason: Factual, concise explanation of why the clause is considered missing.
        status: Current status of the finding (default: 'missing').
        metadata_json: Optional structured metadata.
        created_at: Row creation timestamp.
        updated_at: Last modification timestamp.
    """

    __tablename__ = "missing_clauses"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_missing_clause_confidence",
        ),
        UniqueConstraint(
            "contract_id",
            "version_id",
            "clause_type",
            name="uq_missing_clause_contract_version_type",
        ),
        Index("ix_missing_clauses_contract_version", "contract_id", "version_id"),
        Index("ix_missing_clauses_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        index=True,
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contract_versions.id", ondelete="CASCADE"),
        index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    clause_type: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, server_default="1.0")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="missing")
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
