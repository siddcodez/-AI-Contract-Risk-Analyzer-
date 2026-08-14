"""Pydantic schemas for missing-clause detection.

Defines response structures for detected missing contract clauses,
including confidence metrics, factual explanations, and summary statistics.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MissingClauseItem(BaseModel):
    """Schema representing a single detected missing clause."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contract_id: uuid.UUID
    version_id: uuid.UUID
    clause_type: str = Field(
        ...,
        description="Standardized clause type identifier (e.g., 'data_protection')",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score in the absence determination (0.0 to 1.0)",
    )
    reason: str = Field(
        ...,
        description="Concise, factual explanation of why the clause is considered missing",
    )
    status: str = Field(
        default="missing",
        description="Current state of the missing clause finding",
    )
    metadata_json: dict[str, Any] | None = Field(
        default=None,
        description="Optional structured metadata",
    )
    created_at: datetime


class MissingClauseListResponse(BaseModel):
    """Response payload for missing clause queries."""

    contract_id: uuid.UUID
    version_id: uuid.UUID
    items: list[MissingClauseItem]
    total: int = Field(..., ge=0, description="Total count of missing clauses")


class MissingClauseSummary(BaseModel):
    """Summary schema detailing expected vs detected vs missing clause metrics."""

    contract_id: uuid.UUID
    version_id: uuid.UUID
    contract_type: str
    expected_count: int
    detected_count: int
    missing_count: int
    items: list[MissingClauseItem]
