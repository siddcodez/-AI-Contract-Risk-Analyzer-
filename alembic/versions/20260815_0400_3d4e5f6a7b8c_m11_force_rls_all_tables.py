"""M11: Force Row-Level Security across all tenant tables

Revision ID: 3d4e5f6a7b8c
Revises: 2c3d4e5f6a7b
Create Date: 2026-08-15 04:00:00.000000+00:00

Applies FORCE ROW LEVEL SECURITY to all tenant-scoped tables:
- users
- contracts
- contract_versions
- contract_chunks
- processing_jobs
- analysis_jobs
- risk_findings
- missing_clauses
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "3d4e5f6a7b8c"
down_revision = "2c3d4e5f6a7b"
branch_labels = None
depends_on = None

TENANT_TABLES = [
    "users",
    "contracts",
    "contract_versions",
    "contract_chunks",
    "processing_jobs",
    "analysis_jobs",
    "risk_findings",
    "missing_clauses",
]


def upgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")


def downgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
