"""API tests for Contract Version Comparison: GET /api/v1/contracts/{contract_id}/compare."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from app.api.deps import get_current_user
from app.main import app
from app.models.contract import Contract, ContractStatus
from app.models.user import User, UserRole
from app.schemas.comparison import ClauseChangeType, ClauseDiffItem, ContractComparisonResponse
from httpx import AsyncClient


def _make_user(
    user_id: uuid.UUID | None = None,
    org_id: uuid.UUID | None = None,
    role: UserRole = UserRole.viewer,
) -> User:
    u = User()
    u.id = user_id or uuid.uuid4()
    u.email = "viewer@contractiq.io"
    u.full_name = "Test Viewer"
    u.password_hash = "hashed_password"
    u.role = role
    u.org_id = org_id or uuid.uuid4()
    u.is_active = True
    return u


def _make_contract(
    contract_id: uuid.UUID,
    org_id: uuid.UUID,
    title: str = "Active Master Agreement",
) -> Contract:
    c = Contract()
    c.id = contract_id
    c.title = title
    c.file_name = "active_master.pdf"
    c.file_size = 1024
    c.content_type = "application/pdf"
    c.storage_key = f"contracts/{contract_id}/active_master.pdf"
    c.status = ContractStatus.completed
    c.org_id = org_id
    c.uploaded_by = uuid.uuid4()
    return c


class TestComparisonAPI:
    """Test suite for GET /api/v1/contracts/{contract_id}/compare."""

    async def test_unauthenticated_returns_401(self, async_client: AsyncClient) -> None:
        cid = uuid.uuid4()
        v1 = uuid.uuid4()
        v2 = uuid.uuid4()
        res = await async_client.get(
            f"/api/v1/contracts/{cid}/compare?from_version_id={v1}&to_version_id={v2}",
        )
        assert res.status_code == 401

    @patch("app.services.comparison_service.contract_repo.get_by_id", new_callable=AsyncMock)
    async def test_contract_not_found_returns_404(
        self,
        mock_get_contract: AsyncMock,
        async_client: AsyncClient,
    ) -> None:
        mock_get_contract.return_value = None
        user = _make_user(role=UserRole.viewer)
        app.dependency_overrides[get_current_user] = lambda: user

        cid = uuid.uuid4()
        v1 = uuid.uuid4()
        v2 = uuid.uuid4()
        headers = {"Authorization": "Bearer fake.jwt.token"}
        try:
            res = await async_client.get(
                f"/api/v1/contracts/{cid}/compare?from_version_id={v1}&to_version_id={v2}",
                headers=headers,
            )
            assert res.status_code == 404
            data = res.json()
            assert data["error"]["code"] == "NOT_FOUND"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    async def test_identical_version_ids_returns_422(
        self,
        async_client: AsyncClient,
    ) -> None:
        user = _make_user(role=UserRole.viewer)
        app.dependency_overrides[get_current_user] = lambda: user

        cid = uuid.uuid4()
        vid = uuid.uuid4()
        headers = {"Authorization": "Bearer fake.jwt.token"}
        try:
            res = await async_client.get(
                f"/api/v1/contracts/{cid}/compare?from_version_id={vid}&to_version_id={vid}",
                headers=headers,
            )
            assert res.status_code == 422
            data = res.json()
            assert data["error"]["code"] == "VALIDATION_ERROR"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.services.comparison_service.contract_repo.get_by_id", new_callable=AsyncMock)
    async def test_cross_tenant_isolation_returns_404(
        self,
        mock_get_contract: AsyncMock,
        async_client: AsyncClient,
    ) -> None:
        """Querying a contract belonging to another tenant returns 404 under RLS."""
        user_org_a = _make_user(org_id=uuid.uuid4(), role=UserRole.reviewer)
        mock_get_contract.return_value = None  # RLS blocks cross-tenant
        app.dependency_overrides[get_current_user] = lambda: user_org_a

        other_contract_id = uuid.uuid4()
        v1 = uuid.uuid4()
        v2 = uuid.uuid4()
        headers = {"Authorization": "Bearer fake.jwt.token"}
        try:
            res = await async_client.get(
                f"/api/v1/contracts/{other_contract_id}/compare?from_version_id={v1}&to_version_id={v2}",
                headers=headers,
            )
            assert res.status_code == 404
            data = res.json()
            assert data["error"]["code"] == "NOT_FOUND"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.services.comparison_service.compare_contract_versions", new_callable=AsyncMock)
    async def test_compare_versions_success_response_structure(
        self,
        mock_compare: AsyncMock,
        async_client: AsyncClient,
    ) -> None:
        cid = uuid.uuid4()
        v1 = uuid.uuid4()
        v2 = uuid.uuid4()
        now = datetime.now(UTC)

        user = _make_user(role=UserRole.viewer)
        app.dependency_overrides[get_current_user] = lambda: user

        mock_compare.return_value = ContractComparisonResponse(
            id=uuid.uuid4(),
            contract_id=cid,
            from_version_id=v1,
            to_version_id=v2,
            from_version_number=1,
            to_version_number=2,
            risk_score_from=30,
            risk_score_to=70,
            risk_delta=40,
            clauses_added_count=1,
            clauses_removed_count=0,
            clauses_modified_count=1,
            clauses_unchanged_count=3,
            diff_items=[
                ClauseDiffItem(
                    clause_type="limitation_of_liability",
                    display_name="Limitation of Liability",
                    change_type=ClauseChangeType.modified,
                    from_text="Liability capped at 1x annual fees.",
                    to_text="Unlimited liability for breach of confidentiality.",
                    from_severity="medium",
                    to_severity="critical",
                    ai_explanation=None,
                )
            ],
            created_at=now,
            updated_at=now,
        )

        headers = {"Authorization": "Bearer fake.jwt.token"}
        try:
            res = await async_client.get(
                f"/api/v1/contracts/{cid}/compare?from_version_id={v1}&to_version_id={v2}",
                headers=headers,
            )
            assert res.status_code == 200
            data = res.json()
            assert data["contract_id"] == str(cid)
            assert data["risk_score_from"] == 30
            assert data["risk_score_to"] == 70
            assert data["risk_delta"] == 40
            assert data["clauses_added_count"] == 1
            assert data["clauses_modified_count"] == 1
            assert len(data["diff_items"]) == 1
            assert data["diff_items"][0]["change_type"] == "modified"
            assert "not legal advice" in data["disclaimer"].lower()
        finally:
            app.dependency_overrides.pop(get_current_user, None)
