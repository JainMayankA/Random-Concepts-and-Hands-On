"""
Logoot CRDT — conflict-free replicated sequence for collaborative text editing.

Core insight: instead of storing character indices (which shift when others
insert before them), each character gets a globally unique, totally-ordered
*position identifier*. Two concurrent inserts can never conflict because
positions are always distinguishable regardless of insertion order.

Position identifier: list of (int, site_id) pairs — a path in a virtual tree.
  - Positions are ordered lexicographically: compare component by component.
  - Between any two positions there are infinitely many others (dense order).
  - site_id breaks ties when integer components are equal.

Operations:
  - Insert(position, char, op_id)  — add char at position
  - Delete(op_id)                  — tombstone by op_id (lazy deletion)

Convergence guarantee: any two replicas that have received the same set of
operations will reach identical state, regardless of delivery order.
"""

from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True, order=True)
class PositionComponent:
    value: int
    site_id: str


Position = tuple[PositionComponent, ...]   # type alias

# Sentinels bounding the position space
_MIN_POS: Position = (PositionComponent(0, ""),)
_MAX_POS: Position = (PositionComponent(2**31 - 1, "~"),)

BASE = 32       # branching factor per level
BOUNDARY = 10   # max gap to allocate within before going deeper


@dataclass
class Entry:
    position: Position
    char: str
    op_id: str
    deleted: bool = False


def _between(p: Position, q: Position, site_id: str, depth: int = 0) -> Position:
    """
    Allocate a new position strictly between p and q.
    Uses the boundary+ strategy: prefer allocating near the left boundary
    to keep position lengths short for typical left-to-right editing.
    """
    p_val = p[depth].value if depth < len(p) else 0
    q_val = q[depth].value if depth < len(q) else (2**31 - 1)

    p_site = p[depth].site_id if depth < len(p) else ""
    q_site = q[depth].site_id if depth < len(q) else "~"

    gap = q_val - p_val

    if gap > 1:
        # Enough room at this level — pick a value in (p_val, q_val)
        step = min(BOUNDARY, gap - 1)
        new_val = p_val + random.randint(1, step)
        return p[:depth] + (PositionComponent(new_val, site_id),)

    if gap == 1:
        # No room between p_val and q_val at this level — go one level deeper
        if depth < len(p) - 1:
            sub = _between(p, _MAX_POS, site_id, depth + 1)
            return p[:depth] + (PositionComponent(p_val, p_site),) + sub[depth:]
        else:
            return p + (PositionComponent(random.randint(1, BASE), site_id),)

    # p_val == q_val — same integer, break tie by going deeper
    return _between(p, q, site_id, depth + 1)


class LogootDoc:
    """
    A replicated document built on the Logoot CRDT.

    State: sorted list of Entry objects (including tombstones).
    External operations are pure — they return an Op dict that can be
    broadcast to other replicas and applied via apply_remote().
    """

    def __init__(self, site_id: str):
        self.site_id = site_id
        self._entries: list[Entry] = [
            Entry(_MIN_POS, "", "__start__"),
            Entry(_MAX_POS, "", "__end__"),
        ]
        self._op_index: dict[str, Entry] = {}
        self._clock = 0

    # ── Local operations ──────────────────────────────────────────────

    def insert(self, index: int, char: str) -> dict:
        """
        Insert char at visible position index (0-based, ignoring tombstones).
        Returns an Op dict to broadcast to peers.
        """
        visible = self._visible_entries()
        left_entry  = visible[index]        # entry to the left of insertion point
        right_entry = visible[index + 1]    # entry to the right

        pos = _between(left_entry.position, right_entry.position, self.site_id)
        op_id = f"{self.site_id}:{self._clock}"
        self._clock += 1

        entry = Entry(position=pos, char=char, op_id=op_id)
        self._insert_entry(entry)
        return {"type": "insert", "position": _pos_to_list(pos),
                "char": char, "op_id": op_id, "site_id": self.site_id}

    def delete(self, index: int) -> dict:
        """
        Delete the character at visible position index.
        Returns an Op dict to broadcast to peers.
        """
        visible = self._visible_entries()
        # index + 1 because index 0 is the __start__ sentinel
        entry = visible[index + 1]
        entry.deleted = True
        return {"type": "delete", "op_id": entry.op_id, "site_id": self.site_id}

    # ── Remote operations ─────────────────────────────────────────────

    def apply_remote(self, op: dict):
        """Apply an operation received from another replica."""
        if op["type"] == "insert":
            pos = _pos_from_list(op["position"])
            if op["op_id"] not in self._op_index:
                entry = Entry(pos, op["char"], op["op_id"])
                self._insert_entry(entry)
        elif op["type"] == "delete":
            entry = self._op_index.get(op["op_id"])
            if entry:
                entry.deleted = True

    # ── Read ──────────────────────────────────────────────────────────

    def text(self) -> str:
        return "".join(
            e.char for e in self._entries
            if not e.deleted and e.op_id not in ("__start__", "__end__")
        )

    def __len__(self) -> int:
        return len(self._visible_entries()) - 2  # subtract sentinels

    # ── Internals ─────────────────────────────────────────────────────

    def _insert_entry(self, entry: Entry):
        import bisect
        keys = [e.position for e in self._entries]
        idx = bisect.bisect_left(keys, entry.position)
        self._entries.insert(idx, entry)
        self._op_index[entry.op_id] = entry

    def _visible_entries(self) -> list[Entry]:
        return [e for e in self._entries if not e.deleted]


def _pos_to_list(pos: Position) -> list[list]:
    return [[c.value, c.site_id] for c in pos]


def _pos_from_list(data: list[list]) -> Position:
    return tuple(PositionComponent(c[0], c[1]) for c in data)
