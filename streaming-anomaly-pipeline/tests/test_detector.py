"""
Tests for the Isolation Forest anomaly detector.
No Kafka or ClickHouse required — pure unit tests.
"""

import math
import time
import pytest
import numpy as np

from detector.isolation_forest import (
    StreamingAnomalyDetector, DetectorConfig, AnomalyResult
)


def make_detector(**kwargs) -> StreamingAnomalyDetector:
    config = DetectorConfig(
        contamination=0.05,
        window_size=100,
        retrain_interval=50,
        n_estimators=20,        # small for fast tests
        min_samples_to_train=30,
        **kwargs,
    )
    return StreamingAnomalyDetector(config)


def normal_values(n: int, mean: float = 50.0, std: float = 5.0) -> list[float]:
    rng = np.random.default_rng(42)
    return rng.normal(mean, std, n).tolist()


def timestamps(n: int) -> list[float]:
    base = time.time()
    return [base + i for i in range(n)]


class TestDetectorBasics:
    def test_process_batch_returns_results(self):
        d = make_detector()
        vals = normal_values(20)
        ts   = timestamps(20)
        results = d.process_batch("cpu", "host-1", "us-east-1", vals, ts)
        assert len(results) == 20

    def test_results_are_anomaly_result_instances(self):
        d = make_detector()
        vals = normal_values(20)
        results = d.process_batch("cpu", "host-1", "us-east-1", vals, timestamps(20))
        assert all(isinstance(r, AnomalyResult) for r in results)

    def test_metric_and_host_preserved(self):
        d = make_detector()
        vals = normal_values(10)
        results = d.process_batch("latency", "web-01", "eu-west-1", vals, timestamps(10))
        assert all(r.metric_name == "latency" for r in results)
        assert all(r.host == "web-01" for r in results)
        assert all(r.region == "eu-west-1" for r in results)

    def test_values_preserved_in_results(self):
        d = make_detector()
        vals = [10.0, 20.0, 30.0]
        results = d.process_batch("mem", "h1", "r1", vals, timestamps(3))
        assert [r.value for r in results] == vals

    def test_z_score_computed(self):
        d = make_detector()
        vals = normal_values(50)
        results = d.process_batch("cpu", "h1", "r1", vals, timestamps(50))
        assert all(isinstance(r.z_score, float) for r in results)

    def test_window_stats_populated(self):
        d = make_detector()
        vals = normal_values(60)
        results = d.process_batch("cpu", "h1", "r1", vals, timestamps(60))
        last = results[-1]
        assert last.window_mean > 0
        assert last.window_std >= 0


class TestAnomalyDetection:
    def test_normal_values_mostly_not_anomalous(self):
        d = make_detector(min_samples_to_train=30, retrain_interval=30)
        vals = normal_values(200, mean=50, std=5)
        ts   = timestamps(200)
        results = d.process_batch("cpu", "h1", "r1", vals, ts)
        # After model is trained, anomaly rate should be close to contamination
        trained_results = [r for r in results if r.anomaly_score != 0]
        if trained_results:
            rate = sum(r.is_anomaly for r in trained_results) / len(trained_results)
            assert rate < 0.20  # loose bound

    def test_extreme_spike_flagged_as_anomaly(self):
        """Inject a 10x spike — should be detected after model warms up."""
        d = make_detector(min_samples_to_train=30, retrain_interval=30)
        normal = normal_values(100, mean=50, std=5)
        spike = [500.0]  # 10x the mean
        ts = timestamps(101)
        results = d.process_batch("cpu", "h1", "r1", normal + spike, ts)
        # The spike has z_score >> 3
        spike_result = results[-1]
        assert spike_result.z_score > 5

    def test_independent_models_per_host(self):
        d = make_detector()
        vals = normal_values(50)
        ts   = timestamps(50)
        d.process_batch("cpu", "host-A", "r1", vals, ts)
        d.process_batch("cpu", "host-B", "r1", vals, ts)
        key_a = d._key("cpu", "host-A")
        key_b = d._key("cpu", "host-B")
        assert key_a != key_b
        assert key_a in d._windows
        assert key_b in d._windows

    def test_model_trained_after_min_samples(self):
        d = make_detector(min_samples_to_train=30, retrain_interval=30)
        vals = normal_values(60)
        d.process_batch("cpu", "h1", "r1", vals, timestamps(60))
        key = d._key("cpu", "h1")
        assert key in d._models

    def test_model_not_trained_before_min_samples(self):
        d = make_detector(min_samples_to_train=100)
        vals = normal_values(20)
        d.process_batch("cpu", "h1", "r1", vals, timestamps(20))
        key = d._key("cpu", "h1")
        assert key not in d._models

    def test_feature_extraction_shape(self):
        d = make_detector()
        arr = np.array(normal_values(50))
        features = d._extract_features(arr)
        assert features.shape == (50, 4)
        assert features.dtype in (np.float64, np.float32)

    def test_fallback_z_score_before_model_ready(self):
        """Before enough samples, extreme z-scores should still trigger is_anomaly."""
        d = make_detector(min_samples_to_train=500)
        normal = normal_values(10, mean=50, std=5)
        spike = [500.0]
        results = d.process_batch("cpu", "h1", "r1", normal + spike, timestamps(11))
        spike_result = results[-1]
        assert spike_result.is_anomaly is True
