import asyncio
import uuid
from datetime import datetime, UTC
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text


async def reproduce():
    admin_engine = create_async_engine(
        "postgresql+asyncpg://contract_user:contract_pass@localhost:5432/contract_risk_db"
    )
    app_engine = create_async_engine(
        "postgresql+asyncpg://app_user:app_pass@localhost:5432/contract_risk_db"
    )

    admin_factory = async_sessionmaker(admin_engine, class_=AsyncSession, expire_on_commit=False)
    app_factory = async_sessionmaker(app_engine, class_=AsyncSession, expire_on_commit=False)

    org_a_id = uuid.uuid4()
    org_b_id = uuid.uuid4()
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()
    now = datetime.now(UTC)

    async with admin_factory() as admin_session:
        await admin_session.execute(
            text(
                "INSERT INTO organizations (id, name, slug, is_active, created_at, updated_at) VALUES (:id, :name, :slug, true, :now, :now)"
            ),
            {
                "id": str(org_a_id),
                "name": "Org A",
                "slug": f"slug-a-{org_a_id.hex[:8]}",
                "now": now,
            },
        )
        await admin_session.execute(
            text(
                "INSERT INTO organizations (id, name, slug, is_active, created_at, updated_at) VALUES (:id, :name, :slug, true, :now, :now)"
            ),
            {
                "id": str(org_b_id),
                "name": "Org B",
                "slug": f"slug-b-{org_b_id.hex[:8]}",
                "now": now,
            },
        )
        await admin_session.execute(
            text(
                "INSERT INTO users (id, email, password_hash, full_name, role, org_id, is_active, created_at, updated_at) VALUES (:id, :email, :pw, :name, 'admin', :org_id, true, :now, :now)"
            ),
            {
                "id": str(user_a_id),
                "email": f"a-{user_a_id.hex[:8]}@test.com",
                "pw": "pw",
                "name": "User A",
                "org_id": str(org_a_id),
                "now": now,
            },
        )
        await admin_session.execute(
            text(
                "INSERT INTO users (id, email, password_hash, full_name, role, org_id, is_active, created_at, updated_at) VALUES (:id, :email, :pw, :name, 'viewer', :org_id, true, :now, :now)"
            ),
            {
                "id": str(user_b_id),
                "email": f"b-{user_b_id.hex[:8]}@test.com",
                "pw": "pw",
                "name": "User B",
                "org_id": str(org_b_id),
                "now": now,
            },
        )
        await admin_session.commit()

    async with app_factory() as app_session:
        await app_session.execute(
            text("SELECT set_config('app.current_org_id', :org_id, false)"),
            {"org_id": str(org_a_id)},
        )
        res_a = await app_session.execute(text("SELECT id, email, org_id FROM users"))
        rows_a = res_a.fetchall()
        print("rows_a:", rows_a)
        print("user_a_id:", user_a_id)
        visible_ids_a = {row[0] for row in rows_a}
        print("user_a_id in visible_ids_a:", user_a_id in visible_ids_a)

    async with admin_factory() as admin_session:
        await admin_session.execute(
            text("DELETE FROM users WHERE id IN (:a, :b)"),
            {"a": str(user_a_id), "b": str(user_b_id)},
        )
        await admin_session.execute(
            text("DELETE FROM organizations WHERE id IN (:a, :b)"),
            {"a": str(org_a_id), "b": str(org_b_id)},
        )
        await admin_session.commit()

    await admin_engine.dispose()
    await app_engine.dispose()


asyncio.run(reproduce())
