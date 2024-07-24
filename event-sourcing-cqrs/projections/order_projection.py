"""
CQRS read-side projections.

Projections listen to the event stream and maintain denormalized
read models optimized for queries. They can be rebuilt at any time
by replaying all events — this is the key benefit of event sourcing.

Each projection handles specific event types and updates its own
table. Reads never touch the event store directly.
"""

import json
import logging
from datetime import datetime

import psycopg2
import psycopg2.extras
from psycopg2.extensions import connection as PgConnection

from domain.events import (
    DomainEvent, OrderPlaced, OrderConfirmed,
    OrderShipped, OrderDelivered, OrderCancelled,
    PaymentAuthorized, PaymentFailed,
)

logger = logging.getLogger(__name__)

CREATE_PROJECTIONS_SQL = """
CREATE TABLE IF NOT EXISTS order_summary (
    order_id        VARCHAR(36) PRIMARY KEY,
    customer_id     VARCHAR(36) NOT NULL,
    status          VARCHAR(32) NOT NULL,
    total_amount    NUMERIC(12, 2) NOT NULL,
    item_count      INT NOT NULL DEFAULT 0,
    tracking_number VARCHAR(128),
    placed_at       TIMESTAMPTZ,
    confirmed_at    TIMESTAMPTZ,
    shipped_at      TIMESTAMPTZ,
    delivered_at    TIMESTAMPTZ,
    cancelled_at    TIMESTAMPTZ,
    last_updated    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS customer_order_stats (
    customer_id     VARCHAR(36) PRIMARY KEY,
    total_orders    INT NOT NULL DEFAULT 0,
    total_spent     NUMERIC(12, 2) NOT NULL DEFAULT 0,
    last_order_at   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS projection_checkpoint (
    projection_name VARCHAR(64) PRIMARY KEY,
    last_event_id   BIGINT NOT NULL DEFAULT 0
);
"""


class OrderProjection:
    """
    Maintains order_summary and customer_order_stats read models.
    Can be fully rebuilt by calling rebuild(event_store).
    """

    NAME = "order_projection"

    def __init__(self, conn: PgConnection):
        self.conn = conn
        self._ensure_schema()

    def _ensure_schema(self):
        with self.conn.cursor() as cur:
            cur.execute(CREATE_PROJECTIONS_SQL)
        self.conn.commit()

    def handle(self, event: DomainEvent):
        handlers = {
            OrderPlaced:    self._on_placed,
            OrderConfirmed: self._on_confirmed,
            OrderShipped:   self._on_shipped,
            OrderDelivered: self._on_delivered,
            OrderCancelled: self._on_cancelled,
        }
        handler = handlers.get(type(event))
        if handler:
            handler(event)
            self.conn.commit()

    def _on_placed(self, e: OrderPlaced):
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO order_summary
                    (order_id, customer_id, status, total_amount, item_count, placed_at, last_updated)
                VALUES (%s, %s, 'placed', %s, %s, %s, now())
                ON CONFLICT (order_id) DO NOTHING
                """,
                (e.aggregate_id, e.customer_id, e.total_amount, len(e.items), e.occurred_at),
            )
            cur.execute(
                """
                INSERT INTO customer_order_stats (customer_id, total_orders, total_spent, last_order_at)
                VALUES (%s, 1, %s, %s)
                ON CONFLICT (customer_id) DO UPDATE
                SET total_orders = customer_order_stats.total_orders + 1,
                    total_spent  = customer_order_stats.total_spent + EXCLUDED.total_spent,
                    last_order_at = EXCLUDED.last_order_at
                """,
                (e.customer_id, e.total_amount, e.occurred_at),
            )

    def _on_confirmed(self, e: OrderConfirmed):
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE order_summary SET status='confirmed', confirmed_at=%s, last_updated=now() WHERE order_id=%s",
                (e.occurred_at, e.aggregate_id),
            )

    def _on_shipped(self, e: OrderShipped):
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE order_summary SET status='shipped', tracking_number=%s, shipped_at=%s, last_updated=now() WHERE order_id=%s",
                (e.tracking_number, e.occurred_at, e.aggregate_id),
            )

    def _on_delivered(self, e: OrderDelivered):
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE order_summary SET status='delivered', delivered_at=%s, last_updated=now() WHERE order_id=%s",
                (e.occurred_at, e.aggregate_id),
            )

    def _on_cancelled(self, e: OrderCancelled):
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE order_summary SET status='cancelled', cancelled_at=%s, last_updated=now() WHERE order_id=%s",
                (e.occurred_at, e.aggregate_id),
            )

    # ── Query methods (read side) ─────────────────────────────────────────────

    def get_order(self, order_id: str) -> dict | None:
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM order_summary WHERE order_id = %s", (order_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def list_orders(self, customer_id: str = None, status: str = None,
                    limit: int = 50, offset: int = 0) -> list[dict]:
        filters, params = [], []
        if customer_id:
            filters.append("customer_id = %s"); params.append(customer_id)
        if status:
            filters.append("status = %s"); params.append(status)
        where = "WHERE " + " AND ".join(filters) if filters else ""
        params.extend([limit, offset])
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"SELECT * FROM order_summary {where} ORDER BY placed_at DESC LIMIT %s OFFSET %s", params)
            return [dict(r) for r in cur.fetchall()]

    def get_customer_stats(self, customer_id: str) -> dict | None:
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM customer_order_stats WHERE customer_id = %s", (customer_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def rebuild(self, events: list[DomainEvent]):
        """Wipe and replay all events to rebuild projections from scratch."""
        with self.conn.cursor() as cur:
            cur.execute("TRUNCATE order_summary, customer_order_stats")
        self.conn.commit()
        for event in events:
            self.handle(event)
        logger.info(f"Rebuilt projection from {len(events)} events")
