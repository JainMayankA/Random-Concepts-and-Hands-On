"""
Order placement saga — orchestrates the multi-step workflow:
  1. PlaceOrder      → order created in PLACED state
  2. AuthorizePayment → payment service confirms funds
  3. ConfirmOrder    → order moves to CONFIRMED
  4. (if payment fails) → CancelOrder as compensating transaction

This is a choreography-based saga using an in-process event bus.
In production, replace with RabbitMQ/Kafka for inter-service messaging.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional
import uuid

from domain.events import (
    DomainEvent, OrderPlaced, OrderCancelled,
    PaymentAuthorized, PaymentFailed,
)

logger = logging.getLogger(__name__)


class SagaState(str, Enum):
    STARTED = "started"
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_AUTHORIZED = "payment_authorized"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    FAILED = "failed"


@dataclass
class SagaStep:
    name: str
    action: Callable
    compensation: Optional[Callable] = None
    completed: bool = False


@dataclass
class OrderSaga:
    saga_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str = ""
    customer_id: str = ""
    amount: float = 0.0
    state: SagaState = SagaState.STARTED
    completed_steps: list[str] = field(default_factory=list)
    failure_reason: str = ""


class SagaOrchestrator:
    """
    Manages saga lifecycle. On failure, executes compensating transactions
    in reverse order for all completed steps (Saga rollback pattern).
    """

    def __init__(self, order_service, payment_service):
        self.order_service = order_service
        self.payment_service = payment_service
        self._sagas: dict[str, OrderSaga] = {}

    def start_order_saga(self, order_id: str, customer_id: str, amount: float) -> OrderSaga:
        saga = OrderSaga(order_id=order_id, customer_id=customer_id, amount=amount)
        self._sagas[saga.saga_id] = saga
        logger.info(f"Saga {saga.saga_id} started for order {order_id}")

        steps = [
            SagaStep(
                name="authorize_payment",
                action=lambda: self.payment_service.authorize(order_id, amount, customer_id),
                compensation=lambda: self.payment_service.void_authorization(order_id),
            ),
            SagaStep(
                name="confirm_order",
                action=lambda: self.order_service.confirm(order_id),
                compensation=lambda: self.order_service.cancel(order_id, "saga_rollback", "saga"),
            ),
        ]

        for step in steps:
            try:
                saga.state = SagaState.PAYMENT_PENDING if step.name == "authorize_payment" else saga.state
                step.action()
                step.completed = True
                saga.completed_steps.append(step.name)
                logger.info(f"Saga {saga.saga_id}: step '{step.name}' completed")
            except Exception as e:
                saga.failure_reason = str(e)
                logger.warning(f"Saga {saga.saga_id}: step '{step.name}' failed: {e}. Compensating...")
                saga.state = SagaState.COMPENSATING
                self._compensate(saga, steps, step)
                return saga

        saga.state = SagaState.COMPLETED
        logger.info(f"Saga {saga.saga_id} completed successfully")
        return saga

    def _compensate(self, saga: OrderSaga, steps: list[SagaStep], failed_step: SagaStep):
        """Execute compensating transactions in reverse for all completed steps."""
        completed = [s for s in steps if s.completed]
        for step in reversed(completed):
            if step.compensation:
                try:
                    step.compensation()
                    logger.info(f"Saga {saga.saga_id}: compensated '{step.name}'")
                except Exception as e:
                    logger.error(f"Saga {saga.saga_id}: compensation for '{step.name}' failed: {e}")
        saga.state = SagaState.FAILED

    def get_saga(self, saga_id: str) -> Optional[OrderSaga]:
        return self._sagas.get(saga_id)


# ── Stub services used by the saga (replace with real implementations) ────────

class OrderService:
    def __init__(self, repo):
        self.repo = repo

    def confirm(self, order_id: str):
        order = self.repo.load(order_id)
        order.confirm(confirmed_by="saga")
        self.repo.save(order)

    def cancel(self, order_id: str, reason: str, cancelled_by: str):
        order = self.repo.load(order_id)
        order.cancel(reason=reason, cancelled_by=cancelled_by)
        self.repo.save(order)


class PaymentService:
    """Stub — replace with real payment gateway integration."""

    def authorize(self, order_id: str, amount: float, customer_id: str) -> str:
        if amount > 10_000:
            raise ValueError(f"Amount {amount} exceeds authorization limit")
        logger.info(f"Payment authorized for order {order_id}: ${amount:.2f}")
        return f"auth_{order_id[:8]}"

    def void_authorization(self, order_id: str):
        logger.info(f"Payment authorization voided for order {order_id}")
