"""
Kafka metric producer.

Publishes time-series metric events to a Kafka topic.
In production this would be replaced by your actual instrumentation
(Prometheus remote_write, StatsD, OpenTelemetry, etc.).

For demo / load testing, generates synthetic CPU/memory/latency metrics
with configurable anomaly injection so you can verify detection end-to-end.
"""

from __future__ import annotations
import json
import logging
import math
import os
import random
import time
from dataclasses import asdict, dataclass
from typing import Optional

from kafka import KafkaProducer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)

METRICS_TOPIC = os.getenv("KAFKA_METRICS_TOPIC", "metrics")


@dataclass
class MetricEvent:
    metric_name: str
    value: float
    timestamp: float          # Unix epoch seconds
    host: str
    region: str
    tags: dict

    def to_json(self) -> bytes:
        d = asdict(self)
        d["timestamp"] = self.timestamp
        return json.dumps(d).encode()


class MetricProducer:
    def __init__(self, bootstrap_servers: str = "localhost:9092"):
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: v,
            acks="all",
            retries=3,
            linger_ms=5,
            batch_size=16384,
        )

    def send(self, event: MetricEvent):
        future = self.producer.send(
            METRICS_TOPIC,
            key=f"{event.host}:{event.metric_name}".encode(),
            value=event.to_json(),
        )
        future.add_errback(lambda e: logger.error(f"Kafka send error: {e}"))

    def flush(self):
        self.producer.flush()

    def close(self):
        self.producer.close()


class SyntheticMetricGenerator:
    """
    Generates realistic-looking CPU/memory/latency time series
    with optional burst anomalies for pipeline testing.
    """

    HOSTS = [f"web-{i:02d}" for i in range(1, 6)] + [f"api-{i:02d}" for i in range(1, 4)]
    REGIONS = ["us-east-1", "us-west-2", "eu-west-1"]

    def __init__(self, anomaly_rate: float = 0.02):
        self.anomaly_rate = anomaly_rate
        self._t = 0.0

    def next_batch(self, batch_size: int = 100) -> list[MetricEvent]:
        events = []
        now = time.time()
        for _ in range(batch_size):
            host = random.choice(self.HOSTS)
            region = random.choice(self.REGIONS)
            self._t += 1.0

            # Diurnal pattern + noise
            diurnal = 0.3 * math.sin(2 * math.pi * self._t / 86400)
            is_anomaly = random.random() < self.anomaly_rate

            for metric, base, noise_scale in [
                ("cpu_percent",       40.0, 8.0),
                ("memory_percent",    55.0, 5.0),
                ("request_latency_ms", 120.0, 25.0),
                ("error_rate",          0.5, 0.3),
            ]:
                value = base + diurnal * base + random.gauss(0, noise_scale)
                if is_anomaly:
                    value *= random.uniform(2.5, 5.0)   # spike
                value = max(0.0, round(value, 4))

                events.append(MetricEvent(
                    metric_name=metric,
                    value=value,
                    timestamp=now + self._t * 0.01,
                    host=host,
                    region=region,
                    tags={"env": "prod", "anomaly": is_anomaly},
                ))
        return events


def run_producer(
    bootstrap_servers: str = "localhost:9092",
    rate_per_second: int = 1000,
    duration_seconds: Optional[int] = None,
):
    producer = MetricProducer(bootstrap_servers)
    generator = SyntheticMetricGenerator(anomaly_rate=0.02)
    batch_size = max(1, rate_per_second // 10)
    interval = batch_size / rate_per_second

    logger.info(f"Producing {rate_per_second} metrics/s to {METRICS_TOPIC}")
    start = time.time()
    sent = 0

    try:
        while True:
            if duration_seconds and (time.time() - start) > duration_seconds:
                break
            batch = generator.next_batch(batch_size)
            for event in batch:
                producer.send(event)
            sent += len(batch)
            if sent % 10_000 == 0:
                elapsed = time.time() - start
                logger.info(f"Sent {sent:,} events in {elapsed:.1f}s ({sent/elapsed:.0f}/s)")
            time.sleep(interval)
    finally:
        producer.flush()
        producer.close()
        logger.info(f"Producer done. Total: {sent:,} events")
