"""Unit tests for LLM Service and rule-based risk detection engine."""

from app.models.risk_finding import RiskCategory, RiskSeverity
from app.services.llm_service import _extract_surrounding_sentence, analyze_contract_text


class TestLLMService:
    def test_detects_uncapped_liability_risk(self) -> None:
        chunks = [
            {
                "id": None,
                "chunk_index": 0,
                "content": (
                    "Neither party shall be subject to any uncapped liability under this Agreement."
                ),
            }
        ]
        findings = analyze_contract_text(chunks)
        assert len(findings) >= 1
        finding = findings[0]
        assert finding["category"] == RiskCategory.liability
        assert finding["severity"] == RiskSeverity.critical
        assert "uncapped liability" in finding["evidence"].lower()
        assert finding["confidence"] > 0.9

    def test_detects_broad_indemnification(self) -> None:
        chunks = [
            {
                "id": None,
                "chunk_index": 0,
                "content": (
                    "Provider shall defend, indemnify, and hold harmless Customer "
                    "against any third-party claims."
                ),
            }
        ]
        findings = analyze_contract_text(chunks)
        assert len(findings) >= 1
        finding = findings[0]
        assert finding["category"] == RiskCategory.indemnification
        assert finding["severity"] == RiskSeverity.high

    def test_detects_unilateral_termination(self) -> None:
        chunks = [
            {
                "id": None,
                "chunk_index": 0,
                "content": "Customer may terminate for convenience without notice at any time.",
            }
        ]
        findings = analyze_contract_text(chunks)
        assert len(findings) >= 1
        finding = findings[0]
        assert finding["category"] == RiskCategory.termination

    def test_baseline_finding_if_no_patterns_match(self) -> None:
        chunks = [
            {
                "id": None,
                "chunk_index": 0,
                "content": (
                    "This Agreement is entered into on January 1st by and "
                    "between Party A and Party B."
                ),
            }
        ]
        findings = analyze_contract_text(chunks)
        assert len(findings) == 1
        assert findings[0]["category"] == RiskCategory.other
        assert findings[0]["severity"] == RiskSeverity.low

    def test_extract_surrounding_sentence(self) -> None:
        text = "First sentence. This clause contains uncapped liability terms. Third sentence."
        start = text.find("uncapped liability")
        end = start + len("uncapped liability")
        evidence = _extract_surrounding_sentence(text, start, end)
        assert "uncapped liability terms" in evidence
