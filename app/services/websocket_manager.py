"""WebSocket Connection Manager and Redis PubSub broadcaster for realtime contract updates.

Provides cross-process / cross-instance broadcast using Redis Pub/Sub so Celery workers
running in independent processes or containers can emit events directly to connected
WebSocket clients on any FastAPI server instance.
"""

import asyncio
import json
from typing import Any

import redis.asyncio as aioredis
from fastapi import WebSocket

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections grouped by contract_id."""

    def __init__(self) -> None:
        # contract_id -> set of active WebSocket instances
        self.active_connections: dict[str, set[WebSocket]] = {}
        self._pubsub_task: asyncio.Task[None] | None = None
        self._redis_client: aioredis.Redis | None = None

    async def connect(self, contract_id: str, websocket: WebSocket) -> None:
        """Register an active connection."""
        await websocket.accept()
        if contract_id not in self.active_connections:
            self.active_connections[contract_id] = set()
        self.active_connections[contract_id].add(websocket)
        logger.info("websocket_connected", contract_id=contract_id, client=websocket.client)

    def disconnect(self, contract_id: str, websocket: WebSocket) -> None:
        """Unregister a disconnected connection."""
        if contract_id in self.active_connections:
            self.active_connections[contract_id].discard(websocket)
            if not self.active_connections[contract_id]:
                del self.active_connections[contract_id]
        logger.info("websocket_disconnected", contract_id=contract_id)

    async def send_local(self, contract_id: str, message: dict[str, Any]) -> None:
        """Send message directly to locally connected WebSockets for a contract."""
        conns = list(self.active_connections.get(contract_id, set()))
        if not conns:
            return

        dead_connections: list[WebSocket] = []
        payload_text = json.dumps(message)

        for ws in conns:
            try:
                await ws.send_text(payload_text)
            except Exception as exc:
                logger.warning(
                    "ws_send_failed_disconnecting",
                    contract_id=contract_id,
                    exc_info=exc,
                )
                dead_connections.append(ws)

        for dead_ws in dead_connections:
            self.disconnect(contract_id, dead_ws)

    async def broadcast_event(
        self, contract_id: str, event_type: str, data: dict[str, Any]
    ) -> None:
        """Publish an event to Redis Pub/Sub for cross-instance fanout.

        Falls back to local broadcast if Redis is unavailable.
        """
        payload = {
            "event": event_type,
            "contract_id": contract_id,
            "data": data,
        }

        settings = get_settings()
        try:
            client = aioredis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
            channel = f"contract_events:{contract_id}"
            await client.publish(channel, json.dumps(payload))
            await client.aclose()
        except Exception as exc:
            logger.warning("redis_publish_failed_fallback_local", error=str(exc))
            # Fallback to local dispatch
            await self.send_local(contract_id, payload)


# Global singleton instance
ws_manager = ConnectionManager()
