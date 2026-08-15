import asyncio
import asyncpg

async def check_rls():
    conn = await asyncpg.connect("postgresql://contract_user:contract_pass@127.0.0.1:5432/contract_risk_db")
    query = """
    SELECT
        c.relname AS table_name,
        c.relrowsecurity AS rls_enabled,
        c.relforcerowsecurity AS force_rls,
        COUNT(p.polname) AS policy_count
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    LEFT JOIN pg_policy p ON p.polrelid = c.oid
    WHERE n.nspname = 'public'
      AND c.relkind = 'r'
      AND c.relname != 'alembic_version'
    GROUP BY c.relname, c.relrowsecurity, c.relforcerowsecurity
    ORDER BY c.relname;
    """
    rows = await conn.fetch(query)
    await conn.close()

    print(f"{'Table Name':<28} | {'RLS Enabled':<11} | {'FORCE RLS':<11} | {'Policies'}")
    print("-" * 65)
    for r in rows:
        print(f"{r['table_name']:<28} | {str(r['rls_enabled']):<11} | {str(r['force_rls']):<11} | {r['policy_count']}")

if __name__ == "__main__":
    asyncio.run(check_rls())
