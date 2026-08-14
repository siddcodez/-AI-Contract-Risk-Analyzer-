"""Tests for pipeline observability events and log event verification."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.models.user import User
from app.services.file_validator import ValidatedFile


@pytest.mark.asyncio
async def test_upload_observability_events() -> None:
    from app.services import contract_service

    mock_user = MagicMock(spec=User)
    mock_user.id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    mock_user.org_id = uuid.UUID("00000000-0000-0000-0000-000000000002")

    mock_validated = ValidatedFile(
        sanitized_name="test_contract.txt",
        file_size=100,
        content_type="text/plain",
    )

    mock_session = AsyncMock()

    with (
        patch("app.services.storage_service.upload_file"),
        patch("app.repositories.contract_repo.create", new_callable=AsyncMock) as mock_c_create,
        patch("app.repositories.contract_version_repo.create", new_callable=AsyncMock),
        patch(
            "app.repositories.processing_job_repo.create", new_callable=AsyncMock
        ) as mock_j_create,
        patch("app.services.contract_service.logger.info") as mock_log,
    ):
        mock_c = MagicMock()
        mock_c.id = uuid.UUID("00000000-0000-0000-0000-000000000003")
        mock_c_create.return_value = mock_c

        mock_j = MagicMock()
        mock_j.id = uuid.UUID("00000000-0000-0000-0000-000000000004")
        mock_j.status.value = "queued"
        mock_j_create.return_value = mock_j

        res = await contract_service.upload_contract(
            mock_session,
            user=mock_user,
            file_data=b"Sample contract text content",
            validated=mock_validated,
        )

        assert res.job_id == mock_j.id

        # Verify event log calls
        event_names = [call.args[0] for call in mock_log.call_args_list if call.args]
        assert "upload_started" in event_names
        assert "upload_stored" in event_names
        assert "upload_completed" in event_names
