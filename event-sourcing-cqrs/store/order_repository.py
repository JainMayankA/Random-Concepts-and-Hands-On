"""
Order repository — thin layer between the aggregate and the event store.
Handles load (reconstitute from events) and save (append pending events).
Also notifies projections after each save so the read model stays current.
"""

import logging
from typing import Optional

from domain.aggregates.order import Order
from store.event_store import EventStore, ConcurrencyError

logger = logging.getLogger(__name__)


class OrderRepository:
    def __init__(self, event_store: EventStore, projections: list = None):
        self.store = event_store
        self.projections = projections or []

    def load(self, order_id: str) -> Order:
        events = self.store.load(order_id)
        if not events:
            raise OrderNotFoundError(f"Order {order_id} not found")
        return Order.reconstitute(events)

    def save(self, order: Order, retries: int = 3):
        pending = order.flush_pending()
        if not pending:
            return

        for attempt in range(retries):
            try:
                self.store.append(pending)
                for event in pending:
                    for projection in self.projections:
                        try:
                            projection.handle(event)
                        except Exception as e:
                            logger.error(f"Projection update failed for {event.__class__.__name__}: {e}")
                logger.info(f"Saved {len(pending)} events for order {order.order_id}")
                return
            except ConcurrencyError:
                if attempt == retries - 1:
                    raise
                logger.warning(f"Concurrency conflict for order {order.order_id}, retry {attempt + 1}")
                # Reload and re-apply pending events on top of latest state
                latest = self.load(order.order_id)
                for event in pending:
                    latest.apply(event)
                order = latest

    def exists(self, order_id: str) -> bool:
        return self.store.get_version(order_id) > 0


class OrderNotFoundError(Exception):
    pass
