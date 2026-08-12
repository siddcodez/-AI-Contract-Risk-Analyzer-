"""Authentication service — registration and login business logic.

Orchestrates repositories, password hashing, and JWT creation.
Controllers call this service; this service calls repositories.
No HTTP or FastAPI types appear here — only domain objects and schemas.

Security rules:
- Passwords are NEVER logged or stored in plaintext.
- Tokens are NEVER logged.
- org_id is derived from the database, never from client input.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ConflictError
from app.core.logging import get_logger
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import set_tenant_context
from app.models.user import UserRole
from app.repositories import organization_repo, user_repo
from app.schemas.auth import RegisterRequest, TokenResponse, UserResponse

logger = get_logger(__name__)


async def register_user(
    session: AsyncSession,
    data: RegisterRequest,
) -> tuple[UserResponse, TokenResponse]:
    """Register a new user and organization.

    Flow:
        1. Check for duplicate email (cross-tenant, via SECURITY DEFINER).
        2. Create organization with a unique slug.
        3. Set tenant context for RLS.
        4. Create the first user as admin.
        5. Generate access token.

    Returns:
        (user_response, token_response)

    Raises:
        ConflictError: If the email is already registered.
    """
    # 1. Duplicate check (bypasses RLS via SECURITY DEFINER function)
    if await user_repo.email_exists(session, data.email):
        raise ConflictError("A user with this email already exists")

    # 2. Create organization
    org = await organization_repo.create_with_unique_slug(session, name=data.org_name)
    logger.info("Organization created", org_id=str(org.id), slug=org.slug)

    # 3. Set RLS context so the INSERT passes the WITH CHECK policy
    await set_tenant_context(session, str(org.id))

    # 4. Create admin user
    password_hashed = hash_password(data.password)
    user = await user_repo.create(
        session,
        email=data.email,
        password_hash=password_hashed,
        full_name=data.full_name,
        role=UserRole.admin,
        org_id=org.id,
    )
    logger.info(
        "User registered",
        user_id=str(user.id),
        org_id=str(org.id),
        role=user.role.value,
    )

    # 5. Build responses
    token = create_access_token(
        user_id=str(user.id),
        org_id=str(org.id),
        role=user.role.value,
    )
    user_response = UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        org_id=org.id,
        org_name=org.name,
        created_at=user.created_at,
    )
    token_response = TokenResponse(access_token=token)

    return user_response, token_response


async def authenticate_user(
    session: AsyncSession,
    email: str,
    password: str,
) -> tuple[UserResponse, TokenResponse]:
    """Authenticate a user and return an access token.

    Uses the SECURITY DEFINER function to look up the user by email
    (bypasses RLS — login is inherently cross-tenant).

    Raises:
        AuthenticationError: If credentials are invalid.
    """
    # Look up user by email (bypasses RLS)
    user = await user_repo.get_by_email_for_auth(session, email)

    if user is None or not verify_password(password, user.password_hash):
        # Deliberately vague — don't reveal whether email exists
        raise AuthenticationError("Invalid email or password")

    if not user.is_active:
        raise AuthenticationError("Account is deactivated")

    logger.info(
        "User authenticated",
        user_id=str(user.id),
        org_id=str(user.org_id),
    )

    token = create_access_token(
        user_id=str(user.id),
        org_id=str(user.org_id),
        role=user.role.value,
    )

    org_name = ""
    if hasattr(user, "organization") and user.organization is not None:
        org_name = user.organization.name

    user_response = UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        org_id=user.org_id,
        org_name=org_name,
        created_at=user.created_at,
    )
    token_response = TokenResponse(access_token=token)

    return user_response, token_response
