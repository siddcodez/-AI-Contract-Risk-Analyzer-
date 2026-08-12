"""Pydantic schemas for authentication and user management.

These models define the API boundary — they are the only shapes that
cross between the HTTP layer and the service layer.  Internal domain
objects (ORM models) are never returned directly to clients.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    """POST /auth/register request body."""

    email: EmailStr = Field(description="User email address (globally unique)")
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Password — minimum 8 characters",
    )
    full_name: str = Field(
        min_length=1,
        max_length=255,
        description="Display name",
    )
    org_name: str = Field(
        min_length=1,
        max_length=255,
        description="Organization name (a new org will be created)",
    )


class LoginRequest(BaseModel):
    """POST /auth/login request body."""

    email: EmailStr
    password: str


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class TokenResponse(BaseModel):
    """Token response — matches OAuth2 convention."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105


class UserResponse(BaseModel):
    """Public-facing user representation (never includes password hash)."""

    id: uuid.UUID
    email: str
    full_name: str
    role: str
    org_id: uuid.UUID
    org_name: str
    created_at: datetime
