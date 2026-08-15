import asyncio
import asyncpg

async def test_auth_fix():
    conn = await asyncpg.connect("postgresql://contract_user:contract_pass@127.0.0.1:5432/contract_risk_db")
    
    # Check current status
    print("--- Testing current behavior with FORCE RLS on users ---")
    res = await conn.fetch("SELECT * FROM auth_get_user_by_email($1)", "admin_c26818@acmelegal.com")
    print(f"Result before fix: {res}")

    # For users table, change to NO FORCE ROW LEVEL SECURITY (app_user is still strictly constrained by RLS because app_user is NOT table owner)
    await conn.execute("ALTER TABLE users NO FORCE ROW LEVEL SECURITY;")

    res2 = await conn.fetch("SELECT * FROM auth_get_user_by_email($1)", "admin_c26818@acmelegal.com")
    print(f"Result with NO FORCE RLS on users (as owner): {res2}")

    # Now verify that app_user STILL cannot read across tenants!
    app_conn = await asyncpg.connect("postgresql://app_user:app_pass@127.0.0.1:5432/contract_risk_db")
    app_users_no_context = await app_conn.fetch("SELECT * FROM users")
    print(f"app_user query with no context (should be empty): {len(app_users_no_context)}")

    # Set context to Org 1
    await app_conn.execute("SELECT set_config('app.current_org_id', '50693063-2d2f-4ed4-b3a7-d6362d98a92c', true)")
    app_users_org1 = await app_conn.fetch("SELECT * FROM users")
    print(f"app_user query with Org 1 context (should be 1): {len(app_users_org1)}")

    # Try to select Org 2 user while in Org 1 context
    app_users_org2 = await app_conn.fetch("SELECT * FROM users WHERE org_id = '8072a91d-07a9-452b-b356-7bc85bbff40f'")
    print(f"app_user query for foreign org user (MUST be 0): {len(app_users_org2)}")

    # Call auth_get_user_by_email as app_user
    app_fn_res = await app_conn.fetch("SELECT * FROM auth_get_user_by_email($1)", "admin_c26818@acmelegal.com")
    print(f"app_user calling auth_get_user_by_email (should succeed): {len(app_fn_res)}")

    await app_conn.close()
    await conn.close()

if __name__ == "__main__":
    asyncio.run(test_auth_fix())
