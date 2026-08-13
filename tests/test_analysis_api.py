"""API tests for contract analysis and findings endpoints (M4).

Tests:
GET  /api/v1/contracts/{id}/analysis
GET  /api/v1/contracts/{id}/findings
GET  /api/v1/contracts/{id}/findings/summary
POST /api/v1/contracts/{id}/analyze
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.security import create_access_token
from app.models.analysis_job import AnalysisJobStatus
from app.models.risk_finding import RiskCategory, RiskSeverity
from app.models.user import User, UserRole
from httpx import AsyncClient


def _make_user(role: UserRole = UserRole.reviewer) -> User:
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        password_hash="fakehash",
        full_name="Test User",
        role=role,
        org_id=uuid.uuid4(),
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


class TestAnalysisAPI:
    @patch("app.api.v1.analysis.contract_repo.get_by_id", new_callable=AsyncMock)
    @patch("app.api.v1.analysis.analysis_job_repo.get_latest_by_contract", new_callable=AsyncMock)
    async def test_get_analysis_status_success(
        self,
        mock_get_latest_job: AsyncMock,
        mock_get_contract: AsyncMock,
        async_client: AsyncClient,
    ) -> None:
        user = _make_user(UserRole.viewer)
        headers = {"Authorization": f"Bearer {_make_token(user)}"}

        from app.api.deps import get_current_user
        from app.main import app

        async def _override_user() -> User:
            return user

        app.dependency_overrides[get_current_user] = _override_user

        contract_id = uuid.uuid4()
        job_id = uuid.uuid4()

        mock_contract = MagicMock()
        mock_contract.id = contract_id
        mock_get_contract.return_value = mock_contract

        mock_job = MagicMock()
        mock_job.id = job_id
        mock_job.status = AnalysisJobStatus.completed
        mock_job.findings_count = 3
        mock_job.error_message = None
        mock_get_latest_job.return_value = mock_job

        try:
            res = await async_client.get(
                f"/api/v1/contracts/{contract_id}/analysis",
                headers=headers,
            )
            assert res.status_code == 200
            data = res.json()
            assert data["contract_id"] == str(contract_id)
            assert data["analysis_job_id"] == str(job_id)
            assert data["status"] == "completed"
            assert data["findings_count"] == 3
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.api.v1.analysis.contract_repo.get_by_id", new_callable=AsyncMock)
    @patch("app.api.v1.analysis.risk_finding_repo.list_by_contract", new_callable=AsyncMock)
    @patch("app.api.v1.analysis.risk_finding_repo.count_by_contract", new_callable=AsyncMock)
    async def test_list_findings_success(
        self,
        mock_count: AsyncMock,
        mock_list: AsyncMock,
        mock_get_contract: AsyncMock,
        async_client: AsyncClient,
    ) -> None:
        user = _make_user(UserRole.viewer)
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

        mock_finding = MagicMock()
        mock_finding.id = uuid.uuid4()
        mock_finding.contract_id = contract_id
        mock_finding.version_id = uuid.uuid4()
        mock_finding.org_id = user.org_id
        mock_finding.chunk_id = None
        mock_finding.category = RiskCategory.liability
        mock_finding.severity = RiskSeverity.critical
        mock_finding.title = "Uncapped Liability"
        mock_finding.description = "Detailed risk explanation"
        mock_finding.evidence = "Verbatim quote evidence"
        mock_finding.recommendation = "Suggested redline"
        mock_finding.confidence = 0.95
        mock_finding.metadata_json = None
        mock_finding.created_at = datetime.now(UTC)
        mock_finding.updated_at = datetime.now(UTC)

        mock_list.return_value = [mock_finding]
        mock_count.return_value = 1

        try:
            res = await async_client.get(
                f"/api/v1/contracts/{contract_id}/findings",
                headers=headers,
            )
            assert res.status_code == 200
            data = res.json()
            assert data["total"] == 1
            assert len(data["items"]) == 1
            assert data["items"][0]["category"] == "liability"
            assert data["items"][0]["severity"] == "critical"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.api.v1.analysis.contract_repo.get_by_id", new_callable=AsyncMock)
    @patch("app.api.v1.analysis.risk_finding_repo.get_summary_by_contract", new_callable=AsyncMock)
    async def test_get_findings_summary_success(
        self,
        mock_summary: AsyncMock,
        mock_get_contract: AsyncMock,
        async_client: AsyncClient,
    ) -> None:
        user = _make_user(UserRole.viewer)
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

        mock_summary.return_value = {
            "total": 5,
            "critical": 1,
            "high": 2,
            "medium": 1,
            "low": 1,
        }

        try:
            res = await async_client.get(
                f"/api/v1/contracts/{contract_id}/findings/summary",
                headers=headers,
            )
            assert res.status_code == 200
            data = res.json()
            assert data["total"] == 5
            assert data["critical"] == 1
            assert data["high"] == 2
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.api.v1.analysis.contract_repo.get_by_id", new_callable=AsyncMock)
    @patch("app.api.v1.analysis.analysis_service.trigger_analysis", new_callable=AsyncMock)
    async def test_trigger_analysis_requires_reviewer(
        self,
        mock_trigger: AsyncMock,
        mock_get_contract: AsyncMock,
        async_client: AsyncClient,
    ) -> None:
        user = _make_user(UserRole.reviewer)
        headers = {"Authorization": f"Bearer {_make_token(user)}"}

        from app.api.deps import get_current_user, require_reviewer_or_above
        from app.main import app

        async def _override_user() -> User:
            return user

        app.dependency_overrides[get_current_user] = _override_user
        app.dependency_overrides[require_reviewer_or_above] = _override_user

        contract_id = uuid.uuid4()
        mock_contract = MagicMock()
        mock_contract.id = contract_id
        mock_get_contract.return_value = mock_contract

        mock_job = MagicMock()
        mock_job.id = uuid.uuid4()
        mock_job.status = AnalysisJobStatus.queued
        mock_job.findings_count = 0
        mock_job.error_message = None
        mock_trigger.return_value = mock_job

        try:
            res = await async_client.post(
                f"/api/v1/contracts/{contract_id}/analyze",
                headers=headers,
            )
            assert res.status_code == 202
            data = res.json()
            assert data["status"] == "queued"
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(require_reviewer_or_above, None)
