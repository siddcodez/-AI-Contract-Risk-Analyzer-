"""Unit tests for app.core.security — password hashing and JWT tokens."""

from datetime import timedelta

import jwt as pyjwt
import pytest
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    """bcrypt password hashing tests."""

    def test_hash_is_not_plaintext(self) -> None:
        """Hash must NEVER equal the plaintext password."""
        password = "my-secure-password-123"
        hashed = hash_password(password)
        assert hashed != password

    def test_hash_is_deterministic_per_call(self) -> None:
        """Each call produces a different hash (unique salt)."""
        password = "same-password"
        h1 = hash_password(password)
        h2 = hash_password(password)
        assert h1 != h2  # different salts

    def test_verify_correct_password(self) -> None:
        password = "correct-password"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_wrong_password(self) -> None:
        hashed = hash_password("right-password")
        assert verify_password("wrong-password", hashed) is False

    def test_hash_output_is_bcrypt_format(self) -> None:
        """bcrypt hashes start with $2b$ (or $2a$)."""
        hashed = hash_password("any-password")
        assert hashed.startswith("$2")


class TestJWT:
    """JWT creation and verification tests."""

    def test_create_and_decode_token(self) -> None:
        token = create_access_token(
            user_id="user-123",
            org_id="org-456",
            role="admin",
        )
        payload = decode_access_token(token)

        assert payload["sub"] == "user-123"
        assert payload["org_id"] == "org-456"
        assert payload["role"] == "admin"
        assert "exp" in payload
        assert "iat" in payload

    def test_expired_token_raises(self) -> None:
        """Expired tokens must be rejected."""
        token = create_access_token(
            user_id="user-123",
            org_id="org-456",
            role="viewer",
            expires_delta=timedelta(seconds=-1),
        )
        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_access_token(token)

    def test_invalid_token_raises(self) -> None:
        """Tampered / garbage tokens must be rejected."""
        with pytest.raises(pyjwt.InvalidTokenError):
            decode_access_token("not.a.valid.token")

    def test_tampered_token_raises(self) -> None:
        """A token signed with a different key must be rejected."""
        payload = {"sub": "user-1", "org_id": "org-1", "role": "admin"}
        token = pyjwt.encode(
            payload,
            "wrong-secret-key-minimum-32-chars-long-xxx",
            algorithm="HS256",
        )
        with pytest.raises(pyjwt.InvalidTokenError):
            decode_access_token(token)

    def test_custom_expiry(self) -> None:
        """Custom expiry delta should be honoured."""
        token = create_access_token(
            user_id="u1",
            org_id="o1",
            role="viewer",
            expires_delta=timedelta(hours=2),
        )
        payload = decode_access_token(token)
        # exp should be about 2 hours from now
        assert payload["exp"] > payload["iat"]
