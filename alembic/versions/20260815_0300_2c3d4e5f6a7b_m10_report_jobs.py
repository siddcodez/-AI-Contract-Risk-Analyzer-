"""M10: Contract report jobs table with version scoping, status tracking, and RLS

Revision ID: 2c3d4e5f6a7b
Revises: 1b2c3d4e5f6a
Create Date: 2026-08-15 03:00:00.000000+00:00

Creates:
- report_jobs table tracking async PDF report generation jobs per (contract_id, version_id)
- Row-Level Security (RLS) policies for tenant isolation
- Grants for app_user runtime role
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2c3d4e5f6a7b"
down_revision = "1b2c3d4e5f6a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1. report_jobs table ----------------------------------------------
    op.create_table(
        "report_jobs",
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
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="queued",
            index=True,
        ),
        sa.Column("storage_key", sa.String(1024), nullable=True),
        sa.Column("file_size", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            index=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # --- 2. Row-Level Security (RLS) ---------------------------------------
    op.execute("ALTER TABLE report_jobs ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE report_jobs FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON report_jobs
        FOR ALL
        TO PUBLIC
        USING (org_id::text = current_setting('app.current_org_id', true))
        WITH CHECK (org_id::text = current_setting('app.current_org_id', true));
        """
    )

    # --- 3. Runtime Role Grants --------------------------------------------
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON report_jobs TO app_user;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON report_jobs;")
    op.drop_table("report_jobs")
