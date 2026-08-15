"""Deterministic Contract Version Comparison Engine (M8).

Computes deterministic clause-level diffs (added/removed/modified/unchanged)
and risk score deltas between two versions of the same contract.
Keeps LLM execution strictly out of synchronous diff computation.
"""

import difflib
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.contract_comparison import ContractComparison
from app.models.risk_finding import RiskFinding, RiskSeverity
from app.repositories import (
    comparison_repo,
    contract_repo,
    contract_version_repo,
    risk_finding_repo,
)
from app.schemas.comparison import (
    ClauseChangeType,
    ClauseDiffItem,
    ContractComparisonResponse,
)
from app.services.missing_clause_service import CANONICAL_CLAUSE_TYPES, CLAUSE_DISPLAY_NAMES

logger = get_logger(__name__)

# Severity weights matching deterministic risk score calculation
SEVERITY_WEIGHTS = {
    RiskSeverity.critical: 40,
    RiskSeverity.high: 30,
    RiskSeverity.medium: 20,
    RiskSeverity.low: 10,
}


def compute_version_risk_score(findings: list[RiskFinding]) -> int:
    """Compute deterministic aggregate risk score 0-100 from findings."""
    if not findings:
        return 0
    total = sum(SEVERITY_WEIGHTS.get(f.severity, 20) for f in findings)
    max_possible = len(findings) * 40
    raw = int((total / max_possible) * 100) if max_possible > 0 else 0
    return min(100, max(0, raw))


def _normalize_clause_type(raw_type: str) -> str:
    """Normalize clause type using canonical synonyms."""
    norm = raw_type.strip().lower().replace("-", "_").replace(" ", "_")
    return str(CANONICAL_CLAUSE_TYPES.get(norm, norm))


def _text_similarity(a: str, b: str) -> float:
    """Compute normalized sequence similarity ratio between two clause strings."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    norm_a = " ".join(a.lower().split())
    norm_b = " ".join(b.lower().split())
    if norm_a == norm_b:
        return 1.0
    return difflib.SequenceMatcher(None, norm_a, norm_b).ratio()


def _group_findings_by_clause_type(
    findings: list[RiskFinding],
) -> dict[str, list[RiskFinding]]:
    """Group and sort findings by normalized clause type (highest severity first)."""
    grouped: dict[str, list[RiskFinding]] = {}
    for f in findings:
        cat_str = f.category.value if hasattr(f.category, "value") else str(f.category)
        c_type = _normalize_clause_type(cat_str)
        grouped.setdefault(c_type, []).append(f)

    # Sort each list by severity descending (critical > high > medium > low)
    severity_order = {
        RiskSeverity.critical: 4,
        RiskSeverity.high: 3,
        RiskSeverity.medium: 2,
        RiskSeverity.low: 1,
    }
    for _c_type, f_list in grouped.items():
        f_list.sort(
            key=lambda item: (
                severity_order.get(item.severity, 0),
                len(item.evidence or ""),
            ),
            reverse=True,
        )
    return grouped


def compute_deterministic_diff(
    from_findings: list[RiskFinding],
    to_findings: list[RiskFinding],
) -> tuple[list[dict[str, Any]], int, int, int, int]:
    """Compute deterministic clause diff between from_version and to_version findings.

    Returns:
        (diff_items_data, added_count, removed_count, modified_count, unchanged_count)
    """
    grouped_from = _group_findings_by_clause_type(from_findings)
    grouped_to = _group_findings_by_clause_type(to_findings)

    all_clause_types = sorted(set(grouped_from.keys()) | set(grouped_to.keys()))

    diff_items: list[dict[str, Any]] = []
    added_count = 0
    removed_count = 0
    modified_count = 0
    unchanged_count = 0

    for c_type in all_clause_types:
        f_from_list = grouped_from.get(c_type, [])
        f_to_list = grouped_to.get(c_type, [])
        display_name = CLAUSE_DISPLAY_NAMES.get(c_type, c_type.replace("_", " ").title())

        # Determine number of pairings to inspect
        max_pairs = max(len(f_from_list), len(f_to_list))

        for idx in range(max_pairs):
            f_from = f_from_list[idx] if idx < len(f_from_list) else None
            f_to = f_to_list[idx] if idx < len(f_to_list) else None

            from_text = f_from.evidence if f_from else None
            to_text = f_to.evidence if f_to else None
            from_sev = f_from.severity.value if f_from else None
            to_sev = f_to.severity.value if f_to else None

            if f_from is None and f_to is not None:
                change_type = ClauseChangeType.added
                added_count += 1
            elif f_from is not None and f_to is None:
                change_type = ClauseChangeType.removed
                removed_count += 1
            else:
                sim = _text_similarity(from_text or "", to_text or "")
                if sim >= 0.98 and from_sev == to_sev:
                    change_type = ClauseChangeType.unchanged
                    unchanged_count += 1
                else:
                    change_type = ClauseChangeType.modified
                    modified_count += 1

            diff_items.append(
                {
                    "clause_type": c_type,
                    "display_name": display_name,
                    "change_type": change_type.value,
                    "from_text": from_text,
                    "to_text": to_text,
                    "from_severity": from_sev,
                    "to_severity": to_sev,
                    "ai_explanation": None,
                    "metadata_json": {
                        "from_finding_id": str(f_from.id) if f_from else None,
                        "to_finding_id": str(f_to.id) if f_to else None,
                    },
                }
            )

    return (
        diff_items,
        added_count,
        removed_count,
        modified_count,
        unchanged_count,
    )


async def compare_contract_versions(
    session: AsyncSession,
    *,
    contract_id: uuid.UUID,
    from_version_id: uuid.UUID,
    to_version_id: uuid.UUID,
    org_id: uuid.UUID,
    refresh: bool = False,
) -> ContractComparisonResponse:
    """Perform deterministic comparison between two versions of the same contract.

    Subject to Postgres RLS tenant isolation.

    Raises:
        BadRequestError: If comparing identical version IDs, or if versions
            do not belong to this contract.
        NotFoundError: If contract or either version is not found in tenant context.
    """
    if from_version_id == to_version_id:
        raise ValidationError("Cannot compare a contract version against itself")

    # 1. Validate contract existence (RLS-scoped)
    contract = await contract_repo.get_by_id(session, contract_id)
    if contract is None:
        raise NotFoundError("Contract not found")

    # 2. Validate versions existence and contract association
    v_from = await contract_version_repo.get_by_id(session, from_version_id)
    if v_from is None or v_from.contract_id != contract_id:
        raise NotFoundError("Baseline contract version (from_version) not found")

    v_to = await contract_version_repo.get_by_id(session, to_version_id)
    if v_to is None or v_to.contract_id != contract_id:
        raise NotFoundError("Target contract version (to_version) not found")

    # 3. Check for existing persisted comparison if refresh=False
    existing = await comparison_repo.get_by_versions(
        session,
        contract_id=contract_id,
        from_version_id=from_version_id,
        to_version_id=to_version_id,
    )

    if existing is not None and not refresh:
        logger.info(
            "Returning cached contract version comparison",
            contract_id=str(contract_id),
            from_version_id=str(from_version_id),
            to_version_id=str(to_version_id),
        )
        return _format_comparison_response(existing, v_from.version_number, v_to.version_number)

    # 4. Fetch risk findings for each version
    from_findings = await risk_finding_repo.list_by_contract_and_version(
        session, contract_id, from_version_id
    )
    to_findings = await risk_finding_repo.list_by_contract_and_version(
        session, contract_id, to_version_id
    )

    # 5. Compute deterministic risk scores and delta
    risk_from = compute_version_risk_score(from_findings)
    risk_to = compute_version_risk_score(to_findings)
    risk_delta = risk_to - risk_from

    # 6. Compute deterministic clause diffs
    (
        diff_items_data,
        added_cnt,
        removed_cnt,
        modified_cnt,
        unchanged_cnt,
    ) = compute_deterministic_diff(from_findings, to_findings)

    # 7. Persist comparison record (create or update existing on refresh)
    comparison_data = {
        "risk_score_from": risk_from,
        "risk_score_to": risk_to,
        "risk_delta": risk_delta,
        "clauses_added_count": added_cnt,
        "clauses_removed_count": removed_cnt,
        "clauses_modified_count": modified_cnt,
        "clauses_unchanged_count": unchanged_cnt,
        "diff_summary_json": diff_items_data,
    }

    if existing is not None:
        saved_comparison = await comparison_repo.update_comparison(
            session,
            existing,
            update_data=comparison_data,
        )
    else:
        full_data = {
            "id": uuid.uuid4(),
            "contract_id": contract_id,
            "from_version_id": from_version_id,
            "to_version_id": to_version_id,
            "org_id": org_id,
            **comparison_data,
        }
        saved_comparison = await comparison_repo.create(session, comparison_data=full_data)

    await session.commit()

    logger.info(
        "Computed and saved contract version comparison",
        contract_id=str(contract_id),
        from_version_id=str(from_version_id),
        to_version_id=str(to_version_id),
        risk_delta=risk_delta,
    )

    return _format_comparison_response(saved_comparison, v_from.version_number, v_to.version_number)


def _format_comparison_response(
    comp: ContractComparison,
    from_version_num: int | None = None,
    to_version_num: int | None = None,
) -> ContractComparisonResponse:
    """Format ORM model into ContractComparisonResponse Pydantic model."""
    diff_items = [
        ClauseDiffItem(
            clause_type=it["clause_type"],
            display_name=it.get("display_name", it["clause_type"]),
            change_type=ClauseChangeType(it["change_type"]),
            from_text=it.get("from_text"),
            to_text=it.get("to_text"),
            from_severity=it.get("from_severity"),
            to_severity=it.get("to_severity"),
            ai_explanation=it.get("ai_explanation"),
            metadata_json=it.get("metadata_json"),
        )
        for it in comp.diff_summary_json
    ]

    return ContractComparisonResponse(
        id=comp.id,
        contract_id=comp.contract_id,
        from_version_id=comp.from_version_id,
        to_version_id=comp.to_version_id,
        from_version_number=from_version_num,
        to_version_number=to_version_num,
        risk_score_from=comp.risk_score_from,
        risk_score_to=comp.risk_score_to,
        risk_delta=comp.risk_delta,
        clauses_added_count=comp.clauses_added_count,
        clauses_removed_count=comp.clauses_removed_count,
        clauses_modified_count=comp.clauses_modified_count,
        clauses_unchanged_count=comp.clauses_unchanged_count,
        diff_items=diff_items,
        created_at=comp.created_at,
        updated_at=comp.updated_at,
    )
