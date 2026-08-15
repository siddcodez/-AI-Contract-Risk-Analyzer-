"""API tests for Precedents endpoint: POST /api/v1/contracts/{contract_id}/precedents."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from app.api.deps import get_current_user
from app.main import app
from app.models.contract import Contract, ContractStatus
from app.models.contract_chunk import ContractChunk
from app.models.user import User, UserRole
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
    title: str = "Active MSA 2026",
) -> Contract:
    c = Contract()
    c.id = contract_id
    c.title = title
    c.file_name = "active_msa.pdf"
    c.file_size = 1024
    c.content_type = "application/pdf"
    c.storage_key = f"contracts/{contract_id}/active_msa.pdf"
    c.status = ContractStatus.completed
    c.org_id = org_id
    c.uploaded_by = uuid.uuid4()
    return c


class TestPrecedentsAPI:
    """Test suite for POST /api/v1/contracts/{contract_id}/precedents."""

    async def test_unauthenticated_returns_401(self, async_client: AsyncClient) -> None:
        cid = uuid.uuid4()
        res = await async_client.post(
            f"/api/v1/contracts/{cid}/precedents",
            json={"query": "limitation of liability"},
        )
        assert res.status_code == 401

    @patch("app.api.v1.search.contract_repo.get_by_id", new_callable=AsyncMock)
    async def test_contract_not_found_returns_404(
        self,
        mock_get_contract: AsyncMock,
        async_client: AsyncClient,
    ) -> None:
        mock_get_contract.return_value = None
        user = _make_user(role=UserRole.viewer)
        app.dependency_overrides[get_current_user] = lambda: user

        cid = uuid.uuid4()
        headers = {"Authorization": "Bearer fake.jwt.token"}
        try:
            res = await async_client.post(
                f"/api/v1/contracts/{cid}/precedents",
                headers=headers,
                json={"query": "confidentiality obligation"},
            )
            assert res.status_code == 404
            data = res.json()
            assert data["error"]["code"] == "NOT_FOUND"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.api.v1.search.contract_repo.get_by_id", new_callable=AsyncMock)
    async def test_cross_tenant_isolation_org_cannot_access_other_org_precedents(
        self,
        mock_get_contract: AsyncMock,
        async_client: AsyncClient,
    ) -> None:
        """Cross-tenant check: querying a contract owned by Org B returns exact 404 under RLS."""
        user_org_a = _make_user(org_id=uuid.uuid4(), role=UserRole.reviewer)
        mock_get_contract.return_value = None  # RLS filters out cross-tenant contracts
        app.dependency_overrides[get_current_user] = lambda: user_org_a

        contract_org_b_id = uuid.uuid4()
        headers = {"Authorization": "Bearer fake.jwt.token"}
        try:
            res = await async_client.post(
                f"/api/v1/contracts/{contract_org_b_id}/precedents",
                headers=headers,
                json={"query": "indemnification by vendor"},
            )
            assert res.status_code == 404
            data = res.json()
            assert data["error"]["code"] == "NOT_FOUND"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch(
        "app.services.precedent_service.contract_chunk_repo.search_precedent_chunks",
        new_callable=AsyncMock,
    )
    @patch("app.services.precedent_service.embedding_service.embed_texts")
    @patch("app.api.v1.search.contract_repo.get_by_id", new_callable=AsyncMock)
    async def test_search_precedents_success_response_structure(
        self,
        mock_get_contract: AsyncMock,
        mock_embed: AsyncMock,
        mock_search_chunks: AsyncMock,
        async_client: AsyncClient,
    ) -> None:
        org_id = uuid.uuid4()
        current_contract_id = uuid.uuid4()
        precedent_contract_id = uuid.uuid4()
        precedent_version_id = uuid.uuid4()
        chunk_id = uuid.uuid4()

        user = _make_user(org_id=org_id, role=UserRole.viewer)
        current_contract = _make_contract(current_contract_id, org_id)

        now = datetime.now(UTC)
        precedent_chunk = ContractChunk(
            id=chunk_id,
            contract_id=precedent_contract_id,
            version_id=precedent_version_id,
            org_id=org_id,
            chunk_index=3,
            content="Each party agrees to hold in confidence all confidential information.",
            embedding=[0.05] * 1536,
            created_at=now,
        )

        mock_get_contract.return_value = current_contract
        mock_embed.return_value = [[0.05] * 1536]
        mock_search_chunks.return_value = [
            (precedent_chunk, "Precedent NDA 2024", "precedent_nda.pdf", 0.91),
        ]

        app.dependency_overrides[get_current_user] = lambda: user

        headers = {"Authorization": "Bearer fake.jwt.token"}
        try:
            res = await async_client.post(
                f"/api/v1/contracts/{current_contract_id}/precedents",
                headers=headers,
                json={"query": "confidentiality clause", "top_k": 3, "min_score": 0.50},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["query_contract_id"] == str(current_contract_id)
            assert data["query"] == "confidentiality clause"
            assert data["total_results"] == 1
            assert len(data["items"]) == 1
            item = data["items"][0]
            assert item["chunk_id"] == str(chunk_id)
            assert item["contract_id"] == str(precedent_contract_id)
            assert item["contract_title"] == "Precedent NDA 2024"
            assert item["file_name"] == "precedent_nda.pdf"
            assert item["similarity_score"] == 0.91
            assert "Each party agrees to hold in confidence" in item["content"]
            assert "not legal advice" in data["disclaimer"].lower()
        finally:
            app.dependency_overrides.pop(get_current_user, None)
