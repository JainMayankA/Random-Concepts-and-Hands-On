"""
Document session — manages a single collaborative document.

Responsibilities:
  - Owns one LogootDoc per document
  - Tracks which WebSocket clients are connected
  - Broadcasts operations to all peers
  - Maintains cursor/presence state per client
  - Handles delta sync when a client reconnects after offline
"""

from __future__ import annotations
import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from crdt.logoot import LogootDoc
from crdt.vector_clock import Operation, OperationLog, VectorClock

logger = logging.getLogger(__name__)


@dataclass
class ClientPresence:
    client_id: str
    username: str
    cursor_pos: int = 0
    color: str = "#3B82F6"
    last_seen: float = 0.0


class DocumentSession:
    """
    A live editing session for one document.
    One session per doc_id — created on first connect, destroyed when empty.
    """

    def __init__(self, doc_id: str):
        self.doc_id = doc_id
        self._doc = LogootDoc(site_id=f"server-{doc_id[:8]}")
        self._op_log = OperationLog()
        self._clients: dict[str, "asyncio.Queue"] = {}   # client_id → message queue
        self._presence: dict[str, ClientPresence] = {}

    # ── Client lifecycle ──────────────────────────────────────────────

    def add_client(self, client_id: str, username: str, color: str) -> asyncio.Queue:
        import time
        q: asyncio.Queue = asyncio.Queue()
        self._clients[client_id] = q
        self._presence[client_id] = ClientPresence(
            client_id=client_id,
            username=username,
            color=color,
            last_seen=time.time(),
        )
        logger.info(f"[{self.doc_id}] Client joined: {username} ({client_id})")
        return q

    def remove_client(self, client_id: str):
        self._clients.pop(client_id, None)
        self._presence.pop(client_id, None)
        logger.info(f"[{self.doc_id}] Client left: {client_id}")

    @property
    def client_count(self) -> int:
        return len(self._clients)

    # ── Operation handling ────────────────────────────────────────────

    async def apply_operation(self, op_dict: dict, sender_id: str):
        """Apply an op from a client and broadcast to all other clients."""
        op_type = op_dict.get("type")

        if op_type in ("insert", "delete"):
            self._doc.apply_remote(op_dict)
            op = Operation(
                op_id=op_dict.get("op_id", ""),
                site_id=op_dict.get("site_id", sender_id),
                clock=VectorClock(),
                payload=op_dict,
            )
            self._op_log.append(op)

        msg = json.dumps({"event": "op", "data": op_dict, "sender": sender_id})
        await self._broadcast(msg, exclude=sender_id)

    async def update_cursor(self, client_id: str, pos: int):
        if client_id in self._presence:
            self._presence[client_id].cursor_pos = pos
        msg = json.dumps({
            "event": "cursor",
            "client_id": client_id,
            "pos": pos,
            "color": self._presence[client_id].color if client_id in self._presence else "#888",
            "username": self._presence[client_id].username if client_id in self._presence else "?",
        })
        await self._broadcast(msg, exclude=client_id)

    # ── Initial sync ──────────────────────────────────────────────────

    def initial_state(self, client_clock: Optional[dict] = None) -> dict:
        """
        Returns what a newly connecting client needs.
        If client_clock is provided (reconnect), returns only the delta.
        Otherwise returns the full document text + all ops.
        """
        if client_clock:
            vc = VectorClock.from_dict(client_clock)
            missing = self._op_log.ops_since(vc)
            return {
                "type": "delta_sync",
                "ops": [op.payload for op in missing],
                "presence": self._presence_list(),
            }
        return {
            "type": "full_sync",
            "text": self._doc.text(),
            "op_count": len(self._op_log),
            "presence": self._presence_list(),
        }

    # ── Broadcast ─────────────────────────────────────────────────────

    async def _broadcast(self, message: str, exclude: Optional[str] = None):
        for client_id, queue in list(self._clients.items()):
            if client_id != exclude:
                try:
                    queue.put_nowait(message)
                except asyncio.QueueFull:
                    logger.warning(f"Queue full for client {client_id}, dropping message")

    async def broadcast_presence(self):
        msg = json.dumps({"event": "presence", "clients": self._presence_list()})
        await self._broadcast(msg)

    def _presence_list(self) -> list[dict]:
        return [
            {
                "client_id": p.client_id,
                "username": p.username,
                "cursor_pos": p.cursor_pos,
                "color": p.color,
            }
            for p in self._presence.values()
        ]

    @property
    def text(self) -> str:
        return self._doc.text()
