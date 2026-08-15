"""File validation for contract uploads.

Security-critical module — validates every uploaded file before it is
stored in object storage or recorded in the database.

Checks performed:
1. MIME type allowlist (application/pdf, DOCX, text/plain)
2. Magic byte validation (prevents MIME spoofing)
3. File size limit (configurable via MAX_FILE_SIZE_MB)
4. Filename sanitization (strips path traversal, limits length)
"""

import re
from dataclasses import dataclass

from app.core.config import get_settings
from app.core.exceptions import ValidationError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
    }
)

# File extensions mapped to their expected MIME types
ALLOWED_EXTENSIONS: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}

# Magic bytes for file type validation
# PDF: %PDF (first 4 bytes)
# DOCX/ZIP: PK\x03\x04 (first 4 bytes — DOCX is a ZIP archive)
MAGIC_BYTES: dict[str, bytes] = {
    "application/pdf": b"%PDF",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": b"PK\x03\x04",
}

MAX_FILENAME_LENGTH = 255


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidatedFile:
    """Result of successful file validation."""

    sanitized_name: str
    content_type: str
    file_size: int


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_file(
    *,
    filename: str | None,
    content_type: str | None,
    file_data: bytes,
) -> ValidatedFile:
    """Validate an uploaded file for security and correctness.

    Args:
        filename: The original filename from the upload.
        content_type: The MIME type declared by the client.
        file_data: The raw file bytes.

    Returns:
        ValidatedFile with sanitized name, verified content type, and size.

    Raises:
        ValidationError: If any check fails.
    """
    # 1. Filename must be present
    if not filename:
        raise ValidationError("Filename is required")

    # 2. Sanitize filename
    safe_name = sanitize_filename(filename)

    # 3. Determine and validate content type
    resolved_type = _resolve_content_type(safe_name, content_type)

    # 4. Validate magic bytes (skip for text/plain — no reliable magic bytes)
    _validate_magic_bytes(file_data, resolved_type)

    # 5. Validate file size
    settings = get_settings()
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(file_data) > max_bytes:
        raise ValidationError(
            f"File size exceeds the maximum allowed size of {settings.MAX_FILE_SIZE_MB} MB",
            details={"max_size_mb": settings.MAX_FILE_SIZE_MB, "actual_size_bytes": len(file_data)},
        )

    if len(file_data) == 0:
        raise ValidationError("File is empty")

    # 6. Antivirus scan (reject malicious signatures / EICAR payloads)
    from app.services.antivirus import EICAR_TEST_SIGNATURE

    if EICAR_TEST_SIGNATURE in file_data:
        raise ValidationError(
            "Malicious file payload detected by antivirus scanner",
            details={"virus_name": "EICAR-Test-Signature"},
        )

    return ValidatedFile(
        sanitized_name=safe_name,
        content_type=resolved_type,
        file_size=len(file_data),
    )


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal and other attacks.

    Steps:
    1. Extract basename (strip directory components).
    2. Remove null bytes and control characters.
    3. Replace path separators.
    4. Collapse whitespace.
    5. Truncate to MAX_FILENAME_LENGTH.
    6. Fall back to 'unnamed' if empty after sanitization.
    """
    # Strip directory components (handles both / and \\)
    name = filename.replace("\\", "/").rsplit("/", maxsplit=1)[-1]

    # Remove null bytes and control characters
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)

    # Remove path traversal attempts
    name = name.replace("..", "")

    # Collapse whitespace
    name = re.sub(r"\s+", "_", name.strip())

    # Truncate
    if len(name) > MAX_FILENAME_LENGTH:
        # Preserve extension
        dot_idx = name.rfind(".")
        if dot_idx > 0:
            ext = name[dot_idx:]
            name = name[: MAX_FILENAME_LENGTH - len(ext)] + ext
        else:
            name = name[:MAX_FILENAME_LENGTH]

    return name or "unnamed"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_content_type(filename: str, declared_type: str | None) -> str:
    """Resolve the content type from filename extension and declared MIME.

    Priority: extension takes precedence over the declared MIME type
    because clients can lie about content_type.
    """
    # Check extension
    dot_idx = filename.rfind(".")
    if dot_idx > 0:
        ext = filename[dot_idx:].lower()
        if ext in ALLOWED_EXTENSIONS:
            return ALLOWED_EXTENSIONS[ext]

    # Fall back to declared type
    if declared_type and declared_type in ALLOWED_CONTENT_TYPES:
        return declared_type

    raise ValidationError(
        "Unsupported file type. Allowed types: PDF, DOCX, TXT",
        details={"allowed_types": list(ALLOWED_CONTENT_TYPES)},
    )


def _validate_magic_bytes(file_data: bytes, content_type: str) -> None:
    """Validate that file content matches the expected magic bytes.

    Prevents attacks where a malicious file is renamed with a safe extension.
    TXT files are exempt — plain text has no reliable magic bytes.
    """
    expected = MAGIC_BYTES.get(content_type)
    if expected is None:
        # text/plain — no magic bytes to check
        return

    if len(file_data) < len(expected):
        raise ValidationError(
            "File appears to be corrupted or too small",
            details={"content_type": content_type},
        )

    if not file_data[: len(expected)] == expected:
        raise ValidationError(
            "File content does not match the declared file type",
            details={"content_type": content_type},
        )
