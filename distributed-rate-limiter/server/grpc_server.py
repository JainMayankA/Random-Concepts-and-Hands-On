import time
import logging
import signal
import sys
from concurrent import futures

import grpc
import redis
from prometheus_client import Counter, Histogram, start_http_server

from server.config import Config
from server.limiter import RateLimiter
import proto.ratelimiter_pb2 as pb2
import proto.ratelimiter_pb2_grpc as pb2_grpc

logger = logging.getLogger(__name__)

REQUEST_COUNT = Counter(
    "ratelimiter_requests_total",
    "Total rate limit checks",
    ["algorithm", "result"]
)
REQUEST_LATENCY = Histogram(
    "ratelimiter_request_duration_seconds",
    "Request duration",
    ["algorithm"]
)

ALGO_MAP = {
    pb2.TOKEN_BUCKET: "token_bucket",
    pb2.SLIDING_WINDOW: "sliding_window",
    pb2.FIXED_WINDOW: "fixed_window",
}


class RateLimiterServicer(pb2_grpc.RateLimiterServicer):
    def __init__(self, limiter: RateLimiter):
        self.limiter = limiter

    def _check_one(self, req) -> pb2.CheckResponse:
        algo_name = ALGO_MAP.get(req.algorithm, "token_bucket")
        start = time.perf_counter()

        if req.algorithm == pb2.TOKEN_BUCKET:
            result = self.limiter.check_token_bucket(req.key, req.limit, req.window_seconds)
        elif req.algorithm == pb2.SLIDING_WINDOW:
            result = self.limiter.check_sliding_window(req.key, req.limit, req.window_seconds)
        else:
            result = self.limiter.check_fixed_window(req.key, req.limit, req.window_seconds)

        elapsed = time.perf_counter() - start
        REQUEST_LATENCY.labels(algorithm=algo_name).observe(elapsed)
        REQUEST_COUNT.labels(algorithm=algo_name, result="allowed" if result.allowed else "blocked").inc()

        return pb2.CheckResponse(
            allowed=result.allowed,
            remaining=result.remaining,
            retry_after_ms=result.retry_after_ms
        )

    def Check(self, request, context):
        return self._check_one(request)

    def CheckBatch(self, request, context):
        responses = [self._check_one(r) for r in request.requests]
        return pb2.CheckBatchResponse(responses=responses)


def serve(config: Config):
    redis_client = redis.from_url(config.redis_url, decode_responses=True)
    limiter = RateLimiter(redis_client)

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=config.max_workers),
        options=[
            ("grpc.max_send_message_length", 10 * 1024 * 1024),
            ("grpc.max_receive_message_length", 10 * 1024 * 1024),
        ]
    )
    pb2_grpc.add_RateLimiterServicer_to_server(RateLimiterServicer(limiter), server)
    server.add_insecure_port(f"[::]:{config.grpc_port}")

    start_http_server(config.metrics_port)
    logger.info(f"gRPC server on :{config.grpc_port}, metrics on :{config.metrics_port}")

    server.start()

    def shutdown(sig, frame):
        logger.info("Shutting down...")
        server.stop(grace=5)
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    server.wait_for_termination()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    serve(Config.from_env())
