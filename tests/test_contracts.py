"""Unit tests for contract analysis, playbook, and export endpoints."""

from app.api.v1.contracts import (
    classify_clauses,
    compute_risk_score,
)
from httpx import AsyncClient


class TestClauseClassifier:
    def test_classify_indemnification_clause(self) -> None:
        text = "The vendor shall indemnify and hold harmless the customer from all claims."
        clauses = classify_clauses(text)
        assert len(clauses) == 1
        assert clauses[0]["type"] == "Indemnification"
        assert clauses[0]["severity"] == "high"

    def test_classify_non_compete_clause(self) -> None:
        text = "Employee agrees to a non-compete for a period of two years."
        clauses = classify_clauses(text, sensitivity="strict")
        assert len(clauses) == 1
        assert clauses[0]["type"] == "Non-Compete"
        assert clauses[0]["severity"] == "critical"

    def test_classify_data_processing_clause(self) -> None:
        text = "Vendor shall process personal data in compliance with GDPR regulations."
        clauses = classify_clauses(text, sensitivity="permissive")
        assert len(clauses) == 1
        assert clauses[0]["type"] == "Data Processing"
        assert clauses[0]["severity"] == "high"


class TestRiskScoreComputer:
    def test_empty_clauses_returns_zero(self) -> None:
        assert compute_risk_score([]) == 0

    def test_risk_score_calculation(self) -> None:
        clauses = [{"severity": "high"}, {"severity": "critical"}]
        score_standard = compute_risk_score(clauses, sensitivity="standard")
        score_strict = compute_risk_score(clauses, sensitivity="strict")
        score_permissive = compute_risk_score(clauses, sensitivity="permissive")

        assert score_standard > 0
        assert score_strict >= score_standard
        assert score_permissive <= score_standard


class TestContractsAPI:
    async def test_analyze_contract_text_success(self, async_client: AsyncClient) -> None:
        sample_contract = (
            "This is a long sample contract text for testing purpose. "
            "The vendor shall indemnify and hold harmless the customer from any claims."
        )
        payload = {
            "text": sample_contract,
            "sensitivity": "standard",
        }
        response = await async_client.post("/api/v1/contracts/analyze", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "score" in data
        assert "clauses" in data
        assert len(data["clauses"]) >= 1

    async def test_analyze_contract_file_upload(self, async_client: AsyncClient) -> None:
        file_content = (
            b"Limitation of liability cap is $500 flat in this contract text. "
            b"The vendor shall indemnify and hold harmless the customer."
        )
        files = {"file": ("contract.txt", file_content, "text/plain")}
        response = await async_client.post(
            "/api/v1/contracts/analyze-file", files=files, data={"sensitivity": "standard"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "clauses" in data

    async def test_analyze_contract_no_input_error(self, async_client: AsyncClient) -> None:
        response = await async_client.post("/api/v1/contracts/analyze", json={})
        assert response.status_code == 422  # Validation error for missing text/file

    async def test_list_playbooks(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/contracts/playbooks")
        assert response.status_code == 200
        data = response.json()
        assert "playbooks" in data
        assert len(data["playbooks"]) >= 3

    async def test_export_report_markdown(self, async_client: AsyncClient) -> None:
        payload = {
            "analysis": {
                "score": 75,
                "overall_assessment": "High Risk",
                "clauses": [
                    {
                        "type": "Indemnification",
                        "severity": "high",
                        "snippet": "indemnify and hold harmless",
                        "risk": "Broad liability exposure",
                        "redline": "Limit to direct damages",
                    }
                ],
            },
            "format": "markdown",
        }
        response = await async_client.post("/api/v1/contracts/export", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "# Contract Risk Analysis Report" in data["data"]

    async def test_export_report_json(self, async_client: AsyncClient) -> None:
        payload = {
            "analysis": {
                "score": 40,
                "clauses": [],
            },
            "format": "json",
        }
        response = await async_client.post("/api/v1/contracts/export", json=payload)
        assert response.status_code == 200
        assert "data" in response.json()

    async def test_export_report_unsupported_format(self, async_client: AsyncClient) -> None:
        payload = {
            "analysis": {
                "score": 30,
                "clauses": [],
            },
            "format": "unsupported_fmt",
        }
        response = await async_client.post("/api/v1/contracts/export", json=payload)
        assert response.status_code == 400
