"""Text chunking service for contract processing.

Splits document text into overlapping, deterministic text chunks.
Preserves document reading order and chunk boundaries.
"""

from app.core.config import get_settings
from app.core.exceptions import ValidationError


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[str]:
    """Split normalized text into overlapping chunks.

    Args:
        text: Normalized plain text to chunk.
        chunk_size: Target size per chunk in characters (defaults to settings.CHUNK_SIZE).
        chunk_overlap: Overlap between consecutive chunks in characters
            (defaults to settings.CHUNK_OVERLAP).

    Returns:
        List of non-empty string chunks in reading order.

    Raises:
        ValidationError: If input text is empty or chunking parameters are invalid.
    """
    if not text or not text.strip():
        raise ValidationError("Cannot chunk empty or whitespace-only text")

    settings = get_settings()
    size = chunk_size if chunk_size is not None else settings.CHUNK_SIZE
    overlap = chunk_overlap if chunk_overlap is not None else settings.CHUNK_OVERLAP

    if size <= 0:
        raise ValidationError(f"Chunk size must be positive, got {size}")
    if overlap < 0 or overlap >= size:
        raise ValidationError(
            f"Chunk overlap ({overlap}) must be non-negative and strictly "
            f"less than chunk size ({size})"
        )

    clean_text = text.strip()
    if len(clean_text) <= size:
        return [clean_text]

    chunks: list[str] = []
    step = size - overlap
    start = 0
    text_length = len(clean_text)

    while start < text_length:
        end = start + size
        chunk_str = clean_text[start:end].strip()
        if chunk_str:
            chunks.append(chunk_str)

        if end >= text_length:
            break

        start += step

    return chunks
