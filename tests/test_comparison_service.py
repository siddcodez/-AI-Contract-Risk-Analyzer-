"""Unit and domain tests for Contract Version Comparison Service (M8)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from app.core.exceptions import NotFoundError, ValidationError
from app.models.contract import Contract
from app.models.contract_comparison import ContractComparison
from app.models.contract_version import ContractVersion
from app.models.risk_finding import RiskCategory, RiskFinding, RiskSeverity
from app.schemas.comparison import ClauseChangeType
from app.services.comparison_service import (
    compare_contract_versions,
    compute_deterministic_diff,
    compute_version_risk_score,
)
from sqlalchemy.ext.asyncio import AsyncSession


def _make_finding(
    category: RiskCategory,
    severity: RiskSeverity,
    evidence: str,
    contract_id: uuid.UUID | None = None,
    version_id: uuid.UUID | None = None,
) -> RiskFinding:
    f = RiskFinding()
    f.id = uuid.uuid4()
    f.contract_id = contract_id or uuid.uuid4()
    f.version_id = version_id or uuid.uuid4()
    f.org_id = uuid.uuid4()
    f.category = category
    f.severity = severity
    f.title = f"{category.value} finding"
    f.description = "Detailed risk finding description"
    f.evidence = evidence
    f.recommendation = "Mitigate risk"
    f.confidence = 0.95
    f.created_at = datetime.now(UTC)
    return f


class TestComparisonService:
    """Test suite for deterministic version comparison logic."""

    def test_identical_findings_classified_as_unchanged(self) -> None:
        cid = uuid.uuid4()
        v1 = uuid.uuid4()
        v2 = uuid.uuid4()

        f1 = _make_finding(
            RiskCategory.confidentiality,
            RiskSeverity.medium,
            "Confidentiality shall last 5 years from disclosure.",
            cid,
            v1,
        )
        f2 = _make_finding(
            RiskCategory.confidentiality,
            RiskSeverity.medium,
            "Confidentiality shall last 5 years from disclosure.",
            cid,
            v2,
        )

        diffs, added, removed, modified, unchanged = compute_deterministic_diff([f1], [f2])

        assert added == 0
        assert removed == 0
        assert modified == 0
        assert unchanged == 1
        assert len(diffs) == 1
        assert diffs[0]["change_type"] == ClauseChangeType.unchanged.value
        assert diffs[0]["clause_type"] == "confidentiality"

    def test_clause_added_removed_modified_classification(self) -> None:
        cid = uuid.uuid4()
        v1 = uuid.uuid4()
        v2 = uuid.uuid4()

        # V1: Has confidentiality (will be modified) and data_privacy (will be removed)
        f1_conf = _make_finding(
            RiskCategory.confidentiality,
            RiskSeverity.medium,
            "Confidentiality shall last 3 years.",
            cid,
            v1,
        )
        f1_data = _make_finding(
            RiskCategory.data_privacy,
            RiskSeverity.high,
            "Vendor shall store data only in EU data centers.",
            cid,
            v1,
        )

        # V2: Has confidentiality (modified duration) and indemnification (newly added)
        f2_conf = _make_finding(
            RiskCategory.confidentiality,
            RiskSeverity.low,
            "Confidentiality obligations shall survive indefinitely in perpetuity.",
            cid,
            v2,
        )
        f2_indem = _make_finding(
            RiskCategory.indemnification,
            RiskSeverity.critical,
            "Vendor indemnifies Customer against all third-party claims without limitation.",
            cid,
            v2,
        )

        diffs, added, removed, modified, unchanged = compute_deterministic_diff(
            [f1_conf, f1_data],
            [f2_conf, f2_indem],
        )

        assert added == 1  # indemnification added
        assert removed == 1  # data_privacy removed
        assert modified == 1  # confidentiality modified
        assert unchanged == 0

        diff_by_type = {d["clause_type"]: d for d in diffs}
        assert diff_by_type["indemnification"]["change_type"] == "added"
        assert diff_by_type["data_protection"]["change_type"] == "removed"
        assert diff_by_type["confidentiality"]["change_type"] == "modified"

    def test_multiple_findings_of_same_type_pairing_by_severity(self) -> None:
        """Verify multiple findings of same clause_type are paired stably by severity order."""
        cid = uuid.uuid4()
        v1 = uuid.uuid4()
        v2 = uuid.uuid4()

        # V1: Two indemnity findings (Critical, Medium)
        v1_indem_crit = _make_finding(
            RiskCategory.indemnification,
            RiskSeverity.critical,
            "Customer indemnifies vendor for all indirect losses.",
            cid,
            v1,
        )
        v1_indem_med = _make_finding(
            RiskCategory.indemnification,
            RiskSeverity.medium,
            "Mutual IP indemnity with $1M cap.",
            cid,
            v1,
        )

        # V2: One indemnity finding (Critical)
        v2_indem_crit = _make_finding(
            RiskCategory.indemnification,
            RiskSeverity.critical,
            "Customer indemnifies vendor for all indirect losses.",
            cid,
            v2,
        )

        _diffs, added, removed, modified, unchanged = compute_deterministic_diff(
            [v1_indem_crit, v1_indem_med],
            [v2_indem_crit],
        )

        # The critical finding matched unchanged, the medium finding was removed
        assert unchanged == 1
        assert removed == 1
        assert added == 0
        assert modified == 0

    def test_deterministic_risk_score_and_delta(self) -> None:
        # V1: Low (10) + Medium (20) -> sum=30, max=80 -> 37%
        f_low = _make_finding(RiskCategory.sla, RiskSeverity.low, "SLA text")
        f_med = _make_finding(RiskCategory.payment, RiskSeverity.medium, "Payment text")
        score_v1 = compute_version_risk_score([f_low, f_med])

        # V2: Critical (40) + High (30) -> sum=70, max=80 -> 87%
        f_crit = _make_finding(RiskCategory.liability, RiskSeverity.critical, "Unlimited liability")
        f_high = _make_finding(RiskCategory.termination, RiskSeverity.high, "Immediate termination")
        score_v2 = compute_version_risk_score([f_crit, f_high])

        assert score_v1 == 37
        assert score_v2 == 87
        assert (score_v2 - score_v1) == 50

    @pytest.mark.asyncio
    async def test_compare_rejects_identical_version_ids(self) -> None:
        session = AsyncMock(spec=AsyncSession)
        cid = uuid.uuid4()
        vid = uuid.uuid4()

        with pytest.raises(
            ValidationError,
            match="Cannot compare a contract version against itself",
        ):
            await compare_contract_versions(
                session,
                contract_id=cid,
                from_version_id=vid,
                to_version_id=vid,
                org_id=uuid.uuid4(),
            )

    @pytest.mark.asyncio
    async def test_compare_rejects_version_from_other_contract(self) -> None:
        session = AsyncMock(spec=AsyncSession)
        cid = uuid.uuid4()
        other_cid = uuid.uuid4()
        v1_id = uuid.uuid4()
        v2_id = uuid.uuid4()

        contract = Contract(id=cid, title="MSA Contract")
        v1 = ContractVersion(id=v1_id, contract_id=cid, version_number=1)
        v2_other = ContractVersion(id=v2_id, contract_id=other_cid, version_number=2)

        with (
            patch(
                "app.services.comparison_service.contract_repo.get_by_id",
                new_callable=AsyncMock,
                return_value=contract,
            ),
            patch(
                "app.services.comparison_service.contract_version_repo.get_by_id",
                side_effect=[v1, v2_other],
            ),
        ):
            with pytest.raises(NotFoundError, match=r"Target contract version .* not found"):
                await compare_contract_versions(
                    session,
                    contract_id=cid,
                    from_version_id=v1_id,
                    to_version_id=v2_id,
                    org_id=uuid.uuid4(),
                )

    @pytest.mark.asyncio
    async def test_idempotency_returns_cached_row_when_refresh_false(self) -> None:
        """Verify refresh=False returns cached comparison without re-querying findings."""
        session = AsyncMock(spec=AsyncSession)
        cid = uuid.uuid4()
        v1_id = uuid.uuid4()
        v2_id = uuid.uuid4()
        org_id = uuid.uuid4()

        contract = Contract(id=cid, title="MSA Contract")
        v1 = ContractVersion(id=v1_id, contract_id=cid, version_number=1)
        v2 = ContractVersion(id=v2_id, contract_id=cid, version_number=2)

        cached_comp = ContractComparison(
            id=uuid.uuid4(),
            contract_id=cid,
            from_version_id=v1_id,
            to_version_id=v2_id,
            org_id=org_id,
            risk_score_from=25,
            risk_score_to=60,
            risk_delta=35,
            clauses_added_count=1,
            clauses_removed_count=0,
            clauses_modified_count=1,
            clauses_unchanged_count=2,
            diff_summary_json=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        with (
            patch(
                "app.services.comparison_service.contract_repo.get_by_id",
                new_callable=AsyncMock,
                return_value=contract,
            ),
            patch(
                "app.services.comparison_service.contract_version_repo.get_by_id",
                side_effect=[v1, v2],
            ),
            patch(
                "app.services.comparison_service.comparison_repo.get_by_versions",
                new_callable=AsyncMock,
                return_value=cached_comp,
            ),
            patch(
                "app.services.comparison_service.risk_finding_repo.list_by_contract_and_version",
                new_callable=AsyncMock,
            ) as mock_findings,
        ):
            res = await compare_contract_versions(
                session,
                contract_id=cid,
                from_version_id=v1_id,
                to_version_id=v2_id,
                org_id=org_id,
                refresh=False,
            )

            assert res.risk_delta == 35
            assert res.from_version_number == 1
            assert res.to_version_number == 2
            # Verify risk_finding_repo was never queried because cached row was returned
            mock_findings.assert_not_called()
