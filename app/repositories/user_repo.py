"""Repository for User CRUD operations.

The users table HAS RLS enabled.  Most queries go through the ORM and
are subject to the tenant_isolation policy (org_id must match the
current setting 'app.current_org_id').

Authentication queries (login) use the SECURITY DEFINER function
auth_get_user_by_email() which bypasses RLS, because login must look up
a user across all organisations.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.user import User, UserRole


async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    """Fetch a user by primary key.

    Subject to RLS — caller must set tenant context first.
    """
    result = await session.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
    return result.scalars().first()


async def get_by_email_for_auth(session: AsyncSession, email: str) -> User | None:
    """Look up a user by email for authentication.

    Uses the SECURITY DEFINER function auth_get_user_by_email() to
    bypass RLS.  This is the ONLY cross-tenant user query allowed.
    """
    result = await session.execute(
        text(
            "SELECT id, email, password_hash, full_name, role, "
            "org_id, is_active, created_at, updated_at "
            "FROM auth_get_user_by_email(:email)"
        ),
        {"email": email},
    )
    row = result.mappings().first()
    if row is None:
        return None

    # Build a detached User instance from the function result.
    # This is intentionally not session-bound because the login flow
    # only needs to read fields, not modify the user.
    user = User(
        id=row["id"],
        email=row["email"],
        password_hash=row["password_hash"],
        full_name=row["full_name"],
        role=UserRole(row["role"]),
        org_id=row["org_id"],
        is_active=row["is_active"],
    )
    # Manually set server-generated timestamps
    object.__setattr__(user, "created_at", row["created_at"])
    object.__setattr__(user, "updated_at", row["updated_at"])

    # Eagerly load the organization for the detached user
    org_result = await session.execute(select(Organization).where(Organization.id == row["org_id"]))
    org = org_result.scalars().first()
    if org is not None:
        object.__setattr__(user, "organization", org)

    return user


async def create(
    session: AsyncSession,
    *,
    email: str,
    password_hash: str,
    full_name: str,
    role: UserRole,
    org_id: uuid.UUID,
) -> User:
    """Create a new user.

    Subject to RLS WITH CHECK — caller must set tenant context to the
    target org_id before calling this.
    """
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=password_hash,
        full_name=full_name,
        role=role,
        org_id=org_id,
        is_active=True,
    )
    session.add(user)
    await session.flush()  # populate server-defaults
    return user


async def email_exists(session: AsyncSession, email: str) -> bool:
    """Check if an email is already registered (cross-tenant).

    Uses the SECURITY DEFINER function to bypass RLS.
    """
    result = await session.execute(
        text("SELECT 1 FROM auth_get_user_by_email(:email) LIMIT 1"),
        {"email": email},
    )
    return result.first() is not None


async def list_by_org(
    session: AsyncSession,
    org_id: uuid.UUID,
    *,
    _now: datetime | None = None,
) -> list[User]:
    """List all active users in an organization.

    Subject to RLS — caller must set tenant context first.
    The org_id parameter is used as an application-layer filter
    in addition to the RLS policy.
    """
    _ = _now or datetime.now(UTC)  # reserved for future use
    result = await session.execute(
        select(User)
        .where(User.org_id == org_id, User.is_active.is_(True))
        .order_by(User.created_at)
    )
    return list(result.scalars().all())
