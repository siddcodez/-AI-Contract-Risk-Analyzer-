import asyncio
import asyncpg

async def grant_perms():
    conn = await asyncpg.connect("postgresql://contract_user:contract_pass@127.0.0.1:5432/contract_risk_db")
    await conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'app_user') THEN
                CREATE ROLE app_user WITH LOGIN PASSWORD 'app_pass' NOSUPERUSER NOBYPASSRLS;
            END IF;
        END
        $$;
        GRANT USAGE ON SCHEMA public TO app_user;
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_user;
        GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO app_user;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO app_user;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO app_user;
    """)
    await conn.close()
    print("Granted all permissions on public schema tables/sequences to app_user.")

if __name__ == "__main__":
    asyncio.run(grant_perms())
