"""Pydantic schemas for organizational precedent and similar clause search."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PrecedentSearchRequest(BaseModel):
    """Request payload for finding similar precedent clauses."""

    query: str = Field(
        ...,
        min_length=3,
        max_length=5000,
        description="Clause text or search query to find matching precedent language for",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of precedent clauses to return (1 to 20)",
    )
    min_score: float = Field(
        default=0.50,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity threshold (0.0 to 1.0)",
    )


class PrecedentItem(BaseModel):
    """Schema representing a single retrieved precedent clause from an organization contract."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: uuid.UUID
    contract_id: uuid.UUID
    version_id: uuid.UUID
    contract_title: str
    file_name: str
    chunk_index: int
    content: str
    similarity_score: float
    created_at: datetime
    metadata_json: dict[str, Any] | None = None


class PrecedentSearchResponse(BaseModel):
    """Response payload containing ranked precedent clauses and disclaimer framing."""

    query_contract_id: uuid.UUID
    query: str
    total_results: int
    items: list[PrecedentItem]
    disclaimer: str = (
        "Past reviewed language from organization repository. "
        "For precedent reference only — not legal advice."
    )
