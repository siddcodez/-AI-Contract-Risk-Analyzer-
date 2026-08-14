"""API tests for Missing Clauses endpoint: GET /api/v1/contracts/{contract_id}/missing-clauses."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.api.deps import get_current_user
from app.main import app
from app.models.contract import Contract, ContractStatus
from app.models.contract_version import ContractVersion
from app.models.missing_clause import MissingClause
from app.models.user import User, UserRole


def _make_user(
    user_id: uuid.UUID | None = None,
    org_id: uuid.UUID | None = None,
    role: UserRole = UserRole.reviewer,
) -> User:
    u = User()
    u.id = user_id or uuid.uuid4()
    u.email = "test@contractiq.io"
    u.full_name = "Test Reviewer"
    u.hashed_password = "hashed_password"
    u.role = role
    u.org_id = org_id or uuid.uuid4()
    u.is_active = True
    return u


def _make_contract(
    contract_id: uuid.UUID,
    org_id: uuid.UUID,
    title: str = "Vendor Agreement",
) -> Contract:
    c = Contract()
    c.id = contract_id
    c.title = title
    c.file_name = "contract.pdf"
    c.file_size = 1024
    c.content_type = "application/pdf"
    c.storage_key = f"contracts/{contract_id}/contract.pdf"
    c.status = ContractStatus.completed
    c.org_id = org_id
    c.uploaded_by = uuid.uuid4()
    return c


def _make_version(
    version_id: uuid.UUID,
    contract_id: uuid.UUID,
    org_id: uuid.UUID,
    version_number: int = 1,
) -> ContractVersion:
    v = ContractVersion()
    v.id = version_id
    v.contract_id = contract_id
    v.version_number = version_number
    v.file_name = "contract.pdf"
    v.file_size = 1024
    v.content_type = "application/pdf"
    v.storage_key = f"contracts/{contract_id}/v{version_number}.pdf"
    v.org_id = org_id
    return v


class TestMissingClausesAPI:
    """Test suite for GET /api/v1/contracts/{contract_id}/missing-clauses."""

    async def test_unauthenticated_returns_401(self, async_client: AsyncClient) -> None:
        cid = uuid.uuid4()
        res = await async_client.get(f"/api/v1/contracts/{cid}/missing-clauses")
        assert res.status_code == 401

    @patch("app.api.v1.missing_clauses.contract_repo.get_by_id", new_callable=AsyncMock)
    async def test_contract_not_found_returns_404(
        self,
        mock_get_contract: AsyncMock,
        async_client: AsyncClient,
    ) -> None:
        mock_get_contract.return_value = None
        user = _make_user()
        app.dependency_overrides[get_current_user] = lambda: user

        cid = uuid.uuid4()
        headers = {"Authorization": "Bearer fake.jwt.token"}
        try:
            res = await async_client.get(
                f"/api/v1/contracts/{cid}/missing-clauses",
                headers=headers,
            )
            assert res.status_code == 404
            data = res.json()
            assert data["error"]["code"] == "NOT_FOUND"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.api.v1.missing_clauses.contract_repo.get_by_id", new_callable=AsyncMock)
    async def test_cross_tenant_isolation_returns_404(
        self,
        mock_get_contract: AsyncMock,
        async_client: AsyncClient,
    ) -> None:
        user_org_a = _make_user(org_id=uuid.uuid4())
        mock_get_contract.return_value = None  # RLS filters out cross-tenant contracts
        app.dependency_overrides[get_current_user] = lambda: user_org_a

        contract_org_b_id = uuid.uuid4()
        headers = {"Authorization": "Bearer fake.jwt.token"}
        try:
            res = await async_client.get(
                f"/api/v1/contracts/{contract_org_b_id}/missing-clauses",
                headers=headers,
            )
            assert res.status_code == 404
            data = res.json()
            assert data["error"]["code"] == "NOT_FOUND"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.api.v1.missing_clauses.missing_clause_repo.list_by_contract_and_version", new_callable=AsyncMock)
    @patch("app.api.v1.missing_clauses.contract_version_repo.list_by_contract", new_callable=AsyncMock)
    @patch("app.api.v1.missing_clauses.contract_repo.get_by_id", new_callable=AsyncMock)
    async def test_get_missing_clauses_success(
        self,
        mock_get_contract: AsyncMock,
        mock_list_versions: AsyncMock,
        mock_list_missing: AsyncMock,
        async_client: AsyncClient,
    ) -> None:
        org_id = uuid.uuid4()
        contract_id = uuid.uuid4()
        version_id = uuid.uuid4()

        user = _make_user(org_id=org_id)
        contract = _make_contract(contract_id, org_id)
        version = _make_version(version_id, contract_id, org_id)

        now = datetime.now(timezone.utc)
        mc1 = MissingClause(
            id=uuid.uuid4(),
            contract_id=contract_id,
            version_id=version_id,
            org_id=org_id,
            clause_type="data_protection",
            confidence=0.95,
            reason="No data protection clause was identified among the classified clauses for this contract version.",
            status="missing",
            metadata_json={"contract_type": "vendor_msa"},
            created_at=now,
            updated_at=now,
        )
        mc2 = MissingClause(
            id=uuid.uuid4(),
            contract_id=contract_id,
            version_id=version_id,
            org_id=org_id,
            clause_type="insurance",
            confidence=0.95,
            reason="No insurance clause was identified among the classified clauses for this contract version.",
            status="missing",
            metadata_json={"contract_type": "vendor_msa"},
            created_at=now,
            updated_at=now,
        )

        mock_get_contract.return_value = contract
        mock_list_versions.return_value = [version]
        mock_list_missing.return_value = [mc1, mc2]

        app.dependency_overrides[get_current_user] = lambda: user

        headers = {"Authorization": "Bearer fake.jwt.token"}
        try:
            res = await async_client.get(
                f"/api/v1/contracts/{contract_id}/missing-clauses",
                headers=headers,
            )
            assert res.status_code == 200
            data = res.json()
            assert data["contract_id"] == str(contract_id)
            assert data["version_id"] == str(version_id)
            assert data["total"] == 2
            assert len(data["items"]) == 2
            clause_types = [item["clause_type"] for item in data["items"]]
            assert "data_protection" in clause_types
            assert "insurance" in clause_types
            assert data["items"][0]["confidence"] == 0.95
            assert "No data protection clause" in data["items"][0]["reason"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)
