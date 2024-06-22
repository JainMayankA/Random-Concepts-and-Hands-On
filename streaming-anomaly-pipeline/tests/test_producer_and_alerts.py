"""
Tests for the metric producer generator and alert dispatcher.
"""

import time
import pytest
from unittest.mock import MagicMock, patch

from pipeline.producer import SyntheticMetricGenerator, MetricEvent
from pipeline.alert_dispatcher import AlertDispatcher
from detector.isolation_forest import AnomalyResult


class TestSyntheticMetricGenerator:
    def test_generates_correct_batch_size(self):
        gen = SyntheticMetricGenerator()
        batch = gen.next_batch(batch_size=50)
        # 4 metrics × 50 = 200 events
        assert len(batch) == 50 * 4

    def test_all_events_are_metric_event_instances(self):
        gen = SyntheticMetricGenerator()
        batch = gen.next_batch(batch_size=10)
        assert all(isinstance(e, MetricEvent) for e in batch)

    def test_metric_names_are_expected(self):
        gen = SyntheticMetricGenerator()
        batch = gen.next_batch(batch_size=5)
        names = {e.metric_name for e in batch}
        expected = {"cpu_percent", "memory_percent", "request_latency_ms", "error_rate"}
        assert names == expected

    def test_values_are_non_negative(self):
        gen = SyntheticMetricGenerator()
        batch = gen.next_batch(batch_size=100)
        assert all(e.value >= 0 for e in batch)

    def test_timestamps_are_positive(self):
        gen = SyntheticMetricGenerator()
        batch = gen.next_batch(batch_size=10)
        assert all(e.timestamp > 0 for e in batch)

    def test_hosts_from_known_pool(self):
        gen = SyntheticMetricGenerator()
        batch = gen.next_batch(batch_size=50)
        all_hosts = set(gen.HOSTS)
        assert all(e.host in all_hosts for e in batch)

    def test_to_json_roundtrip(self):
        import json
        gen = SyntheticMetricGenerator()
        event = gen.next_batch(batch_size=1)[0]
        data = json.loads(event.to_json())
        assert data["metric_name"] == event.metric_name
        assert data["value"] == event.value
        assert data["host"] == event.host

    def test_anomaly_rate_respected(self):
        gen = SyntheticMetricGenerator(anomaly_rate=1.0)  # all anomalies
        batch = gen.next_batch(batch_size=50)
        anomalies = [e for e in batch if e.tags.get("anomaly")]
        assert len(anomalies) > 0


class TestAlertDispatcher:
    def _make_result(self, metric="cpu", host="h1", z=4.0, score=-0.2) -> AnomalyResult:
        return AnomalyResult(
            metric_name=metric, host=host, region="us-east-1",
            value=150.0, timestamp=time.time(),
            anomaly_score=score, is_anomaly=True,
            z_score=z, window_mean=50.0, window_std=5.0,
        )

    def test_first_alert_is_sent(self):
        d = AlertDispatcher(cooldown_seconds=300)
        result = self._make_result()
        sent = d.dispatch(result)
        assert sent is True

    def test_duplicate_alert_suppressed_by_cooldown(self):
        d = AlertDispatcher(cooldown_seconds=300)
        result = self._make_result()
        d.dispatch(result)
        sent_again = d.dispatch(result)
        assert sent_again is False

    def test_different_host_not_suppressed(self):
        d = AlertDispatcher(cooldown_seconds=300)
        d.dispatch(self._make_result(host="h1"))
        sent = d.dispatch(self._make_result(host="h2"))
        assert sent is True

    def test_different_metric_not_suppressed(self):
        d = AlertDispatcher(cooldown_seconds=300)
        d.dispatch(self._make_result(metric="cpu"))
        sent = d.dispatch(self._make_result(metric="memory"))
        assert sent is True

    def test_cooldown_expiry_allows_resend(self):
        d = AlertDispatcher(cooldown_seconds=0)
        result = self._make_result()
        d.dispatch(result)
        time.sleep(0.01)
        sent = d.dispatch(result)
        assert sent is True

    def test_critical_severity_on_high_z(self):
        d = AlertDispatcher()
        result = self._make_result(z=6.0, score=-0.4)
        alert = d._build_alert(result)
        assert alert.severity == "critical"

    def test_warning_severity_on_moderate_z(self):
        d = AlertDispatcher()
        result = self._make_result(z=3.5, score=-0.1)
        alert = d._build_alert(result)
        assert alert.severity == "warning"

    def test_webhook_not_fired_when_url_empty(self):
        d = AlertDispatcher(webhook_url="")
        with patch("httpx.post") as mock_post:
            d._fire_webhook(d._build_alert(self._make_result()))
            mock_post.assert_not_called()

    def test_webhook_fired_when_url_set(self):
        d = AlertDispatcher(webhook_url="http://example.com/hook")
        with patch("httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            d._fire_webhook(d._build_alert(self._make_result()))
            mock_post.assert_called_once()
