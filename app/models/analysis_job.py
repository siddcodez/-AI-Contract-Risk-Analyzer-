"""AnalysisJob model — tracks async contract risk analysis execution state.

Each contract analysis execution creates an AnalysisJob (queued → processing → completed | failed).
Stores total findings count and diagnostic error details on failure.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnalysisJobStatus(enum.StrEnum):
    """Analysis job lifecycle states."""

    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class AnalysisJob(Base):
    """An async contract risk analysis job.

    Attributes:
        id: Primary key (UUID).
        contract_id: FK to the contract being analyzed.
        version_id: FK to the specific contract version.
        org_id: FK to organization (RLS tenant isolation filter).
        status: Current analysis job status.
        started_at: Timestamp when risk analysis started.
        completed_at: Timestamp when risk analysis finished.
        error_message: Error details if analysis failed.
        findings_count: Total number of risk findings detected.
        created_at: Row creation timestamp.
        updated_at: Last modification timestamp.
    """

    __tablename__ = "analysis_jobs"

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
    status: Mapped[AnalysisJobStatus] = mapped_column(
        PG_ENUM(
            AnalysisJobStatus,
            name="analysis_job_status",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=AnalysisJobStatus.queued,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
