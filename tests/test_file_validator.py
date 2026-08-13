"""Unit tests for file validation logic (M2).

Tests the file_validator module in isolation — no database, no storage,
no HTTP layer.  Covers MIME type allowlist, magic byte checking, file
size limits, and filename sanitization.
"""

import pytest
from app.services.file_validator import (
    ALLOWED_CONTENT_TYPES,
    MAX_FILENAME_LENGTH,
    ValidatedFile,
    sanitize_filename,
    validate_file,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Minimal valid PDF header (enough to pass magic-byte check)
PDF_HEADER = b"%PDF-1.4 " + b"x" * 100

# Minimal valid DOCX header (PK zip signature + padding)
DOCX_HEADER = b"PK\x03\x04" + b"x" * 100

# Plain text content
TXT_CONTENT = b"This is a plain text contract for testing purposes."


# ---------------------------------------------------------------------------
# MIME type allowlist
# ---------------------------------------------------------------------------


class TestAllowedTypes:
    def test_pdf_is_allowed(self) -> None:
        assert "application/pdf" in ALLOWED_CONTENT_TYPES

    def test_docx_is_allowed(self) -> None:
        assert (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            in ALLOWED_CONTENT_TYPES
        )

    def test_txt_is_allowed(self) -> None:
        assert "text/plain" in ALLOWED_CONTENT_TYPES

    def test_html_is_not_allowed(self) -> None:
        assert "text/html" not in ALLOWED_CONTENT_TYPES

    def test_exe_is_not_allowed(self) -> None:
        assert "application/octet-stream" not in ALLOWED_CONTENT_TYPES


# ---------------------------------------------------------------------------
# validate_file — happy paths
# ---------------------------------------------------------------------------


class TestValidateFileSuccess:
    def test_validate_pdf(self) -> None:
        result = validate_file(
            filename="contract.pdf",
            content_type="application/pdf",
            file_data=PDF_HEADER,
        )
        assert isinstance(result, ValidatedFile)
        assert result.sanitized_name == "contract.pdf"
        assert result.content_type == "application/pdf"
        assert result.file_size == len(PDF_HEADER)

    def test_validate_docx(self) -> None:
        result = validate_file(
            filename="agreement.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            file_data=DOCX_HEADER,
        )
        assert result.sanitized_name == "agreement.docx"
        assert (
            result.content_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    def test_validate_txt(self) -> None:
        result = validate_file(
            filename="notes.txt",
            content_type="text/plain",
            file_data=TXT_CONTENT,
        )
        assert result.sanitized_name == "notes.txt"
        assert result.content_type == "text/plain"

    def test_extension_overrides_declared_type(self) -> None:
        """Extension takes priority over declared MIME type."""
        result = validate_file(
            filename="contract.pdf",
            content_type="application/octet-stream",  # wrong MIME
            file_data=PDF_HEADER,
        )
        assert result.content_type == "application/pdf"


# ---------------------------------------------------------------------------
# validate_file — rejection cases
# ---------------------------------------------------------------------------


class TestValidateFileRejection:
    def test_reject_missing_filename(self) -> None:
        from app.core.exceptions import ValidationError

        with pytest.raises(ValidationError, match="Filename is required"):
            validate_file(filename=None, content_type="text/plain", file_data=TXT_CONTENT)

    def test_reject_empty_filename(self) -> None:
        from app.core.exceptions import ValidationError

        with pytest.raises(ValidationError, match="Filename is required"):
            validate_file(filename="", content_type="text/plain", file_data=TXT_CONTENT)

    def test_reject_unsupported_extension(self) -> None:
        from app.core.exceptions import ValidationError

        with pytest.raises(ValidationError, match="Unsupported file type"):
            validate_file(
                filename="malware.exe",
                content_type="application/octet-stream",
                file_data=b"\x00" * 100,
            )

    def test_reject_empty_file(self) -> None:
        from app.core.exceptions import ValidationError

        with pytest.raises(ValidationError, match="File is empty"):
            validate_file(filename="contract.txt", content_type="text/plain", file_data=b"")

    def test_reject_bad_magic_bytes_pdf(self) -> None:
        """A .pdf file with non-PDF content should be rejected."""
        from app.core.exceptions import ValidationError

        with pytest.raises(ValidationError, match="does not match"):
            validate_file(
                filename="fake.pdf",
                content_type="application/pdf",
                file_data=b"NOT_A_PDF" + b"x" * 100,
            )

    def test_reject_bad_magic_bytes_docx(self) -> None:
        """A .docx file with non-ZIP content should be rejected."""
        from app.core.exceptions import ValidationError

        with pytest.raises(ValidationError, match="does not match"):
            validate_file(
                filename="fake.docx",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                file_data=b"NOT_A_ZIP" + b"x" * 100,
            )

    def test_reject_oversized_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Files exceeding MAX_FILE_SIZE_MB should be rejected."""
        # Patch settings to use a tiny max size for testing (1 byte)
        from unittest.mock import MagicMock

        from app.core.exceptions import ValidationError

        mock_settings = MagicMock()
        mock_settings.MAX_FILE_SIZE_MB = 0  # effectively 0 bytes

        # We need ge=1 in config, so let's mock to allow 1 MB but test with >1MB
        mock_settings.MAX_FILE_SIZE_MB = 1  # 1 MB
        monkeypatch.setattr("app.services.file_validator.get_settings", lambda: mock_settings)

        # Create a file slightly over 1 MB
        oversized = b"%PDF" + b"x" * (1024 * 1024 + 1)

        with pytest.raises(ValidationError, match="exceeds the maximum"):
            validate_file(
                filename="huge.pdf",
                content_type="application/pdf",
                file_data=oversized,
            )

    def test_reject_truncated_file(self) -> None:
        """A file too small to have valid magic bytes should be rejected."""
        from app.core.exceptions import ValidationError

        with pytest.raises(ValidationError, match="corrupted or too small"):
            validate_file(
                filename="tiny.pdf",
                content_type="application/pdf",
                file_data=b"%P",  # less than 4 bytes
            )


# ---------------------------------------------------------------------------
# sanitize_filename
# ---------------------------------------------------------------------------


class TestSanitizeFilename:
    def test_normal_filename_unchanged(self) -> None:
        assert sanitize_filename("contract.pdf") == "contract.pdf"

    def test_strips_directory_components_unix(self) -> None:
        assert sanitize_filename("/etc/passwd") == "passwd"

    def test_strips_directory_components_windows(self) -> None:
        assert sanitize_filename("C:\\Users\\evil\\malware.exe") == "malware.exe"

    def test_removes_path_traversal(self) -> None:
        result = sanitize_filename("../../etc/passwd.txt")
        assert ".." not in result
        assert result.endswith(".txt")

    def test_removes_null_bytes(self) -> None:
        result = sanitize_filename("contract\x00.pdf")
        assert "\x00" not in result

    def test_collapses_whitespace(self) -> None:
        result = sanitize_filename("my   contract   file.pdf")
        assert "   " not in result
        assert result == "my_contract_file.pdf"

    def test_truncates_long_filename_preserves_extension(self) -> None:
        long_name = "a" * 300 + ".pdf"
        result = sanitize_filename(long_name)
        assert len(result) <= MAX_FILENAME_LENGTH
        assert result.endswith(".pdf")

    def test_empty_filename_becomes_unnamed(self) -> None:
        assert sanitize_filename("") == "unnamed"

    def test_only_dots_becomes_unnamed(self) -> None:
        # ".." is removed, leaving empty string → "unnamed"
        assert sanitize_filename("..") == "unnamed"
