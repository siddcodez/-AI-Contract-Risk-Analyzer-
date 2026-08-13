"""M2: contracts, contract_versions, and processing_jobs

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-13 01:00:00.000000+00:00

Creates:
- contract_status enum type (pending, processing, completed, failed)
- job_status enum type (queued, processing, completed, failed)
- contracts table with FK to organizations and users
- contract_versions table with FK to contracts and organizations
- processing_jobs table with FK to contracts and organizations
- Row-Level Security policies on all three tables
- Grants for the app_user runtime role
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Enum types ----------------------------------------------------------
    contract_status = sa.Enum(
        "pending", "processing", "completed", "failed",
        name="contract_status",
    )
    contract_status.create(op.get_bind(), checkfirst=True)

    job_status = sa.Enum(
        "queued", "processing", "completed", "failed",
        name="job_status",
    )
    job_status.create(op.get_bind(), checkfirst=True)

    # --- contracts -----------------------------------------------------------
    op.create_table(
        "contracts",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("file_name", sa.String(512), nullable=False),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("content_type", sa.String(255), nullable=False),
        sa.Column(
            "storage_key", sa.String(1024), nullable=False, unique=True,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "processing", "completed", "failed",
                name="contract_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "org_id",
            sa.Uuid,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "uploaded_by",
            sa.Uuid,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=False,
        ),
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
    )

    # --- contract_versions ---------------------------------------------------
    op.create_table(
        "contract_versions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "contract_id",
            sa.Uuid,
            sa.ForeignKey("contracts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("version_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("file_name", sa.String(512), nullable=False),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("content_type", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column(
            "org_id",
            sa.Uuid,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- processing_jobs -----------------------------------------------------
    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "contract_id",
            sa.Uuid,
            sa.ForeignKey("contracts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "queued", "processing", "completed", "failed",
                name="job_status",
                create_type=False,
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "org_id",
            sa.Uuid,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
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
    )

    # --- Row-Level Security --------------------------------------------------
    for table in ("contracts", "contract_versions", "processing_jobs"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
                FOR ALL
                USING (org_id::text = current_setting('app.current_org_id', true))
                WITH CHECK (org_id::text = current_setting('app.current_org_id', true))
            """
        )

    # --- Grants for app_user -------------------------------------------------
    for table in ("contracts", "contract_versions", "processing_jobs"):
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user"
        )


def downgrade() -> None:
    for table in ("contracts", "contract_versions", "processing_jobs"):
        op.execute(
            f"REVOKE ALL ON {table} FROM app_user"
        )

    for table in ("processing_jobs", "contract_versions", "contracts"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.drop_table(table)

    job_status = sa.Enum(name="job_status")
    job_status.drop(op.get_bind(), checkfirst=True)

    contract_status = sa.Enum(name="contract_status")
    contract_status.drop(op.get_bind(), checkfirst=True)
