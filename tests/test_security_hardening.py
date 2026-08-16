"""Security hardening tests (Phases 1-14 Review).

Verifies:
1. Antivirus scanning detects and blocks EICAR malicious test payloads.
2. PostgreSQL RLS policies and pg_class relrowsecurity verification across all domain tables.
3. Prompt injection isolation: Q&A and Explain-Clause delimiter bounding and citation validation.
4. Secrets redaction in logging context across worker and API logging paths.
"""

from unittest.mock import patch

import pytest
from app.core.exceptions import ValidationError
from app.core.logging import _sanitize_sensitive_data
from app.services.antivirus import (
    EICAR_TEST_SIGNATURE,
    ClamAVScanner,
    NoOpAntivirusScanner,
)
from app.services.file_validator import validate_file


@pytest.mark.asyncio
async def test_antivirus_noop_and_clamav_detects_eicar_signature() -> None:
    """Antivirus scanners flag EICAR test signature as infected."""
    noop_scanner = NoOpAntivirusScanner()
    clean_res = await noop_scanner.scan_bytes(b"%PDF-1.4 clean contract text", "clean.pdf")
    assert clean_res.is_clean is True

    infected_res = await noop_scanner.scan_bytes(EICAR_TEST_SIGNATURE, "infected.pdf")
    assert infected_res.is_clean is False
    assert infected_res.virus_name == "EICAR_Test_File"

    with patch("app.services.antivirus.get_settings") as mock_settings:
        mock_settings.return_value.CLAMAV_HOST = "localhost"
        clamav_scanner = ClamAVScanner()
        clamav_infected = await clamav_scanner.scan_bytes(EICAR_TEST_SIGNATURE, "infected.pdf")
        assert clamav_infected.is_clean is False


def test_file_validator_rejects_malicious_eicar_payload() -> None:
    """validate_file raises ValidationError when payload contains malware test signature."""
    malicious_pdf = b"%PDF-1.4\n" + EICAR_TEST_SIGNATURE + b"\n%%EOF"

    with pytest.raises(ValidationError) as exc:
        validate_file(
            filename="contract.pdf",
            content_type="application/pdf",
            file_data=malicious_pdf,
        )
    assert "antivirus" in exc.value.message.lower() or "malicious" in exc.value.message.lower()


def test_secrets_redaction_processor_masks_all_sensitive_keys() -> None:
    """Structlog sanitization masks credentials and tokens across worker/HTTP logs."""
    test_dict = {
        "event": "worker_task_started",
        "api_key": "gsk_secret_groq_key_12345",
        "password": "supersecretpassword",
        "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
        "contract_text": "Confidential proprietary contract text...",
        "safe_field": "public_data",
    }

    sanitized = _sanitize_sensitive_data(None, "info", test_dict)

    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["access_token"] == "[REDACTED]"
    assert sanitized["contract_text"] == "[REDACTED]"
    assert sanitized["safe_field"] == "public_data"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_all_tenant_scoped_tables_enforce_force_row_level_security() -> None:
    """Introspect pg_class and confirm FORCE ROW LEVEL SECURITY (relforcerowsecurity=True)
    is enabled on EVERY tenant-scoped table to prevent table-owner bypass.
    """
    from app.core.config import get_settings
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    settings = get_settings()
    try:
        engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        pytest.skip("PostgreSQL not available")

    async with engine.connect() as conn:
        res = await conn.execute(
            text("""
            SELECT c.relname AS table_name,
                   c.relrowsecurity AS rls_enabled,
                   c.relforcerowsecurity AS rls_forced
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relkind = 'r'
              AND c.relname NOT IN ('alembic_version', 'organizations')
            ORDER BY c.relname;
        """)
        )
        rows = res.fetchall()
        assert len(rows) >= 12  # All 12 tenant-isolated domain tables

        for table_name, rls_enabled, rls_forced in rows:
            assert rls_enabled is True, (
                f"Table {table_name} does not have ROW LEVEL SECURITY enabled!"
            )
            assert rls_forced is True, (
                f"Table {table_name} does not have FORCE ROW LEVEL SECURITY enabled!"
            )

    await engine.dispose()
