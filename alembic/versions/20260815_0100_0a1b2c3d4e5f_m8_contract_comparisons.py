"""M8: contract comparisons table with RLS, uniqueness constraint, and indexes

Revision ID: 0a1b2c3d4e5f
Revises: f6a7b8c9d0e1
Create Date: 2026-08-15 01:00:00.000000+00:00

Creates:
- comparisons table for persisting deterministic contract version comparisons
- Unique constraint on (contract_id, from_version_id, to_version_id) for idempotency
- Row-Level Security (RLS) policy for tenant isolation
- Grants for app_user runtime role
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "0a1b2c3d4e5f"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- comparisons table -------------------------------------------------
    op.create_table(
        "comparisons",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "contract_id",
            sa.Uuid,
            sa.ForeignKey("contracts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "from_version_id",
            sa.Uuid,
            sa.ForeignKey("contract_versions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "to_version_id",
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
        sa.Column("risk_score_from", sa.Integer, nullable=False, server_default="0"),
        sa.Column("risk_score_to", sa.Integer, nullable=False, server_default="0"),
        sa.Column("risk_delta", sa.Integer, nullable=False, server_default="0"),
        sa.Column("clauses_added_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("clauses_removed_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("clauses_modified_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("clauses_unchanged_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("diff_summary_json", JSONB, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "contract_id",
            "from_version_id",
            "to_version_id",
            name="uq_contract_comparison_versions",
        ),
    )

    # --- Row-Level Security (RLS) ------------------------------------------
    op.execute("ALTER TABLE comparisons ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE comparisons FORCE ROW LEVEL SECURITY;")

    op.execute(
        """
        CREATE POLICY tenant_isolation ON comparisons
        FOR ALL
        TO PUBLIC
        USING (org_id::text = current_setting('app.current_org_id', true))
        WITH CHECK (org_id::text = current_setting('app.current_org_id', true));
        """
    )

    # --- Runtime Role Grants ------------------------------------------------
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON comparisons TO app_user;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON comparisons;")
    op.drop_table("comparisons")
