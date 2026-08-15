"""M9: Review actions and Audit logs with RLS, risk_findings status column, and indexes

Revision ID: 1b2c3d4e5f6a
Revises: 0a1b2c3d4e5f
Create Date: 2026-08-15 02:00:00.000000+00:00

Creates:
- status column on risk_findings (server_default="pending_review")
- review_actions table for append-only reviewer action audit history
- audit_logs table for tenant-scoped immutable system audit trails
- Row-Level Security (RLS) policies for tenant isolation on both tables
- Grants for app_user runtime role
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "1b2c3d4e5f6a"
down_revision = "0a1b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1. Add status column to risk_findings with backfill default --------
    op.add_column(
        "risk_findings",
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="pending_review",
        ),
    )

    # --- 2. review_actions table (append-only) -----------------------------
    op.create_table(
        "review_actions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "contract_id",
            sa.Uuid,
            sa.ForeignKey("contracts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "finding_id",
            sa.Uuid,
            sa.ForeignKey("risk_findings.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "reviewer_id",
            sa.Uuid,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "org_id",
            sa.Uuid,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            index=True,
        ),
    )

    # --- 3. audit_logs table (append-only) ---------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "org_id",
            sa.Uuid,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.Uuid,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("user_email", sa.String(320), nullable=True),
        sa.Column("action", sa.String(64), nullable=False, index=True),
        sa.Column("entity_type", sa.String(64), nullable=False, index=True),
        sa.Column("entity_id", sa.Uuid, nullable=True, index=True),
        sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            index=True,
        ),
    )

    # --- 4. Row-Level Security (RLS) ---------------------------------------
    for table_name in ("review_actions", "audit_logs"):
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table_name}
            FOR ALL
            TO PUBLIC
            USING (org_id::text = current_setting('app.current_org_id', true))
            WITH CHECK (org_id::text = current_setting('app.current_org_id', true));
            """
        )

    # --- 5. Runtime Role Grants --------------------------------------------
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON review_actions TO app_user;
                GRANT SELECT, INSERT, UPDATE, DELETE ON audit_logs TO app_user;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON audit_logs;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON review_actions;")
    op.drop_table("audit_logs")
    op.drop_table("review_actions")
    op.drop_column("risk_findings", "status")
