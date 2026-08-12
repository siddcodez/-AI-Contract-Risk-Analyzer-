"""Authentication endpoints.

POST /api/v1/auth/register — create organisation + first admin user
POST /api/v1/auth/login    — authenticate and receive access token
GET  /api/v1/auth/me       — return current user profile (requires auth)

Controllers are thin: validate → delegate to service → return response.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=201,
    summary="Register a new organisation and admin user",
)
async def register(
    data: RegisterRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Create a new organisation and its first user (admin role).

    Returns an access token so the user is immediately authenticated.
    """
    _user_response, token_response = await auth_service.register_user(session, data)
    return token_response


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive access token",
)
async def login(
    data: LoginRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Validate credentials and return a JWT access token."""
    _user_response, token_response = await auth_service.authenticate_user(
        session, data.email, data.password
    )
    return token_response


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Return the profile of the currently authenticated user."""
    org_name = ""
    if hasattr(current_user, "organization") and current_user.organization is not None:
        org_name = current_user.organization.name

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.value,
        org_id=current_user.org_id,
        org_name=org_name,
        created_at=current_user.created_at,
    )
