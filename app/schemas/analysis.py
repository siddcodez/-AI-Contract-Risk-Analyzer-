"""Pydantic schemas for AI contract analysis jobs and status."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.analysis_job import AnalysisJobStatus


class AnalysisJobResponse(BaseModel):
    """Schema representing an AnalysisJob state."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contract_id: uuid.UUID
    version_id: uuid.UUID
    org_id: uuid.UUID
    status: AnalysisJobStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    findings_count: int = Field(default=0, ge=0)
    created_at: datetime
    updated_at: datetime


class AnalysisStatusResponse(BaseModel):
    """Schema representing overall contract analysis status."""

    contract_id: uuid.UUID
    analysis_job_id: uuid.UUID | None = None
    status: AnalysisJobStatus
    findings_count: int = Field(default=0, ge=0)
    error_message: str | None = None
