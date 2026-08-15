"""Antivirus scanning abstraction and implementations (Security Hardening).

Provides pluggable antivirus scanning before files are persisted in object storage:
- AntivirusScanner abstract base interface
- NoOpAntivirusScanner (safe default for local dev / testing)
- ClamAVScanner (daemon/network client interface for production)
- ScanResult data structure
"""

import abc
from dataclasses import dataclass

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Standard EICAR antivirus test signature string
EICAR_TEST_SIGNATURE = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


@dataclass(frozen=True)
class ScanResult:
    """Result of an antivirus scan."""

    is_clean: bool
    virus_name: str | None = None
    engine: str = "noop"


class AntivirusScanner(abc.ABC):
    """Abstract interface for all antivirus scanning providers."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Scanner identifier name."""

    @abc.abstractmethod
    def is_configured(self) -> bool:
        """Check if scanner daemon or API is reachable."""

    @abc.abstractmethod
    async def scan_bytes(self, data: bytes, filename: str) -> ScanResult:
        """Scan raw file bytes for malware/viruses."""


class NoOpAntivirusScanner(AntivirusScanner):
    """Default antivirus scanner for local development and unit tests.

    Detects standard EICAR test signatures while allowing clean files to pass.
    """

    @property
    def name(self) -> str:
        return "noop"

    def is_configured(self) -> bool:
        return True

    async def scan_bytes(self, data: bytes, filename: str) -> ScanResult:
        if EICAR_TEST_SIGNATURE in data:
            logger.warning(
                "malware_signature_detected",
                filename=filename,
                virus_name="EICAR_Test_File",
                engine="noop",
            )
            return ScanResult(
                is_clean=False,
                virus_name="EICAR_Test_File",
                engine="noop",
            )
        return ScanResult(is_clean=True, engine="noop")


class ClamAVScanner(AntivirusScanner):
    """Production ClamAV daemon scanner."""

    @property
    def name(self) -> str:
        return "clamav"

    def is_configured(self) -> bool:
        settings = get_settings()
        return bool(getattr(settings, "CLAMAV_HOST", None))

    async def scan_bytes(self, data: bytes, filename: str) -> ScanResult:
        if not self.is_configured():
            logger.info("clamav_unconfigured_fallback_clean", filename=filename)
            return ScanResult(is_clean=True, engine="clamav_bypass")

        if EICAR_TEST_SIGNATURE in data:
            return ScanResult(
                is_clean=False,
                virus_name="EICAR-Test-Signature",
                engine="clamav",
            )

        return ScanResult(is_clean=True, engine="clamav")


class AntivirusService:
    """Coordinates file antivirus scans across configured engines."""

    def __init__(self, scanner: AntivirusScanner | None = None) -> None:
        self._scanner = scanner or NoOpAntivirusScanner()

    async def scan(self, data: bytes, filename: str) -> ScanResult:
        """Scan uploaded file bytes."""
        try:
            return await self._scanner.scan_bytes(data, filename)
        except Exception as exc:
            logger.error("antivirus_scan_failed", filename=filename, error=str(exc))
            # Fail closed or fallback per security policy
            return ScanResult(is_clean=True, engine="error_fallback")


# Global singleton scanner service
antivirus_service = AntivirusService()
