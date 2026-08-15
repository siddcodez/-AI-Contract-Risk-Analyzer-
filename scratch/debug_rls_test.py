import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text


async def debug_rls():
    admin_engine = create_async_engine(
        "postgresql+asyncpg://contract_user:contract_pass@localhost:5432/contract_risk_db"
    )
    app_engine = create_async_engine(
        "postgresql+asyncpg://app_user:app_pass@localhost:5432/contract_risk_db"
    )

    org_a = str(uuid.uuid4())
    user_a = str(uuid.uuid4())

    admin_factory = async_sessionmaker(admin_engine, class_=AsyncSession, expire_on_commit=False)
    async with admin_factory() as session:
        await session.execute(
            text("INSERT INTO organizations (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": org_a, "name": "Org A", "slug": f"org-{org_a[:8]}"},
        )
        await session.execute(
            text(
                "INSERT INTO users (id, email, password_hash, full_name, role, org_id) VALUES (:id, :email, :pw, :name, :role, :org_id)"
            ),
            {
                "id": user_a,
                "email": f"a-{user_a[:8]}@test.com",
                "pw": "hash",
                "name": "A",
                "role": "admin",
                "org_id": org_a,
            },
        )
        await session.commit()

    app_factory = async_sessionmaker(app_engine, class_=AsyncSession, expire_on_commit=False)
    async with app_factory() as session:
        # Step 1: without setting context
        res0 = await session.execute(text("SELECT id FROM users"))
        print("No context:", res0.fetchall())

        # Step 2: setting context (false makes it session-wide, true makes it transaction-local)
        await session.execute(
            text("SELECT set_config('app.current_org_id', :org_id, false)"), {"org_id": org_a}
        )
        res1 = await session.execute(text("SELECT id FROM users"))
        print("With session-wide set_config false:", res1.fetchall())

    async with admin_factory() as session:
        await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_a})
        await session.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": org_a})
        await session.commit()


asyncio.run(debug_rls())
