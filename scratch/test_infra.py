import asyncio
import asyncpg
import redis.asyncio as aioredis
from supabase import create_client
from app.core.config import get_settings


async def test_all():
    settings = get_settings()
    print("[1/3] Testing PostgreSQL on 5432...")
    conn = await asyncpg.connect("postgresql://contract_user:contract_pass@localhost:5432/contract_risk_db")
    row = await conn.fetchval("SELECT 1")
    await conn.close()
    print(f"Postgres OK: {row}")

    print("[2/3] Testing Redis on 6379...")
    r = aioredis.Redis.from_url(settings.REDIS_URL)
    pong = await r.ping()
    await r.aclose()
    print(f"Redis OK: {pong}")

    print(f"[3/3] Testing Supabase Storage at {settings.SUPABASE_URL}...")
    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    print("Supabase client initialized OK")


if __name__ == "__main__":
    asyncio.run(test_all())
