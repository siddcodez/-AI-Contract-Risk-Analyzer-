"""API tests for search and retrieval endpoints (M5).

Tests:
POST /api/v1/contracts/{id}/search
POST /api/v1/contracts/{id}/retrieval
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.security import create_access_token
from app.models.user import User, UserRole
from httpx import AsyncClient


def _make_user(role: UserRole = UserRole.reviewer, org_id: uuid.UUID | None = None) -> User:
    user = User(
        id=uuid.uuid4(),
        email="searchtest@example.com",
        password_hash="fakehash",
        full_name="Search User",
        role=role,
        org_id=org_id or uuid.uuid4(),
        is_active=True,
    )
    object.__setattr__(user, "created_at", datetime.now(UTC))
    object.__setattr__(user, "updated_at", datetime.now(UTC))
    return user


def _make_token(user: User) -> str:
    return create_access_token(
        user_id=str(user.id),
        org_id=str(user.org_id),
        role=user.role.value,
    )


class TestSearchAPI:
    async def test_search_unauthenticated_returns_401(self, async_client: AsyncClient) -> None:
        contract_id = uuid.uuid4()
        res = await async_client.post(
            f"/api/v1/contracts/{contract_id}/search",
            json={"query": "limitation of liability"},
        )
        assert res.status_code == 401

    @patch("app.api.v1.search.contract_repo.get_by_id", new_callable=AsyncMock)
    @patch("app.api.v1.search.retrieval_service.search_chunks", new_callable=AsyncMock)
    async def test_search_success(
        self,
        mock_search_chunks: AsyncMock,
        mock_get_contract: AsyncMock,
        async_client: AsyncClient,
    ) -> None:
        user = _make_user()
        headers = {"Authorization": f"Bearer {_make_token(user)}"}

        from app.api.deps import get_current_user
        from app.main import app

        async def _override_user() -> User:
            return user

        app.dependency_overrides[get_current_user] = _override_user

        contract_id = uuid.uuid4()
        mock_contract = MagicMock()
        mock_contract.id = contract_id
        mock_get_contract.return_value = mock_contract

        mock_item = {
            "chunk_id": uuid.uuid4(),
            "contract_id": contract_id,
            "version_id": uuid.uuid4(),
            "chunk_index": 0,
            "content": "Liability shall be capped at total fees paid.",
            "similarity_score": 0.91,
        }
        mock_search_chunks.return_value = [mock_item]

        try:
            res = await async_client.post(
                f"/api/v1/contracts/{contract_id}/search",
                headers=headers,
                json={"query": "liability cap", "top_k": 5, "min_score": 0.20},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["contract_id"] == str(contract_id)
            assert data["total_results"] == 1
            assert len(data["items"]) == 1
            assert data["items"][0]["similarity_score"] == 0.91
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.api.v1.search.contract_repo.get_by_id", new_callable=AsyncMock)
    @patch("app.api.v1.search.retrieval_service.build_rag_context", new_callable=AsyncMock)
    async def test_retrieval_success(
        self,
        mock_rag: AsyncMock,
        mock_get_contract: AsyncMock,
        async_client: AsyncClient,
    ) -> None:
        user = _make_user()
        headers = {"Authorization": f"Bearer {_make_token(user)}"}

        from app.api.deps import get_current_user
        from app.main import app

        async def _override_user() -> User:
            return user

        app.dependency_overrides[get_current_user] = _override_user

        contract_id = uuid.uuid4()
        mock_contract = MagicMock()
        mock_contract.id = contract_id
        mock_get_contract.return_value = mock_contract

        mock_rag.return_value = {
            "context_text": "[Chunk 0 | similarity=0.91]\nLiability shall be capped.",
            "chunks_count": 1,
            "total_chars": 57,
            "items": [
                {
                    "chunk_id": uuid.uuid4(),
                    "contract_id": contract_id,
                    "version_id": uuid.uuid4(),
                    "chunk_index": 0,
                    "content": "Liability shall be capped.",
                    "similarity_score": 0.91,
                }
            ],
        }

        try:
            res = await async_client.post(
                f"/api/v1/contracts/{contract_id}/retrieval",
                headers=headers,
                json={"query": "liability", "max_chunks": 3},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["contract_id"] == str(contract_id)
            assert data["chunks_count"] == 1
            assert "Liability shall be capped" in data["context_text"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.api.v1.search.contract_repo.get_by_id", new_callable=AsyncMock)
    async def test_search_contract_not_found(
        self,
        mock_get_contract: AsyncMock,
        async_client: AsyncClient,
    ) -> None:
        user = _make_user()
        headers = {"Authorization": f"Bearer {_make_token(user)}"}

        from app.api.deps import get_current_user
        from app.main import app

        async def _override_user() -> User:
            return user

        app.dependency_overrides[get_current_user] = _override_user

        mock_get_contract.return_value = None
        contract_id = uuid.uuid4()

        try:
            res = await async_client.post(
                f"/api/v1/contracts/{contract_id}/search",
                headers=headers,
                json={"query": "test query"},
            )
            assert res.status_code == 404
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    async def test_search_invalid_payload_422(self, async_client: AsyncClient) -> None:
        user = _make_user()
        headers = {"Authorization": f"Bearer {_make_token(user)}"}

        from app.api.deps import get_current_user
        from app.main import app

        async def _override_user() -> User:
            return user

        app.dependency_overrides[get_current_user] = _override_user

        contract_id = uuid.uuid4()

        try:
            res = await async_client.post(
                f"/api/v1/contracts/{contract_id}/search",
                headers=headers,
                json={"query": "valid query", "top_k": -5},
            )
            assert res.status_code == 422
        finally:
            app.dependency_overrides.pop(get_current_user, None)
