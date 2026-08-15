"""M3: contract_chunks table with pgvector embeddings and RLS

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-13 02:00:00.000000+00:00

Creates:
- pgvector extension (if not already enabled)
- contract_chunks table with vector(1536) embedding column
- Row-Level Security policy for tenant isolation
- Grants for app_user runtime role
"""

import pgvector
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Enable pgvector extension -------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # --- contract_chunks table -----------------------------------------------
    op.create_table(
        "contract_chunks",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "contract_id",
            sa.Uuid,
            sa.ForeignKey("contracts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "version_id",
            sa.Uuid,
            sa.ForeignKey("contract_versions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "org_id",
            sa.Uuid,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(1536), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "contract_id",
            "version_id",
            "chunk_index",
            name="uq_contract_chunk_index",
        ),
    )

    op.create_index(
        "ix_contract_chunks_contract_chunk",
        "contract_chunks",
        ["contract_id", "chunk_index"],
    )

    # --- Row-Level Security --------------------------------------------------
    op.execute("ALTER TABLE contract_chunks ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON contract_chunks
            FOR ALL
            USING (org_id::text = current_setting('app.current_org_id', true))
            WITH CHECK (org_id::text = current_setting('app.current_org_id', true))
        """
    )

    # --- Grants for app_user -------------------------------------------------
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON contract_chunks TO app_user")


def downgrade() -> None:
    op.execute("REVOKE ALL ON contract_chunks FROM app_user")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON contract_chunks")
    op.drop_index("ix_contract_chunks_contract_chunk", table_name="contract_chunks")
    op.drop_table("contract_chunks")
