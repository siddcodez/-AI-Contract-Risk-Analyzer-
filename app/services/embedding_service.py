"""Embedding generation service.

Provides a pluggable provider abstraction for generating vector embeddings.
By default, uses a deterministic pseudo-random vector generator (mock) based
on SHA-256 hash of the text, ensuring 100% offline unit/integration tests
with exact dimension compliance (1536 dimensions).
"""

import hashlib
import math

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingError(AppError):
    """Raised when vector embedding generation fails."""

    message = "Embedding generation failed"
    code = "EMBEDDING_ERROR"
    status_code = 500


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate vector embeddings for a list of text strings.

    Args:
        texts: List of text chunks to embed.

    Returns:
        List of float vectors, each of length settings.EMBEDDING_DIMENSION.

    Raises:
        EmbeddingError: If embedding generation fails or dimension mismatch occurs.
    """
    if not texts:
        return []

    settings = get_settings()
    dimension = settings.EMBEDDING_DIMENSION
    provider = settings.EMBEDDING_PROVIDER.lower()

    if provider == "mock":
        embeddings = [_generate_mock_vector(t, dimension) for t in texts]
    else:
        logger.warning(
            "Unknown or unsupported embedding provider, falling back to mock",
            provider=provider,
        )
        embeddings = [_generate_mock_vector(t, dimension) for t in texts]

    # Validate output dimensions
    for idx, vec in enumerate(embeddings):
        if len(vec) != dimension:
            raise EmbeddingError(
                f"Generated embedding dimension ({len(vec)}) does not match "
                f"required setting ({dimension})",
                details={"chunk_index": idx, "expected_dimension": dimension},
            )

    return embeddings


def _generate_mock_vector(text: str, dimension: int) -> list[float]:
    """Generate a unit-normalized pseudo-random float vector deterministically.

    Uses SHA-256 seed expansion to produce reproducible float values in range [-1.0, 1.0].
    """
    raw_vec: list[float] = []
    base_seed = text.encode("utf-8")

    # Generate pseudo-random numbers by hashing with counter suffixes
    counter = 0
    while len(raw_vec) < dimension:
        seed = base_seed + f":{counter}".encode()
        hash_digest = hashlib.sha256(seed).digest()

        # Extract 4-byte floats from hash
        for i in range(0, len(hash_digest), 4):
            if len(raw_vec) >= dimension:
                break
            val_int = int.from_bytes(hash_digest[i : i + 4], byteorder="big", signed=True)
            val_float = val_int / (2**31)  # float in [-1.0, 1.0]
            raw_vec.append(val_float)

        counter += 1

    # L2 normalize the vector
    norm = math.sqrt(sum(x * x for x in raw_vec))
    if norm > 0:
        return [round(x / norm, 6) for x in raw_vec]

    return [0.0] * dimension
