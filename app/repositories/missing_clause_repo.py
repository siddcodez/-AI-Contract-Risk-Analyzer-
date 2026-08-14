"""Repository for MissingClause DB operations.

missing_clauses table HAS RLS enabled — all queries are subject to the
tenant_isolation policy (org_id must match current app.current_org_id setting).
"""

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.missing_clause import MissingClause


async def bulk_create(
    session: AsyncSession,
    *,
    items: list[dict[str, Any]],
) -> list[MissingClause]:
    """Bulk create missing clause records.

    Subject to RLS WITH CHECK — caller must ensure org_id matches current tenant.
    """
    records = [MissingClause(**data) for data in items]
    session.add_all(records)
    await session.flush()
    return records


async def delete_by_contract_and_version(
    session: AsyncSession,
    contract_id: uuid.UUID,
    version_id: uuid.UUID,
) -> None:
    """Delete all existing missing clauses for a specific contract version.

    Ensures idempotency when re-running detection.
    Subject to RLS.
    """
    await session.execute(
        delete(MissingClause).where(
            MissingClause.contract_id == contract_id,
            MissingClause.version_id == version_id,
        )
    )
    await session.flush()


async def list_by_contract_and_version(
    session: AsyncSession,
    contract_id: uuid.UUID,
    version_id: uuid.UUID,
) -> list[MissingClause]:
    """Fetch missing clauses for a specific contract version.

    Subject to RLS — caller must set tenant context first.
    """
    stmt = (
        select(MissingClause)
        .where(
            MissingClause.contract_id == contract_id,
            MissingClause.version_id == version_id,
        )
        .order_by(MissingClause.clause_type.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_by_contract(
    session: AsyncSession,
    contract_id: uuid.UUID,
) -> list[MissingClause]:
    """Fetch all missing clauses for a contract across all versions.

    Subject to RLS.
    """
    stmt = (
        select(MissingClause)
        .where(MissingClause.contract_id == contract_id)
        .order_by(MissingClause.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
