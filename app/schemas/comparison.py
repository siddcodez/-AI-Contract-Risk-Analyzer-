"""Pydantic schemas for Contract Version Comparison (M8)."""

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ClauseChangeType(enum.StrEnum):
    """Classification of change for a specific clause between two versions."""

    added = "added"
    removed = "removed"
    modified = "modified"
    unchanged = "unchanged"


class ClauseDiffItem(BaseModel):
    """Detailed diff for a single clause category between versions."""

    clause_type: str = Field(..., description="Canonical clause type identifier")
    display_name: str = Field(..., description="Human-readable clause name")
    change_type: ClauseChangeType = Field(..., description="Classification of change")
    from_text: str | None = Field(None, description="Original clause text in from_version")
    to_text: str | None = Field(None, description="Updated clause text in to_version")
    from_severity: str | None = Field(None, description="Severity in from_version")
    to_severity: str | None = Field(None, description="Severity in to_version")
    ai_explanation: str | None = Field(
        None,
        description="Optional non-authoritative AI summary of modification (if generated)",
    )
    metadata_json: dict[str, Any] | None = None


class ContractComparisonResponse(BaseModel):
    """Response payload for contract version comparison."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contract_id: uuid.UUID
    from_version_id: uuid.UUID
    to_version_id: uuid.UUID
    from_version_number: int | None = None
    to_version_number: int | None = None
    risk_score_from: int
    risk_score_to: int
    risk_delta: int
    clauses_added_count: int
    clauses_removed_count: int
    clauses_modified_count: int
    clauses_unchanged_count: int
    diff_items: list[ClauseDiffItem]
    created_at: datetime
    updated_at: datetime
    disclaimer: str = (
        "Deterministic version comparison based on classified findings and text diffing. "
        "Not legal advice."
    )


class ClauseExplanationRequest(BaseModel):
    """On-demand request for AI explanation of a specific modified clause."""

    clause_type: str
    from_text: str = Field(..., min_length=5)
    to_text: str = Field(..., min_length=5)


class ClauseExplanationResponse(BaseModel):
    """Response payload for on-demand AI explanation of a modified clause."""

    clause_type: str
    explanation: str
    is_ai_generated: bool = True
    disclaimer: str = "AI-generated summary of clause modifications. Not legal advice."
