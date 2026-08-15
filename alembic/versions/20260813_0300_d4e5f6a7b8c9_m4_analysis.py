"""M4: risk_findings and analysis_jobs tables with RLS

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-13 03:00:00.000000+00:00

Creates:
- risk_severity, risk_category, and analysis_job_status PostgreSQL enums
- risk_findings table with confidence constraint and JSONB metadata
- analysis_jobs table for tracking AI risk analysis pipeline execution
- Row-Level Security policies for tenant isolation
- Grants for app_user runtime role
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None

SEVERITY_ENUM = postgresql.ENUM(
    "low", "medium", "high", "critical", name="risk_severity", create_type=False
)
CATEGORY_ENUM = postgresql.ENUM(
    "termination",
    "liability",
    "indemnification",
    "payment",
    "confidentiality",
    "intellectual_property",
    "data_privacy",
    "security",
    "governing_law",
    "dispute_resolution",
    "renewal",
    "compliance",
    "sla",
    "insurance",
    "other",
    name="risk_category",
    create_type=False,
)
ANALYSIS_STATUS_ENUM = postgresql.ENUM(
    "queued", "processing", "completed", "failed", name="analysis_job_status", create_type=False
)


def upgrade() -> None:
    # --- Create ENUMs safely ------------------------------------------------
    sa.Enum("low", "medium", "high", "critical", name="risk_severity").create(
        op.get_bind(), checkfirst=True
    )
    sa.Enum(
        "termination",
        "liability",
        "indemnification",
        "payment",
        "confidentiality",
        "intellectual_property",
        "data_privacy",
        "security",
        "governing_law",
        "dispute_resolution",
        "renewal",
        "compliance",
        "sla",
        "insurance",
        "other",
        name="risk_category",
    ).create(op.get_bind(), checkfirst=True)
    sa.Enum("queued", "processing", "completed", "failed", name="analysis_job_status").create(
        op.get_bind(), checkfirst=True
    )

    # --- risk_findings table ------------------------------------------------
    op.create_table(
        "risk_findings",
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
            "chunk_id",
            sa.Uuid,
            sa.ForeignKey("contract_chunks.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "category",
            CATEGORY_ENUM,
            nullable=False,
            server_default="other",
        ),
        sa.Column(
            "severity",
            SEVERITY_ENUM,
            nullable=False,
            server_default="medium",
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("evidence", sa.Text, nullable=False),
        sa.Column("recommendation", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default="1.0"),
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
            name="ck_risk_finding_confidence",
        ),
    )

    op.create_index(
        "ix_risk_findings_contract_severity",
        "risk_findings",
        ["contract_id", "severity"],
    )
    op.create_index(
        "ix_risk_findings_contract_category",
        "risk_findings",
        ["contract_id", "category"],
    )

    # --- analysis_jobs table ------------------------------------------------
    op.create_table(
        "analysis_jobs",
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
            ANALYSIS_STATUS_ENUM,
            nullable=False,
            server_default="queued",
            index=True,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("findings_count", sa.Integer, nullable=False, server_default="0"),
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
    for table in ("risk_findings", "analysis_jobs"):
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
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON risk_findings TO app_user")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON analysis_jobs TO app_user")


def downgrade() -> None:
    op.execute("REVOKE ALL ON analysis_jobs FROM app_user")
    op.execute("REVOKE ALL ON risk_findings FROM app_user")

    for table in ("analysis_jobs", "risk_findings"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("analysis_jobs")
    op.drop_table("risk_findings")

    ANALYSIS_STATUS_ENUM.drop(op.get_bind(), checkfirst=True)
    CATEGORY_ENUM.drop(op.get_bind(), checkfirst=True)
    SEVERITY_ENUM.drop(op.get_bind(), checkfirst=True)
