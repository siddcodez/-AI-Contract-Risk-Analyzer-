"""ContractVersion model — tracks versioned uploads of a contract.

When a contract is re-uploaded or revised, a new version row is created.
Each version has its own storage_key pointing to the file in object storage.
Version 1 is always created alongside the initial Contract record.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ContractVersion(Base):
    """A versioned snapshot of a contract document.

    Attributes:
        id: Primary key (UUID).
        contract_id: FK to the parent contract.
        version_number: Monotonically increasing version (1, 2, 3…).
        file_name: Original filename for this version.
        file_size: File size in bytes.
        content_type: MIME type.
        storage_key: Object key in MinIO / S3.
        org_id: FK to organization (RLS filter — denormalised for policy).
        created_at: Row creation timestamp.
    """

    __tablename__ = "contract_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    file_name: Mapped[str] = mapped_column(String(512))
    file_size: Mapped[int] = mapped_column(Integer)
    content_type: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(1024))
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
