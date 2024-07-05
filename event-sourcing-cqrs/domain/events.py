"""
Domain events for the order management system.
Every state change in the system is represented as an immutable event.
Events are the source of truth — never mutate, only append.
"""

from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def new_id() -> str:
    return str(uuid.uuid4())


@dataclass(frozen=True)
class DomainEvent:
    event_id: str = field(default_factory=new_id)
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    aggregate_id: str = ""
    aggregate_type: str = ""
    version: int = 0

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.__class__.__name__,
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "version": self.version,
            "occurred_at": self.occurred_at.isoformat(),
            "payload": self._payload(),
        }

    def _payload(self) -> dict:
        return {}


# ── Order events ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class OrderPlaced(DomainEvent):
    customer_id: str = ""
    items: tuple = field(default_factory=tuple)
    total_amount: float = 0.0
    aggregate_type: str = "Order"

    def _payload(self) -> dict:
        return {
            "customer_id": self.customer_id,
            "items": list(self.items),
            "total_amount": self.total_amount,
        }


@dataclass(frozen=True)
class OrderConfirmed(DomainEvent):
    confirmed_by: str = ""
    aggregate_type: str = "Order"

    def _payload(self) -> dict:
        return {"confirmed_by": self.confirmed_by}


@dataclass(frozen=True)
class OrderShipped(DomainEvent):
    tracking_number: str = ""
    carrier: str = ""
    aggregate_type: str = "Order"

    def _payload(self) -> dict:
        return {"tracking_number": self.tracking_number, "carrier": self.carrier}


@dataclass(frozen=True)
class OrderDelivered(DomainEvent):
    delivered_at: datetime = field(default_factory=datetime.utcnow)
    aggregate_type: str = "Order"

    def _payload(self) -> dict:
        return {"delivered_at": self.delivered_at.isoformat()}


@dataclass(frozen=True)
class OrderCancelled(DomainEvent):
    reason: str = ""
    cancelled_by: str = ""
    aggregate_type: str = "Order"

    def _payload(self) -> dict:
        return {"reason": self.reason, "cancelled_by": self.cancelled_by}


# ── Payment events ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PaymentAuthorized(DomainEvent):
    order_id: str = ""
    amount: float = 0.0
    payment_method: str = ""
    aggregate_type: str = "Payment"

    def _payload(self) -> dict:
        return {"order_id": self.order_id, "amount": self.amount, "payment_method": self.payment_method}


@dataclass(frozen=True)
class PaymentFailed(DomainEvent):
    order_id: str = ""
    reason: str = ""
    aggregate_type: str = "Payment"

    def _payload(self) -> dict:
        return {"order_id": self.order_id, "reason": self.reason}


# Registry for deserializing events from the store
EVENT_REGISTRY: dict[str, type] = {
    "OrderPlaced": OrderPlaced,
    "OrderConfirmed": OrderConfirmed,
    "OrderShipped": OrderShipped,
    "OrderDelivered": OrderDelivered,
    "OrderCancelled": OrderCancelled,
    "PaymentAuthorized": PaymentAuthorized,
    "PaymentFailed": PaymentFailed,
}
