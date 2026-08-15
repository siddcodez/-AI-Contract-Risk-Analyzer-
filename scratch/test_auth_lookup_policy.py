import asyncio
import asyncpg

async def test_auth_lookup():
    conn = await asyncpg.connect("postgresql://contract_user:contract_pass@127.0.0.1:5432/contract_risk_db")
    
    # 1. Update policy on users
    await conn.execute("""
        DROP POLICY IF EXISTS tenant_isolation ON users;
        CREATE POLICY tenant_isolation ON users
            FOR ALL
            USING (
                (org_id::text = current_setting('app.current_org_id', true))
                OR (current_setting('app.is_auth_lookup', true) = 'true')
            )
            WITH CHECK (
                (org_id::text = current_setting('app.current_org_id', true))
            );
        ALTER TABLE users FORCE ROW LEVEL SECURITY;
        ALTER FUNCTION auth_get_user_by_email(TEXT) SET app.is_auth_lookup = 'true';
    """)
    print("Updated users policy and function setting.")

    # 2. Test auth_get_user_by_email as app_user
    app_conn = await asyncpg.connect("postgresql://app_user:app_pass@127.0.0.1:5432/contract_risk_db")
    user_res = await app_conn.fetch("SELECT * FROM auth_get_user_by_email($1)", "admin_c26818@acmelegal.com")
    print(f"app_user auth lookup result: {len(user_res)} row found (id={user_res[0]['id']})")

    # 3. Test direct table query as app_user with NO context (MUST BE 0)
    app_direct_no_ctx = await app_conn.fetch("SELECT * FROM users")
    print(f"app_user direct SELECT with NO context (MUST BE 0): {len(app_direct_no_ctx)}")

    # 4. Test direct table query as app_user with Org 1 context (MUST BE 1)
    await app_conn.execute("SELECT set_config('app.current_org_id', '50693063-2d2f-4ed4-b3a7-d6362d98a92c', true)")
    app_direct_org1 = await app_conn.fetch("SELECT * FROM users")
    print(f"app_user direct SELECT with Org 1 context (MUST BE 1): {len(app_direct_org1)}")

    # 5. Test direct table query as app_user with foreign Org 2 (MUST BE 0)
    app_direct_org2 = await app_conn.fetch("SELECT * FROM users WHERE org_id = '8072a91d-07a9-452b-b356-7bc85bbff40f'")
    print(f"app_user direct SELECT for Org 2 user (MUST BE 0): {len(app_direct_org2)}")

    # 6. Verify FORCE RLS is still True on users table
    r = await app_conn.fetchrow("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'users'")
    print(f"users table - RLS: {r['relrowsecurity']}, FORCE RLS: {r['relforcerowsecurity']}")

    await app_conn.close()
    await conn.close()

if __name__ == "__main__":
    asyncio.run(test_auth_lookup())
