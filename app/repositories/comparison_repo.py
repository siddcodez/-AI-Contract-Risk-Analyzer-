"""Repository for ContractComparison database operations.

comparisons table HAS RLS enabled — all queries are subject to the
tenant_isolation policy (org_id must match current app.current_org_id setting).
"""

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract_comparison import ContractComparison


async def get_by_versions(
    session: AsyncSession,
    contract_id: uuid.UUID,
    from_version_id: uuid.UUID,
    to_version_id: uuid.UUID,
) -> ContractComparison | None:
    """Fetch existing comparison between two contract versions.

    Subject to RLS — caller must set tenant context first.
    """
    result = await session.execute(
        select(ContractComparison).where(
            ContractComparison.contract_id == contract_id,
            ContractComparison.from_version_id == from_version_id,
            ContractComparison.to_version_id == to_version_id,
        )
    )
    return result.scalars().first()


async def create(
    session: AsyncSession,
    *,
    comparison_data: dict[str, Any],
) -> ContractComparison:
    """Create a new contract comparison record.

    Subject to RLS WITH CHECK.
    """
    comparison = ContractComparison(**comparison_data)
    session.add(comparison)
    await session.flush()
    return comparison


async def update_comparison(
    session: AsyncSession,
    comparison: ContractComparison,
    *,
    update_data: dict[str, Any],
) -> ContractComparison:
    """Update an existing comparison record (used on refresh=True).

    Subject to RLS.
    """
    for key, value in update_data.items():
        setattr(comparison, key, value)
    await session.flush()
    return comparison


async def delete_by_contract(
    session: AsyncSession,
    contract_id: uuid.UUID,
) -> None:
    """Delete all comparisons for a contract.

    Subject to RLS.
    """
    await session.execute(
        delete(ContractComparison).where(ContractComparison.contract_id == contract_id)
    )
    await session.flush()
