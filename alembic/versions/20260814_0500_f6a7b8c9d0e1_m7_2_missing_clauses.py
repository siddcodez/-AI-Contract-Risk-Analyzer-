"""M7.2: missing_clauses table with RLS, uniqueness constraint, and indexes

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-14 05:00:00.000000+00:00

Creates:
- missing_clauses table for persisting detected missing contract clauses
- Unique constraint on (contract_id, version_id, clause_type) for idempotency
- Check constraint on confidence (0.0 to 1.0)
- Row-Level Security (RLS) policy for tenant isolation
- Grants for app_user runtime role
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- missing_clauses table ---------------------------------------------
    op.create_table(
        "missing_clauses",
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
        sa.Column("clause_type", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="missing"),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_missing_clause_confidence",
        ),
        sa.UniqueConstraint(
            "contract_id",
            "version_id",
            "clause_type",
            name="uq_missing_clause_contract_version_type",
        ),
    )

    op.create_index(
        "ix_missing_clauses_contract_version",
        "missing_clauses",
        ["contract_id", "version_id"],
    )
    op.create_index(
        "ix_missing_clauses_clause_type",
        "missing_clauses",
        ["clause_type"],
    )

    # --- Row-Level Security --------------------------------------------------
    op.execute("ALTER TABLE missing_clauses ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON missing_clauses
            FOR ALL
            USING (org_id::text = current_setting('app.current_org_id', true))
            WITH CHECK (org_id::text = current_setting('app.current_org_id', true))
        """
    )

    # --- Grants for app_user -------------------------------------------------
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON missing_clauses TO app_user")


def downgrade() -> None:
    op.execute("REVOKE ALL ON missing_clauses FROM app_user")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON missing_clauses")
    op.drop_index("ix_missing_clauses_clause_type", table_name="missing_clauses")
    op.drop_index("ix_missing_clauses_contract_version", table_name="missing_clauses")
    op.drop_table("missing_clauses")
