"""Unit and domain tests for MissingClauseService."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.missing_clause import MissingClause
from app.models.risk_finding import RiskCategory, RiskFinding, RiskSeverity
from app.services.missing_clause_service import (
    CANONICAL_CLAUSE_TYPES,
    DEFAULT_EXPECTED_CLAUSES,
    detect_missing_clauses,
    detect_present_clauses_from_text,
    get_expected_clauses,
    normalize_clause_type,
    normalize_contract_type,
)


class TestClauseNormalization:
    """Test clause type and contract type normalization logic."""

    def test_synonym_normalization(self) -> None:
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

    def test_case_and_whitespace_normalization(self) -> None:
        assert normalize_clause_type("  Confidentiality  ") == "confidentiality"
        assert normalize_clause_type("TERMINATION") == "termination"
        assert normalize_clause_type("Non-Compete") == "non_compete"
        assert normalize_clause_type("DATA PROTECTION") == "data_protection"

    def test_contract_type_normalization(self) -> None:
        assert normalize_contract_type("vendor_msa") == "vendor_msa"
        assert normalize_contract_type("Vendor Master Services Agreement") == "vendor_msa"
        assert normalize_contract_type("Non-Disclosure Agreement (NDA)") == "nda"
        assert normalize_contract_type("SaaS Subscription Agreement") == "saas_msa"
        assert normalize_contract_type("Employment Contract") == "employment"
        assert normalize_contract_type("Custom Services Agreement") == "general_commercial"
        assert normalize_contract_type(None) == "general_commercial"

    def test_expected_clauses_resolution(self) -> None:
        vendor_clauses = get_expected_clauses("vendor_msa")
        assert "confidentiality" in vendor_clauses
        assert "limitation_of_liability" in vendor_clauses
        assert "indemnification" in vendor_clauses
        assert "data_protection" in vendor_clauses

        nda_clauses = get_expected_clauses("nda")
        assert "confidentiality" in nda_clauses
        assert "governing_law" in nda_clauses
        assert "non_compete" not in nda_clauses

    def test_organization_playbook_override(self) -> None:
        custom_overrides = {
            "vendor_msa": ["confidentiality", "warranty", "insurance"],
        }
        res = get_expected_clauses("vendor_msa", org_overrides=custom_overrides)
        assert res == ["confidentiality", "warranty", "insurance"]


class TestTextPatternClassification:
    """Test text pattern matching for clause types."""

    def test_detects_indemnification_and_liability(self) -> None:
        chunks = [
            "Vendor agrees to defend, indemnify, and hold harmless Client against third-party claims.",
            "In no event shall either party's aggregate liability exceed the total fees paid.",
        ]
        detected = detect_present_clauses_from_text(chunks)
        assert "indemnification" in detected
        assert "limitation_of_liability" in detected
        assert "confidentiality" not in detected

    def test_detects_data_protection_and_termination(self) -> None:
        chunks = [
            "Each party must comply with applicable data protection laws and GDPR requirements.",
            "Either party may terminate this agreement upon 30 days prior written notice.",
        ]
        detected = detect_present_clauses_from_text(chunks)
        assert "data_protection" in detected
        assert "termination" in detected


class TestDetectMissingClauses:
    """Test async missing clause detection service orchestration."""

    @pytest.mark.asyncio
    async def test_all_expected_clauses_present_returns_empty(self) -> None:
        contract_id = uuid.uuid4()
        version_id = uuid.uuid4()
        org_id = uuid.uuid4()

        # Mock findings covering all NDA clauses: confidentiality, termination, governing_law, dispute_resolution
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
    async def test_one_or_more_missing_clauses_persisted_idempotently(self) -> None:
        contract_id = uuid.uuid4()
        version_id = uuid.uuid4()
        org_id = uuid.uuid4()

        # Contract has confidentiality and governing_law, but is missing termination and dispute_resolution
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
                category=RiskCategory.governing_law,
                severity=RiskSeverity.low,
                title="Governing Law",
                description="Delaware",
                evidence="Delaware laws apply",
                recommendation="",
                confidence=0.9,
            ),
        ]

        session = AsyncMock(spec=AsyncSession)

        created_mock_records = [
            MissingClause(
                id=uuid.uuid4(),
                contract_id=contract_id,
                version_id=version_id,
                org_id=org_id,
                clause_type="termination",
                confidence=0.95,
                reason="No termination clause was identified among the classified clauses for this contract version.",
            ),
            MissingClause(
                id=uuid.uuid4(),
                contract_id=contract_id,
                version_id=version_id,
                org_id=org_id,
                clause_type="dispute_resolution",
                confidence=0.95,
                reason="No dispute resolution clause was identified among the classified clauses for this contract version.",
            ),
        ]

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
                return_value=created_mock_records,
            ) as mock_bulk_create,
        ):
            results = await detect_missing_clauses(
                session,
                contract_id=contract_id,
                version_id=version_id,
                org_id=org_id,
                contract_type="nda",
            )
            assert len(results) == 2
            mock_delete.assert_called_once_with(session, contract_id, version_id)
            mock_bulk_create.assert_called_once()
            call_items = mock_bulk_create.call_args[1]["items"]
            missing_types = [it["clause_type"] for it in call_items]
            assert "termination" in missing_types
            assert "dispute_resolution" in missing_types
            for it in call_items:
                assert 0.0 <= it["confidence"] <= 1.0
                assert "No " in it["reason"]
                assert "clause was identified" in it["reason"]

    @pytest.mark.asyncio
    async def test_version_isolation(self) -> None:
        """Verify findings from version 1 do not affect detection for version 2."""
        contract_id = uuid.uuid4()
        v1_id = uuid.uuid4()
        v2_id = uuid.uuid4()
        org_id = uuid.uuid4()

        # Finding belongs to v1 only
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
                return_value=[],
            ) as mock_bulk_create,
        ):
            # Run for v2
            await detect_missing_clauses(
                session,
                contract_id=contract_id,
                version_id=v2_id,
                org_id=org_id,
                contract_type="nda",
            )
            # For v2, since mock_findings was for v1, confidentiality should still be missing in v2
            call_items = mock_bulk_create.call_args[1]["items"]
            missing_types = [it["clause_type"] for it in call_items]
            assert "confidentiality" in missing_types
