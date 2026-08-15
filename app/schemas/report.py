"""Pydantic schemas for Contract PDF Reports (Phase 12)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReportGenerateResponse(BaseModel):
    """Response returned immediately when report generation is triggered."""

    contract_id: uuid.UUID
    version_id: uuid.UUID
    job_id: uuid.UUID
    status: str
    message: str


class ReportStatusResponse(BaseModel):
    """Status of the latest report generation job for a contract version."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contract_id: uuid.UUID
    version_id: uuid.UUID
    status: str
    storage_key: str | None = None
    file_size: int | None = None
    error_message: str | None = None
    download_url: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
