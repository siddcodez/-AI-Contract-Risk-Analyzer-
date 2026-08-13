"""Document text extraction service for PDF, DOCX, and TXT files.

Extracts plain text from raw file bytes, normalizes whitespace and line breaks,
and raises DocumentExtractionError for corrupt or unreadable files.
"""

import io
import re

import docx
import pypdf

from app.core.exceptions import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)


class DocumentExtractionError(AppError):
    """Raised when text extraction fails for a document."""

    message = "Document extraction failed"
    code = "DOCUMENT_EXTRACTION_ERROR"
    status_code = 422


def extract_text(file_data: bytes, content_type: str, file_name: str) -> str:
    """Extract and normalize plain text from a document.

    Args:
        file_data: Raw bytes of the document.
        content_type: MIME type (application/pdf, DOCX, or text/plain).
        file_name: Original file name for context/logging.

    Returns:
        Normalized plain text extracted from the file.

    Raises:
        DocumentExtractionError: If text extraction fails or yields empty text.
    """
    if not file_data:
        raise DocumentExtractionError("File content is empty", details={"file_name": file_name})

    try:
        if content_type == "application/pdf" or file_name.lower().endswith(".pdf"):
            text = _extract_pdf(file_data, file_name)
        elif (
            content_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or file_name.lower().endswith(".docx")
        ):
            text = _extract_docx(file_data, file_name)
        elif content_type == "text/plain" or file_name.lower().endswith(".txt"):
            text = _extract_txt(file_data)
        else:
            raise DocumentExtractionError(
                f"Unsupported document format: {content_type}",
                details={"file_name": file_name, "content_type": content_type},
            )
    except DocumentExtractionError:
        raise
    except Exception as exc:
        logger.error("Text extraction failed", file_name=file_name, exc_info=exc)
        raise DocumentExtractionError(
            f"Failed to extract text from file: {file_name}",
            details={"file_name": file_name, "error": str(exc)},
        ) from exc

    normalized = normalize_text(text)
    if not normalized.strip():
        raise DocumentExtractionError(
            "Extracted text is empty or contains only whitespace",
            details={"file_name": file_name},
        )

    return normalized


def normalize_text(text: str) -> str:
    """Normalize extracted text.

    Steps:
    1. Remove null bytes and non-printable control characters (except newlines/tabs).
    2. Replace Windows CRLF (\r\n) with Unix LF (\n).
    3. Strip trailing spaces from each line.
    4. Collapse 3+ consecutive newlines into 2 newlines (preserve paragraph gaps).
    """
    # Remove null bytes and ASCII control characters except \t and \n
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Standardize line endings
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")

    # Strip trailing whitespace per line
    lines = [line.rstrip() for line in cleaned.split("\n")]
    cleaned = "\n".join(lines)

    # Collapse excessive blank lines (>2 consecutive \n -> \n\n)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


def _extract_pdf(file_data: bytes, file_name: str) -> str:
    try:
        reader = pypdf.PdfReader(io.BytesIO(file_data))
        pages_text: list[str] = []
        for _i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                pages_text.append(page_text)

        if not pages_text:
            raise DocumentExtractionError(
                "PDF contains no extractable text (image-only or encrypted)",
                details={"file_name": file_name},
            )

        return "\n\n".join(pages_text)
    except DocumentExtractionError:
        raise
    except Exception as exc:
        raise DocumentExtractionError(
            f"Corrupt or invalid PDF file: {file_name}",
            details={"file_name": file_name, "error": str(exc)},
        ) from exc


def _extract_docx(file_data: bytes, file_name: str) -> str:
    try:
        doc = docx.Document(io.BytesIO(file_data))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        if not paragraphs:
            raise DocumentExtractionError(
                "DOCX document contains no text paragraphs",
                details={"file_name": file_name},
            )
        return "\n\n".join(paragraphs)
    except DocumentExtractionError:
        raise
    except Exception as exc:
        raise DocumentExtractionError(
            f"Corrupt or invalid DOCX file: {file_name}",
            details={"file_name": file_name, "error": str(exc)},
        ) from exc


def _extract_txt(file_data: bytes) -> str:
    try:
        return file_data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return file_data.decode("latin-1")
        except Exception as exc:
            raise DocumentExtractionError(
                "Failed to decode text file using UTF-8 or Latin-1",
                details={"error": str(exc)},
            ) from exc
