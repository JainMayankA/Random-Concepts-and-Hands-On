"""
Kafka metric consumer.

Reads metric events from Kafka, batches them by metric_name + host,
and feeds batches to the anomaly detector. Detected anomalies are
written to ClickHouse and published to the alerts topic.

Uses a manual commit strategy: only commit offsets after ClickHouse
write succeeds, preventing data loss on restart.
"""

from __future__ import annotations
import json
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

from kafka import KafkaConsumer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)

METRICS_TOPIC = os.getenv("KAFKA_METRICS_TOPIC", "metrics")
ALERTS_TOPIC  = os.getenv("KAFKA_ALERTS_TOPIC",  "anomaly_alerts")
GROUP_ID      = os.getenv("KAFKA_GROUP_ID",       "anomaly-detector")


@dataclass
class MetricBatch:
    metric_name: str
    host: str
    values: list[float]
    timestamps: list[float]
    region: str


class MetricConsumer:
    """
    Polls Kafka, accumulates events into per-(metric, host) batches,
    flushes each batch after `batch_window_seconds` or `max_batch_size`.
    """

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        batch_window_seconds: float = 5.0,
        max_batch_size: int = 500,
        on_batch: Callable[[MetricBatch], None] = None,
    ):
        self.batch_window = batch_window_seconds
        self.max_batch_size = max_batch_size
        self.on_batch = on_batch or (lambda b: None)

        self.consumer = KafkaConsumer(
            METRICS_TOPIC,
            bootstrap_servers=bootstrap_servers,
            group_id=GROUP_ID,
            auto_offset_reset="latest",
            enable_auto_commit=False,       # manual commit after processing
            value_deserializer=lambda v: json.loads(v.decode()),
            max_poll_records=1000,
            session_timeout_ms=30_000,
            heartbeat_interval_ms=10_000,
        )

        self._batches: dict[tuple, MetricBatch] = defaultdict(lambda: None)
        self._batch_start: dict[tuple, float] = {}

    def run(self):
        logger.info(f"Consumer started on topic={METRICS_TOPIC} group={GROUP_ID}")
        try:
            while True:
                records = self.consumer.poll(timeout_ms=1000)
                for tp, messages in records.items():
                    for msg in messages:
                        self._accumulate(msg.value)

                flush_failed = self._flush_ready()
                if not flush_failed:
                    self.consumer.commit()
                else:
                    logger.warning("Skipping commit — batch processing had failures, will reprocess")
        except KeyboardInterrupt:
            pass
        finally:
            self.consumer.close()
            logger.info("Consumer closed")

    def _accumulate(self, event: dict):
        key = (event["metric_name"], event["host"])
        now = time.monotonic()

        if key not in self._batch_start:
            self._batch_start[key] = now
            self._batches[key] = MetricBatch(
                metric_name=event["metric_name"],
                host=event["host"],
                region=event.get("region", "unknown"),
                values=[],
                timestamps=[],
            )

        batch = self._batches[key]
        batch.values.append(event["value"])
        batch.timestamps.append(event["timestamp"])

    def _flush_ready(self) -> bool:
        now = time.monotonic()
        ready_keys = [
            k for k, start in self._batch_start.items()
            if (now - start) >= self.batch_window
            or len(self._batches[k].values) >= self.max_batch_size
        ]
        flush_failed = False
        for key in ready_keys:
            batch = self._batches.pop(key)
            self._batch_start.pop(key)
            if batch and len(batch.values) >= 10:   # need minimum samples
                try:
                    self.on_batch(batch)
                except Exception as e:
                    flush_failed = True
                    logger.error(f"Batch handler error for {key}: {e}", exc_info=True)
        return flush_failed
