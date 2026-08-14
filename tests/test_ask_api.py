"""API integration tests for grounded contract Q&A endpoint (M7.1).

Tests:
POST /api/v1/contracts/{id}/ask
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import LLMError
from app.core.security import create_access_token
from app.models.user import User, UserRole
from app.schemas.search import GroundedCitation
from app.services.llm_service import GroundedAnswer
from httpx import AsyncClient


def _make_user(role: UserRole = UserRole.reviewer, org_id: uuid.UUID | None = None) -> User:
    user = User(
        id=uuid.uuid4(),
        email="askqa@example.com",
        password_hash="fakehash",
        full_name="Ask QA User",
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


class TestAskAPI:
    async def test_ask_unauthenticated_returns_401(self, async_client: AsyncClient) -> None:
        contract_id = uuid.uuid4()
        res = await async_client.post(
            f"/api/v1/contracts/{contract_id}/ask",
            json={"query": "Can the vendor increase the price without my approval?"},
        )
        assert res.status_code == 401

    @patch("app.api.v1.search.contract_repo.get_by_id", new_callable=AsyncMock)
    @patch("app.api.v1.search.retrieval_service.build_rag_context", new_callable=AsyncMock)
    @patch("app.api.v1.search.llm_service.generate_grounded_answer", new_callable=AsyncMock)
    async def test_ask_success_with_grounded_answer(
        self,
        mock_generate_answer: AsyncMock,
        mock_build_rag: AsyncMock,
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
        chunk_id = uuid.uuid4()

        mock_contract = MagicMock()
        mock_contract.id = contract_id
        mock_get_contract.return_value = mock_contract

        mock_build_rag.return_value = {
            "context_text": (
                "[Chunk 0 | similarity=0.92]\n"
                "All pricing adjustments must be set forth in an executed SOW."
            ),
            "chunks_count": 1,
            "total_chars": 95,
            "items": [
                {
                    "chunk_id": chunk_id,
                    "contract_id": contract_id,
                    "version_id": uuid.uuid4(),
                    "chunk_index": 0,
                    "content": "All pricing adjustments must be set forth in an executed SOW.",
                    "similarity_score": 0.92,
                }
            ],
        }

        mock_citation = GroundedCitation(
            chunk_id=chunk_id,
            chunk_index=0,
            similarity_score=0.92,
            quote="pricing adjustments must be set forth in an executed Statement of Work",
        )

        mock_generate_answer.return_value = GroundedAnswer(
            answer="The contract does not permit unilateral price increases without approval.",
            confidence=0.95,
            citations=[mock_citation],
            model="mock-grounded-qa",
        )

        try:
            res = await async_client.post(
                f"/api/v1/contracts/{contract_id}/ask",
                headers=headers,
                json={"query": "Can the vendor increase the price without my approval?"},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["contract_id"] == str(contract_id)
            assert data["query"] == "Can the vendor increase the price without my approval?"
            assert "price" in data["answer"].lower()
            assert data["confidence"] == 0.95
            assert len(data["citations"]) == 1
            assert data["citations"][0]["chunk_id"] == str(chunk_id)
            assert data["citations"][0]["chunk_index"] == 0
            assert data["citations"][0]["similarity_score"] == 0.92
            assert "pricing adjustments" in data["citations"][0]["quote"]
            assert data["retrieval_count"] == 1
            assert data["model"] == "mock-grounded-qa"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.api.v1.search.contract_repo.get_by_id", new_callable=AsyncMock)
    async def test_ask_contract_not_found(
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
                f"/api/v1/contracts/{contract_id}/ask",
                headers=headers,
                json={"query": "What are the payment terms?"},
            )
            assert res.status_code == 404
            assert res.json()["error"]["code"] == "NOT_FOUND"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    async def test_ask_invalid_payload_422(self, async_client: AsyncClient) -> None:
        user = _make_user()
        headers = {"Authorization": f"Bearer {_make_token(user)}"}

        from app.api.deps import get_current_user
        from app.main import app

        async def _override_user() -> User:
            return user

        app.dependency_overrides[get_current_user] = _override_user

        contract_id = uuid.uuid4()

        try:
            # Empty query
            res = await async_client.post(
                f"/api/v1/contracts/{contract_id}/ask",
                headers=headers,
                json={"query": ""},
            )
            assert res.status_code == 422

            # Negative top_k
            res2 = await async_client.post(
                f"/api/v1/contracts/{contract_id}/ask",
                headers=headers,
                json={"query": "valid query", "top_k": -1},
            )
            assert res2.status_code == 422
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.api.v1.search.contract_repo.get_by_id", new_callable=AsyncMock)
    @patch("app.api.v1.search.retrieval_service.build_rag_context", new_callable=AsyncMock)
    @patch("app.api.v1.search.llm_service.generate_grounded_answer", new_callable=AsyncMock)
    async def test_ask_llm_failure_sanitized_502(
        self,
        mock_generate_answer: AsyncMock,
        mock_build_rag: AsyncMock,
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

        mock_build_rag.return_value = {
            "context_text": "Sample context",
            "chunks_count": 1,
            "total_chars": 14,
            "items": [],
        }

        mock_generate_answer.side_effect = LLMError("Groq service unavailable")

        try:
            res = await async_client.post(
                f"/api/v1/contracts/{contract_id}/ask",
                headers=headers,
                json={"query": "What is the liability cap?"},
            )
            assert res.status_code == 502
            data = res.json()
            assert data["error"]["code"] == "LLM_ERROR"
            assert "Groq service unavailable" in data["error"]["message"]
            # Ensure no secret keys or internal stack traces are returned
            assert "api_key" not in res.text
            assert "traceback" not in res.text.lower()
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.api.v1.search.contract_repo.get_by_id", new_callable=AsyncMock)
    async def test_ask_cross_tenant_isolation_returns_404(
        self,
        mock_get_contract: AsyncMock,
        async_client: AsyncClient,
    ) -> None:
        user_org_a = _make_user(org_id=uuid.uuid4())
        headers = {"Authorization": f"Bearer {_make_token(user_org_a)}"}

        from app.api.deps import get_current_user
        from app.main import app

        async def _override_user() -> User:
            return user_org_a

        app.dependency_overrides[get_current_user] = _override_user

        # Contract belongs to Org B, so repository returns None under RLS
        mock_get_contract.return_value = None
        contract_id_org_b = uuid.uuid4()

        try:
            res = await async_client.post(
                f"/api/v1/contracts/{contract_id_org_b}/ask",
                headers=headers,
                json={"query": "Can the vendor increase the price?"},
            )
            assert res.status_code == 404
            assert res.json()["error"]["code"] == "NOT_FOUND"
        finally:
            app.dependency_overrides.pop(get_current_user, None)
