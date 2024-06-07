"""
Isolation Forest anomaly detector with online sliding window.

Isolation Forest works by randomly partitioning the feature space:
anomalies are isolated in fewer splits (shorter path length) than
normal points, because they occupy low-density regions.

Online adaptation: we maintain a sliding window of recent values
and periodically retrain the model so it adapts to gradual drift
(e.g. CPU baseline rising over time due to new traffic patterns).

Features per window:
  - raw value
  - z-score within window
  - rolling mean deviation
  - rate of change (first derivative)
"""

from __future__ import annotations
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


@dataclass
class AnomalyResult:
    metric_name: str
    host: str
    region: str
    value: float
    timestamp: float
    anomaly_score: float          # raw IF score (more negative = more anomalous)
    is_anomaly: bool
    z_score: float
    window_mean: float
    window_std: float


@dataclass
class DetectorConfig:
    contamination: float = 0.05   # expected fraction of anomalies
    window_size: int = 200         # rolling window for feature extraction
    retrain_interval: int = 500    # retrain model every N new samples
    n_estimators: int = 100
    min_samples_to_train: int = 50


class StreamingAnomalyDetector:
    """
    Per-(metric, host) Isolation Forest with sliding window and periodic retraining.
    Each unique (metric_name, host) gets its own model instance to capture
    host-specific baselines.
    """

    def __init__(self, config: Optional[DetectorConfig] = None):
        self.config = config or DetectorConfig()
        self._models:   dict[str, IsolationForest] = {}
        self._scalers:  dict[str, StandardScaler] = {}
        self._windows:  dict[str, deque] = {}
        self._counters: dict[str, int] = {}
        self._last_retrain: dict[str, int] = {}

    def _key(self, metric: str, host: str) -> str:
        return f"{metric}::{host}"

    def process_batch(self, metric_name: str, host: str, region: str,
                      values: list[float], timestamps: list[float]) -> list[AnomalyResult]:
        key = self._key(metric_name, host)

        # Update sliding window
        if key not in self._windows:
            self._windows[key] = deque(maxlen=self.config.window_size)
            self._counters[key] = 0
            self._last_retrain[key] = 0

        window = self._windows[key]
        window.extend(values)
        self._counters[key] += len(values)

        # Retrain if enough data and interval elapsed
        count = self._counters[key]
        if (count >= self.config.min_samples_to_train and
                count - self._last_retrain.get(key, 0) >= self.config.retrain_interval):
            self._train(key)
            self._last_retrain[key] = count

        results = []
        for value, ts in zip(values, timestamps):
            result = self._score_point(key, metric_name, host, region, value, ts)
            results.append(result)

        return results

    def _train(self, key: str):
        window = list(self._windows[key])
        if len(window) < self.config.min_samples_to_train:
            return

        X = self._extract_features(np.array(window))

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        model = IsolationForest(
            n_estimators=self.config.n_estimators,
            contamination=self.config.contamination,
            random_state=42,
            n_jobs=-1,
        )
        model.fit(X_scaled)

        self._models[key] = model
        self._scalers[key] = scaler
        logger.debug(f"Retrained model for {key} on {len(window)} samples")

    def _score_point(self, key: str, metric: str, host: str, region: str,
                     value: float, timestamp: float) -> AnomalyResult:
        window = list(self._windows[key])
        win_arr = np.array(window) if window else np.array([value])
        mean = float(np.mean(win_arr))
        std  = float(np.std(win_arr)) or 1.0
        z    = (value - mean) / std

        is_anomaly = False
        score = 0.0

        if key in self._models:
            X = self._extract_features(np.array([*window[-49:], value]))
            x_point = X[[-1]]
            x_scaled = self._scalers[key].transform(x_point)
            score = float(self._models[key].score_samples(x_scaled)[0])
            # IsolationForest: predict returns -1 for anomaly, 1 for normal
            pred = self._models[key].predict(x_scaled)[0]
            is_anomaly = (pred == -1)
        else:
            # Fallback: z-score > 3 while model warms up
            is_anomaly = abs(z) > 3.0

        return AnomalyResult(
            metric_name=metric,
            host=host,
            region=region,
            value=round(value, 4),
            timestamp=timestamp,
            anomaly_score=round(score, 6),
            is_anomaly=is_anomaly,
            z_score=round(z, 4),
            window_mean=round(mean, 4),
            window_std=round(std, 4),
        )

    def _extract_features(self, values: np.ndarray) -> np.ndarray:
        """
        Extract a feature matrix from a 1-D value array.
        Each row = one time step, columns = [value, z_score, mean_dev, rate_of_change].
        """
        n = len(values)
        mean = np.mean(values)
        std  = np.std(values) or 1.0

        z_scores = (values - mean) / std
        mean_dev = np.abs(values - mean)
        roc = np.diff(values, prepend=values[0])

        return np.column_stack([values, z_scores, mean_dev, roc])
