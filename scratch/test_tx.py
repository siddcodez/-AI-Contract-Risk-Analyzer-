import asyncio
import asyncpg

async def test_auth_lookup_tx():
    app_conn = await asyncpg.connect("postgresql://app_user:app_pass@127.0.0.1:5432/contract_risk_db")

    async with app_conn.transaction():
        await app_conn.execute("SELECT set_config('app.current_org_id', '50693063-2d2f-4ed4-b3a7-d6362d98a92c', true)")
        app_direct_org1 = await app_conn.fetch("SELECT * FROM users")
        print(f"app_user direct SELECT inside Org 1 tx (MUST BE 1): {len(app_direct_org1)}")

        app_direct_org2 = await app_conn.fetch("SELECT * FROM users WHERE org_id = '8072a91d-07a9-452b-b356-7bc85bbff40f'")
        print(f"app_user direct SELECT for foreign Org 2 inside Org 1 tx (MUST BE 0): {len(app_direct_org2)}")

    await app_conn.close()

if __name__ == "__main__":
    asyncio.run(test_auth_lookup_tx())
