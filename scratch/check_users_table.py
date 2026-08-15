import asyncio
import asyncpg

async def check_users_table():
    conn = await asyncpg.connect("postgresql://contract_user:contract_pass@127.0.0.1:5432/contract_risk_db")
    users = await conn.fetch("SELECT * FROM users")
    orgs = await conn.fetch("SELECT * FROM organizations")
    print(f"Total Users: {len(users)}")
    for u in users:
        print(f"User: id={u['id']}, email={u['email']}, org_id={u['org_id']}")
    print(f"Total Orgs: {len(orgs)}")
    for o in orgs:
        print(f"Org: id={o['id']}, name={o['name']}")
    
    # Test function directly
    if users:
        fn_res = await conn.fetch("SELECT * FROM auth_get_user_by_email($1)", users[0]['email'])
        print(f"Function result as contract_user: {fn_res}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_users_table())
