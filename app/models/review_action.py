"""ReviewAction model — tracks human reviewer decisions on risk findings.

Append-only review action log tracking reviewer decisions (approved/rejected),
optional comments, and timestamps.
Subject to PostgreSQL Row-Level Security (RLS) tenant isolation.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReviewActionType(enum.StrEnum):
    """Review decision types."""

    approved = "approved"
    rejected = "rejected"


class ReviewAction(Base):
    """An append-only review decision record for a contract risk finding.

    Attributes:
        id: Primary key (UUID).
        contract_id: FK to parent contract.
        finding_id: FK to target risk finding.
        reviewer_id: FK to reviewer user.
        org_id: FK to organization (RLS tenant isolation).
        action: Review decision (approved | rejected).
        comment: Optional reviewer rationale/notes.
        created_at: Review timestamp.
    """

    __tablename__ = "review_actions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        index=True,
    )
    finding_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("risk_findings.id", ondelete="CASCADE"),
        index=True,
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    action: Mapped[str] = mapped_column(String(32))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    # Relationships
    reviewer: Mapped["User"] = relationship(lazy="selectin")  # type: ignore[name-defined]  # noqa: F821
