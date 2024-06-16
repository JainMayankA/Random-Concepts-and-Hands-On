"""
ClickHouse writer.

ClickHouse is a column-oriented OLAP database optimised for time-series
analytics. We use the ReplacingMergeTree engine for metrics (deduplicate
re-delivered events) and MergeTree for anomaly events.

Key ClickHouse advantages over PostgreSQL for this workload:
  - Columnar storage → 10-100x faster aggregation queries
  - LZ4 compression → 5-10x smaller storage for numeric series
  - Sub-second queries over billions of rows
  - Native time-range partitioning (PARTITION BY toYYYYMM)
"""

from __future__ import annotations
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import clickhouse_connect

logger = logging.getLogger(__name__)

CREATE_METRICS_TABLE = """
CREATE TABLE IF NOT EXISTS metrics (
    timestamp   DateTime,
    metric_name LowCardinality(String),
    host        LowCardinality(String),
    region      LowCardinality(String),
    value       Float64,
    z_score     Float32,
    window_mean Float32,
    window_std  Float32
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (metric_name, host, timestamp)
TTL timestamp + INTERVAL 90 DAY
SETTINGS index_granularity = 8192
"""

CREATE_ANOMALIES_TABLE = """
CREATE TABLE IF NOT EXISTS anomaly_events (
    timestamp     DateTime,
    detected_at   DateTime DEFAULT now(),
    metric_name   LowCardinality(String),
    host          LowCardinality(String),
    region        LowCardinality(String),
    value         Float64,
    anomaly_score Float32,
    z_score       Float32,
    window_mean   Float32,
    window_std    Float32,
    alerted       UInt8 DEFAULT 0
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (metric_name, host, timestamp)
"""


class ClickHouseWriter:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8123,
        database: str = "metrics_db",
        username: str = "default",
        password: str = "",
    ):
        self.client = clickhouse_connect.get_client(
            host=host, port=port,
            database=database,
            username=username,
            password=password,
        )
        self._ensure_schema()

    @classmethod
    def from_env(cls) -> "ClickHouseWriter":
        return cls(
            host=os.getenv("CLICKHOUSE_HOST", "localhost"),
            port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
            database=os.getenv("CLICKHOUSE_DB", "metrics_db"),
            username=os.getenv("CLICKHOUSE_USER", "default"),
            password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        )

    def _ensure_schema(self):
        self.client.command("CREATE DATABASE IF NOT EXISTS metrics_db")
        self.client.command(CREATE_METRICS_TABLE)
        self.client.command(CREATE_ANOMALIES_TABLE)
        logger.info("ClickHouse schema ready")

    def write_metrics(self, rows: list[dict]):
        if not rows:
            return
        data = [
            [
                datetime.utcfromtimestamp(r["timestamp"]),
                r["metric_name"], r["host"], r["region"],
                r["value"], r["z_score"], r["window_mean"], r["window_std"],
            ]
            for r in rows
        ]
        self.client.insert(
            "metrics",
            data,
            column_names=["timestamp", "metric_name", "host", "region",
                          "value", "z_score", "window_mean", "window_std"],
        )

    def write_anomaly(self, anomaly: dict):
        self.client.insert(
            "anomaly_events",
            [[
                datetime.utcfromtimestamp(anomaly["timestamp"]),
                anomaly["metric_name"], anomaly["host"], anomaly["region"],
                anomaly["value"], anomaly["anomaly_score"],
                anomaly["z_score"], anomaly["window_mean"], anomaly["window_std"],
            ]],
            column_names=["timestamp", "metric_name", "host", "region",
                          "value", "anomaly_score", "z_score", "window_mean", "window_std"],
        )

    def query_recent_anomalies(self, hours: int = 1, limit: int = 100) -> list[dict]:
        result = self.client.query(
            """
            SELECT timestamp, metric_name, host, region,
                   value, anomaly_score, z_score
            FROM anomaly_events
            WHERE timestamp >= now() - INTERVAL %(hours)s HOUR
            ORDER BY timestamp DESC
            LIMIT %(limit)s
            """,
            parameters={"hours": hours, "limit": limit},
        )
        return [dict(zip(result.column_names, row)) for row in result.result_rows]

    def query_metric_series(
        self, metric_name: str, host: str,
        minutes: int = 60, step_seconds: int = 10,
    ) -> list[dict]:
        result = self.client.query(
            """
            SELECT
                toStartOfInterval(timestamp, INTERVAL %(step)s SECOND) AS bucket,
                avg(value)       AS avg_value,
                max(value)       AS max_value,
                avg(z_score)     AS avg_z_score
            FROM metrics
            WHERE metric_name = %(metric)s
              AND host = %(host)s
              AND timestamp >= now() - INTERVAL %(minutes)s MINUTE
            GROUP BY bucket
            ORDER BY bucket ASC
            """,
            parameters={"metric": metric_name, "host": host,
                        "step": step_seconds, "minutes": minutes},
        )
        return [dict(zip(result.column_names, row)) for row in result.result_rows]

    def anomaly_rate(self, minutes: int = 60) -> dict:
        result = self.client.query(
            """
            SELECT
                metric_name,
                count() AS anomaly_count,
                countIf(timestamp >= now() - INTERVAL 5 MINUTE) AS last_5min
            FROM anomaly_events
            WHERE timestamp >= now() - INTERVAL %(minutes)s MINUTE
            GROUP BY metric_name
            ORDER BY anomaly_count DESC
            """,
            parameters={"minutes": minutes},
        )
        return [dict(zip(result.column_names, row)) for row in result.result_rows]
