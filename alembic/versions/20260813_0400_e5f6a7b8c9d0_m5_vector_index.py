"""M5: HNSW vector index on contract_chunks.embedding

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-13 04:00:00.000000+00:00

Creates:
- HNSW vector index on contract_chunks.embedding using vector_cosine_ops
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Create HNSW vector index for pgvector cosine distance -------------
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_contract_chunks_embedding_hnsw
        ON contract_chunks
        USING hnsw (embedding vector_cosine_ops);
        """
    )


def downgrade() -> None:
    # --- Drop HNSW vector index ---------------------------------------------
    op.execute("DROP INDEX IF EXISTS ix_contract_chunks_embedding_hnsw;")
