import pytest
import sqlite3
import json
from unittest.mock import MagicMock, patch
from datetime import datetime

from domain.aggregates.order import Order, OrderStatus
from domain.events import OrderPlaced, OrderConfirmed, OrderShipped
from sagas.order_saga import SagaOrchestrator, OrderService, PaymentService, SagaState

SAMPLE_ITEMS = [
    {"product_id": "p1", "name": "Widget", "quantity": 1, "unit_price": 25.00},
]


# ── Saga tests (no DB needed) ─────────────────────────────────────────────────

class TestOrderSaga:
    def _make_orchestrator(self, payment_fails=False):
        mock_repo = MagicMock()
        mock_order = MagicMock()
        mock_repo.load.return_value = mock_order

        order_svc = OrderService(mock_repo)
        payment_svc = PaymentService()

        if payment_fails:
            payment_svc.authorize = MagicMock(side_effect=ValueError("Card declined"))

        return SagaOrchestrator(order_svc, payment_svc), mock_repo

    def test_successful_saga_completes(self):
        orch, _ = self._make_orchestrator()
        saga = orch.start_order_saga("ord-s1", "cust-1", 100.0)
        assert saga.state == SagaState.COMPLETED
        assert "authorize_payment" in saga.completed_steps
        assert "confirm_order" in saga.completed_steps

    def test_failed_payment_triggers_compensation(self):
        orch, mock_repo = self._make_orchestrator(payment_fails=True)
        saga = orch.start_order_saga("ord-s2", "cust-1", 100.0)
        assert saga.state == SagaState.FAILED
        assert saga.failure_reason != ""

    def test_saga_stored_and_retrievable(self):
        orch, _ = self._make_orchestrator()
        saga = orch.start_order_saga("ord-s3", "cust-1", 50.0)
        retrieved = orch.get_saga(saga.saga_id)
        assert retrieved is not None
        assert retrieved.order_id == "ord-s3"

    def test_amount_over_limit_fails_saga(self):
        orch, _ = self._make_orchestrator()
        saga = orch.start_order_saga("ord-s4", "cust-1", 999_999.0)
        assert saga.state == SagaState.FAILED

    def test_saga_has_unique_id(self):
        orch, _ = self._make_orchestrator()
        s1 = orch.start_order_saga("ord-s5", "cust-1", 10.0)
        s2 = orch.start_order_saga("ord-s6", "cust-1", 10.0)
        assert s1.saga_id != s2.saga_id


# ── Event reconstitution tests ────────────────────────────────────────────────

class TestEventReconstitution:
    def test_order_rebuilt_correctly_from_event_sequence(self):
        events = [
            OrderPlaced(aggregate_id="ord-r1", version=1, customer_id="cust-42",
                        items=tuple(SAMPLE_ITEMS), total_amount=25.0),
            OrderConfirmed(aggregate_id="ord-r1", version=2, confirmed_by="saga"),
            OrderShipped(aggregate_id="ord-r1", version=3,
                         tracking_number="TRK999", carrier="DHL"),
        ]
        order = Order.reconstitute(events)
        assert order.status == OrderStatus.SHIPPED
        assert order.tracking_number == "TRK999"
        assert order.version == 3

    def test_partial_replay_stops_at_given_version(self):
        events = [
            OrderPlaced(aggregate_id="ord-r2", version=1, customer_id="cust-1",
                        items=tuple(SAMPLE_ITEMS), total_amount=25.0),
        ]
        order = Order.reconstitute(events)
        assert order.status == OrderStatus.PLACED

    def test_empty_event_stream_returns_blank_order(self):
        order = Order.reconstitute([])
        assert order.order_id is None
        assert order.version == 0
