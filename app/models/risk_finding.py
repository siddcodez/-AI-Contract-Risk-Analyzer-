"""RiskFinding model — represents a detected legal or business risk in a contract.

Each finding is linked to a contract, version, organization (tenant isolation),
and optionally a specific contract text chunk. Findings detail the risk category,
severity rating, verbatim text evidence, recommendation, and confidence score.
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RiskSeverity(enum.StrEnum):
    """Severity classification for contract risks."""

    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class RiskCategory(enum.StrEnum):
    """Legal and business risk categories."""

    termination = "termination"
    liability = "liability"
    indemnification = "indemnification"
    payment = "payment"
    confidentiality = "confidentiality"
    intellectual_property = "intellectual_property"
    data_privacy = "data_privacy"
    security = "security"
    governing_law = "governing_law"
    dispute_resolution = "dispute_resolution"
    renewal = "renewal"
    compliance = "compliance"
    sla = "sla"
    insurance = "insurance"
    other = "other"


class RiskFinding(Base):
    """A risk finding detected in a contract document.

    Attributes:
        id: Primary key (UUID).
        contract_id: FK to the parent contract.
        version_id: FK to the specific contract version.
        org_id: FK to organization (RLS tenant isolation filter).
        chunk_id: FK to the text chunk where evidence was found (optional).
        category: Risk category enum.
        severity: Risk severity rating enum.
        title: Short title summarizing the risk finding.
        description: Detailed explanation of the legal or business risk.
        evidence: Verbatim clause text extracted from the document as proof.
        recommendation: Suggested redline or mitigation guidance.
        confidence: Confidence score between 0.0 and 1.0.
        metadata_json: Optional structured metadata (JSON).
        created_at: Row creation timestamp.
        updated_at: Last modification timestamp.
    """

    __tablename__ = "risk_findings"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_risk_finding_confidence",
        ),
        Index("ix_risk_findings_contract_severity", "contract_id", "severity"),
        Index("ix_risk_findings_contract_category", "contract_id", "category"),
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
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contract_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category: Mapped[RiskCategory] = mapped_column(
        PG_ENUM(
            RiskCategory,
            name="risk_category",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=RiskCategory.other,
    )
    severity: Mapped[RiskSeverity] = mapped_column(
        PG_ENUM(
            RiskSeverity,
            name="risk_severity",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=RiskSeverity.medium,
    )
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
