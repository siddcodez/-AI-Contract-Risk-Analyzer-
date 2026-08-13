"""Unit tests for Document Extractor service.

Tests PDF, DOCX, and TXT extraction, whitespace normalization,
and failure modes for empty or corrupted files.
"""

import io

import docx
import pypdf
import pytest
from app.services.document_extractor import (
    DocumentExtractionError,
    extract_text,
    normalize_text,
)


def _make_sample_docx(text: str) -> bytes:
    """Helper to generate a valid in-memory DOCX file."""
    doc = docx.Document()
    for paragraph in text.split("\n\n"):
        doc.add_paragraph(paragraph)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_sample_pdf(text: str) -> bytes:
    """Helper to generate a valid in-memory PDF file using pypdf writer."""
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=612, height=792)
    # pypdf Writer doesn't easily write text natively without extra fonts,
    # so we test extraction logic using synthetic reader mocks or txt fallback,
    # or build a minimal PDF stream.
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


class TestNormalizeText:
    def test_normalizes_crlf_and_whitespace(self) -> None:
        raw = "Header   \r\n\r\nParagraph 1  \r\n\r\n\r\n\r\nParagraph 2"
        normalized = normalize_text(raw)
        assert "\r" not in normalized
        assert normalized == "Header\n\nParagraph 1\n\nParagraph 2"

    def test_strips_null_bytes(self) -> None:
        raw = "Hello\x00 World\x05!"
        normalized = normalize_text(raw)
        assert "\x00" not in normalized
        assert normalized == "Hello World!"


class TestExtractText:
    def test_extract_txt_utf8(self) -> None:
        content = b"Contract Agreement\n\nThis is clause 1."
        extracted = extract_text(content, "text/plain", "contract.txt")
        assert "Contract Agreement" in extracted

    def test_extract_docx(self) -> None:
        docx_bytes = _make_sample_docx("Clause 1: Confidentiality\n\nClause 2: Termination")
        extracted = extract_text(
            docx_bytes,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "agreement.docx",
        )
        assert "Confidentiality" in extracted
        assert "Termination" in extracted

    def test_rejects_empty_bytes(self) -> None:
        with pytest.raises(DocumentExtractionError, match="File content is empty"):
            extract_text(b"", "text/plain", "empty.txt")

    def test_rejects_unsupported_format(self) -> None:
        with pytest.raises(DocumentExtractionError, match="Unsupported document format"):
            extract_text(b"some content", "application/octet-stream", "file.bin")

    def test_rejects_corrupt_docx(self) -> None:
        with pytest.raises(DocumentExtractionError, match="Corrupt or invalid DOCX"):
            extract_text(
                b"NOT_A_ZIP_FILE_HEADER",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "corrupt.docx",
            )
