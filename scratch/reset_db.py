import asyncio
import asyncpg
import subprocess

async def reset_db_and_check():
    print("[1] Dropping all tables/schema in contract_risk_db to start from ZERO...")
    conn = await asyncpg.connect("postgresql://contract_user:contract_pass@localhost:5432/contract_risk_db")
    await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO contract_user; GRANT ALL ON SCHEMA public TO public;")
    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    await conn.close()
    print("Database reset to empty schema with vector extension enabled.")

if __name__ == "__main__":
    asyncio.run(reset_db_and_check())
