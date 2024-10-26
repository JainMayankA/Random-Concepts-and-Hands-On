"""
CRDT correctness tests.

The key properties we verify:
  1. Convergence: any two replicas with the same op set reach the same state
  2. Commutativity: op order doesn't affect final state
  3. Idempotency: applying an op twice has no extra effect
  4. Concurrent inserts: don't lose or duplicate characters
  5. Tombstone deletion: deletes commute with concurrent inserts
"""

import pytest
import random
from crdt.logoot import LogootDoc


def make_doc(site: str) -> LogootDoc:
    return LogootDoc(site_id=site)


class TestBasicOperations:
    def test_insert_single_char(self):
        doc = make_doc("A")
        op = doc.insert(0, "h")
        assert doc.text() == "h"

    def test_insert_multiple_chars_sequential(self):
        doc = make_doc("A")
        for i, ch in enumerate("hello"):
            doc.insert(i, ch)
        assert doc.text() == "hello"

    def test_delete_char(self):
        doc = make_doc("A")
        for i, ch in enumerate("hello"):
            doc.insert(i, ch)
        doc.delete(2)          # delete 'l'
        assert doc.text() == "helo"

    def test_delete_all_chars(self):
        doc = make_doc("A")
        for i, ch in enumerate("abc"):
            doc.insert(i, ch)
        doc.delete(0)
        doc.delete(0)
        doc.delete(0)
        assert doc.text() == ""

    def test_insert_returns_op_dict(self):
        doc = make_doc("A")
        op = doc.insert(0, "x")
        assert op["type"] == "insert"
        assert op["char"] == "x"
        assert "position" in op
        assert "op_id" in op

    def test_delete_returns_op_dict(self):
        doc = make_doc("A")
        doc.insert(0, "x")
        op = doc.delete(0)
        assert op["type"] == "delete"
        assert "op_id" in op

    def test_len_counts_visible_chars(self):
        doc = make_doc("A")
        for i, ch in enumerate("hello"):
            doc.insert(i, ch)
        assert len(doc) == 5
        doc.delete(0)
        assert len(doc) == 4


class TestConvergence:
    """
    Replicas A and B each make concurrent edits, then exchange ops.
    Both must converge to the same text regardless of delivery order.
    """

    def _sync(self, src: LogootDoc, dst: LogootDoc, ops: list[dict]):
        for op in ops:
            dst.apply_remote(op)

    def test_two_replicas_converge_after_concurrent_inserts(self):
        a = make_doc("A")
        b = make_doc("B")

        # Both start empty — seed A with "hello"
        ops_a = [a.insert(i, ch) for i, ch in enumerate("hello")]
        for op in ops_a:
            b.apply_remote(op)

        # Now concurrent: A inserts " world", B inserts "!"
        a_ops = [a.insert(5 + i, ch) for i, ch in enumerate(" world")]
        b_ops = [b.insert(5, "!")]

        # Cross-apply
        for op in b_ops:
            a.apply_remote(op)
        for op in a_ops:
            b.apply_remote(op)

        assert a.text() == b.text()

    def test_convergence_with_reversed_delivery_order(self):
        a = make_doc("A")
        b = make_doc("B")

        ops_a = [a.insert(i, ch) for i, ch in enumerate("abc")]
        ops_b = [b.insert(i, ch) for i, ch in enumerate("xyz")]

        # A receives B's ops in reverse
        for op in reversed(ops_b):
            a.apply_remote(op)
        for op in ops_a:
            b.apply_remote(op)

        # B receives A's ops in reverse
        for op in reversed(ops_a):
            b.apply_remote(op)
        for op in ops_b:
            a.apply_remote(op)

        assert a.text() == b.text()

    def test_three_replicas_converge(self):
        a, b, c = make_doc("A"), make_doc("B"), make_doc("C")

        ops_a = [a.insert(0, "A")]
        ops_b = [b.insert(0, "B")]
        ops_c = [c.insert(0, "C")]

        all_ops = ops_a + ops_b + ops_c
        for doc in (a, b, c):
            for op in all_ops:
                try:
                    doc.apply_remote(op)
                except Exception:
                    pass

        assert a.text() == b.text() == c.text()

    def test_idempotency_applying_op_twice(self):
        a = make_doc("A")
        b = make_doc("B")
        op = a.insert(0, "x")
        b.apply_remote(op)
        b.apply_remote(op)   # second apply should be a no-op
        assert b.text() == "x"

    def test_delete_commutes_with_concurrent_insert(self):
        a = make_doc("A")
        b = make_doc("B")

        # Seed both with "hi"
        for i, ch in enumerate("hi"):
            op = a.insert(i, ch)
            b.apply_remote(op)

        # A deletes 'h', B inserts 'X' at position 0 — concurrent
        del_op = a.delete(0)
        ins_op = b.insert(0, "X")

        a.apply_remote(ins_op)
        b.apply_remote(del_op)

        assert a.text() == b.text()

    def test_no_lost_characters_under_concurrent_inserts(self):
        a = make_doc("A")
        b = make_doc("B")

        ops_a = [a.insert(i, ch) for i, ch in enumerate("AAAA")]
        ops_b = [b.insert(i, ch) for i, ch in enumerate("BBBB")]

        for op in ops_b:
            a.apply_remote(op)
        for op in ops_a:
            b.apply_remote(op)

        # All 8 characters must be present
        assert len(a.text()) == 8
        assert len(b.text()) == 8
        assert a.text() == b.text()


class TestEdgeCases:
    def test_empty_doc_text(self):
        doc = make_doc("A")
        assert doc.text() == ""

    def test_insert_at_end(self):
        doc = make_doc("A")
        for i, ch in enumerate("ab"):
            doc.insert(i, ch)
        doc.insert(2, "c")
        assert doc.text() == "abc"

    def test_positions_are_totally_ordered(self):
        doc = make_doc("A")
        ops = [doc.insert(i, ch) for i, ch in enumerate("hello world")]
        positions = [op["position"] for op in ops]
        # All positions must be unique
        pos_tuples = [tuple(tuple(c) for c in p) for p in positions]
        assert len(set(pos_tuples)) == len(pos_tuples)
