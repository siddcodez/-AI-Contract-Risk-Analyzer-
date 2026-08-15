"""ContractComparison model — persists version-to-version contract diffs.

Tracks deterministic clause diffs (added/removed/modified/unchanged),
risk score changes (risk_delta), and structured change items.
Subject to PostgreSQL Row-Level Security (RLS) tenant isolation.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ContractComparison(Base):
    """Persisted comparison between two versions of the same contract.

    Attributes:
        id: Primary key (UUID).
        contract_id: FK to parent contract.
        from_version_id: FK to baseline version.
        to_version_id: FK to target version.
        org_id: FK to organization (RLS tenant isolation).
        risk_score_from: Deterministic risk score of from_version (0-100).
        risk_score_to: Deterministic risk score of to_version (0-100).
        risk_delta: Difference in risk score (risk_score_to - risk_score_from).
        clauses_added_count: Number of newly introduced clauses.
        clauses_removed_count: Number of removed clauses.
        clauses_modified_count: Number of modified clauses.
        clauses_unchanged_count: Number of unchanged clauses.
        diff_summary_json: JSON list of ClauseDiffItem dictionaries.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "comparisons"
    __table_args__ = (
        UniqueConstraint(
            "contract_id",
            "from_version_id",
            "to_version_id",
            name="uq_contract_comparison_versions",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        index=True,
    )
    from_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contract_versions.id", ondelete="CASCADE"),
        index=True,
    )
    to_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contract_versions.id", ondelete="CASCADE"),
        index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    risk_score_from: Mapped[int] = mapped_column(Integer, default=0)
    risk_score_to: Mapped[int] = mapped_column(Integer, default=0)
    risk_delta: Mapped[int] = mapped_column(Integer, default=0)
    clauses_added_count: Mapped[int] = mapped_column(Integer, default=0)
    clauses_removed_count: Mapped[int] = mapped_column(Integer, default=0)
    clauses_modified_count: Mapped[int] = mapped_column(Integer, default=0)
    clauses_unchanged_count: Mapped[int] = mapped_column(Integer, default=0)
    diff_summary_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
