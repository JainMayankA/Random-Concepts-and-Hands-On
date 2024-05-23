"""
Thin FastAPI HTTP shim that proxies /check → gRPC.
Used by Locust benchmarks only. Not production code.

Run alongside the gRPC server:
    uvicorn benchmarks.http_shim:app --port 8001 --workers 4
"""

from fastapi import FastAPI
from pydantic import BaseModel

import proto.ratelimiter_pb2 as pb2
from client.grpc_client import RateLimiterClient

app = FastAPI()
_client = RateLimiterClient(host="localhost", port=50051)

ALGO_MAP = {
    "TOKEN_BUCKET": pb2.TOKEN_BUCKET,
    "SLIDING_WINDOW": pb2.SLIDING_WINDOW,
    "FIXED_WINDOW": pb2.FIXED_WINDOW,
}


class CheckRequest(BaseModel):
    key: str
    algorithm: str = "TOKEN_BUCKET"
    limit: int = 100
    window_seconds: int = 60


@app.post("/check")
def check(req: CheckRequest):
    algo = ALGO_MAP.get(req.algorithm, pb2.TOKEN_BUCKET)
    result = _client.check(req.key, algo, req.limit, req.window_seconds)
    return {
        "allowed": result.allowed,
        "remaining": result.remaining,
        "retry_after_ms": result.retry_after_ms,
    }
