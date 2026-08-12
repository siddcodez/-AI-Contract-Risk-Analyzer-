"""Verification script for runtime Alembic migration against live PostgreSQL.

Executes all 8 migration lifecycle checks:
1. Fresh database reset (schema public cascade).
2. Check user_role enum does NOT exist before migration.
3. Run `alembic upgrade head`.
4. Verify organizations table, users table, user_role enum (count=1),
   users.role type, RLS enabled, RLS policy, and auth_get_user_by_email function.
5. Run `alembic downgrade base`.
6. Verify all tables, type, function, and policy are removed.
7. Run `alembic upgrade head` a second time from downgraded state.
8. Re-verify everything intact.
"""

import asyncio
import os
import subprocess
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

_ADMIN_URL = os.environ.get(
    "MIGRATION_DATABASE_URL",
    "postgresql+asyncpg://contract_user:contract_pass@localhost:5432/contract_risk_db",
)


async def reset_database(engine) -> None:
    """Drop and recreate public schema, reset roles and privileges."""
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO contract_user"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(
            text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'app_user') THEN
                    CREATE ROLE app_user WITH LOGIN PASSWORD 'app_pass' NOSUPERUSER NOBYPASSRLS;
                END IF;
            END
            $$;
        """)
        )
        await conn.execute(text("GRANT CONNECT ON DATABASE contract_risk_db TO app_user;"))
        await conn.execute(text("GRANT USAGE ON SCHEMA public TO app_user;"))
        await conn.execute(
            text(
                "ALTER DEFAULT PRIVILEGES FOR ROLE contract_user IN SCHEMA public "
                "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;"
            )
        )
        await conn.execute(
            text(
                "ALTER DEFAULT PRIVILEGES FOR ROLE contract_user IN SCHEMA public "
                "GRANT USAGE, SELECT ON SEQUENCES TO app_user;"
            )
        )
        await conn.execute(
            text(
                "ALTER DEFAULT PRIVILEGES FOR ROLE contract_user IN SCHEMA public "
                "GRANT EXECUTE ON FUNCTIONS TO app_user;"
            )
        )


async def check_enum_count(engine) -> int:
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT count(*) FROM pg_type WHERE typname = 'user_role'"))
        return res.scalar() or 0


async def check_schema_after_upgrade(engine) -> dict[str, bool]:
    results = {}
    async with engine.connect() as conn:
        # 1. organizations table exists
        res = await conn.execute(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'organizations'"
            )
        )
        results["organizations_table"] = res.scalar() == 1

        # 2. users table exists
        res = await conn.execute(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'users'"
            )
        )
        results["users_table"] = res.scalar() == 1

        # 3. user_role enum exists exactly once
        enum_cnt = await check_enum_count(engine)
        results["user_role_enum_count_is_1"] = enum_cnt == 1

        # 4. users.role column uses user_role data type
        res = await conn.execute(
            text(
                "SELECT udt_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'role'"
            )
        )
        results["users_role_column_type"] = res.scalar() == "user_role"

        # 5. RLS is enabled on users
        res = await conn.execute(
            text("SELECT relrowsecurity FROM pg_class WHERE relname = 'users'")
        )
        results["rls_enabled_on_users"] = res.scalar() is True

        # 6. tenant_isolation RLS policy exists
        res = await conn.execute(
            text("SELECT count(*) FROM pg_policy WHERE polname = 'tenant_isolation'")
        )
        results["tenant_isolation_policy"] = res.scalar() == 1

        # 7. auth_get_user_by_email function exists
        res = await conn.execute(
            text("SELECT count(*) FROM pg_proc WHERE proname = 'auth_get_user_by_email'")
        )
        results["auth_get_user_by_email_function"] = res.scalar() == 1

    return results


async def check_schema_after_downgrade(engine) -> dict[str, bool]:
    results = {}
    async with engine.connect() as conn:
        # organizations table gone
        res = await conn.execute(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'organizations'"
            )
        )
        results["organizations_table_removed"] = res.scalar() == 0

        # users table gone
        res = await conn.execute(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'users'"
            )
        )
        results["users_table_removed"] = res.scalar() == 0

        # user_role enum gone
        enum_cnt = await check_enum_count(engine)
        results["user_role_enum_removed"] = enum_cnt == 0

        # tenant_isolation policy gone
        res = await conn.execute(
            text("SELECT count(*) FROM pg_policy WHERE polname = 'tenant_isolation'")
        )
        results["tenant_isolation_policy_removed"] = res.scalar() == 0

        # auth_get_user_by_email function gone
        res = await conn.execute(
            text("SELECT count(*) FROM pg_proc WHERE proname = 'auth_get_user_by_email'")
        )
        results["auth_function_removed"] = res.scalar() == 0

    return results


def run_alembic_cmd(cmd: str) -> None:
    print(f"Executing: alembic {cmd}")
    env = os.environ.copy()
    env["MIGRATION_DATABASE_URL"] = _ADMIN_URL
    res = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", *cmd.split()],
        capture_output=True,
        text=True,
        env=env,
    )
    if res.returncode != 0:
        print("STDOUT:", res.stdout)
        print("STDERR:", res.stderr)
        raise RuntimeError(f"Alembic command '{cmd}' failed with code {res.returncode}")
    print("SUCCESS:", res.stdout.strip())


async def main() -> None:
    engine = create_async_engine(_ADMIN_URL)

    # 1. Fresh database reset
    print("\n--- STEP 1: Resetting Database ---")
    await reset_database(engine)

    # 2. Check user_role before migration
    print("\n--- STEP 2: Check user_role before migration ---")
    cnt_before = await check_enum_count(engine)
    print(f"user_role enum count before migration: {cnt_before}")
    assert cnt_before == 0, "user_role should NOT exist before migration"

    # 3. First upgrade
    print("\n--- STEP 3: First alembic upgrade head ---")
    run_alembic_cmd("upgrade head")

    # 4. Verify post-upgrade state
    print("\n--- STEP 4: Verifying post-upgrade schema ---")
    up1_checks = await check_schema_after_upgrade(engine)
    for check_name, status in up1_checks.items():
        print(f"  {check_name}: {'PASS' if status else 'FAIL'}")
        assert status, f"Check failed: {check_name}"

    # 5. Downgrade
    print("\n--- STEP 5: Alembic downgrade base ---")
    run_alembic_cmd("downgrade base")

    # 6. Verify post-downgrade state
    print("\n--- STEP 6: Verifying post-downgrade schema ---")
    down_checks = await check_schema_after_downgrade(engine)
    for check_name, status in down_checks.items():
        print(f"  {check_name}: {'PASS' if status else 'FAIL'}")
        assert status, f"Check failed: {check_name}"

    # 7. Second upgrade
    print("\n--- STEP 7: Second alembic upgrade head from clean downgrade ---")
    run_alembic_cmd("upgrade head")

    # 8. Re-verify post-upgrade state
    print("\n--- STEP 8: Re-verifying post-second-upgrade schema ---")
    up2_checks = await check_schema_after_upgrade(engine)
    for check_name, status in up2_checks.items():
        print(f"  {check_name}: {'PASS' if status else 'FAIL'}")
        assert status, f"Check failed: {check_name}"

    await engine.dispose()
    print("\n==========================================")
    print("ALL RUNTIME MIGRATION CHECKS PASSED PERFECTLY!")
    print("==========================================")


if __name__ == "__main__":
    asyncio.run(main())
