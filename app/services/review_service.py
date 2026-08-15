"""Review service — orchestrates human reviewer decisions and audit logs."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.audit_log import AuditActionType
from app.models.review_action import ReviewAction
from app.models.user import User
from app.repositories import contract_repo, review_action_repo, risk_finding_repo
from app.services import audit_service


async def submit_review_action(
    session: AsyncSession,
    *,
    contract_id: uuid.UUID,
    finding_id: uuid.UUID,
    user: User,
    action: str,
    comment: str | None = None,
    ip_address: str | None = None,
) -> ReviewAction:
    """Submit a reviewer decision on a risk finding within a single atomic transaction.

    1. Validates contract and finding exist (RLS-scoped).
    2. Updates finding status (approved/rejected).
    3. Records append-only ReviewAction entry.
    4. Writes AuditLog event (CLAUSE_APPROVED or CLAUSE_REJECTED).
    """
    # 1. Validate contract exists
    contract = await contract_repo.get_by_id(session, contract_id)
    if contract is None:
        raise NotFoundError("Contract not found")

    # 2. Validate finding exists and belongs to contract
    finding = await risk_finding_repo.get_by_id(session, finding_id)
    if finding is None or finding.contract_id != contract_id:
        raise NotFoundError("Risk finding not found")

    norm_action = action.strip().lower()

    # 3. Update finding status in-place
    finding.status = norm_action

    # 4. Append ReviewAction row
    review = await review_action_repo.create(
        session,
        contract_id=contract_id,
        finding_id=finding_id,
        reviewer_id=user.id,
        org_id=user.org_id,
        action=norm_action,
        comment=comment,
    )

    # 5. Write audit log entry in the same transaction
    audit_action = (
        AuditActionType.CLAUSE_APPROVED
        if norm_action == "approved"
        else AuditActionType.CLAUSE_REJECTED
    )
    cat_str = (
        finding.category.value if hasattr(finding.category, "value") else str(finding.category)
    )
    await audit_service.log_audit_event(
        session,
        org_id=user.org_id,
        action=audit_action,
        entity_type="risk_finding",
        entity_id=finding.id,
        user_id=user.id,
        user_email=user.email,
        metadata_json={
            "contract_id": str(contract_id),
            "contract_title": contract.title,
            "finding_category": cat_str,
            "action": norm_action,
            "has_comment": bool(comment),
        },
        ip_address=ip_address,
    )

    await session.commit()
    return review
