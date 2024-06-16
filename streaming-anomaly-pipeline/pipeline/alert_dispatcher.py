"""
Alert dispatcher.

When the detector flags an anomaly, the dispatcher:
  1. Deduplicates — suppresses repeated alerts for the same (metric, host)
     within a cooldown window (prevents alert storms)
  2. Enriches — adds context from recent history
  3. Publishes to Kafka alerts topic (downstream consumers: PagerDuty, Slack)
  4. Optionally fires a webhook for immediate HTTP notification
"""

from __future__ import annotations
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "300"))
WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")


@dataclass
class Alert:
    metric_name: str
    host: str
    region: str
    value: float
    anomaly_score: float
    z_score: float
    window_mean: float
    window_std: float
    timestamp: float
    severity: str        # critical | warning | info


class AlertDispatcher:
    def __init__(
        self,
        kafka_producer=None,
        webhook_url: str = WEBHOOK_URL,
        cooldown_seconds: int = ALERT_COOLDOWN_SECONDS,
    ):
        self.kafka_producer = kafka_producer
        self.webhook_url = webhook_url
        self.cooldown = cooldown_seconds
        self._last_alert: dict[str, float] = {}

    def dispatch(self, anomaly_result) -> bool:
        """
        Dispatch an alert for an anomaly result.
        Returns True if alert was sent, False if suppressed by cooldown.
        """
        key = f"{anomaly_result.metric_name}::{anomaly_result.host}"
        now = time.time()
        last = self._last_alert.get(key, 0.0)

        if now - last < self.cooldown:
            logger.debug(f"Alert suppressed (cooldown): {key}")
            return False

        self._last_alert[key] = now
        alert = self._build_alert(anomaly_result)

        self._publish_kafka(alert)
        self._fire_webhook(alert)

        logger.warning(
            f"ANOMALY ALERT [{alert.severity}] "
            f"{alert.metric_name} on {alert.host}: "
            f"value={alert.value:.2f} z={alert.z_score:.2f} "
            f"(mean={alert.window_mean:.2f} ± {alert.window_std:.2f})"
        )
        return True

    def _build_alert(self, result) -> Alert:
        # Severity by z-score magnitude
        abs_z = abs(result.z_score)
        if abs_z >= 5 or result.anomaly_score < -0.3:
            severity = "critical"
        elif abs_z >= 3:
            severity = "warning"
        else:
            severity = "info"

        return Alert(
            metric_name=result.metric_name,
            host=result.host,
            region=result.region,
            value=result.value,
            anomaly_score=result.anomaly_score,
            z_score=result.z_score,
            window_mean=result.window_mean,
            window_std=result.window_std,
            timestamp=result.timestamp,
            severity=severity,
        )

    def _publish_kafka(self, alert: Alert):
        if not self.kafka_producer:
            return
        alerts_topic = os.getenv("KAFKA_ALERTS_TOPIC", "anomaly_alerts")
        payload = json.dumps({
            "type": "anomaly_alert",
            "severity": alert.severity,
            "metric_name": alert.metric_name,
            "host": alert.host,
            "region": alert.region,
            "value": alert.value,
            "anomaly_score": alert.anomaly_score,
            "z_score": alert.z_score,
            "window_mean": alert.window_mean,
            "window_std": alert.window_std,
            "timestamp": alert.timestamp,
        }).encode()
        self.kafka_producer.send(alerts_topic, value=payload)

    def _fire_webhook(self, alert: Alert):
        if not self.webhook_url:
            return
        payload = {
            "text": (
                f"*[{alert.severity.upper()}]* Anomaly detected\n"
                f"Metric: `{alert.metric_name}` on `{alert.host}` ({alert.region})\n"
                f"Value: `{alert.value:.2f}` (mean: `{alert.window_mean:.2f}` ± `{alert.window_std:.2f}`)\n"
                f"Z-score: `{alert.z_score:.2f}`  Score: `{alert.anomaly_score:.4f}`"
            )
        }
        try:
            httpx.post(self.webhook_url, json=payload, timeout=5)
        except Exception as e:
            logger.warning(f"Webhook fire failed: {e}")
