import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DB_URL = "postgresql+asyncpg://contract_user:contract_pass@localhost:5432/contract_risk_db"


async def check():
    engine = create_async_engine(DB_URL)
    async with engine.connect() as conn:
        res = await conn.execute(
            text(
                "SELECT id, contract_id, chunk_index, length(content), embedding IS NOT NULL FROM contract_chunks ORDER BY created_at DESC LIMIT 10"
            )
        )
        rows = res.fetchall()
        print(f"Total chunks found: {len(rows)}")
        for r in rows:
            print(r)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check())
