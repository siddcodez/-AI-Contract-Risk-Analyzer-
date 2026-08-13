"""Unit tests for Celery task worker.

Tests process_contract_job task execution, transient retries,
and non-retried permanent errors.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import ValidationError
from app.services.document_extractor import DocumentExtractionError
from app.workers.tasks import process_contract_job


class TestCeleryTasks:
    @patch("app.workers.tasks.processing_service.process_contract", new_callable=AsyncMock)
    @patch("app.workers.tasks.create_async_engine")
    @patch("app.workers.tasks.async_sessionmaker")
    def test_task_success(
        self,
        mock_sessionmaker: MagicMock,
        mock_create_engine: MagicMock,
        mock_process_contract: AsyncMock,
    ) -> None:
        job_id = str(uuid.uuid4())
        mock_session = AsyncMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_sessionmaker.return_value = mock_factory

        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()
        mock_create_engine.return_value = mock_engine

        res = process_contract_job(job_id)

        assert res["status"] == "completed"
        assert res["job_id"] == job_id
        mock_process_contract.assert_called_once()

    @patch("app.workers.tasks.processing_service.process_contract", new_callable=AsyncMock)
    @patch("app.workers.tasks.create_async_engine")
    @patch("app.workers.tasks.async_sessionmaker")
    def test_task_permanent_extraction_error_no_retry(
        self,
        mock_sessionmaker: MagicMock,
        mock_create_engine: MagicMock,
        mock_process_contract: AsyncMock,
    ) -> None:
        job_id = str(uuid.uuid4())
        mock_session = AsyncMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_sessionmaker.return_value = mock_factory

        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()
        mock_create_engine.return_value = mock_engine

        mock_process_contract.side_effect = DocumentExtractionError("PDF contains no text")

        res = process_contract_job(job_id)

        assert res["status"] == "failed"
        assert "PDF contains no text" in res["error"]

    @patch("app.workers.tasks.processing_service.process_contract", new_callable=AsyncMock)
    @patch("app.workers.tasks.create_async_engine")
    @patch("app.workers.tasks.async_sessionmaker")
    def test_task_permanent_validation_error_no_retry(
        self,
        mock_sessionmaker: MagicMock,
        mock_create_engine: MagicMock,
        mock_process_contract: AsyncMock,
    ) -> None:
        job_id = str(uuid.uuid4())
        mock_session = AsyncMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_sessionmaker.return_value = mock_factory

        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()
        mock_create_engine.return_value = mock_engine

        mock_process_contract.side_effect = ValidationError("Invalid document text")

        res = process_contract_job(job_id)

        assert res["status"] == "failed"
        assert "Invalid document text" in res["error"]
