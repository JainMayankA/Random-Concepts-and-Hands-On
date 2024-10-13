"""
Vector clock and operation log for causal ordering.

Vector clocks let each replica track which operations it has seen from
every other site. Before applying a remote op, we verify its causal
dependencies are already satisfied — preventing out-of-order application.

For the editor use case, causal ordering matters for delete operations:
a delete for op_id X must be applied after the insert for X.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VectorClock:
    """
    Maps site_id → logical clock value.
    clock[site] = N means we've seen N operations from that site.
    """
    _clock: dict[str, int] = field(default_factory=dict)

    def increment(self, site_id: str) -> int:
        self._clock[site_id] = self._clock.get(site_id, 0) + 1
        return self._clock[site_id]

    def update(self, other: "VectorClock"):
        for site, val in other._clock.items():
            self._clock[site] = max(self._clock.get(site, 0), val)

    def get(self, site_id: str) -> int:
        return self._clock.get(site_id, 0)

    def dominates(self, other: "VectorClock") -> bool:
        """True if self has seen everything other has seen (and possibly more)."""
        return all(
            self._clock.get(site, 0) >= val
            for site, val in other._clock.items()
        )

    def concurrent_with(self, other: "VectorClock") -> bool:
        """True if neither clock dominates the other — events are concurrent."""
        return not self.dominates(other) and not other.dominates(self)

    def to_dict(self) -> dict:
        return dict(self._clock)

    @classmethod
    def from_dict(cls, d: dict) -> "VectorClock":
        vc = cls()
        vc._clock = dict(d)
        return vc

    def __repr__(self) -> str:
        return f"VectorClock({self._clock})"


@dataclass
class Operation:
    op_id: str
    site_id: str
    clock: VectorClock
    payload: dict        # the raw insert/delete dict


class OperationLog:
    """
    Append-only log of all operations applied to a document.
    Used for:
      - Replaying history to new clients (delta sync)
      - Detecting missing ops from a peer's vector clock
      - Providing undo/redo history
    """

    def __init__(self):
        self._ops: list[Operation] = []
        self._by_id: dict[str, Operation] = {}

    def append(self, op: Operation):
        self._ops.append(op)
        self._by_id[op.op_id] = op

    def get(self, op_id: str) -> Optional[Operation]:
        return self._by_id.get(op_id)

    def ops_since(self, client_clock: VectorClock) -> list[Operation]:
        """Return all ops the client hasn't seen yet based on its vector clock."""
        missing = []
        for op in self._ops:
            seen = client_clock.get(op.site_id)
            op_seq = int(op.op_id.split(":")[-1]) + 1  # 0-indexed → 1-indexed count
            if op_seq > seen:
                missing.append(op)
        return missing

    def __len__(self) -> int:
        return len(self._ops)
