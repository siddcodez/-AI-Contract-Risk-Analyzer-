import asyncio
import asyncpg

async def check_policies():
    conn = await asyncpg.connect("postgresql://contract_user:contract_pass@127.0.0.1:5432/contract_risk_db")
    policies = await conn.fetch("SELECT * FROM pg_policies WHERE tablename = 'users'")
    print(f"Policies on users: {policies}")
    for p in policies:
        print(f"Policy: name={p['policyname']}, qual={p['qual']}, with_check={p['with_check']}")
    
    roles = await conn.fetch("SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname IN ('contract_user', 'app_user')")
    print(f"Roles: {roles}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_policies())
