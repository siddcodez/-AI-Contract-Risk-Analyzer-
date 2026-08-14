"""Tests for structured logging system and context correlation."""

import logging
from unittest.mock import patch

from app.core.config import get_settings
from app.core.logging import (
    _inject_context_vars,
    _sanitize_sensitive_data,
    clear_correlation_context,
    configure_logging,
    generate_request_id,
    get_logger,
    reset_correlation_context,
    set_correlation_context,
)


def test_generate_request_id() -> None:
    req_id = generate_request_id()
    assert isinstance(req_id, str)
    assert len(req_id) == 36


def test_correlation_context_lifecycle() -> None:
    clear_correlation_context()

    tokens = set_correlation_context(
        request_id="req-123",
        org_id="org-456",
        user_id="user-789",
        contract_id="contract-abc",
        job_id="job-def",
        analysis_job_id="ajob-ghi",
    )

    event_dict: dict[str, str] = {}
    event_dict = _inject_context_vars(None, "info", event_dict)

    assert event_dict["request_id"] == "req-123"
    assert event_dict["org_id"] == "org-456"
    assert event_dict["organization_id"] == "org-456"
    assert event_dict["user_id"] == "user-789"
    assert event_dict["contract_id"] == "contract-abc"
    assert event_dict["job_id"] == "job-def"
    assert event_dict["analysis_job_id"] == "ajob-ghi"

    reset_correlation_context(tokens)

    event_dict_reset: dict[str, str] = {}
    event_dict_reset = _inject_context_vars(None, "info", event_dict_reset)
    assert "request_id" not in event_dict_reset


def test_sanitize_sensitive_data() -> None:
    event_dict = {
        "event": "user_login",
        "password": "supersecretpassword",
        "jwt": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "api_key": "sk-1234567890",
        "contract_text": "CONFIDENTIAL AGREEMENT TEXT",
        "safe_field": "public_data",
    }

    sanitized = _sanitize_sensitive_data(None, "info", event_dict)

    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["jwt"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["contract_text"] == "[REDACTED]"
    assert sanitized["safe_field"] == "public_data"


def test_configure_logging_dev_mode() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    with (
        patch.object(settings, "ENVIRONMENT", "development"),
        patch.object(settings, "LOG_LEVEL", "INFO"),
    ):
        configure_logging()
        logger = get_logger("test.logger")
        assert logger is not None
        assert logging.getLogger().level == logging.INFO


def test_configure_logging_production_mode() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    with (
        patch.object(settings, "ENVIRONMENT", "production"),
        patch.object(settings, "LOG_LEVEL", "INFO"),
    ):
        configure_logging()
        logger = get_logger("test.prod.logger")
        assert logger is not None
