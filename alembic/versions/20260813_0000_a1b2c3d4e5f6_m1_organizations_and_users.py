"""M1: organizations and users with RLS

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-08-13 00:00:00.000000+00:00

Creates:
- user_role enum type (admin, reviewer, viewer)
- organizations table
- users table with FK to organizations
- Row-Level Security policy on users (tenant isolation)
- SECURITY DEFINER function for authentication (RLS bypass)
- Grants for the app_user runtime role
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Enum type -----------------------------------------------------------
    user_role = sa.Enum("admin", "reviewer", "viewer", name="user_role")
    user_role.create(op.get_bind(), checkfirst=True)

    # --- organizations -------------------------------------------------------
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "slug", sa.String(255), nullable=False, unique=True, index=True
        ),
        sa.Column(
            "is_active", sa.Boolean, nullable=False, server_default="true"
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

    # --- users ---------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "email", sa.String(320), nullable=False, unique=True, index=True
        ),
        sa.Column("password_hash", sa.String(1024), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM(
                "admin",
                "reviewer",
                "viewer",
                name="user_role",
                create_type=False,
            ),
            nullable=False,
            server_default="viewer",
        ),
        sa.Column(
            "org_id",
            sa.Uuid,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "is_active", sa.Boolean, nullable=False, server_default="true"
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
    #
    # The tenant_isolation policy ensures that app_user (non-superuser)
    # can only SELECT/INSERT/UPDATE/DELETE rows where org_id matches
    # the current transaction's app.current_org_id setting.
    #
    # contract_user (table owner) is NOT subject to RLS — this is the
    # PostgreSQL default when FORCE ROW LEVEL SECURITY is not used.
    # This allows Alembic migrations and admin scripts to operate
    # without RLS restrictions.

    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY tenant_isolation ON users
            FOR ALL
            USING (org_id::text = current_setting('app.current_org_id', true))
            WITH CHECK (org_id::text = current_setting('app.current_org_id', true))
        """
    )

    # --- SECURITY DEFINER function for login ---------------------------------
    #
    # Login must look up a user by email across ALL organisations.
    # This function runs as the table owner (contract_user) which
    # bypasses RLS, allowing the auth flow to find the user.
    #
    # Only the email-based lookup is exposed — no generic RLS bypass.

    op.execute(
        """
        CREATE OR REPLACE FUNCTION auth_get_user_by_email(p_email TEXT)
        RETURNS TABLE (
            id UUID,
            email VARCHAR(320),
            password_hash VARCHAR(1024),
            full_name VARCHAR(255),
            role user_role,
            org_id UUID,
            is_active BOOLEAN,
            created_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ
        )
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = public
        AS $$
            SELECT u.id, u.email, u.password_hash, u.full_name,
                   u.role, u.org_id, u.is_active, u.created_at, u.updated_at
            FROM users u
            WHERE u.email = p_email AND u.is_active = true
            LIMIT 1;
        $$
        """
    )

    # --- Grants for app_user -------------------------------------------------
    #
    # These are explicit grants in addition to the ALTER DEFAULT PRIVILEGES
    # set in init_db.sql.  Belt-and-suspenders: ensures app_user has access
    # even if init_db.sql privileges were not applied.

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON organizations TO app_user")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON users TO app_user")
    op.execute(
        "GRANT EXECUTE ON FUNCTION auth_get_user_by_email(TEXT) TO app_user"
    )


def downgrade() -> None:
    op.execute(
        "REVOKE EXECUTE ON FUNCTION auth_get_user_by_email(TEXT) FROM app_user"
    )
    op.execute("REVOKE ALL ON users FROM app_user")
    op.execute("REVOKE ALL ON organizations FROM app_user")

    op.execute("DROP FUNCTION IF EXISTS auth_get_user_by_email(TEXT)")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON users")

    op.drop_table("users")
    op.drop_table("organizations")

    user_role = sa.Enum(name="user_role")
    user_role.drop(op.get_bind(), checkfirst=True)
