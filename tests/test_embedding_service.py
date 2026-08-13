"""Unit tests for Embedding Service.

Tests deterministic mock embedding generation, output dimensions (1536),
batch inputs, and empty list handling.
"""

from app.services.embedding_service import embed_texts


class TestEmbeddingService:
    def test_embeds_single_text(self) -> None:
        texts = ["This is a sample contract clause for vector embedding."]
        vectors = embed_texts(texts)
        assert len(vectors) == 1
        assert len(vectors[0]) == 1536
        assert all(isinstance(val, float) for val in vectors[0])

    def test_embeds_batch(self) -> None:
        texts = ["Clause 1: Term", "Clause 2: Payment", "Clause 3: Termination"]
        vectors = embed_texts(texts)
        assert len(vectors) == 3
        for vec in vectors:
            assert len(vec) == 1536

    def test_deterministic_output(self) -> None:
        text = "Identical text content should produce identical mock vector."
        vec1 = embed_texts([text])[0]
        vec2 = embed_texts([text])[0]
        assert vec1 == vec2

    def test_empty_list_returns_empty(self) -> None:
        vectors = embed_texts([])
        assert vectors == []
