"""Pydantic schemas for semantic search and RAG retrieval APIs (M5)."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class ContractSearchRequest(BaseModel):
    """Payload for semantic vector similarity search requests."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        min_length=1,
        max_length=2000,
        description="Free-text legal query to search across contract chunks",
    )
    top_k: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Maximum number of search results to return",
    )
    min_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score threshold (0.0 to 1.0)",
    )
    version_id: uuid.UUID | None = Field(
        default=None,
        description="Optional contract version ID filter",
    )


class ChunkSearchResultItem(BaseModel):
    """Single matching chunk result item from vector search."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: uuid.UUID
    contract_id: uuid.UUID
    version_id: uuid.UUID
    chunk_index: int
    content: str
    similarity_score: float = Field(ge=0.0, le=1.0)


class ContractSearchResponse(BaseModel):
    """Response wrapper for contract semantic search endpoint."""

    contract_id: uuid.UUID
    query: str
    total_results: int
    items: list[ChunkSearchResultItem]


class RAGContextRequest(BaseModel):
    """Payload for RAG context retrieval requests."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        min_length=1,
        max_length=2000,
        description="Query topic for generating grounded RAG context window",
    )
    top_k: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Max candidate chunks retrieved during vector search",
    )
    min_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score threshold",
    )
    max_chunks: int | None = Field(
        default=None,
        ge=1,
        le=50,
        description="Maximum chunks included in assembled context",
    )
    max_chars: int | None = Field(
        default=None,
        ge=100,
        le=50000,
        description="Maximum character budget for assembled context string",
    )
    version_id: uuid.UUID | None = Field(
        default=None,
        description="Optional contract version ID filter",
    )


class RAGContextResponse(BaseModel):
    """Response wrapper for RAG context retrieval endpoint."""

    contract_id: uuid.UUID
    query: str
    context_text: str
    chunks_count: int
    total_chars: int
    items: list[ChunkSearchResultItem]


class GroundedCitation(BaseModel):
    """Structured evidence citation grounded in a retrieved contract chunk."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: uuid.UUID
    chunk_index: int
    similarity_score: float = Field(ge=0.0, le=1.0)
    quote: str = Field(min_length=1, description="Verbatim quote from the referenced chunk")


class AskContractRequest(BaseModel):
    """Payload for grounded contract Q&A / RAG generation requests."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        min_length=1,
        max_length=2000,
        description="Question to be answered using only retrieved contract context",
    )
    top_k: int | None = Field(
        default=None,
        ge=1,
        le=50,
        description="Max candidate chunks to retrieve during vector search",
    )
    min_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score threshold (0.0 to 1.0)",
    )
    version_id: uuid.UUID | None = Field(
        default=None,
        description="Optional contract version ID filter",
    )


class AskContractResponse(BaseModel):
    """Response wrapper for grounded contract Q&A."""

    contract_id: uuid.UUID
    query: str
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    citations: list[GroundedCitation]
    retrieval_count: int
    model: str
