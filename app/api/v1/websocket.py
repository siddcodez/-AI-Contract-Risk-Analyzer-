"""WebSocket API endpoints for realtime contract processing status (Phase 13).

Provides:
- WebSocket endpoint `/api/v1/ws/contracts/{contract_id}`
- Pre-accept JWT authentication + tenant authorization
- Immediate disconnect on invalid tokens or cross-tenant contract access
"""

import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.logging import get_logger
from app.core.security import decode_access_token
from app.db.session import _get_session_factory, set_tenant_context
from app.models.user import User
from app.repositories import contract_repo, user_repo
from app.services.websocket_manager import ws_manager

logger = get_logger(__name__)

router = APIRouter(tags=["websocket"])


async def _authenticate_websocket(
    websocket: WebSocket,
    token: str | None,
    contract_id: uuid.UUID,
) -> tuple[User | None, bool]:
    """Validate JWT token and contract ownership before accepting the socket."""
    if not token:
        logger.warning("ws_auth_failed_missing_token", client=websocket.client)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing auth token")
        return None, False

    try:
        payload = decode_access_token(token)
    except Exception as exc:
        logger.warning("ws_auth_failed_invalid_jwt", error=str(exc))
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return None, False

    user_id_str = payload.get("sub")
    org_id_str = payload.get("org_id")
    if not user_id_str or not org_id_str:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token payload")
        return None, False

    from app.db.session import _session_factory, init_db

    if _session_factory is None:
        init_db()

    session_factory = _get_session_factory()
    async with session_factory() as session:
        # Set tenant RLS context first so subsequent user and contract lookups succeed under RLS
        await set_tenant_context(session, org_id_str)

        user = await user_repo.get_by_id(session, uuid.UUID(user_id_str))
        if user is None or not user.is_active:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User inactive")
            return None, False

        contract = await contract_repo.get_by_id(session, contract_id)
        if contract is None:
            # Contract does not exist or belongs to another tenant
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Contract not found or access denied",
            )
            return None, False

        return user, True


@router.websocket("/ws/contracts/{contract_id}")
async def contract_events_websocket(
    websocket: WebSocket,
    contract_id: uuid.UUID,
    token: str | None = Query(None, description="JWT Bearer token for handshake authentication"),
) -> None:
    """WebSocket endpoint for receiving real-time contract processing events.

    Accepts connection only after verifying JWT and contract tenant access.
    """
    user, is_authorized = await _authenticate_websocket(websocket, token, contract_id)
    if not is_authorized or user is None:
        return

    cid_str = str(contract_id)
    await ws_manager.connect(cid_str, websocket)

    try:
        # Initial greeting / connection confirmed
        await websocket.send_json(
            {
                "event": "CONNECTED",
                "contract_id": cid_str,
                "user_email": user.email,
            }
        )

        # Keep connection open waiting for client ping or server broadcast
        while True:
            # Client can send ping
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(cid_str, websocket)
    except Exception as exc:
        logger.info("ws_connection_closed", contract_id=cid_str, error=str(exc))
        ws_manager.disconnect(cid_str, websocket)
