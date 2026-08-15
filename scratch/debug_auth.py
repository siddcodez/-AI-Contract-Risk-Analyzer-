import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.repositories import user_repo
from app.core.security import verify_password, hash_password

async def debug_auth():
    engine = create_async_engine("postgresql+asyncpg://app_user:app_pass@127.0.0.1:5432/contract_risk_db")
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        email = "admin_935302@acmelegal.com"
        user = await user_repo.get_by_email_for_auth(session, email)
        print(f"User found: {user}")
        if user:
            print(f"Password hash: {user.password_hash}")
            verified = verify_password("StrongPassword123!", user.password_hash)
            print(f"Password verify result: {verified}")

if __name__ == "__main__":
    asyncio.run(debug_auth())
