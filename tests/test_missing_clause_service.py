"""Unit and domain tests for MissingClauseService."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from app.models.risk_finding import RiskCategory, RiskFinding, RiskSeverity
from app.services.missing_clause_service import (
    detect_missing_clauses,
    detect_present_clauses_from_text,
    get_expected_clauses,
    normalize_clause_type,
    normalize_contract_type,
)
from sqlalchemy.ext.asyncio import AsyncSession


class TestClauseNormalization:
    """Test clause type and contract type normalization logic."""

    def test_synonym_normalization(self) -> None:
        """Case 5: Canonical synonym normalization."""
        assert normalize_clause_type("indemnity") == "indemnification"
        assert normalize_clause_type("indemnification") == "indemnification"
        assert normalize_clause_type("liability") == "limitation_of_liability"
        assert normalize_clause_type("limitation_of_liability") == "limitation_of_liability"
        assert normalize_clause_type("payment") == "payment_terms"
        assert normalize_clause_type("payment_terms") == "payment_terms"
        assert normalize_clause_type("data_privacy") == "data_protection"
        assert normalize_clause_type("privacy") == "data_protection"
        assert normalize_clause_type("security") == "data_protection"
        assert normalize_clause_type("arbitration") == "dispute_resolution"
        assert normalize_clause_type("nda") == "confidentiality"

    def test_casing_and_whitespace_normalization(self) -> None:
        """Case 6: Casing, hyphens, and whitespace insensitivity."""
        assert normalize_clause_type("  Confidentiality  ") == "confidentiality"
        assert normalize_clause_type("TERMINATION") == "termination"
        assert normalize_clause_type("Non-Compete") == "non_compete"
        assert normalize_clause_type("DATA PROTECTION") == "data_protection"

    def test_contract_type_normalization(self) -> None:
        """Normalized contract types map to expected playbook categories."""
        assert normalize_contract_type("vendor_msa") == "vendor_msa"
        assert normalize_contract_type("Vendor Master Services Agreement") == "vendor_msa"
        assert normalize_contract_type("Non-Disclosure Agreement (NDA)") == "nda"
        assert normalize_contract_type("SaaS Subscription Agreement") == "saas_msa"
        assert normalize_contract_type("Employment Contract") == "employment"
        assert normalize_contract_type("Custom Services Agreement") == "general_commercial"
        assert normalize_contract_type(None) == "general_commercial"

    def test_unknown_clause_type_handled_gracefully(self) -> None:
        """Case 11: Unknown/unrecognized clause types should not crash or misalign."""
        custom_type = "custom_environmental_audit_clause"
        normalized = normalize_clause_type(custom_type)
        assert normalized == "custom_environmental_audit_clause"

        mixed_case_custom = "  Custom Environmental-Audit "
        normalized_mixed = normalize_clause_type(mixed_case_custom)
        assert normalized_mixed == "custom_environmental_audit"

    def test_expected_clauses_resolution(self) -> None:
        """Default expected clauses per contract type."""
        vendor_clauses = get_expected_clauses("vendor_msa")
        assert "confidentiality" in vendor_clauses
        assert "limitation_of_liability" in vendor_clauses
        assert "indemnification" in vendor_clauses
        assert "data_protection" in vendor_clauses

        nda_clauses = get_expected_clauses("nda")
        assert "confidentiality" in nda_clauses
        assert "governing_law" in nda_clauses
        assert "non_compete" not in nda_clauses

    def test_custom_organization_playbook_override(self) -> None:
        """Case 4: Custom organization playbook overrides default expected list."""
        custom_overrides = {
            "vendor_msa": ["confidentiality", "warranty", "insurance"],
        }
        res = get_expected_clauses("vendor_msa", org_overrides=custom_overrides)
        assert res == ["confidentiality", "warranty", "insurance"]


class TestTextPatternClassification:
    """Test text pattern matching for clause types."""

    def test_detects_indemnification_and_liability(self) -> None:
        chunks = [
            "Vendor agrees to defend, indemnify, and hold harmless Client.",
            "In no event shall either party's aggregate liability exceed fees paid.",
        ]
        detected = detect_present_clauses_from_text(chunks)
        assert "indemnification" in detected
        assert "limitation_of_liability" in detected
        assert "confidentiality" not in detected

    def test_detects_data_protection_and_termination(self) -> None:
        chunks = [
            "Each party must comply with applicable data protection laws and GDPR.",
            "Either party may terminate this agreement upon 30 days written notice.",
        ]
        detected = detect_present_clauses_from_text(chunks)
        assert "data_protection" in detected
        assert "termination" in detected


class TestDetectMissingClauses:
    """Domain and orchestration test cases for detect_missing_clauses."""

    @pytest.mark.asyncio
    async def test_empty_document_all_clauses_missing_with_low_confidence(self) -> None:
        """Case 1: Empty document (no chunks/findings) -> all expected missing with 0.50 conf."""
        contract_id = uuid.uuid4()
        version_id = uuid.uuid4()
        org_id = uuid.uuid4()

        session = AsyncMock(spec=AsyncSession)

        with (
            patch(
                "app.services.missing_clause_service.risk_finding_repo.list_by_contract",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.services.missing_clause_service.contract_chunk_repo.list_by_contract",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.services.missing_clause_service.missing_clause_repo.delete_by_contract_and_version",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.missing_clause_service.missing_clause_repo.bulk_create",
                new_callable=AsyncMock,
            ) as mock_bulk_create,
        ):
            await detect_missing_clauses(
                session,
                contract_id=contract_id,
                version_id=version_id,
                org_id=org_id,
                contract_type="nda",
            )
            mock_bulk_create.assert_called_once()
            items = mock_bulk_create.call_args[1]["items"]
            assert len(items) == 4  # NDA expects 4 clauses
            for it in items:
                assert it["confidence"] == 0.50  # unextracted/empty document baseline

    @pytest.mark.asyncio
    async def test_standard_nda_with_full_clauses_returns_zero_missing(self) -> None:
        """Case 2: Standard NDA with all clauses present returns empty list."""
        contract_id = uuid.uuid4()
        version_id = uuid.uuid4()
        org_id = uuid.uuid4()

        mock_findings = [
            RiskFinding(
                id=uuid.uuid4(),
                contract_id=contract_id,
                version_id=version_id,
                org_id=org_id,
                category=RiskCategory.confidentiality,
                severity=RiskSeverity.low,
                title="Confidentiality",
                description="Standard",
                evidence="Keep secret",
                recommendation="",
                confidence=0.9,
            ),
            RiskFinding(
                id=uuid.uuid4(),
                contract_id=contract_id,
                version_id=version_id,
                org_id=org_id,
                category=RiskCategory.termination,
                severity=RiskSeverity.low,
                title="Termination",
                description="30 days",
                evidence="Terminate upon notice",
                recommendation="",
                confidence=0.9,
            ),
            RiskFinding(
                id=uuid.uuid4(),
                contract_id=contract_id,
                version_id=version_id,
                org_id=org_id,
                category=RiskCategory.governing_law,
                severity=RiskSeverity.low,
                title="Governing Law",
                description="Delaware",
                evidence="Delaware laws apply",
                recommendation="",
                confidence=0.9,
            ),
            RiskFinding(
                id=uuid.uuid4(),
                contract_id=contract_id,
                version_id=version_id,
                org_id=org_id,
                category=RiskCategory.dispute_resolution,
                severity=RiskSeverity.low,
                title="Dispute Resolution",
                description="Arbitration",
                evidence="Binding arbitration",
                recommendation="",
                confidence=0.9,
            ),
        ]

        session = AsyncMock(spec=AsyncSession)

        with (
            patch(
                "app.services.missing_clause_service.risk_finding_repo.list_by_contract",
                new_callable=AsyncMock,
                return_value=mock_findings,
            ),
            patch(
                "app.services.missing_clause_service.contract_chunk_repo.list_by_contract",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.services.missing_clause_service.missing_clause_repo.delete_by_contract_and_version",
                new_callable=AsyncMock,
            ) as mock_delete,
            patch(
                "app.services.missing_clause_service.missing_clause_repo.bulk_create",
                new_callable=AsyncMock,
            ) as mock_bulk_create,
        ):
            results = await detect_missing_clauses(
                session,
                contract_id=contract_id,
                version_id=version_id,
                org_id=org_id,
                contract_type="nda",
            )
            assert results == []
            mock_delete.assert_called_once_with(session, contract_id, version_id)
            mock_bulk_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_standard_vendor_msa_missing_data_protection_and_insurance(self) -> None:
        """Case 3: Standard Vendor MSA missing data_protection and insurance."""
        contract_id = uuid.uuid4()
        version_id = uuid.uuid4()
        org_id = uuid.uuid4()

        # Provide all vendor_msa clauses except data_protection and insurance
        present_categories = [
            RiskCategory.confidentiality,
            RiskCategory.liability,
            RiskCategory.indemnification,
            RiskCategory.termination,
            RiskCategory.payment,
            RiskCategory.governing_law,
            RiskCategory.dispute_resolution,
            RiskCategory.other,  # maps to general
        ]
        mock_findings = [
            RiskFinding(
                id=uuid.uuid4(),
                contract_id=contract_id,
                version_id=version_id,
                org_id=org_id,
                category=cat,
                severity=RiskSeverity.low,
                title=f"{cat} finding",
                description="",
                evidence="",
                recommendation="",
                confidence=0.9,
            )
            for cat in present_categories
        ]

        session = AsyncMock(spec=AsyncSession)

        with (
            patch(
                "app.services.missing_clause_service.risk_finding_repo.list_by_contract",
                new_callable=AsyncMock,
                return_value=mock_findings,
            ),
            patch(
                "app.services.missing_clause_service.contract_chunk_repo.list_by_contract",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.services.missing_clause_service.missing_clause_repo.delete_by_contract_and_version",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.missing_clause_service.missing_clause_repo.bulk_create",
                new_callable=AsyncMock,
            ) as mock_bulk_create,
        ):
            await detect_missing_clauses(
                session,
                contract_id=contract_id,
                version_id=version_id,
                org_id=org_id,
                contract_type="vendor_msa",
            )
            call_items = mock_bulk_create.call_args[1]["items"]
            missing_types = {it["clause_type"] for it in call_items}
            assert "data_protection" in missing_types
            assert "insurance" in missing_types

    @pytest.mark.asyncio
    async def test_chunk_presence_determines_confidence_score(self) -> None:
        """Case 7: Chunk presence and classification coverage compute deterministic confidence."""
        contract_id = uuid.uuid4()
        version_id = uuid.uuid4()
        org_id = uuid.uuid4()

        class MockChunk:
            def __init__(self, c_id: uuid.UUID, v_id: uuid.UUID, content: str):
                self.id = c_id
                self.version_id = v_id
                self.content = content

        mock_chunks = [
            MockChunk(uuid.uuid4(), version_id, "Vendor agrees to keep information confidential.")
        ]

        session = AsyncMock(spec=AsyncSession)

        with (
            patch(
                "app.services.missing_clause_service.risk_finding_repo.list_by_contract",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.services.missing_clause_service.contract_chunk_repo.list_by_contract",
                new_callable=AsyncMock,
                return_value=mock_chunks,
            ),
            patch(
                "app.services.missing_clause_service.missing_clause_repo.delete_by_contract_and_version",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.missing_clause_service.missing_clause_repo.bulk_create",
                new_callable=AsyncMock,
            ) as mock_bulk_create,
        ):
            await detect_missing_clauses(
                session,
                contract_id=contract_id,
                version_id=version_id,
                org_id=org_id,
                contract_type="nda",
            )
            items = mock_bulk_create.call_args[1]["items"]
            # With text extracted and partial coverage, confidence should be >= 0.80 and <= 0.95
            for it in items:
                assert 0.80 <= it["confidence"] <= 0.95

    @pytest.mark.asyncio
    async def test_idempotency_repeated_runs_produce_zero_duplicates(self) -> None:
        """Case 8: Repeated execution replaces previous missing clauses without duplicates."""
        contract_id = uuid.uuid4()
        version_id = uuid.uuid4()
        org_id = uuid.uuid4()

        session = AsyncMock(spec=AsyncSession)

        with (
            patch(
                "app.services.missing_clause_service.risk_finding_repo.list_by_contract",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.services.missing_clause_service.contract_chunk_repo.list_by_contract",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.services.missing_clause_service.missing_clause_repo.delete_by_contract_and_version",
                new_callable=AsyncMock,
            ) as mock_delete,
            patch(
                "app.services.missing_clause_service.missing_clause_repo.bulk_create",
                new_callable=AsyncMock,
            ) as mock_bulk_create,
        ):
            # First execution
            await detect_missing_clauses(
                session,
                contract_id=contract_id,
                version_id=version_id,
                org_id=org_id,
                contract_type="nda",
            )
            # Second execution
            await detect_missing_clauses(
                session,
                contract_id=contract_id,
                version_id=version_id,
                org_id=org_id,
                contract_type="nda",
            )

            assert mock_delete.call_count == 2
            mock_delete.assert_called_with(session, contract_id, version_id)
            assert mock_bulk_create.call_count == 2

    @pytest.mark.asyncio
    async def test_version_isolation_findings_do_not_leak_between_versions(self) -> None:
        """Case 9: Findings in version 1 do not alter missing clause computation for version 2."""
        contract_id = uuid.uuid4()
        v1_id = uuid.uuid4()
        v2_id = uuid.uuid4()
        org_id = uuid.uuid4()

        mock_findings = [
            RiskFinding(
                id=uuid.uuid4(),
                contract_id=contract_id,
                version_id=v1_id,
                org_id=org_id,
                category=RiskCategory.confidentiality,
                severity=RiskSeverity.low,
                title="Confidentiality v1",
                description="",
                evidence="",
                recommendation="",
                confidence=0.9,
            ),
        ]

        session = AsyncMock(spec=AsyncSession)

        with (
            patch(
                "app.services.missing_clause_service.risk_finding_repo.list_by_contract",
                new_callable=AsyncMock,
                return_value=mock_findings,
            ),
            patch(
                "app.services.missing_clause_service.contract_chunk_repo.list_by_contract",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.services.missing_clause_service.missing_clause_repo.delete_by_contract_and_version",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.missing_clause_service.missing_clause_repo.bulk_create",
                new_callable=AsyncMock,
            ) as mock_bulk_create,
        ):
            await detect_missing_clauses(
                session,
                contract_id=contract_id,
                version_id=v2_id,
                org_id=org_id,
                contract_type="nda",
            )
            call_items = mock_bulk_create.call_args[1]["items"]
            missing_types = [it["clause_type"] for it in call_items]
            # Since mock_findings was for v1, v2 still sees confidentiality as missing
            assert "confidentiality" in missing_types

    @pytest.mark.asyncio
    async def test_factual_absence_reasoning_without_legal_hallucination(self) -> None:
        """Case 10: Reasons are strictly factual absence descriptions without legal advice."""
        contract_id = uuid.uuid4()
        version_id = uuid.uuid4()
        org_id = uuid.uuid4()

        session = AsyncMock(spec=AsyncSession)

        with (
            patch(
                "app.services.missing_clause_service.risk_finding_repo.list_by_contract",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.services.missing_clause_service.contract_chunk_repo.list_by_contract",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.services.missing_clause_service.missing_clause_repo.delete_by_contract_and_version",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.missing_clause_service.missing_clause_repo.bulk_create",
                new_callable=AsyncMock,
            ) as mock_bulk_create,
        ):
            await detect_missing_clauses(
                session,
                contract_id=contract_id,
                version_id=version_id,
                org_id=org_id,
                contract_type="nda",
            )
            items = mock_bulk_create.call_args[1]["items"]
            for it in items:
                reason = it["reason"]
                assert reason.startswith("No ")
                assert "clause was identified among the classified clauses" in reason
                assert "illegal" not in reason.lower()
                assert "void" not in reason.lower()
                assert "violation" not in reason.lower()
