"""Pydantic schemas for risk findings."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.risk_finding import RiskCategory, RiskSeverity


class RiskFindingResponse(BaseModel):
    """Schema representing a single detected risk finding."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contract_id: uuid.UUID
    version_id: uuid.UUID
    org_id: uuid.UUID
    chunk_id: uuid.UUID | None = None
    category: RiskCategory
    severity: RiskSeverity
    title: str
    description: str
    evidence: str
    recommendation: str
    confidence: float = Field(ge=0.0, le=1.0)
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class RiskFindingListResponse(BaseModel):
    """Paginated list of risk findings."""

    items: list[RiskFindingResponse]
    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1)


class RiskSummaryResponse(BaseModel):
    """Summary counts of risk findings categorized by severity level."""

    total: int = Field(ge=0)
    critical: int = Field(ge=0)
    high: int = Field(ge=0)
    medium: int = Field(ge=0)
    low: int = Field(ge=0)
