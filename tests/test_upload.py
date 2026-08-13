"""Unit tests for contract upload and management endpoints (M2).

Tests the upload, list, details, and status endpoints via the async
HTTP client.  All database and storage operations are mocked.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.security import create_access_token
from app.models.user import User, UserRole
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_user(
    role: UserRole = UserRole.reviewer,
) -> User:
    """Create a fake User object for dependency injection."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        password_hash="fakehash",
        full_name="Test User",
        role=role,
        org_id=uuid.uuid4(),
        is_active=True,
    )
    # Set timestamps that would normally come from the server
    object.__setattr__(user, "created_at", datetime.now(UTC))
    object.__setattr__(user, "updated_at", datetime.now(UTC))
    return user


def _make_token(user: User) -> str:
    """Create a valid JWT for the given user."""
    return create_access_token(
        user_id=str(user.id),
        org_id=str(user.org_id),
        role=user.role.value,
    )


@pytest.fixture
def reviewer_user() -> User:
    return _make_user(UserRole.reviewer)


@pytest.fixture
def admin_user() -> User:
    return _make_user(UserRole.admin)


@pytest.fixture
def viewer_user() -> User:
    return _make_user(UserRole.viewer)


# ---------------------------------------------------------------------------
# Upload endpoint tests
# ---------------------------------------------------------------------------


class TestUploadEndpoint:
    async def test_upload_requires_auth(self, async_client: AsyncClient) -> None:
        """Upload without auth token should return 401."""
        files = {"file": ("contract.txt", b"some contract text content here", "text/plain")}
        response = await async_client.post("/api/v1/contracts/upload", files=files)
        assert response.status_code == 401

    async def test_upload_forbidden_for_viewer(
        self,
        async_client: AsyncClient,
        viewer_user: User,
    ) -> None:
        """Viewers should not be able to upload contracts (403)."""
        from app.api.deps import get_current_user
        from app.main import app

        async def _override() -> User:
            return viewer_user

        app.dependency_overrides[get_current_user] = _override
        try:
            token = _make_token(viewer_user)
            files = {"file": ("contract.txt", b"some contract text", "text/plain")}
            response = await async_client.post(
                "/api/v1/contracts/upload",
                files=files,
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    async def test_upload_rejects_unsupported_file_type(
        self,
        async_client: AsyncClient,
        reviewer_user: User,
    ) -> None:
        """Uploading an unsupported file type should return 422."""
        from app.api.deps import get_current_user, require_reviewer_or_above
        from app.main import app

        async def _override_user() -> User:
            return reviewer_user

        app.dependency_overrides[get_current_user] = _override_user
        app.dependency_overrides[require_reviewer_or_above] = _override_user
        try:
            files = {"file": ("malware.exe", b"\x00" * 100, "application/octet-stream")}
            response = await async_client.post("/api/v1/contracts/upload", files=files)
            assert response.status_code == 422
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(require_reviewer_or_above, None)

    async def test_upload_rejects_empty_file(
        self,
        async_client: AsyncClient,
        reviewer_user: User,
    ) -> None:
        """Uploading an empty file should return 422."""
        from app.api.deps import get_current_user, require_reviewer_or_above
        from app.main import app

        async def _override_user() -> User:
            return reviewer_user

        app.dependency_overrides[get_current_user] = _override_user
        app.dependency_overrides[require_reviewer_or_above] = _override_user
        try:
            files = {"file": ("empty.txt", b"", "text/plain")}
            response = await async_client.post("/api/v1/contracts/upload", files=files)
            assert response.status_code == 422
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(require_reviewer_or_above, None)

    @patch("app.services.contract_service.storage_service.upload_file")
    async def test_upload_success(
        self,
        mock_upload: MagicMock,
        async_client: AsyncClient,
        reviewer_user: User,
        mock_get_db: AsyncMock,
    ) -> None:
        """Successful upload returns 201 with contract_id and job_id."""
        from app.api.deps import get_current_user, require_reviewer_or_above
        from app.main import app

        async def _override_user() -> User:
            return reviewer_user

        app.dependency_overrides[get_current_user] = _override_user
        app.dependency_overrides[require_reviewer_or_above] = _override_user

        # Mock storage upload
        mock_upload.return_value = "test-key"

        # Mock the repo calls
        contract_id = uuid.uuid4()
        job_id = uuid.uuid4()
        now = datetime.now(UTC)

        mock_contract = MagicMock()
        mock_contract.id = contract_id
        mock_contract.created_at = now

        mock_job = MagicMock()
        mock_job.id = job_id
        mock_job.status = MagicMock()
        mock_job.status.value = "queued"

        with (
            patch(
                "app.services.contract_service.contract_repo.create",
                new_callable=AsyncMock,
                return_value=mock_contract,
            ),
            patch(
                "app.services.contract_service.contract_version_repo.create",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.contract_service.processing_job_repo.create",
                new_callable=AsyncMock,
                return_value=mock_job,
            ),
            patch("app.workers.tasks.process_contract_job.delay") as mock_delay,
        ):
            try:
                files = {
                    "file": ("contract.txt", b"This is a valid contract text file.", "text/plain")
                }
                response = await async_client.post("/api/v1/contracts/upload", files=files)
                assert response.status_code == 201
                data = response.json()
                assert "contract_id" in data
                assert "job_id" in data
                assert data["status"] == "queued"
                assert data["file_name"] == "contract.txt"
                assert data["content_type"] == "text/plain"
                mock_delay.assert_called_once_with(str(job_id))
            finally:
                app.dependency_overrides.pop(get_current_user, None)
                app.dependency_overrides.pop(require_reviewer_or_above, None)


# ---------------------------------------------------------------------------
# List contracts endpoint tests
# ---------------------------------------------------------------------------


class TestListEndpoint:
    async def test_list_requires_auth(self, async_client: AsyncClient) -> None:
        """List without auth should return 401."""
        response = await async_client.get("/api/v1/contracts/list")
        assert response.status_code == 401

    @patch("app.services.contract_service.contract_repo.list_by_org", new_callable=AsyncMock)
    @patch("app.services.contract_service.contract_repo.count_by_org", new_callable=AsyncMock)
    async def test_list_returns_contracts(
        self,
        mock_count: AsyncMock,
        mock_list: AsyncMock,
        async_client: AsyncClient,
        reviewer_user: User,
    ) -> None:
        """Authenticated user gets a list of contracts."""
        from app.api.deps import get_current_user
        from app.main import app

        async def _override_user() -> User:
            return reviewer_user

        app.dependency_overrides[get_current_user] = _override_user

        mock_list.return_value = []
        mock_count.return_value = 0

        try:
            token = _make_token(reviewer_user)
            response = await async_client.get(
                "/api/v1/contracts/list",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert "contracts" in data
            assert data["total"] == 0
            assert data["skip"] == 0
            assert data["limit"] == 20
        finally:
            app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Contract status endpoint tests
# ---------------------------------------------------------------------------


class TestStatusEndpoint:
    async def test_status_requires_auth(self, async_client: AsyncClient) -> None:
        """Status check without auth should return 401."""
        contract_id = uuid.uuid4()
        response = await async_client.get(f"/api/v1/contracts/{contract_id}/status")
        assert response.status_code == 401

    @patch(
        "app.services.contract_service.contract_repo.get_by_id",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.contract_service.processing_job_repo.get_by_contract_id",
        new_callable=AsyncMock,
    )
    async def test_status_returns_contract_and_job(
        self,
        mock_get_job: AsyncMock,
        mock_get_contract: AsyncMock,
        async_client: AsyncClient,
        reviewer_user: User,
    ) -> None:
        """Authenticated user can check contract status."""
        from app.api.deps import get_current_user
        from app.main import app

        async def _override_user() -> User:
            return reviewer_user

        app.dependency_overrides[get_current_user] = _override_user

        contract_id = uuid.uuid4()
        job_id = uuid.uuid4()

        mock_contract = MagicMock()
        mock_contract.id = contract_id
        mock_contract.status = MagicMock()
        mock_contract.status.value = "pending"
        mock_get_contract.return_value = mock_contract

        mock_job = MagicMock()
        mock_job.id = job_id
        mock_job.status = MagicMock()
        mock_job.status.value = "queued"
        mock_job.error_message = None
        mock_get_job.return_value = mock_job

        try:
            token = _make_token(reviewer_user)
            response = await async_client.get(
                f"/api/v1/contracts/{contract_id}/status",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["contract_status"] == "pending"
            assert data["job_status"] == "queued"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch(
        "app.services.contract_service.contract_repo.get_by_id",
        new_callable=AsyncMock,
        return_value=None,
    )
    async def test_status_not_found(
        self,
        mock_get_contract: AsyncMock,
        async_client: AsyncClient,
        reviewer_user: User,
    ) -> None:
        """Status check for non-existent contract returns 404."""
        from app.api.deps import get_current_user
        from app.main import app

        async def _override_user() -> User:
            return reviewer_user

        app.dependency_overrides[get_current_user] = _override_user

        try:
            token = _make_token(reviewer_user)
            contract_id = uuid.uuid4()
            response = await async_client.get(
                f"/api/v1/contracts/{contract_id}/status",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 404
        finally:
            app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Contract details endpoint tests
# ---------------------------------------------------------------------------


class TestDetailsEndpoint:
    async def test_details_requires_auth(self, async_client: AsyncClient) -> None:
        """Details without auth should return 401."""
        contract_id = uuid.uuid4()
        response = await async_client.get(f"/api/v1/contracts/{contract_id}/details")
        assert response.status_code == 401

    @patch(
        "app.services.contract_service.contract_repo.get_by_id",
        new_callable=AsyncMock,
    )
    async def test_details_returns_contract(
        self,
        mock_get: AsyncMock,
        async_client: AsyncClient,
        reviewer_user: User,
    ) -> None:
        """Authenticated user gets contract details."""
        from app.api.deps import get_current_user
        from app.main import app

        async def _override_user() -> User:
            return reviewer_user

        app.dependency_overrides[get_current_user] = _override_user

        contract_id = uuid.uuid4()
        now = datetime.now(UTC)

        mock_contract = MagicMock()
        mock_contract.id = contract_id
        mock_contract.title = "Test Contract"
        mock_contract.file_name = "test.pdf"
        mock_contract.file_size = 12345
        mock_contract.content_type = "application/pdf"
        mock_contract.status = MagicMock()
        mock_contract.status.value = "pending"
        mock_contract.org_id = reviewer_user.org_id
        mock_contract.uploaded_by = reviewer_user.id
        mock_contract.created_at = now
        mock_contract.updated_at = now
        mock_get.return_value = mock_contract

        try:
            token = _make_token(reviewer_user)
            response = await async_client.get(
                f"/api/v1/contracts/{contract_id}/details",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["title"] == "Test Contract"
            assert data["file_name"] == "test.pdf"
            assert data["status"] == "pending"
        finally:
            app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Storage service tests
# ---------------------------------------------------------------------------


class TestStorageService:
    @patch("app.services.storage_service._get_s3_client")
    def test_upload_file_calls_s3(self, mock_client_factory: MagicMock) -> None:
        """upload_file should call upload_fileobj on the S3 client."""
        from app.services import storage_service

        mock_client = MagicMock()
        mock_client_factory.return_value = mock_client

        result = storage_service.upload_file(
            file_data=b"test data",
            key="org/contract/file.txt",
            content_type="text/plain",
        )

        assert result == "org/contract/file.txt"
        mock_client.upload_fileobj.assert_called_once()

    @patch("app.services.storage_service._get_s3_client")
    def test_delete_file_calls_s3(self, mock_client_factory: MagicMock) -> None:
        """delete_file should call delete_object on the S3 client."""
        from app.services import storage_service

        mock_client = MagicMock()
        mock_client_factory.return_value = mock_client

        storage_service.delete_file("org/contract/file.txt")

        mock_client.delete_object.assert_called_once()

    @patch("app.services.storage_service._get_s3_client")
    def test_generate_presigned_url(self, mock_client_factory: MagicMock) -> None:
        """generate_presigned_url should return a URL string."""
        from app.services import storage_service

        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://minio.local/signed-url"
        mock_client_factory.return_value = mock_client

        url = storage_service.generate_presigned_url("org/contract/file.txt")

        assert url == "https://minio.local/signed-url"
        mock_client.generate_presigned_url.assert_called_once()
