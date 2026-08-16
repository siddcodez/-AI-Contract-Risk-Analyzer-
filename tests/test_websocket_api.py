"""WebSocket API integration tests (Phase 13)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from app.core.security import create_access_token
from app.main import app
from app.models.contract import Contract, ContractStatus
from app.models.user import User, UserRole
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def _make_user(role: UserRole = UserRole.reviewer, org_id: uuid.UUID | None = None) -> User:
    oid = org_id or uuid.uuid4()
    return User(
        id=uuid.uuid4(),
        email=f"user_{role.value}@example.com",
        full_name="Test User",
        role=role,
        org_id=oid,
        password_hash="fakehash",
        is_active=True,
    )


def _make_contract(org_id: uuid.UUID) -> Contract:
    return Contract(
        id=uuid.uuid4(),
        title="Realtime Contract.pdf",
        file_name="realtime.pdf",
        file_size=1024,
        content_type="application/pdf",
        status=ContractStatus.processing,
        org_id=org_id,
        uploaded_by=uuid.uuid4(),
    )


def test_websocket_connection_rejected_without_token() -> None:
    """Connecting to WebSocket without token is immediately rejected."""
    client = TestClient(app)
    cid = uuid.uuid4()

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/api/v1/ws/contracts/{cid}"):
            pass
    assert exc.value.code == 1008


def test_websocket_connection_rejected_for_cross_tenant_contract() -> None:
    """Valid JWT token cannot connect to another organization's contract WebSocket."""
    user = _make_user(org_id=uuid.uuid4())
    other_org_contract = _make_contract(org_id=uuid.uuid4())

    token = create_access_token(
        user_id=str(user.id),
        org_id=str(user.org_id),
        role=user.role.value,
    )
    client = TestClient(app)

    with (
        patch(
            "app.repositories.user_repo.get_by_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.api.v1.websocket.set_tenant_context",
            new_callable=AsyncMock,
        ) as mock_set_ctx,
        patch(
            "app.repositories.contract_repo.get_by_id",
            new=AsyncMock(return_value=None),  # RLS returns None for other tenant
        ),
    ):
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(
                f"/api/v1/ws/contracts/{other_org_contract.id}?token={token}"
            ):
                pass
        assert exc.value.code == 1008
        mock_set_ctx.assert_awaited_once()


def test_websocket_connection_accepted_and_pings() -> None:
    """Valid JWT and authorized contract handshake successfully connects and answers ping."""
    user = _make_user(org_id=uuid.uuid4())
    contract = _make_contract(org_id=user.org_id)

    token = create_access_token(
        user_id=str(user.id),
        org_id=str(user.org_id),
        role=user.role.value,
    )
    client = TestClient(app)

    with (
        patch(
            "app.repositories.user_repo.get_by_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.api.v1.websocket.set_tenant_context",
            new_callable=AsyncMock,
        ),
        patch(
            "app.repositories.contract_repo.get_by_id",
            new=AsyncMock(return_value=contract),
        ),
    ):
        with client.websocket_connect(f"/api/v1/ws/contracts/{contract.id}?token={token}") as ws:
            data = ws.receive_json()
            assert data["event"] == "CONNECTED"
            assert data["contract_id"] == str(contract.id)

            ws.send_text("ping")
            resp = ws.receive_text()
            assert resp == "pong"


@pytest.mark.asyncio
async def test_analysis_completion_triggers_websocket_broadcast_and_notification() -> None:
    """Completing an analysis job emits an ANALYSIS_COMPLETED event to the WebSocket
    broadcast manager and dispatches notification if high risk.
    """
    from app.models.analysis_job import AnalysisJob, AnalysisJobStatus
    from app.services import analysis_service

    org_id = uuid.uuid4()
    contract = _make_contract(org_id=org_id)
    job = AnalysisJob(
        id=uuid.uuid4(),
        contract_id=contract.id,
        version_id=uuid.uuid4(),
        org_id=org_id,
        status=AnalysisJobStatus.processing,
    )

    mock_session = AsyncMock()

    with (
        patch("app.services.analysis_service.set_tenant_context", new=AsyncMock()),
        patch("app.repositories.analysis_job_repo.get_by_id", new=AsyncMock(return_value=job)),
        patch(
            "app.repositories.contract_chunk_repo.list_by_contract", new=AsyncMock(return_value=[])
        ),
        patch("app.repositories.risk_finding_repo.delete_by_contract_and_version", new=AsyncMock()),
        patch("app.services.llm_service.analyze_contract_text", return_value=[]),
        patch("app.repositories.risk_finding_repo.bulk_create", new=AsyncMock()),
        patch("app.repositories.contract_repo.get_by_id", new=AsyncMock(return_value=contract)),
        patch(
            "app.services.missing_clause_service.detect_missing_clauses",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.websocket_manager.ws_manager.broadcast_event", new=AsyncMock()
        ) as mock_broadcast,
    ):
        await analysis_service.analyze_contract(mock_session, job.id)
        mock_broadcast.assert_called_once()
        call_kwargs = mock_broadcast.call_args.kwargs
        assert call_kwargs["contract_id"] == str(contract.id)
        assert call_kwargs["event_type"] == "ANALYSIS_COMPLETED"


@pytest.mark.asyncio
async def test_report_generation_triggers_websocket_broadcast_and_notification() -> None:
    """Completing report generation emits a REPORT_GENERATED event to the WebSocket
    broadcast manager and dispatches a notification.
    """
    from app.models.contract_version import ContractVersion
    from app.models.report_job import ReportJob, ReportJobStatus
    from app.services import report_service

    org_id = uuid.uuid4()
    contract = _make_contract(org_id=org_id)
    version = ContractVersion(
        id=uuid.uuid4(),
        contract_id=contract.id,
        version_number=1,
        file_name="report_contract.pdf",
        file_size=1024,
        content_type="application/pdf",
        storage_key="contracts/key.pdf",
        org_id=org_id,
    )
    job = ReportJob(
        id=uuid.uuid4(),
        contract_id=contract.id,
        version_id=version.id,
        org_id=org_id,
        status=ReportJobStatus.processing,
    )

    mock_session = AsyncMock()

    with (
        patch("app.repositories.report_job_repo.get_by_id", new=AsyncMock(return_value=job)),
        patch("app.repositories.report_job_repo.update_status", new=AsyncMock(return_value=job)),
        patch("app.repositories.contract_repo.get_by_id", new=AsyncMock(return_value=contract)),
        patch(
            "app.repositories.contract_version_repo.get_by_id", new=AsyncMock(return_value=version)
        ),
        patch(
            "app.repositories.risk_finding_repo.list_by_contract_and_version",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.repositories.missing_clause_repo.list_by_contract_and_version",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.repositories.review_action_repo.list_by_contract", new=AsyncMock(return_value=[])
        ),
        patch(
            "app.services.report_generator.create_annotated_contract_pdf",
            return_value=b"%PDF-1.4 Fake %%EOF",
        ),
        patch("app.services.storage_service.upload_file", return_value="contracts/key.pdf"),
        patch("app.services.audit_service.log_audit_event", new=AsyncMock()),
        patch(
            "app.services.websocket_manager.ws_manager.broadcast_event", new=AsyncMock()
        ) as mock_broadcast,
        patch(
            "app.services.notification_service.notification_service.dispatch", new=AsyncMock()
        ) as mock_notif,
    ):
        await report_service.execute_report_generation(
            mock_session,
            job_id=job.id,
            user_id=uuid.uuid4(),
            user_email="reviewer@example.com",
        )
        mock_broadcast.assert_called_once()
        call_kwargs = mock_broadcast.call_args.kwargs
        assert call_kwargs["contract_id"] == str(contract.id)
        assert call_kwargs["event_type"] == "REPORT_GENERATED"
        mock_notif.assert_called_once()
