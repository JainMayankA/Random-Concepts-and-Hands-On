"""
Tests for vector clock causal tracking and document session management.
"""

import asyncio
import pytest
from crdt.vector_clock import VectorClock, OperationLog, Operation


class TestVectorClock:
    def test_increment_starts_at_one(self):
        vc = VectorClock()
        val = vc.increment("A")
        assert val == 1

    def test_increment_increases_per_site(self):
        vc = VectorClock()
        vc.increment("A")
        val = vc.increment("A")
        assert val == 2

    def test_different_sites_independent(self):
        vc = VectorClock()
        vc.increment("A")
        val_b = vc.increment("B")
        assert val_b == 1
        assert vc.get("A") == 1

    def test_update_takes_max(self):
        vc1 = VectorClock()
        vc1.increment("A")
        vc1.increment("A")   # A=2

        vc2 = VectorClock()
        vc2.increment("A")   # A=1
        vc2.increment("B")   # B=1

        vc1.update(vc2)
        assert vc1.get("A") == 2   # max(2,1)
        assert vc1.get("B") == 1   # max(0,1)

    def test_dominates_when_all_greater_or_equal(self):
        vc1 = VectorClock.from_dict({"A": 3, "B": 2})
        vc2 = VectorClock.from_dict({"A": 2, "B": 1})
        assert vc1.dominates(vc2)
        assert not vc2.dominates(vc1)

    def test_concurrent_when_neither_dominates(self):
        vc1 = VectorClock.from_dict({"A": 3, "B": 1})
        vc2 = VectorClock.from_dict({"A": 1, "B": 3})
        assert vc1.concurrent_with(vc2)

    def test_serialization_roundtrip(self):
        vc = VectorClock.from_dict({"A": 5, "B": 3})
        restored = VectorClock.from_dict(vc.to_dict())
        assert restored.get("A") == 5
        assert restored.get("B") == 3

    def test_empty_clock_dominated_by_any(self):
        empty = VectorClock()
        nonempty = VectorClock.from_dict({"A": 1})
        assert nonempty.dominates(empty)


class TestOperationLog:
    def _make_op(self, op_id: str, site_id: str, seq: int) -> Operation:
        return Operation(
            op_id=f"{site_id}:{seq}",
            site_id=site_id,
            clock=VectorClock.from_dict({site_id: seq + 1}),
            payload={"type": "insert", "op_id": f"{site_id}:{seq}"},
        )

    def test_append_and_length(self):
        log = OperationLog()
        log.append(self._make_op("A:0", "A", 0))
        log.append(self._make_op("A:1", "A", 1))
        assert len(log) == 2

    def test_get_by_id(self):
        log = OperationLog()
        op = self._make_op("A:0", "A", 0)
        log.append(op)
        assert log.get("A:0") is op

    def test_get_missing_returns_none(self):
        log = OperationLog()
        assert log.get("nonexistent") is None

    def test_ops_since_returns_unseen(self):
        log = OperationLog()
        for i in range(5):
            log.append(self._make_op(f"A:{i}", "A", i))

        # Client has seen 0,1,2 from A → should get 3,4
        client_clock = VectorClock.from_dict({"A": 3})
        missing = log.ops_since(client_clock)
        assert len(missing) == 2
        assert missing[0].op_id == "A:3"
        assert missing[1].op_id == "A:4"

    def test_ops_since_empty_clock_returns_all(self):
        log = OperationLog()
        for i in range(3):
            log.append(self._make_op(f"A:{i}", "A", i))
        missing = log.ops_since(VectorClock())
        assert len(missing) == 3
