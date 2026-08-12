"""Password hashing and JWT token management.

Security invariants:
- Passwords are hashed with bcrypt (one-way, salted).
- JWT tokens contain only the minimum required claims.
- Tokens are signed with HS256 using SECRET_KEY.
- Passwords, tokens, and sensitive data are NEVER logged.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt.

    Returns a bcrypt hash string that can be stored in the database.
    The result is NEVER equal to the input (one-way function).
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash.

    Returns True only if the password matches.
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------


def create_access_token(
    *,
    user_id: str,
    org_id: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token.

    Claims:
        sub:    User ID (string UUID).
        org_id: Organization ID (string UUID).
        role:   User role (admin | reviewer | viewer).
        iat:    Issued-at timestamp.
        exp:    Expiry timestamp.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload: dict[str, Any] = {
        "sub": user_id,
        "org_id": org_id,
        "role": role,
        "iat": now,
        "exp": expire,
    }
    encoded: str = jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token.

    Validates both the signature and the expiry timestamp.

    Raises:
        jwt.ExpiredSignatureError: Token has expired.
        jwt.InvalidTokenError: Token is invalid (bad signature, malformed, etc.).

    Returns:
        The decoded payload dictionary.
    """
    settings = get_settings()
    payload: dict[str, Any] = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    return payload
