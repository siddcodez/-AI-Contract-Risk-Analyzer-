"""Repository for ReviewAction database operations.

review_actions table HAS RLS enabled — all queries are subject to the
tenant_isolation policy.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review_action import ReviewAction


async def create(
    session: AsyncSession,
    *,
    contract_id: uuid.UUID,
    finding_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    org_id: uuid.UUID,
    action: str,
    comment: str | None = None,
) -> ReviewAction:
    """Record an append-only review action on a risk finding.

    Subject to RLS WITH CHECK.
    """
    review = ReviewAction(
        id=uuid.uuid4(),
        contract_id=contract_id,
        finding_id=finding_id,
        reviewer_id=reviewer_id,
        org_id=org_id,
        action=action,
        comment=comment,
    )
    session.add(review)
    await session.flush()
    return review


async def list_by_finding(
    session: AsyncSession,
    finding_id: uuid.UUID,
) -> list[ReviewAction]:
    """Fetch complete review history for a specific risk finding, newest first.

    Subject to RLS.
    """
    result = await session.execute(
        select(ReviewAction)
        .where(ReviewAction.finding_id == finding_id)
        .order_by(ReviewAction.created_at.desc())
    )
    return list(result.scalars().all())


async def list_by_contract(
    session: AsyncSession,
    contract_id: uuid.UUID,
) -> list[ReviewAction]:
    """Fetch all review actions for a contract, newest first.

    Subject to RLS.
    """
    result = await session.execute(
        select(ReviewAction)
        .where(ReviewAction.contract_id == contract_id)
        .order_by(ReviewAction.created_at.desc())
    )
    return list(result.scalars().all())
