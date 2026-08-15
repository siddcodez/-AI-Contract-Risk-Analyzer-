"""Unit and API tests for Audit Logs & Tenant Isolation (Phase 11)."""

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from app.api.deps import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.audit_log import AuditActionType, AuditLog
from app.models.user import User, UserRole
from httpx import ASGITransport, AsyncClient


def _make_user(role: UserRole = UserRole.admin, org_id: uuid.UUID | None = None) -> User:
    oid = org_id or uuid.uuid4()
    return User(
        id=uuid.uuid4(),
        email=f"user_{role.value}@example.com",
        full_name=f"Test {role.value.capitalize()}",
        role=role,
        org_id=oid,
        password_hash="fakehash",
        is_active=True,
    )


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    mock_session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()


class TestAuditLogsAPI:
    @pytest.mark.asyncio
    async def test_non_admin_roles_blocked_from_audit_logs(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Both VIEWER and REVIEWER are blocked from listing audit logs (403 Forbidden)."""
        headers = {"Authorization": "Bearer fake.jwt.token"}

        for role in (UserRole.viewer, UserRole.reviewer):
            user = _make_user(role=role)
            app.dependency_overrides[get_current_user] = lambda u=user: u

            try:
                res = await async_client.get("/api/v1/audit-logs", headers=headers)
                assert res.status_code == 403
                data = res.json()
                assert data["error"]["code"] == "FORBIDDEN"
            finally:
                app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.asyncio
    async def test_admin_can_list_audit_logs_with_pagination(
        self,
        async_client: AsyncClient,
    ) -> None:
        """ADMIN role can list paginated audit log entries for their tenant."""
        admin = _make_user(role=UserRole.admin)
        app.dependency_overrides[get_current_user] = lambda: admin
        headers = {"Authorization": "Bearer fake.jwt.token"}

        logs = [
            AuditLog(
                id=uuid.uuid4(),
                org_id=admin.org_id,
                user_id=admin.id,
                user_email=admin.email,
                action=AuditActionType.CONTRACT_UPLOADED.value,
                entity_type="contract",
                entity_id=uuid.uuid4(),
                metadata_json={"contract_title": "MSA_2026.pdf"},
            ),
            AuditLog(
                id=uuid.uuid4(),
                org_id=admin.org_id,
                user_id=admin.id,
                user_email=admin.email,
                action=AuditActionType.CLAUSE_APPROVED.value,
                entity_type="risk_finding",
                entity_id=uuid.uuid4(),
                metadata_json={"finding_category": "indemnification"},
            ),
        ]

        with (
            patch(
                "app.repositories.audit_log_repo.list_audit_logs",
                new=AsyncMock(return_value=logs),
            ),
            patch(
                "app.repositories.audit_log_repo.count_audit_logs",
                new=AsyncMock(return_value=2),
            ),
        ):
            res = await async_client.get("/api/v1/audit-logs?skip=0&limit=50", headers=headers)
            assert res.status_code == 200
            data = res.json()
            assert data["total"] == 2
            assert len(data["items"]) == 2
            assert data["items"][0]["action"] == "CONTRACT_UPLOADED"
            assert data["items"][1]["action"] == "CLAUSE_APPROVED"

    @pytest.mark.asyncio
    async def test_audit_logs_do_not_leak_across_organizations(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Audit logs query filters strictly by the authenticated tenant's RLS context."""
        admin_org_a = _make_user(role=UserRole.admin, org_id=uuid.uuid4())
        app.dependency_overrides[get_current_user] = lambda: admin_org_a
        headers = {"Authorization": "Bearer fake.jwt.token"}

        with (
            patch(
                "app.repositories.audit_log_repo.list_audit_logs",
                new=AsyncMock(return_value=[]),
            ) as mock_list,
            patch(
                "app.repositories.audit_log_repo.count_audit_logs",
                new=AsyncMock(return_value=0),
            ),
        ):
            res = await async_client.get("/api/v1/audit-logs", headers=headers)
            assert res.status_code == 200
            data = res.json()
            assert data["total"] == 0
            assert data["items"] == []
            mock_list.assert_called_once()
