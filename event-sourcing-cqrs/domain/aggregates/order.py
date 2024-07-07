"""
Order aggregate root.

Key design: state is NEVER stored directly. The aggregate is always
reconstituted by replaying its event stream from the event store.
apply() dispatches each event to a handler that mutates in-memory state.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from domain.events import (
    DomainEvent, OrderPlaced, OrderConfirmed,
    OrderShipped, OrderDelivered, OrderCancelled,
)


class OrderStatus(str, Enum):
    DRAFT = "draft"
    PLACED = "placed"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


@dataclass
class OrderItem:
    product_id: str
    name: str
    quantity: int
    unit_price: float

    @property
    def subtotal(self) -> float:
        return self.quantity * self.unit_price


class Order:
    """
    Aggregate root for the Order bounded context.
    Raises domain exceptions for invalid state transitions.
    Pending events are accumulated in _pending and flushed to the store on save.
    """

    def __init__(self):
        self.order_id: Optional[str] = None
        self.customer_id: Optional[str] = None
        self.status: OrderStatus = OrderStatus.DRAFT
        self.items: list[OrderItem] = []
        self.total_amount: float = 0.0
        self.tracking_number: Optional[str] = None
        self.version: int = 0
        self._pending: list[DomainEvent] = []

    # ── Command handlers (write side) ────────────────────────────────────────

    @classmethod
    def place(cls, order_id: str, customer_id: str, items: list[dict]) -> "Order":
        order = cls()
        total = sum(i["quantity"] * i["unit_price"] for i in items)
        event = OrderPlaced(
            aggregate_id=order_id,
            version=1,
            customer_id=customer_id,
            items=tuple(items),
            total_amount=round(total, 2),
        )
        order._raise(event)
        return order

    def confirm(self, confirmed_by: str = "system"):
        if self.status != OrderStatus.PLACED:
            raise ValueError(f"Cannot confirm order in status {self.status}")
        self._raise(OrderConfirmed(
            aggregate_id=self.order_id,
            version=self.version + 1,
            confirmed_by=confirmed_by,
        ))

    def ship(self, tracking_number: str, carrier: str):
        if self.status != OrderStatus.CONFIRMED:
            raise ValueError(f"Cannot ship order in status {self.status}")
        self._raise(OrderShipped(
            aggregate_id=self.order_id,
            version=self.version + 1,
            tracking_number=tracking_number,
            carrier=carrier,
        ))

    def deliver(self):
        if self.status != OrderStatus.SHIPPED:
            raise ValueError(f"Cannot deliver order in status {self.status}")
        self._raise(OrderDelivered(aggregate_id=self.order_id, version=self.version + 1))

    def cancel(self, reason: str, cancelled_by: str = "customer"):
        if self.status in (OrderStatus.DELIVERED, OrderStatus.CANCELLED):
            raise ValueError(f"Cannot cancel order in status {self.status}")
        self._raise(OrderCancelled(
            aggregate_id=self.order_id,
            version=self.version + 1,
            reason=reason,
            cancelled_by=cancelled_by,
        ))

    # ── Event application (reconstitution) ───────────────────────────────────

    def _raise(self, event: DomainEvent):
        self.apply(event)
        self._pending.append(event)

    def apply(self, event: DomainEvent):
        handlers = {
            OrderPlaced: self._on_placed,
            OrderConfirmed: self._on_confirmed,
            OrderShipped: self._on_shipped,
            OrderDelivered: self._on_delivered,
            OrderCancelled: self._on_cancelled,
        }
        handler = handlers.get(type(event))
        if handler:
            handler(event)
        self.version = event.version

    def _on_placed(self, e: OrderPlaced):
        self.order_id = e.aggregate_id
        self.customer_id = e.customer_id
        self.items = [OrderItem(**i) for i in e.items]
        self.total_amount = e.total_amount
        self.status = OrderStatus.PLACED

    def _on_confirmed(self, _):
        self.status = OrderStatus.CONFIRMED

    def _on_shipped(self, e: OrderShipped):
        self.status = OrderStatus.SHIPPED
        self.tracking_number = e.tracking_number

    def _on_delivered(self, _):
        self.status = OrderStatus.DELIVERED

    def _on_cancelled(self, _):
        self.status = OrderStatus.CANCELLED

    @classmethod
    def reconstitute(cls, events: list[DomainEvent]) -> "Order":
        """Replay an event stream to rebuild aggregate state."""
        order = cls()
        for event in events:
            order.apply(event)
        return order

    def flush_pending(self) -> list[DomainEvent]:
        pending = list(self._pending)
        self._pending.clear()
        return pending
