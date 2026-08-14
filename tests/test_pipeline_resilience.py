"""Tests for Celery task failure resilience, retry behavior, and idempotency."""

from typing import Any
from unittest.mock import MagicMock, patch

from app.core.exceptions import StorageError, ValidationError
from app.services.document_extractor import DocumentExtractionError
from app.workers.tasks import analyze_contract_job, process_contract_job


def _mock_asyncio_run_error(exc: Exception) -> Any:
    def _side_effect(coro: Any) -> Any:
        if hasattr(coro, "close"):
            coro.close()
        raise exc

    return _side_effect


def test_process_contract_job_transient_error_retries() -> None:
    mock_retry = MagicMock(side_effect=Exception("CeleryRetryCalled"))

    with (
        patch.object(process_contract_job, "retry", mock_retry),
        patch(
            "app.workers.tasks.asyncio.run",
            side_effect=_mock_asyncio_run_error(StorageError("MinIO socket timeout")),
        ),
    ):
        try:
            process_contract_job("00000000-0000-0000-0000-000000000001", request_id="req-r1")
        except Exception as exc:
            assert "CeleryRetryCalled" in str(exc)

    mock_retry.assert_called_once()


def test_process_contract_job_permanent_extraction_error_no_retry() -> None:
    mock_retry = MagicMock()

    with (
        patch.object(process_contract_job, "retry", mock_retry),
        patch(
            "app.workers.tasks.asyncio.run",
            side_effect=_mock_asyncio_run_error(DocumentExtractionError("Encrypted PDF")),
        ),
    ):
        res = process_contract_job("00000000-0000-0000-0000-000000000002", request_id="req-r2")

    assert res["status"] == "failed"
    assert "Encrypted PDF" in res["error"]
    assert not mock_retry.called


def test_process_contract_job_permanent_validation_error_no_retry() -> None:
    mock_retry = MagicMock()

    with (
        patch.object(process_contract_job, "retry", mock_retry),
        patch(
            "app.workers.tasks.asyncio.run",
            side_effect=_mock_asyncio_run_error(ValidationError("Corrupted DOCX format")),
        ),
    ):
        res = process_contract_job("00000000-0000-0000-0000-000000000003", request_id="req-r3")

    assert res["status"] == "failed"
    assert "Corrupted DOCX" in res["error"]
    assert not mock_retry.called


def test_analyze_contract_job_transient_error_retries() -> None:
    mock_retry = MagicMock(side_effect=Exception("CeleryRetryCalled"))

    with (
        patch.object(analyze_contract_job, "retry", mock_retry),
        patch(
            "app.workers.tasks.asyncio.run",
            side_effect=_mock_asyncio_run_error(ConnectionError("Redis connection lost")),
        ),
    ):
        try:
            analyze_contract_job("00000000-0000-0000-0000-000000000004", request_id="req-r4")
        except Exception as exc:
            assert "CeleryRetryCalled" in str(exc)

    mock_retry.assert_called_once()
