"""Unit tests for the auth API endpoints.

All database and service calls are mocked — no Docker services required.
These test the HTTP layer, request validation, and response shapes.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from app.core.security import create_access_token, hash_password
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.schemas.auth import TokenResponse, UserResponse
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Helpers — create mock domain objects
# ---------------------------------------------------------------------------


def _make_org(
    org_id: uuid.UUID | None = None,
    name: str = "Test Corp",
    slug: str = "test-corp",
) -> Organization:
    org = Organization(
        id=org_id or uuid.uuid4(),
        name=name,
        slug=slug,
        is_active=True,
    )
    object.__setattr__(org, "created_at", datetime.now(UTC))
    object.__setattr__(org, "updated_at", datetime.now(UTC))
    return org


def _make_user(
    org: Organization,
    user_id: uuid.UUID | None = None,
    email: str = "test@example.com",
    role: UserRole = UserRole.admin,
    password: str = "secure-password-123",
) -> User:
    user = User(
        id=user_id or uuid.uuid4(),
        email=email,
        password_hash=hash_password(password),
        full_name="Test User",
        role=role,
        org_id=org.id,
        is_active=True,
    )
    object.__setattr__(user, "created_at", datetime.now(UTC))
    object.__setattr__(user, "updated_at", datetime.now(UTC))
    object.__setattr__(user, "organization", org)
    return user


def _make_token(user: User) -> str:
    return create_access_token(
        user_id=str(user.id),
        org_id=str(user.org_id),
        role=user.role.value,
    )


# Patch targets
AUTH_SERVICE = "app.api.v1.auth.auth_service"
GET_CURRENT_USER = "app.api.deps.get_current_user"


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------


class TestRegister:
    async def test_register_success(self, async_client: AsyncClient) -> None:
        """Successful registration returns 201 with a token."""
        org = _make_org()
        user = _make_user(org)
        token = _make_token(user)

        mock_response = (
            UserResponse(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                role=user.role.value,
                org_id=org.id,
                org_name=org.name,
                created_at=user.created_at,
            ),
            TokenResponse(access_token=token),
        )

        with patch(
            f"{AUTH_SERVICE}.register_user",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            resp = await async_client.post(
                "/api/v1/auth/register",
                json={
                    "email": "new@example.com",
                    "password": "strong-pass-123",
                    "full_name": "New User",
                    "org_name": "New Corp",
                },
            )

        assert resp.status_code == 201
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    async def test_register_duplicate_email(self, async_client: AsyncClient) -> None:
        """Duplicate email returns 409 Conflict."""
        from app.core.exceptions import ConflictError

        with patch(
            f"{AUTH_SERVICE}.register_user",
            new_callable=AsyncMock,
            side_effect=ConflictError("A user with this email already exists"),
        ):
            resp = await async_client.post(
                "/api/v1/auth/register",
                json={
                    "email": "dup@example.com",
                    "password": "strong-pass-123",
                    "full_name": "Dup User",
                    "org_name": "Dup Corp",
                },
            )

        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "CONFLICT"

    async def test_register_short_password_rejected(self, async_client: AsyncClient) -> None:
        """Password shorter than 8 chars is rejected at validation."""
        resp = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "valid@example.com",
                "password": "short",
                "full_name": "User",
                "org_name": "Org",
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Login tests
# ---------------------------------------------------------------------------


class TestLogin:
    async def test_login_success(self, async_client: AsyncClient) -> None:
        """Valid credentials return a token."""
        org = _make_org()
        user = _make_user(org)
        token = _make_token(user)

        mock_response = (
            UserResponse(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                role=user.role.value,
                org_id=org.id,
                org_name=org.name,
                created_at=user.created_at,
            ),
            TokenResponse(access_token=token),
        )

        with patch(
            f"{AUTH_SERVICE}.authenticate_user",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            resp = await async_client.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "secure-password-123"},
            )

        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_login_wrong_password(self, async_client: AsyncClient) -> None:
        """Bad credentials return 401."""
        from app.core.exceptions import AuthenticationError

        with patch(
            f"{AUTH_SERVICE}.authenticate_user",
            new_callable=AsyncMock,
            side_effect=AuthenticationError("Invalid email or password"),
        ):
            resp = await async_client.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "wrong-pass"},
            )

        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHORIZED"

    async def test_login_nonexistent_email(self, async_client: AsyncClient) -> None:
        """Unknown email returns 401 (same as wrong password — no info leak)."""
        from app.core.exceptions import AuthenticationError

        with patch(
            f"{AUTH_SERVICE}.authenticate_user",
            new_callable=AsyncMock,
            side_effect=AuthenticationError("Invalid email or password"),
        ):
            resp = await async_client.post(
                "/api/v1/auth/login",
                json={"email": "ghost@example.com", "password": "anything"},
            )

        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /auth/me tests
# ---------------------------------------------------------------------------


class TestMe:
    async def test_me_with_valid_token(self, async_client: AsyncClient) -> None:
        """Authenticated user gets their profile."""
        from app.api.deps import get_current_user
        from app.main import app

        org = _make_org()
        user = _make_user(org)

        app.dependency_overrides[get_current_user] = lambda: user
        try:
            resp = await async_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {_make_token(user)}"},
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == user.email
        assert body["role"] == "admin"
        assert body["org_name"] == org.name

    async def test_me_without_token(self, async_client: AsyncClient) -> None:
        """No token → 401."""
        resp = await async_client.get("/api/v1/auth/me")
        assert resp.status_code in (401, 403)

    async def test_me_with_expired_token(self, async_client: AsyncClient) -> None:
        """Expired token → 401."""
        from app.api.deps import get_current_user
        from app.core.exceptions import AuthenticationError
        from app.main import app

        def _raise_expired() -> None:
            raise AuthenticationError("Token has expired")

        app.dependency_overrides[get_current_user] = _raise_expired
        try:
            resp = await async_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer expired-token-here"},
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert resp.status_code == 401

    async def test_me_with_invalid_token(self, async_client: AsyncClient) -> None:
        """Garbage token → 401."""
        from app.api.deps import get_current_user
        from app.core.exceptions import AuthenticationError
        from app.main import app

        def _raise_invalid() -> None:
            raise AuthenticationError("Invalid authentication token")

        app.dependency_overrides[get_current_user] = _raise_invalid
        try:
            resp = await async_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer not-a-real-token"},
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# RBAC tests
# ---------------------------------------------------------------------------


class TestRBAC:
    """Test role-based access control via require_role dependency."""

    async def test_admin_can_access_admin_endpoint(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Admin role should be accepted."""
        from app.api.deps import get_current_user
        from app.main import app

        org = _make_org()
        admin_user = _make_user(org, role=UserRole.admin)

        app.dependency_overrides[get_current_user] = lambda: admin_user
        try:
            resp = await async_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {_make_token(admin_user)}"},
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    async def test_reviewer_role_works(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Reviewer can access authenticated endpoints."""
        from app.api.deps import get_current_user
        from app.main import app

        org = _make_org()
        reviewer = _make_user(org, role=UserRole.reviewer)

        app.dependency_overrides[get_current_user] = lambda: reviewer
        try:
            resp = await async_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {_make_token(reviewer)}"},
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert resp.status_code == 200
        assert resp.json()["role"] == "reviewer"

    async def test_viewer_role_works(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Viewer can access authenticated endpoints."""
        from app.api.deps import get_current_user
        from app.main import app

        org = _make_org()
        viewer = _make_user(org, role=UserRole.viewer)

        app.dependency_overrides[get_current_user] = lambda: viewer
        try:
            resp = await async_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {_make_token(viewer)}"},
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert resp.status_code == 200
        assert resp.json()["role"] == "viewer"

    async def test_require_role_blocks_insufficient_role(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Viewer cannot access admin-only actions → 403."""
        from app.api.deps import get_current_user
        from app.core.exceptions import ForbiddenError
        from app.main import app

        def _raise_forbidden() -> None:
            raise ForbiddenError("Role 'viewer' does not have permission for this action")

        app.dependency_overrides[get_current_user] = _raise_forbidden
        try:
            resp = await async_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer some-token"},
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"


# ---------------------------------------------------------------------------
# Cross-org access test (application layer)
# ---------------------------------------------------------------------------


class TestCrossOrgAccess:
    async def test_user_sees_own_org_data(self, async_client: AsyncClient) -> None:
        """A user's /me response contains their own org, not another org."""
        from app.api.deps import get_current_user
        from app.main import app

        org_a = _make_org(name="Org A", slug="org-a")
        org_b = _make_org(name="Org B", slug="org-b")
        user_a = _make_user(org_a, email="a@orga.com")

        app.dependency_overrides[get_current_user] = lambda: user_a
        try:
            resp = await async_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {_make_token(user_a)}"},
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        body = resp.json()
        assert body["org_id"] == str(org_a.id)
        assert body["org_name"] == "Org A"
        # Should NOT see org B's data
        assert body["org_id"] != str(org_b.id)
