"""ReportJob model — tracks async PDF report generation jobs.

Tied explicitly to (contract_id, version_id) to ensure precise version scoping.
Subject to PostgreSQL Row-Level Security (RLS) tenant isolation.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReportJobStatus(enum.StrEnum):
    """Report generation job lifecycle states."""

    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ReportJob(Base):
    """An async PDF report generation job.

    Attributes:
        id: Primary key (UUID).
        contract_id: FK to parent contract.
        version_id: FK to specific contract version.
        org_id: FK to organization (RLS tenant isolation).
        status: Job status (queued | processing | completed | failed).
        storage_key: MinIO/S3 object key where generated PDF is stored.
        file_size: Size in bytes of the generated PDF.
        error_message: Failure details if generation failed.
        started_at: Timestamp when generation began.
        completed_at: Timestamp when generation finished.
        created_at: Row creation timestamp.
        updated_at: Last modification timestamp.
    """

    __tablename__ = "report_jobs"

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
    status: Mapped[str] = mapped_column(String(32), default=ReportJobStatus.queued, index=True)
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True, default=None)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
