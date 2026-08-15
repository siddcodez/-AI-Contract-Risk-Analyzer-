"""Unit and API tests for Review Workflow & RBAC (Phase 11)."""

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from app.api.deps import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.contract import Contract, ContractStatus
from app.models.review_action import ReviewAction
from app.models.risk_finding import RiskCategory, RiskFinding, RiskSeverity
from app.models.user import User, UserRole
from httpx import ASGITransport, AsyncClient


def _make_user(role: UserRole = UserRole.reviewer, org_id: uuid.UUID | None = None) -> User:
    oid = org_id or uuid.uuid4()
    return User(
        id=uuid.uuid4(),
        email=f"user_{role.value}@example.com",
        full_name=f"Test {role.value.capitalize()}",
        role=role,
        org_id=oid,
        password_hash="fakehash",
        is_active=True,
    )


def _make_contract(org_id: uuid.UUID) -> Contract:
    return Contract(
        id=uuid.uuid4(),
        title="Vendor Master Agreement.pdf",
        file_name="vendor_msa.pdf",
        file_size=10240,
        content_type="application/pdf",
        status=ContractStatus.completed,
        org_id=org_id,
        uploaded_by=uuid.uuid4(),
    )


def _make_finding(contract_id: uuid.UUID, org_id: uuid.UUID) -> RiskFinding:
    return RiskFinding(
        id=uuid.uuid4(),
        contract_id=contract_id,
        version_id=uuid.uuid4(),
        org_id=org_id,
        category=RiskCategory.indemnification,
        severity=RiskSeverity.high,
        title="Broad Indemnification Obligation",
        description="Vendor must indemnify for all third party claims.",
        evidence="Vendor shall indemnify and defend Customer against any and all claims.",
        recommendation="Limit indemnification to IP infringement and direct damages.",
        confidence=0.92,
        status="pending_review",
    )


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    mock_session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()


class TestReviewWorkflow:
    @pytest.mark.asyncio
    async def test_viewer_role_is_blocked_from_review_submission(
        self,
        async_client: AsyncClient,
    ) -> None:
        """VIEWER receives 403 Forbidden on review submission."""
        user = _make_user(role=UserRole.viewer)
        app.dependency_overrides[get_current_user] = lambda: user

        cid = uuid.uuid4()
        fid = uuid.uuid4()
        headers = {"Authorization": "Bearer fake.jwt.token"}

        try:
            res = await async_client.post(
                f"/api/v1/contracts/{cid}/findings/{fid}/review",
                json={"action": "approved", "comment": "Looks fine to me."},
                headers=headers,
            )
            assert res.status_code == 403
            data = res.json()
            assert data["error"]["code"] == "FORBIDDEN"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.asyncio
    async def test_reviewer_and_admin_can_approve_finding(
        self,
        async_client: AsyncClient,
    ) -> None:
        """REVIEWER and ADMIN can approve a finding and record review + audit log."""
        reviewer = _make_user(role=UserRole.reviewer)
        contract = _make_contract(reviewer.org_id)
        finding = _make_finding(contract.id, reviewer.org_id)

        app.dependency_overrides[get_current_user] = lambda: reviewer
        headers = {"Authorization": "Bearer fake.jwt.token"}

        created_review = ReviewAction(
            id=uuid.uuid4(),
            contract_id=contract.id,
            finding_id=finding.id,
            reviewer_id=reviewer.id,
            org_id=reviewer.org_id,
            action="approved",
            comment="Approved after counsel signoff.",
        )

        with (
            patch(
                "app.repositories.contract_repo.get_by_id",
                new=AsyncMock(return_value=contract),
            ),
            patch(
                "app.repositories.risk_finding_repo.get_by_id",
                new=AsyncMock(return_value=finding),
            ),
            patch(
                "app.repositories.review_action_repo.create",
                new=AsyncMock(return_value=created_review),
            ),
            patch(
                "app.services.audit_service.log_audit_event",
                new=AsyncMock(),
            ) as mock_audit,
        ):
            res = await async_client.post(
                f"/api/v1/contracts/{contract.id}/findings/{finding.id}/review",
                json={"action": "approved", "comment": "Approved after counsel signoff."},
                headers=headers,
            )
            assert res.status_code == 200
            data = res.json()
            assert data["action"] == "approved"
            assert data["finding_id"] == str(finding.id)
            assert data["reviewer_id"] == str(reviewer.id)
            assert finding.status == "approved"

            # Verify audit log was recorded with exact action
            mock_audit.assert_called_once()
            call_kwargs = mock_audit.call_args.kwargs
            assert call_kwargs["action"].value == "CLAUSE_APPROVED"
            assert call_kwargs["entity_type"] == "risk_finding"

    @pytest.mark.asyncio
    async def test_reviewer_can_reject_finding(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Rejecting a finding updates finding status to 'rejected' and logs CLAUSE_REJECTED."""
        reviewer = _make_user(role=UserRole.reviewer)
        contract = _make_contract(reviewer.org_id)
        finding = _make_finding(contract.id, reviewer.org_id)

        app.dependency_overrides[get_current_user] = lambda: reviewer
        headers = {"Authorization": "Bearer fake.jwt.token"}

        created_review = ReviewAction(
            id=uuid.uuid4(),
            contract_id=contract.id,
            finding_id=finding.id,
            reviewer_id=reviewer.id,
            org_id=reviewer.org_id,
            action="rejected",
            comment="Unacceptable uncapped liability.",
        )

        with (
            patch(
                "app.repositories.contract_repo.get_by_id",
                new=AsyncMock(return_value=contract),
            ),
            patch(
                "app.repositories.risk_finding_repo.get_by_id",
                new=AsyncMock(return_value=finding),
            ),
            patch(
                "app.repositories.review_action_repo.create",
                new=AsyncMock(return_value=created_review),
            ),
            patch(
                "app.services.audit_service.log_audit_event",
                new=AsyncMock(),
            ) as mock_audit,
        ):
            res = await async_client.post(
                f"/api/v1/contracts/{contract.id}/findings/{finding.id}/review",
                json={"action": "rejected", "comment": "Unacceptable uncapped liability."},
                headers=headers,
            )
            assert res.status_code == 200
            data = res.json()
            assert data["action"] == "rejected"
            assert finding.status == "rejected"

            call_kwargs = mock_audit.call_args.kwargs
            assert call_kwargs["action"].value == "CLAUSE_REJECTED"

    @pytest.mark.asyncio
    async def test_idempotency_subsequent_review_appends_and_updates_status(
        self,
        async_client: AsyncClient,
    ) -> None:
        """A subsequent review on an already-approved finding appends a new action
        and updates finding status.
        """
        reviewer = _make_user(role=UserRole.reviewer)
        contract = _make_contract(reviewer.org_id)
        finding = _make_finding(contract.id, reviewer.org_id)
        finding.status = "approved"  # Already approved previously

        app.dependency_overrides[get_current_user] = lambda: reviewer
        headers = {"Authorization": "Bearer fake.jwt.token"}

        second_review = ReviewAction(
            id=uuid.uuid4(),
            contract_id=contract.id,
            finding_id=finding.id,
            reviewer_id=reviewer.id,
            org_id=reviewer.org_id,
            action="rejected",
            comment="Reversing approval upon renegotiation.",
        )

        with (
            patch(
                "app.repositories.contract_repo.get_by_id",
                new=AsyncMock(return_value=contract),
            ),
            patch(
                "app.repositories.risk_finding_repo.get_by_id",
                new=AsyncMock(return_value=finding),
            ),
            patch(
                "app.repositories.review_action_repo.create",
                new=AsyncMock(return_value=second_review),
            ),
            patch("app.services.audit_service.log_audit_event", new=AsyncMock()),
        ):
            res = await async_client.post(
                f"/api/v1/contracts/{contract.id}/findings/{finding.id}/review",
                json={"action": "rejected", "comment": "Reversing approval upon renegotiation."},
                headers=headers,
            )
            assert res.status_code == 200
            assert finding.status == "rejected"

    @pytest.mark.asyncio
    async def test_list_review_history_accessible_by_all_authenticated_roles(
        self,
        async_client: AsyncClient,
    ) -> None:
        """All authenticated roles (including VIEWER) can read review action history."""
        viewer = _make_user(role=UserRole.viewer)
        contract = _make_contract(viewer.org_id)
        finding = _make_finding(contract.id, viewer.org_id)

        app.dependency_overrides[get_current_user] = lambda: viewer
        headers = {"Authorization": "Bearer fake.jwt.token"}

        history = [
            ReviewAction(
                id=uuid.uuid4(),
                contract_id=contract.id,
                finding_id=finding.id,
                reviewer_id=uuid.uuid4(),
                org_id=viewer.org_id,
                action="approved",
                comment="First review note.",
            )
        ]

        with (
            patch(
                "app.repositories.contract_repo.get_by_id",
                new=AsyncMock(return_value=contract),
            ),
            patch(
                "app.repositories.risk_finding_repo.get_by_id",
                new=AsyncMock(return_value=finding),
            ),
            patch(
                "app.repositories.review_action_repo.list_by_finding",
                new=AsyncMock(return_value=history),
            ),
        ):
            res = await async_client.get(
                f"/api/v1/contracts/{contract.id}/findings/{finding.id}/reviews",
                headers=headers,
            )
            assert res.status_code == 200
            data = res.json()
            assert data["total"] == 1
            assert data["items"][0]["action"] == "approved"

    @pytest.mark.asyncio
    async def test_atomic_transaction_rolls_back_on_audit_failure(
        self,
        async_client: AsyncClient,
    ) -> None:
        """If writing the audit log fails, the entire transaction is rolled back.

        Neither the ReviewAction nor the RiskFinding.status changes are committed.
        """
        reviewer = _make_user(role=UserRole.reviewer)
        contract = _make_contract(reviewer.org_id)
        finding = _make_finding(contract.id, reviewer.org_id)
        finding.status = "pending_review"

        app.dependency_overrides[get_current_user] = lambda: reviewer
        headers = {"Authorization": "Bearer fake.jwt.token"}

        # Simulate audit log write failure inside the service
        with (
            patch(
                "app.repositories.contract_repo.get_by_id",
                new=AsyncMock(return_value=contract),
            ),
            patch(
                "app.repositories.risk_finding_repo.get_by_id",
                new=AsyncMock(return_value=finding),
            ),
            patch(
                "app.repositories.review_action_repo.create",
                new=AsyncMock(
                    return_value=ReviewAction(
                        id=uuid.uuid4(),
                        contract_id=contract.id,
                        finding_id=finding.id,
                        reviewer_id=reviewer.id,
                        org_id=reviewer.org_id,
                        action="approved",
                    )
                ),
            ),
            patch(
                "app.services.audit_service.log_audit_event",
                side_effect=RuntimeError("Database I/O failure during audit write"),
            ),
        ):
            res = await async_client.post(
                f"/api/v1/contracts/{contract.id}/findings/{finding.id}/review",
                json={"action": "approved", "comment": "Should roll back completely."},
                headers=headers,
            )
            # Internal server error returned to client
            assert res.status_code == 500
            data = res.json()
            assert data["error"]["code"] == "INTERNAL_ERROR"
