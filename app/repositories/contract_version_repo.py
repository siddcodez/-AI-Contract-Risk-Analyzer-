"""Repository for ContractVersion operations.

contract_versions has RLS enabled — all queries are filtered by
the tenant_isolation policy.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract_version import ContractVersion


async def create(
    session: AsyncSession,
    *,
    contract_id: uuid.UUID,
    version_number: int,
    file_name: str,
    file_size: int,
    content_type: str,
    storage_key: str,
    org_id: uuid.UUID,
) -> ContractVersion:
    """Create a new contract version record.

    Subject to RLS WITH CHECK — caller must set tenant context first.
    """
    version = ContractVersion(
        id=uuid.uuid4(),
        contract_id=contract_id,
        version_number=version_number,
        file_name=file_name,
        file_size=file_size,
        content_type=content_type,
        storage_key=storage_key,
        org_id=org_id,
    )
    session.add(version)
    await session.flush()
    return version


async def list_by_contract(
    session: AsyncSession,
    contract_id: uuid.UUID,
) -> list[ContractVersion]:
    """List all versions for a contract, ordered by version number.

    Subject to RLS — caller must set tenant context first.
    """
    result = await session.execute(
        select(ContractVersion)
        .where(ContractVersion.contract_id == contract_id)
        .order_by(ContractVersion.version_number)
    )
    return list(result.scalars().all())


async def get_by_id(
    session: AsyncSession,
    version_id: uuid.UUID,
) -> ContractVersion | None:
    """Fetch a contract version by ID.

    Subject to RLS.
    """
    result = await session.execute(select(ContractVersion).where(ContractVersion.id == version_id))
    return result.scalars().first()


async def get_latest_by_contract(
    session: AsyncSession,
    contract_id: uuid.UUID,
) -> ContractVersion | None:
    """Fetch the latest version for a contract by version_number.

    Subject to RLS.
    """
    result = await session.execute(
        select(ContractVersion)
        .where(ContractVersion.contract_id == contract_id)
        .order_by(ContractVersion.version_number.desc())
        .limit(1)
    )
    return result.scalars().first()
