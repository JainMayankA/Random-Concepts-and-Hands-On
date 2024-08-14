import pytest
from domain.aggregates.order import Order, OrderStatus
from domain.events import OrderPlaced, OrderConfirmed, OrderShipped, OrderDelivered, OrderCancelled

SAMPLE_ITEMS = [
    {"product_id": "p1", "name": "Widget", "quantity": 2, "unit_price": 19.99},
    {"product_id": "p2", "name": "Gadget", "quantity": 1, "unit_price": 49.99},
]


class TestOrderAggregate:
    def test_place_order_sets_status(self):
        order = Order.place("ord-1", "cust-1", SAMPLE_ITEMS)
        assert order.status == OrderStatus.PLACED
        assert order.order_id == "ord-1"
        assert order.customer_id == "cust-1"

    def test_place_order_calculates_total(self):
        order = Order.place("ord-2", "cust-1", SAMPLE_ITEMS)
        assert order.total_amount == round(2 * 19.99 + 49.99, 2)

    def test_place_raises_pending_event(self):
        order = Order.place("ord-3", "cust-1", SAMPLE_ITEMS)
        pending = order.flush_pending()
        assert len(pending) == 1
        assert isinstance(pending[0], OrderPlaced)

    def test_flush_clears_pending(self):
        order = Order.place("ord-4", "cust-1", SAMPLE_ITEMS)
        order.flush_pending()
        assert order.flush_pending() == []

    def test_confirm_transitions_status(self):
        order = Order.place("ord-5", "cust-1", SAMPLE_ITEMS)
        order.flush_pending()
        order.confirm()
        assert order.status == OrderStatus.CONFIRMED

    def test_confirm_raises_on_wrong_status(self):
        order = Order.place("ord-6", "cust-1", SAMPLE_ITEMS)
        order.flush_pending()
        order.confirm()
        order.flush_pending()
        with pytest.raises(ValueError, match="Cannot confirm"):
            order.confirm()

    def test_full_lifecycle(self):
        order = Order.place("ord-7", "cust-1", SAMPLE_ITEMS)
        order.flush_pending()
        order.confirm()
        order.flush_pending()
        order.ship("TRACK123", "FedEx")
        order.flush_pending()
        order.deliver()
        assert order.status == OrderStatus.DELIVERED

    def test_cancel_from_placed(self):
        order = Order.place("ord-8", "cust-1", SAMPLE_ITEMS)
        order.flush_pending()
        order.cancel("changed my mind")
        assert order.status == OrderStatus.CANCELLED

    def test_cannot_cancel_delivered(self):
        order = Order.place("ord-9", "cust-1", SAMPLE_ITEMS)
        order.flush_pending()
        order.confirm(); order.flush_pending()
        order.ship("T1", "UPS"); order.flush_pending()
        order.deliver(); order.flush_pending()
        with pytest.raises(ValueError, match="Cannot cancel"):
            order.cancel("too late")

    def test_version_increments_with_events(self):
        order = Order.place("ord-10", "cust-1", SAMPLE_ITEMS)
        assert order.version == 1
        order.flush_pending()
        order.confirm()
        assert order.version == 2

    def test_reconstitute_from_events(self):
        original = Order.place("ord-11", "cust-1", SAMPLE_ITEMS)
        original.flush_pending()
        original.confirm()
        all_events = [
            OrderPlaced(aggregate_id="ord-11", version=1, customer_id="cust-1",
                        items=tuple(SAMPLE_ITEMS), total_amount=89.97),
            OrderConfirmed(aggregate_id="ord-11", version=2, confirmed_by="system"),
        ]
        rebuilt = Order.reconstitute(all_events)
        assert rebuilt.status == OrderStatus.CONFIRMED
        assert rebuilt.order_id == "ord-11"
        assert rebuilt.version == 2
