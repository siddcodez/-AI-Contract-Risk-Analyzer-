"""Unit tests for Chunking Service.

Tests deterministic sliding window text chunking, overlap boundaries,
order preservation, and invalid input validation.
"""

import pytest
from app.core.exceptions import ValidationError
from app.services.chunking_service import chunk_text


class TestChunkingService:
    def test_small_text_single_chunk(self) -> None:
        text = "Short text contract clause."
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_sliding_window_chunks(self) -> None:
        # 250 character text with chunk_size=100 and overlap=20 (step=80)
        text = "A" * 250
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
        assert len(chunks) > 1
        # Order preservation
        assert len(chunks[0]) == 100
        assert chunks[0] == "A" * 100

    def test_rejects_empty_text(self) -> None:
        with pytest.raises(ValidationError, match="Cannot chunk empty"):
            chunk_text("")

    def test_rejects_whitespace_text(self) -> None:
        with pytest.raises(ValidationError, match="Cannot chunk empty"):
            chunk_text("   \n\n\t  ")

    def test_rejects_invalid_overlap(self) -> None:
        with pytest.raises(ValidationError, match="must be non-negative and strictly less"):
            chunk_text("Sample contract text", chunk_size=100, chunk_overlap=100)
