"""Repository for Contract CRUD operations.

The contracts table HAS RLS enabled.  All queries are subject to the
tenant_isolation policy (org_id must match the current session's
app.current_org_id setting).  Caller must set tenant context before
calling any function in this module.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract, ContractStatus


async def create(
    session: AsyncSession,
    *,
    title: str,
    file_name: str,
    file_size: int,
    content_type: str,
    storage_key: str,
    org_id: uuid.UUID,
    uploaded_by: uuid.UUID,
    status: ContractStatus = ContractStatus.pending,
) -> Contract:
    """Create a new contract record.

    Subject to RLS WITH CHECK — caller must set tenant context to the
    target org_id before calling this.
    """
    contract = Contract(
        id=uuid.uuid4(),
        title=title,
        file_name=file_name,
        file_size=file_size,
        content_type=content_type,
        storage_key=storage_key,
        status=status,
        org_id=org_id,
        uploaded_by=uploaded_by,
    )
    session.add(contract)
    await session.flush()
    return contract


async def get_by_id(
    session: AsyncSession,
    contract_id: uuid.UUID,
) -> Contract | None:
    """Fetch a contract by primary key.

    Subject to RLS — caller must set tenant context first.
    """
    result = await session.execute(select(Contract).where(Contract.id == contract_id))
    return result.scalars().first()


async def list_by_org(
    session: AsyncSession,
    org_id: uuid.UUID,
    *,
    skip: int = 0,
    limit: int = 20,
) -> list[Contract]:
    """List contracts for an organization with pagination.

    Subject to RLS — caller must set tenant context first.
    The org_id parameter is an application-layer filter in addition
    to the RLS policy.
    """
    result = await session.execute(
        select(Contract)
        .where(Contract.org_id == org_id)
        .order_by(Contract.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_by_org(
    session: AsyncSession,
    org_id: uuid.UUID,
) -> int:
    """Count contracts for an organization.

    Subject to RLS — caller must set tenant context first.
    """
    result = await session.execute(
        select(func.count()).select_from(Contract).where(Contract.org_id == org_id)
    )
    count = result.scalar()
    return count if count is not None else 0


async def update_status(
    session: AsyncSession,
    contract_id: uuid.UUID,
    status: ContractStatus,
) -> Contract | None:
    """Update the processing status of a contract.

    Subject to RLS — caller must set tenant context first.
    """
    contract = await get_by_id(session, contract_id)
    if contract is None:
        return None
    contract.status = status
    await session.flush()
    return contract
