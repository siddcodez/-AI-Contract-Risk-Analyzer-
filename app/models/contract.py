"""Contract model — represents an uploaded contract document.

Each contract belongs to one organization (tenant isolation via org_id)
and tracks the uploaded file's metadata plus its processing status.
The actual file content lives in object storage (MinIO/S3); the
storage_key column holds the object key.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ContractStatus(enum.StrEnum):
    """Processing lifecycle states for a contract."""

    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class Contract(Base):
    """An uploaded contract document.

    Attributes:
        id: Primary key (UUID).
        title: Display name for the contract.
        file_name: Original uploaded filename.
        file_size: File size in bytes.
        content_type: MIME type of the uploaded file.
        storage_key: Object key in MinIO / S3.
        status: Current processing status.
        org_id: FK to the owning organization (RLS filter).
        uploaded_by: FK to the user who uploaded the contract.
        created_at: Row creation timestamp.
        updated_at: Last modification timestamp.
    """

    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(512))
    file_name: Mapped[str] = mapped_column(String(512))
    file_size: Mapped[int] = mapped_column(Integer)
    content_type: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(1024), unique=True)
    status: Mapped[ContractStatus] = mapped_column(
        PG_ENUM(
            ContractStatus,
            name="contract_status",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=ContractStatus.pending,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships (eager-load to avoid async lazy-load errors)
    organization: Mapped["Organization"] = relationship(lazy="selectin")  # type: ignore[name-defined]  # noqa: F821
    uploader: Mapped["User"] = relationship(lazy="selectin")  # type: ignore[name-defined]  # noqa: F821
