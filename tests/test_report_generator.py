"""Unit tests for Contract PDF Report generation and assembly (Phase 12)."""

import io
import uuid

from app.services.report_generator import create_annotated_contract_pdf
from pypdf import PdfReader


def test_pdf_report_generation_and_assembly_structure() -> None:
    """Verify that create_annotated_contract_pdf produces a compliant PDF document.

    Checks:
    - Valid PDF binary structure parseable by pypdf
    - Correct page count
    - Embedded metadata and findings representation
    """
    findings = [
        {
            "category": "indemnification",
            "severity": "critical",
            "title": "Broad Uncapped Indemnity",
            "description": "Vendor indemnifies customer with zero limitation.",
            "evidence": "Vendor shall defend and hold harmless against all losses.",
            "recommendation": "Cap indemnification to direct damages under SOW.",
            "status": "approved",
        },
        {
            "category": "liability",
            "severity": "high",
            "title": "Unilateral Liability Carveout",
            "description": "Customer liability capped, vendor uncapped.",
            "evidence": "In no event shall customer liability exceed $100.",
            "recommendation": "Make liability cap mutual.",
            "status": "pending_review",
        },
    ]

    missing = [
        {
            "clause_type": "data_protection",
            "confidence": 0.94,
            "reason": "No GDPR compliance terms found in document.",
        }
    ]

    reviews = [
        {
            "action": "approved",
            "comment": "Reviewed by lead counsel.",
        }
    ]

    pdf_bytes = create_annotated_contract_pdf(
        contract_title="Master Software Licensing Agreement.pdf",
        file_name="msla_v2.pdf",
        version_number=2,
        risk_score=75,
        findings=findings,
        missing_clauses=missing,
        reviews=reviews,
        org_id=str(uuid.uuid4()),
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert pdf_bytes.rstrip().endswith(b"%%EOF")

    # Parse with pypdf to verify internal PDF integrity
    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1

    # Extract text from first page and check key content markers
    page_text = reader.pages[0].extract_text()
    assert "CONTRACTIQ" in page_text
    assert "RISK ANALYSIS REPORT" in page_text
    assert "CONFIDENTIAL" in page_text


def test_pdf_report_generation_clean_contract_empty_sections() -> None:
    """Verify that create_annotated_contract_pdf handles empty findings, empty missing
    clauses, and empty reviews gracefully without crashing or producing a malformed PDF.
    """
    pdf_bytes = create_annotated_contract_pdf(
        contract_title="Clean Standard Non-Disclosure Agreement.pdf",
        file_name="clean_nda.pdf",
        version_number=1,
        risk_score=0,
        findings=[],
        missing_clauses=[],
        reviews=[],
        org_id=str(uuid.uuid4()),
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert pdf_bytes.rstrip().endswith(b"%%EOF")

    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) == 1

    page_text = reader.pages[0].extract_text()
    assert "CONTRACTIQ" in page_text
    assert "Clean Standard Non-Disclosure Agreement" in page_text
    assert "No risk anomalies detected." in page_text
    assert "All standard required clauses detected." in page_text
