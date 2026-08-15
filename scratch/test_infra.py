import asyncio
import redis.asyncio as aioredis
import asyncpg
import boto3

async def test_all():
    print("[1/3] Testing PostgreSQL on 5432...")
    conn = await asyncpg.connect("postgresql://contract_user:contract_pass@localhost:5432/contract_risk_db")
    row = await conn.fetchval("SELECT 1")
    await conn.close()
    print(f"Postgres OK: {row}")

    print("[2/3] Testing Redis on 6379...")
    r = aioredis.Redis.from_url("redis://localhost:6379/0")
    pong = await r.ping()
    await r.aclose()
    print(f"Redis OK: {pong}")

    print("[3/3] Testing MinIO on 9000...")
    s3 = boto3.client(
        "s3",
        endpoint_url="http://localhost:9000",
        aws_access_key_id="minioadmin",
        aws_secret_access_key="minioadmin",
        region_name="us-east-1",
        use_ssl=False,
    )
    buckets = s3.list_buckets()
    print(f"MinIO OK: {[b['Name'] for b in buckets.get('Buckets', [])]}")

if __name__ == "__main__":
    asyncio.run(test_all())
