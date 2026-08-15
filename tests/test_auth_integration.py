"""Integration test: PostgreSQL Row-Level Security enforcement.

This test connects to a REAL PostgreSQL instance to prove that:
- User A in Org A cannot see User B in Org B.
- The tenant_isolation RLS policy on the users table works.

Requires Docker services running (or CI environment).
Automatically skipped if PostgreSQL is not available.
"""

import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# ---------------------------------------------------------------------------
# Connection URLs from environment
# ---------------------------------------------------------------------------

# Admin URL — can bypass RLS (table owner, or superuser)
_ADMIN_URL = os.environ.get(
    "MIGRATION_DATABASE_URL",
    "postgresql+asyncpg://contract_user:contract_pass@localhost:5432/contract_risk_db",
)

# App URL — subject to RLS (non-superuser, no BYPASSRLS)
_APP_URL = os.environ.get(
    "APP_DATABASE_URL",
    "postgresql+asyncpg://app_user:app_pass@localhost:5432/contract_risk_db",
)


async def _db_is_available() -> bool:
    """Check if PostgreSQL is reachable."""
    try:
        engine = create_async_engine(_ADMIN_URL, pool_pre_ping=True)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.integration


@pytest.fixture
async def admin_session() -> AsyncSession:
    """Session connected as the admin/migration role (bypasses RLS)."""
    engine = create_async_engine(_ADMIN_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session  # type: ignore[misc]
    await engine.dispose()


@pytest.fixture
async def app_session() -> AsyncSession:
    """Session connected as the app_user role (subject to RLS)."""
    engine = create_async_engine(_APP_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session  # type: ignore[misc]
    await engine.dispose()


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


class TestRLSEnforcement:
    """Prove that RLS blocks cross-tenant access at the PostgreSQL level."""

    async def test_org_a_cannot_see_org_b_users(
        self,
        admin_session: AsyncSession,
        app_session: AsyncSession,
    ) -> None:
        """Organisation A's user cannot read Organisation B's users.

        Setup (admin connection — bypasses RLS):
            1. Create Org A and Org B.
            2. Create User A in Org A and User B in Org B.

        Assert (app_user connection — RLS enforced):
            3. Set tenant context to Org A → SELECT users → only User A visible.
            4. Set tenant context to Org B → SELECT users → only User B visible.

        Cleanup (admin connection):
            5. Delete test data.
        """
        # Check if DB is available, skip if not
        if not await _db_is_available():
            pytest.skip("PostgreSQL not available")

        # --- Unique IDs for this test run ---
        org_a_id = uuid.uuid4()
        org_b_id = uuid.uuid4()
        user_a_id = uuid.uuid4()
        user_b_id = uuid.uuid4()
        now = datetime.now(UTC)

        try:
            # --- Setup: create orgs and users via admin connection ---
            await admin_session.execute(
                text(
                    "INSERT INTO organizations "
                    "(id, name, slug, is_active, created_at, updated_at) "
                    "VALUES (:id, :name, :slug, true, :now, :now)"
                ),
                {
                    "id": str(org_a_id),
                    "name": "RLS Test Org A",
                    "slug": f"rls-test-a-{org_a_id.hex[:8]}",
                    "now": now,
                },
            )
            await admin_session.execute(
                text(
                    "INSERT INTO organizations "
                    "(id, name, slug, is_active, created_at, updated_at) "
                    "VALUES (:id, :name, :slug, true, :now, :now)"
                ),
                {
                    "id": str(org_b_id),
                    "name": "RLS Test Org B",
                    "slug": f"rls-test-b-{org_b_id.hex[:8]}",
                    "now": now,
                },
            )
            await admin_session.execute(
                text(
                    "INSERT INTO users "
                    "(id, email, password_hash, full_name, role, org_id, "
                    "is_active, created_at, updated_at) "
                    "VALUES (:id, :email, :pw, :name, 'admin', :org_id, "
                    "true, :now, :now)"
                ),
                {
                    "id": str(user_a_id),
                    "email": f"rls-a-{user_a_id.hex[:8]}@test.com",
                    "pw": "$2b$12$fakehashfortest_a_placeholder",
                    "name": "User A",
                    "org_id": str(org_a_id),
                    "now": now,
                },
            )
            await admin_session.execute(
                text(
                    "INSERT INTO users "
                    "(id, email, password_hash, full_name, role, org_id, "
                    "is_active, created_at, updated_at) "
                    "VALUES (:id, :email, :pw, :name, 'viewer', :org_id, "
                    "true, :now, :now)"
                ),
                {
                    "id": str(user_b_id),
                    "email": f"rls-b-{user_b_id.hex[:8]}@test.com",
                    "pw": "$2b$12$fakehashfortest_b_placeholder",
                    "name": "User B",
                    "org_id": str(org_b_id),
                    "now": now,
                },
            )
            await admin_session.commit()

            # --- Assert: app_user with Org A context ---
            # Set tenant context to Org A
            await app_session.execute(
                text("SELECT set_config('app.current_org_id', :org_id, false)"),
                {"org_id": str(org_a_id)},
            )

            result_a = await app_session.execute(text("SELECT id, email, org_id FROM users"))
            rows_a = result_a.fetchall()

            # Should ONLY see User A
            visible_ids_a = {uuid.UUID(str(row[0])) for row in rows_a}
            assert user_a_id in visible_ids_a, "User A should be visible when tenant is Org A"
            assert user_b_id not in visible_ids_a, "User B must NOT be visible when tenant is Org A"

            # --- Assert: app_user with Org B context ---
            await app_session.execute(
                text("SELECT set_config('app.current_org_id', :org_id, false)"),
                {"org_id": str(org_b_id)},
            )

            result_b = await app_session.execute(text("SELECT id, email, org_id FROM users"))
            rows_b = result_b.fetchall()

            # Should ONLY see User B
            visible_ids_b = {uuid.UUID(str(row[0])) for row in rows_b}
            assert user_b_id in visible_ids_b, "User B should be visible when tenant is Org B"
            assert user_a_id not in visible_ids_b, "User A must NOT be visible when tenant is Org B"

            # --- Assert: no context → no rows visible ---
            # Reset context setting to empty
            await app_session.execute(text("SELECT set_config('app.current_org_id', '', false)"))
            result_no_ctx = await app_session.execute(text("SELECT id FROM users"))
            rows_no_ctx = result_no_ctx.fetchall()

            # Without context, current_setting returns '' which matches no UUID
            no_ctx_ids = {uuid.UUID(str(row[0])) for row in rows_no_ctx}
            assert user_a_id not in no_ctx_ids, "User A must NOT be visible without tenant context"
            assert user_b_id not in no_ctx_ids, "User B must NOT be visible without tenant context"

        finally:
            # --- Cleanup: admin connection bypasses RLS ---
            await admin_session.execute(
                text("DELETE FROM users WHERE id IN (:a, :b)"),
                {"a": str(user_a_id), "b": str(user_b_id)},
            )
            await admin_session.execute(
                text("DELETE FROM organizations WHERE id IN (:a, :b)"),
                {"a": str(org_a_id), "b": str(org_b_id)},
            )
            await admin_session.commit()
