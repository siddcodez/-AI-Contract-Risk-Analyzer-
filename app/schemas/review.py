"""Pydantic schemas for Review Actions and Audit Logs (Phase 11)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReviewActionCreateRequest(BaseModel):
    """Payload for submitting a reviewer decision on a risk finding."""

    action: str = Field(
        ..., pattern="^(approved|rejected)$", description="'approved' or 'rejected'"
    )
    comment: str | None = Field(
        None, max_length=2000, description="Optional reviewer notes/rationale"
    )


class ReviewActionResponse(BaseModel):
    """Response payload for a recorded review action."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contract_id: uuid.UUID
    finding_id: uuid.UUID
    reviewer_id: uuid.UUID | None = None
    org_id: uuid.UUID
    action: str
    comment: str | None = None
    created_at: datetime | None = None


class ReviewActionListResponse(BaseModel):
    """List of review actions for a finding or contract."""

    items: list[ReviewActionResponse]
    total: int


class AuditLogResponse(BaseModel):
    """Response payload for a single immutable audit log record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    user_id: uuid.UUID | None = None
    user_email: str | None = None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None = None
    metadata_json: dict[str, Any]
    ip_address: str | None = None
    created_at: datetime | None = None


class AuditLogListResponse(BaseModel):
    """Paginated list of audit logs."""

    items: list[AuditLogResponse]
    total: int
    skip: int
    limit: int
