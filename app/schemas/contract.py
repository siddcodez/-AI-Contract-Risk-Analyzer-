"""Pydantic schemas for contract upload and management.

These models define the API boundary for M2 contract endpoints.
Internal ORM models are never returned directly to clients.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ContractUploadResponse(BaseModel):
    """Returned after a successful contract upload."""

    contract_id: uuid.UUID
    job_id: uuid.UUID
    status: str = Field(description="Processing job status (queued)")
    file_name: str
    file_size: int = Field(description="File size in bytes")
    content_type: str
    created_at: datetime


class ContractResponse(BaseModel):
    """Full contract details for GET endpoints."""

    id: uuid.UUID
    title: str
    file_name: str
    file_size: int
    content_type: str
    status: str
    org_id: uuid.UUID
    uploaded_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ContractListResponse(BaseModel):
    """Paginated contract list wrapper."""

    contracts: list[ContractResponse]
    total: int
    skip: int
    limit: int


class ContractStatusResponse(BaseModel):
    """Contract processing status check."""

    contract_id: uuid.UUID
    contract_status: str
    job_id: uuid.UUID | None = None
    job_status: str | None = None
    error_message: str | None = None


class ProcessingJobResponse(BaseModel):
    """Processing job details."""

    id: uuid.UUID
    contract_id: uuid.UUID
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
