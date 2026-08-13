"""Repository for ContractChunk DB operations.

contract_chunks table HAS RLS enabled — all queries are subject to the
tenant_isolation policy (org_id must match the current session's app.current_org_id setting).
"""

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract_chunk import ContractChunk


async def bulk_create(
    session: AsyncSession,
    *,
    chunks_data: list[dict[str, Any]],
) -> list[ContractChunk]:
    """Bulk create contract chunk records.

    Subject to RLS WITH CHECK — caller must ensure org_id matches current tenant.
    """
    chunks = [ContractChunk(**data) for data in chunks_data]
    session.add_all(chunks)
    await session.flush()
    return chunks


async def delete_by_contract_and_version(
    session: AsyncSession,
    contract_id: uuid.UUID,
    version_id: uuid.UUID,
) -> None:
    """Delete all existing chunks for a specific contract version.

    Used to ensure idempotency when retrying a contract processing job.
    Subject to RLS.
    """
    await session.execute(
        delete(ContractChunk).where(
            ContractChunk.contract_id == contract_id,
            ContractChunk.version_id == version_id,
        )
    )
    await session.flush()


async def list_by_contract(
    session: AsyncSession,
    contract_id: uuid.UUID,
) -> list[ContractChunk]:
    """Fetch all chunks for a contract, ordered by chunk_index.

    Subject to RLS — caller must set tenant context first.
    """
    result = await session.execute(
        select(ContractChunk)
        .where(ContractChunk.contract_id == contract_id)
        .order_by(ContractChunk.chunk_index.asc())
    )
    return list(result.scalars().all())
