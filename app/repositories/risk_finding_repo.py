"""Repository for RiskFinding DB operations.

risk_findings table HAS RLS enabled — all queries are subject to the
tenant_isolation policy (org_id must match current app.current_org_id setting).
"""

import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.risk_finding import RiskCategory, RiskFinding, RiskSeverity


async def bulk_create(
    session: AsyncSession,
    *,
    findings_data: list[dict[str, Any]],
) -> list[RiskFinding]:
    """Bulk create risk finding records.

    Subject to RLS WITH CHECK — caller must ensure org_id matches current tenant.
    """
    findings = [RiskFinding(**data) for data in findings_data]
    session.add_all(findings)
    await session.flush()
    return findings


async def delete_by_contract_and_version(
    session: AsyncSession,
    contract_id: uuid.UUID,
    version_id: uuid.UUID,
) -> None:
    """Delete all existing risk findings for a contract version.

    Ensures idempotency when re-running contract risk analysis.
    Subject to RLS.
    """
    await session.execute(
        delete(RiskFinding).where(
            RiskFinding.contract_id == contract_id,
            RiskFinding.version_id == version_id,
        )
    )
    await session.flush()


async def list_by_contract(
    session: AsyncSession,
    contract_id: uuid.UUID,
    *,
    category: RiskCategory | str | None = None,
    severity: RiskSeverity | str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> list[RiskFinding]:
    """Fetch risk findings for a contract with optional filtering and pagination.

    Subject to RLS — caller must set tenant context first.
    """
    stmt = select(RiskFinding).where(RiskFinding.contract_id == contract_id)

    if category is not None:
        cat_val = category.value if isinstance(category, RiskCategory) else category
        stmt = stmt.where(RiskFinding.category == cat_val)

    if severity is not None:
        sev_val = severity.value if isinstance(severity, RiskSeverity) else severity
        stmt = stmt.where(RiskFinding.severity == sev_val)

    stmt = stmt.order_by(RiskFinding.created_at.desc()).offset(skip).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_by_contract(
    session: AsyncSession,
    contract_id: uuid.UUID,
    *,
    category: RiskCategory | str | None = None,
    severity: RiskSeverity | str | None = None,
) -> int:
    """Count risk findings for a contract matching optional filters.

    Subject to RLS — caller must set tenant context first.
    """
    stmt = (
        select(func.count()).select_from(RiskFinding).where(RiskFinding.contract_id == contract_id)
    )

    if category is not None:
        cat_val = category.value if isinstance(category, RiskCategory) else category
        stmt = stmt.where(RiskFinding.category == cat_val)

    if severity is not None:
        sev_val = severity.value if isinstance(severity, RiskSeverity) else severity
        stmt = stmt.where(RiskFinding.severity == sev_val)

    result = await session.execute(stmt)
    count = result.scalar()
    return count if count is not None else 0


async def get_summary_by_contract(
    session: AsyncSession,
    contract_id: uuid.UUID,
) -> dict[str, int]:
    """Get count summary of risk findings for a contract grouped by severity level.

    Subject to RLS — caller must set tenant context first.
    """
    stmt = (
        select(RiskFinding.severity, func.count(RiskFinding.id))
        .where(RiskFinding.contract_id == contract_id)
        .group_by(RiskFinding.severity)
    )
    result = await session.execute(stmt)
    counts = {
        row[0].value if isinstance(row[0], RiskSeverity) else str(row[0]): row[1]
        for row in result.all()
    }

    total = sum(counts.values())
    return {
        "total": total,
        "critical": counts.get("critical", 0),
        "high": counts.get("high", 0),
        "medium": counts.get("medium", 0),
        "low": counts.get("low", 0),
    }
