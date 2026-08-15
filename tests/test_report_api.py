"""API and integration tests for PDF Report Endpoints & Celery Integration (Phase 12)."""

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from app.api.deps import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.contract import Contract, ContractStatus
from app.models.contract_version import ContractVersion
from app.models.report_job import ReportJob, ReportJobStatus
from app.models.user import User, UserRole
from httpx import ASGITransport, AsyncClient


def _make_user(role: UserRole = UserRole.reviewer, org_id: uuid.UUID | None = None) -> User:
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


def _make_contract(org_id: uuid.UUID) -> Contract:
    return Contract(
        id=uuid.uuid4(),
        title="Enterprise SOW Agreement.pdf",
        file_name="sow_agreement.pdf",
        file_size=20480,
        content_type="application/pdf",
        status=ContractStatus.completed,
        org_id=org_id,
        uploaded_by=uuid.uuid4(),
    )


def _make_version(
    contract_id: uuid.UUID, org_id: uuid.UUID, version_number: int = 1
) -> ContractVersion:
    return ContractVersion(
        id=uuid.uuid4(),
        contract_id=contract_id,
        version_number=version_number,
        file_name=f"contract_v{version_number}.pdf",
        file_size=20480,
        content_type="application/pdf",
        storage_key=f"contracts/{org_id}/{contract_id}/v{version_number}/contract.pdf",
        org_id=org_id,
    )


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    mock_session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()


class TestReportsAPI:
    @pytest.mark.asyncio
    async def test_viewer_is_blocked_from_generating_report(
        self,
        async_client: AsyncClient,
    ) -> None:
        """VIEWER receives 403 Forbidden when triggering report generation."""
        user = _make_user(role=UserRole.viewer)
        app.dependency_overrides[get_current_user] = lambda: user

        cid = uuid.uuid4()
        headers = {"Authorization": "Bearer fake.jwt.token"}

        try:
            res = await async_client.post(
                f"/api/v1/contracts/{cid}/reports/generate",
                headers=headers,
            )
            assert res.status_code == 403
            data = res.json()
            assert data["error"]["code"] == "FORBIDDEN"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.asyncio
    async def test_reviewer_can_trigger_async_report_generation(
        self,
        async_client: AsyncClient,
    ) -> None:
        """REVIEWER triggers report generation returning 202 Accepted and queuing Celery task."""
        reviewer = _make_user(role=UserRole.reviewer)
        contract = _make_contract(reviewer.org_id)
        version = _make_version(contract.id, reviewer.org_id, version_number=1)

        app.dependency_overrides[get_current_user] = lambda: reviewer
        headers = {"Authorization": "Bearer fake.jwt.token"}

        created_job = ReportJob(
            id=uuid.uuid4(),
            contract_id=contract.id,
            version_id=version.id,
            org_id=reviewer.org_id,
            status=ReportJobStatus.queued,
        )

        with (
            patch(
                "app.repositories.contract_repo.get_by_id",
                new=AsyncMock(return_value=contract),
            ),
            patch(
                "app.repositories.contract_version_repo.get_latest_by_contract",
                new=AsyncMock(return_value=version),
            ),
            patch(
                "app.repositories.report_job_repo.get_latest_by_contract_and_version",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.repositories.report_job_repo.create",
                new=AsyncMock(return_value=created_job),
            ),
            patch("app.workers.tasks.generate_contract_report_job.delay") as mock_celery,
        ):
            res = await async_client.post(
                f"/api/v1/contracts/{contract.id}/reports/generate",
                headers=headers,
            )
            assert res.status_code == 202
            data = res.json()
            assert data["status"] == "queued"
            assert data["contract_id"] == str(contract.id)
            assert data["version_id"] == str(version.id)
            mock_celery.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_generation_is_deduplicated(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Triggering generation while a job is already in flight returns the existing
        job without re-dispatching.
        """
        reviewer = _make_user(role=UserRole.reviewer)
        contract = _make_contract(reviewer.org_id)
        version = _make_version(contract.id, reviewer.org_id, version_number=1)

        app.dependency_overrides[get_current_user] = lambda: reviewer
        headers = {"Authorization": "Bearer fake.jwt.token"}

        in_flight_job = ReportJob(
            id=uuid.uuid4(),
            contract_id=contract.id,
            version_id=version.id,
            org_id=reviewer.org_id,
            status=ReportJobStatus.processing,
        )

        with (
            patch(
                "app.repositories.contract_repo.get_by_id",
                new=AsyncMock(return_value=contract),
            ),
            patch(
                "app.repositories.contract_version_repo.get_latest_by_contract",
                new=AsyncMock(return_value=version),
            ),
            patch(
                "app.repositories.report_job_repo.get_latest_by_contract_and_version",
                new=AsyncMock(return_value=in_flight_job),
            ),
            patch("app.workers.tasks.generate_contract_report_job.delay") as mock_celery,
        ):
            res = await async_client.post(
                f"/api/v1/contracts/{contract.id}/reports/generate",
                headers=headers,
            )
            assert res.status_code == 202
            data = res.json()
            assert data["job_id"] == str(in_flight_job.id)
            assert data["status"] == "processing"
            # Should not dispatch a duplicate task
            mock_celery.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_latest_report_status_accessible_to_all_roles(
        self,
        async_client: AsyncClient,
    ) -> None:
        """All authenticated roles (including VIEWER) can check report status."""
        viewer = _make_user(role=UserRole.viewer)
        contract = _make_contract(viewer.org_id)
        version = _make_version(contract.id, viewer.org_id)

        app.dependency_overrides[get_current_user] = lambda: viewer
        headers = {"Authorization": "Bearer fake.jwt.token"}

        completed_job = ReportJob(
            id=uuid.uuid4(),
            contract_id=contract.id,
            version_id=version.id,
            org_id=viewer.org_id,
            status=ReportJobStatus.completed,
            storage_key=f"contracts/{viewer.org_id}/{contract.id}/reports/report.pdf",
            file_size=4096,
        )

        with (
            patch(
                "app.repositories.contract_repo.get_by_id",
                new=AsyncMock(return_value=contract),
            ),
            patch(
                "app.repositories.contract_version_repo.get_latest_by_contract",
                new=AsyncMock(return_value=version),
            ),
            patch(
                "app.repositories.report_job_repo.get_latest_by_contract_and_version",
                new=AsyncMock(return_value=completed_job),
            ),
        ):
            res = await async_client.get(
                f"/api/v1/contracts/{contract.id}/reports/latest",
                headers=headers,
            )
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "completed"
            assert "download" in data["download_url"]

    @pytest.mark.asyncio
    async def test_download_report_streams_pdf_file(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Downloading report streams the file bytes with attachment disposition."""
        viewer = _make_user(role=UserRole.viewer)
        contract = _make_contract(viewer.org_id)
        version = _make_version(contract.id, viewer.org_id)

        app.dependency_overrides[get_current_user] = lambda: viewer
        headers = {"Authorization": "Bearer fake.jwt.token"}

        completed_job = ReportJob(
            id=uuid.uuid4(),
            contract_id=contract.id,
            version_id=version.id,
            org_id=viewer.org_id,
            status=ReportJobStatus.completed,
            storage_key="contracts/some_key.pdf",
        )

        fake_pdf_content = b"%PDF-1.4 Fake PDF stream bytes %%EOF"

        with (
            patch(
                "app.repositories.contract_repo.get_by_id",
                new=AsyncMock(return_value=contract),
            ),
            patch(
                "app.repositories.contract_version_repo.get_latest_by_contract",
                new=AsyncMock(return_value=version),
            ),
            patch(
                "app.repositories.report_job_repo.get_latest_by_contract_and_version",
                new=AsyncMock(return_value=completed_job),
            ),
            patch(
                "app.services.storage_service.download_file",
                return_value=fake_pdf_content,
            ),
        ):
            res = await async_client.get(
                f"/api/v1/contracts/{contract.id}/reports/download",
                headers=headers,
            )
            assert res.status_code == 200
            assert res.headers["content-type"] == "application/pdf"
            assert "attachment;" in res.headers["content-disposition"]
            assert res.content == fake_pdf_content
