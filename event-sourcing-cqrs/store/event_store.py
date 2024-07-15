"""
Append-only PostgreSQL event store.

Schema:
  events(event_id, aggregate_id, aggregate_type, event_type,
         version, payload, occurred_at)

Optimistic concurrency: INSERT fails if a row with the same
(aggregate_id, version) already exists — preventing lost updates
under concurrent writes without row-level locking.
"""

import json
import logging
from datetime import datetime
from typing import Optional

import psycopg2
import psycopg2.extras
from psycopg2.extensions import connection as PgConnection

from domain.events import DomainEvent, EVENT_REGISTRY

logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS events (
    id           BIGSERIAL PRIMARY KEY,
    event_id     UUID        NOT NULL UNIQUE,
    aggregate_id VARCHAR(36) NOT NULL,
    aggregate_type VARCHAR(64) NOT NULL,
    event_type   VARCHAR(128) NOT NULL,
    version      INT         NOT NULL,
    payload      JSONB       NOT NULL DEFAULT '{}',
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (aggregate_id, version)
);
CREATE INDEX IF NOT EXISTS idx_events_aggregate ON events(aggregate_id, version);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
"""


class EventStore:
    def __init__(self, conn: PgConnection):
        self.conn = conn
        self._ensure_schema()

    def _ensure_schema(self):
        with self.conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
        self.conn.commit()

    def append(self, events: list[DomainEvent], expected_version: Optional[int] = None):
        """
        Append events atomically. Raises ConcurrencyError if another writer
        already wrote at the expected version (optimistic concurrency control).
        """
        with self.conn.cursor() as cur:
            for event in events:
                try:
                    cur.execute(
                        """
                        INSERT INTO events
                            (event_id, aggregate_id, aggregate_type, event_type, version, payload, occurred_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            event.event_id,
                            event.aggregate_id,
                            event.aggregate_type,
                            event.__class__.__name__,
                            event.version,
                            json.dumps(event._payload()),
                            event.occurred_at,
                        ),
                    )
                except psycopg2.errors.UniqueViolation:
                    self.conn.rollback()
                    raise ConcurrencyError(
                        f"Concurrency conflict on {event.aggregate_id} v{event.version}"
                    )
        self.conn.commit()
        logger.debug(f"Appended {len(events)} events for {events[0].aggregate_id}")

    def load(self, aggregate_id: str, from_version: int = 0) -> list[DomainEvent]:
        """Load and deserialize all events for an aggregate."""
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT event_type, version, payload, occurred_at, aggregate_id, aggregate_type, event_id
                FROM events
                WHERE aggregate_id = %s AND version > %s
                ORDER BY version ASC
                """,
                (aggregate_id, from_version),
            )
            rows = cur.fetchall()

        return [self._deserialize(row) for row in rows]

    def load_by_type(self, event_type: str, limit: int = 100, offset: int = 0) -> list[DomainEvent]:
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM events WHERE event_type = %s ORDER BY id LIMIT %s OFFSET %s",
                (event_type, limit, offset),
            )
            return [self._deserialize(r) for r in cur.fetchall()]

    def _deserialize(self, row: dict) -> DomainEvent:
        cls = EVENT_REGISTRY.get(row["event_type"])
        if not cls:
            raise ValueError(f"Unknown event type: {row['event_type']}")
        payload = row["payload"] if isinstance(row["payload"], dict) else json.loads(row["payload"])
        return cls(
            event_id=str(row["event_id"]),
            aggregate_id=row["aggregate_id"],
            aggregate_type=row["aggregate_type"],
            version=row["version"],
            occurred_at=row["occurred_at"] if isinstance(row["occurred_at"], datetime) else datetime.fromisoformat(row["occurred_at"]),
            **payload,
        )

    def get_version(self, aggregate_id: str) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT MAX(version) FROM events WHERE aggregate_id = %s",
                (aggregate_id,),
            )
            result = cur.fetchone()[0]
            return result or 0


class ConcurrencyError(Exception):
    pass
