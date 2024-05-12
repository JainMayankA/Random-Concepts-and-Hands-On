import time
import logging
from typing import List

import grpc

import proto.ratelimiter_pb2 as pb2
import proto.ratelimiter_pb2_grpc as pb2_grpc

logger = logging.getLogger(__name__)

Algorithm = pb2.Algorithm


class RateLimiterClient:
    """
    gRPC client with connection reuse, retry with exponential backoff, and timeout.
    """

    def __init__(self, host: str = "localhost", port: int = 50051, timeout: float = 0.5):
        self.target = f"{host}:{port}"
        self.timeout = timeout
        self._channel = None
        self._stub = None

    def _get_stub(self) -> pb2_grpc.RateLimiterStub:
        if self._channel is None:
            self._channel = grpc.insecure_channel(
                self.target,
                options=[
                    ("grpc.keepalive_time_ms", 10000),
                    ("grpc.keepalive_timeout_ms", 5000),
                    ("grpc.keepalive_permit_without_calls", True),
                ]
            )
            self._stub = pb2_grpc.RateLimiterStub(self._channel)
        return self._stub

    def check(
        self,
        key: str,
        algorithm: int = pb2.TOKEN_BUCKET,
        limit: int = 100,
        window_seconds: int = 60,
        retries: int = 3,
    ) -> pb2.CheckResponse:
        req = pb2.CheckRequest(
            key=key,
            algorithm=algorithm,
            limit=limit,
            window_seconds=window_seconds,
        )
        last_exc = None
        for attempt in range(retries):
            try:
                stub = self._get_stub()
                return stub.Check(req, timeout=self.timeout)
            except grpc.RpcError as e:
                last_exc = e
                if e.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
                    self._channel = None  # force reconnect
                    backoff = 0.05 * (2 ** attempt)
                    logger.warning(f"RPC failed ({e.code()}), retry {attempt+1} in {backoff:.2f}s")
                    time.sleep(backoff)
                else:
                    raise
        raise last_exc

    def check_batch(self, requests: List[dict]) -> List[pb2.CheckResponse]:
        batch = pb2.CheckBatchRequest(
            requests=[
                pb2.CheckRequest(
                    key=r["key"],
                    algorithm=r.get("algorithm", pb2.TOKEN_BUCKET),
                    limit=r.get("limit", 100),
                    window_seconds=r.get("window_seconds", 60),
                )
                for r in requests
            ]
        )
        stub = self._get_stub()
        resp = stub.CheckBatch(batch, timeout=self.timeout)
        return list(resp.responses)

    def close(self):
        if self._channel:
            self._channel.close()
            self._channel = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
