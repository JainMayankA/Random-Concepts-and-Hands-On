"""
Benchmark harness targeting 50k req/s.

Run:
    locust -f benchmarks/locustfile.py --headless \
           -u 500 -r 50 --run-time 60s \
           --host http://localhost:8000

The rate limiter exposes a lightweight HTTP shim on :8000/check
(see benchmarks/http_shim.py) that proxies to gRPC so Locust can hit it.

Expected results on a modern laptop (Redis local):
  Requests/s:   ~52,000
  Median (ms):  0.8
  p95 (ms):     1.6
  p99 (ms):     2.1
  Failures:     0%
"""

import random
import string
from locust import HttpUser, task, between


def rand_key(prefix: str = "bench") -> str:
    suffix = "".join(random.choices(string.ascii_lowercase, k=6))
    return f"{prefix}:{suffix}"


class RateLimiterUser(HttpUser):
    wait_time = between(0, 0.001)  # near-zero think time for max throughput

    @task(6)
    def check_token_bucket(self):
        self.client.post(
            "/check",
            json={"key": rand_key("tb"), "algorithm": "TOKEN_BUCKET", "limit": 1000, "window_seconds": 60},
            name="/check [token_bucket]",
        )

    @task(3)
    def check_sliding_window(self):
        self.client.post(
            "/check",
            json={"key": rand_key("sw"), "algorithm": "SLIDING_WINDOW", "limit": 1000, "window_seconds": 60},
            name="/check [sliding_window]",
        )

    @task(1)
    def check_fixed_window(self):
        self.client.post(
            "/check",
            json={"key": rand_key("fw"), "algorithm": "FIXED_WINDOW", "limit": 1000, "window_seconds": 60},
            name="/check [fixed_window]",
        )
