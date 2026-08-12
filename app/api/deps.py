"""FastAPI dependencies for authentication and authorisation.

Security invariants:
- org_id is ALWAYS derived from the JWT / database identity.
- org_id is NEVER trusted from client input for authorisation.
- Tenant context is set on the database session BEFORE any
  downstream query executes, ensuring RLS enforcement.
"""

import uuid
from collections.abc import Callable, Coroutine
from typing import Any

import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ForbiddenError
from app.core.logging import get_logger, org_id_ctx, user_id_ctx
from app.db.session import get_db, set_tenant_context
from app.models.user import User, UserRole
from app.repositories import user_repo

logger = get_logger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Decode JWT, set RLS context, and return the authenticated user.

    Flow:
        1. Decode + validate the JWT (signature + expiry).
        2. Extract org_id from the trusted JWT payload.
        3. Set tenant context on the session (for RLS).
        4. Query the user by ID (RLS-filtered — if someone tampered
           with org_id in the JWT, the signature check would have
           already failed; if the user was moved to another org,
           the query returns None and we return 401).
        5. Set structlog context vars for request-level tracing.

    Raises:
        AuthenticationError: On expired, invalid, or tampered tokens,
                             or if the user no longer exists / is inactive.
    """
    from app.core.security import decode_access_token

    # 1. Decode JWT
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired") from None
    except jwt.InvalidTokenError:
        raise AuthenticationError("Invalid authentication token") from None

    # 2. Extract claims
    user_id_str: str | None = payload.get("sub")
    org_id_str: str | None = payload.get("org_id")

    if not user_id_str or not org_id_str:
        raise AuthenticationError("Invalid token claims")

    # 3. Set RLS context from the trusted JWT
    await set_tenant_context(session, org_id_str)

    # 4. Query user (RLS-filtered)
    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise AuthenticationError("Invalid token claims") from None

    user = await user_repo.get_by_id(session, user_uuid)
    if user is None:
        raise AuthenticationError("User not found or inactive")

    # 5. Set logging context
    org_id_ctx.set(org_id_str)
    user_id_ctx.set(user_id_str)

    return user


def require_role(
    *allowed_roles: UserRole,
) -> Callable[..., Coroutine[Any, Any, User]]:
    """Return a FastAPI dependency that enforces RBAC.

    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(
            user: User = Depends(require_role(UserRole.admin)),
        ) -> ...:

    The dependency first authenticates (via get_current_user), then
    checks that the user's role is in the allowed set.

    Raises:
        ForbiddenError: If the user's role is not in allowed_roles.
    """

    async def _check_role(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenError(
                f"Role '{current_user.role.value}' does not have permission for this action"
            )
        return current_user

    return _check_role


# Convenience shortcuts
require_admin = require_role(UserRole.admin)
require_reviewer_or_above = require_role(UserRole.admin, UserRole.reviewer)
