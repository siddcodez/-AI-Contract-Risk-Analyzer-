"""ProcessingJob model — tracks async contract processing state.

Each contract upload creates exactly one ProcessingJob (initially queued).
The Celery worker pipeline (M3) transitions the job through its lifecycle:
queued → processing → completed | failed.

The error_message field captures failure details for debugging without
exposing internal stack traces to the client.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class JobStatus(enum.StrEnum):
    """Processing job lifecycle states."""

    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ProcessingJob(Base):
    """An async processing job for a contract.

    Attributes:
        id: Primary key (UUID).
        contract_id: FK to the contract being processed.
        status: Current job status.
        started_at: When processing began (null until picked up).
        completed_at: When processing finished (null until done).
        error_message: Failure details (null on success).
        org_id: FK to organization (RLS filter).
        created_at: Row creation timestamp.
        updated_at: Last modification timestamp.
    """

    __tablename__ = "processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        index=True,
    )
    status: Mapped[JobStatus] = mapped_column(
        PG_ENUM(
            JobStatus,
            name="job_status",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=JobStatus.queued,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
