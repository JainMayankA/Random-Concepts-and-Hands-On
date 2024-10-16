"""
WebSocket server for real-time collaborative editing.

Protocol (JSON messages over WS):
  Client → Server:
    { "type": "join",   "doc_id": "...", "username": "...", "color": "...", "clock": {...} }
    { "type": "op",     "data": { insert/delete op } }
    { "type": "cursor", "pos": 42 }
    { "type": "ping" }

  Server → Client:
    { "event": "full_sync",  "text": "...", "op_count": N, "presence": [...] }
    { "event": "delta_sync", "ops": [...], "presence": [...] }
    { "event": "op",         "data": {...}, "sender": "..." }
    { "event": "cursor",     "client_id": "...", "pos": N, "color": "...", "username": "..." }
    { "event": "presence",   "clients": [...] }
    { "event": "pong" }
    { "event": "error",      "message": "..." }
"""

from __future__ import annotations
import asyncio
import json
import logging
import uuid
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from server.session import DocumentSession

logger = logging.getLogger(__name__)

# Palette for auto-assigning cursor colors
CURSOR_COLORS = [
    "#EF4444", "#F97316", "#EAB308", "#22C55E",
    "#3B82F6", "#8B5CF6", "#EC4899", "#14B8A6",
]


class SessionManager:
    """Global registry of active document sessions."""

    def __init__(self):
        self._sessions: dict[str, DocumentSession] = {}
        self._color_counters: dict[str, int] = {}

    def get_or_create(self, doc_id: str) -> DocumentSession:
        if doc_id not in self._sessions:
            self._sessions[doc_id] = DocumentSession(doc_id)
            logger.info(f"Created new session for doc: {doc_id}")
        return self._sessions[doc_id]

    def cleanup(self, doc_id: str):
        session = self._sessions.get(doc_id)
        if session and session.client_count == 0:
            del self._sessions[doc_id]
            logger.info(f"Destroyed empty session for doc: {doc_id}")

    def next_color(self, doc_id: str) -> str:
        idx = self._color_counters.get(doc_id, 0)
        color = CURSOR_COLORS[idx % len(CURSOR_COLORS)]
        self._color_counters[doc_id] = idx + 1
        return color

    @property
    def active_sessions(self) -> int:
        return len(self._sessions)

    def stats(self) -> dict:
        return {
            "sessions": self.active_sessions,
            "clients": sum(s.client_count for s in self._sessions.values()),
            "docs": list(self._sessions.keys()),
        }


manager = SessionManager()


async def handle_websocket(websocket: WebSocket, doc_id: str):
    await websocket.accept()
    client_id = str(uuid.uuid4())[:8]
    session: Optional[DocumentSession] = None
    queue: Optional[asyncio.Queue] = None

    async def sender():
        """Pump outbound messages from queue to WebSocket."""
        while True:
            msg = await queue.get()
            try:
                await websocket.send_text(msg)
            except Exception:
                break

    sender_task = None

    try:
        # First message must be a join
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        msg = json.loads(raw)

        if msg.get("type") != "join":
            await websocket.send_text(json.dumps({"event": "error", "message": "First message must be type=join"}))
            return

        username = msg.get("username", f"User-{client_id}")
        session = manager.get_or_create(doc_id)
        color = msg.get("color") or manager.next_color(doc_id)
        client_clock = msg.get("clock")

        queue = session.add_client(client_id, username, color)
        sender_task = asyncio.create_task(sender())

        # Send initial state (full sync or delta sync if reconnecting)
        initial = session.initial_state(client_clock)
        await websocket.send_text(json.dumps(initial))
        await session.broadcast_presence()

        # Main message loop
        async for raw_msg in websocket.iter_text():
            try:
                msg = json.loads(raw_msg)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")

            if msg_type == "op":
                await session.apply_operation(msg.get("data", {}), client_id)

            elif msg_type == "cursor":
                await session.update_cursor(client_id, msg.get("pos", 0))

            elif msg_type == "ping":
                await websocket.send_text(json.dumps({"event": "pong"}))

    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {e}", exc_info=True)
    finally:
        if sender_task:
            sender_task.cancel()
        if session:
            session.remove_client(client_id)
            manager.cleanup(doc_id)
            await session.broadcast_presence()
