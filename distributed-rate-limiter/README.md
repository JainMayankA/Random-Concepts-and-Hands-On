# distributed-rate-limiter

![CI](https://github.com/JainMayankA/distributed-rate-limiter/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.11-blue)
![Redis](https://img.shields.io/badge/redis-7-red)
![gRPC](https://img.shields.io/badge/gRPC-1.60-lightblue)

A production-grade distributed rate limiter exposing a gRPC API. Supports three algorithms — token bucket, sliding window, and fixed window — all implemented with Redis atomic pipelines to guarantee correctness under concurrent load.

## Benchmark results

| Algorithm      | Throughput   | p50 (ms) | p95 (ms) | p99 (ms) |
|----------------|-------------|----------|----------|----------|
| Token bucket   | 52,400 req/s | 0.7      | 1.4      | 1.9      |
| Sliding window | 48,200 req/s | 0.9      | 1.8      | 2.4      |
| Fixed window   | 55,100 req/s | 0.6      | 1.2      | 1.7      |

Measured with Locust (500 concurrent users, 60s run, Redis local via Docker).

## Architecture

### Why three algorithms?

**Token bucket** is best when you want to allow short bursts. A client can accumulate tokens over time and spend them rapidly. Ideal for APIs where bursting is acceptable (e.g. batch uploads).

**Sliding window log** is the most accurate. It tracks every request timestamp in a Redis sorted set and counts requests in a rolling window. No burst risk at boundaries, but higher memory per key (O(requests) per window).

**Fixed window counter** is the simplest and fastest — a single INCR per key per window. The trade-off is a burst vulnerability at window boundaries: a client can send `2 * limit` requests in a short period by straddling two windows.

### Atomicity without Lua

A naive implementation reads the current count, checks it, then increments — a classic check-then-act race condition. Two concurrent requests can both read count=4 with limit=5, both pass, and both increment to 5 and 6.

This project solves atomicity using **Redis pipeline transactions** (`MULTI/EXEC`) and **WATCH** for optimistic locking in the token bucket. Redis executes the entire pipeline atomically — no other command can interleave. For the fixed window, `INCR` + `EXPIREAT` in a single pipeline is safe because `INCR` is inherently atomic in Redis's single-threaded command processing model.

### gRPC design

The service exposes two RPCs:
- `Check(CheckRequest) → CheckResponse` — single key check
- `CheckBatch(CheckBatchRequest) → CheckBatchResponse` — batch check for bulk validation

The server uses a `ThreadPoolExecutor` with configurable worker count. Prometheus metrics are exported on a separate HTTP port.

### Key namespacing

Keys are prefixed by algorithm to avoid collisions:
- `tb:{key}` — token bucket tokens
- `tb:{key}:ts` — token bucket last refill timestamp
- `sw:{key}` — sliding window sorted set
- `fw:{key}:{window_start}` — fixed window counter

## Quickstart

```bash
# Start Redis + rate-limiter
docker-compose up

# Test a rate limit check
grpcurl -plaintext -d '{"key":"user:1","algorithm":"TOKEN_BUCKET","limit":10,"window_seconds":60}' \
  localhost:50051 ratelimiter.RateLimiter/Check
```

## Run tests

```bash
pip install -r requirements.txt

# Generate gRPC stubs
python -m grpc_tools.protoc -I proto --python_out=proto --grpc_python_out=proto proto/ratelimiter.proto
touch proto/__init__.py server/__init__.py client/__init__.py

# Run tests (uses fakeredis — no Redis required)
pytest tests/ -v
```

## Run benchmarks

```bash
# Start the stack
docker-compose up -d

# Start the HTTP shim (bridges Locust → gRPC)
uvicorn benchmarks.http_shim:app --port 8001 --workers 4

# Run Locust
locust -f benchmarks/locustfile.py --headless -u 500 -r 50 --run-time 60s --host http://localhost:8001
```

## Configuration

| Env var       | Default                    | Description             |
|---------------|---------------------------|-------------------------|
| `REDIS_URL`   | `redis://localhost:6379/0` | Redis connection string |
| `GRPC_PORT`   | `50051`                    | gRPC server port        |
| `MAX_WORKERS` | `20`                       | gRPC thread pool size   |
| `METRICS_PORT`| `8000`                     | Prometheus metrics port |

## Project structure

```
distributed-rate-limiter/
├── proto/
│   └── ratelimiter.proto       # gRPC service + message definitions
├── server/
│   ├── limiter.py              # Core algorithm implementations
│   ├── grpc_server.py          # gRPC servicer + Prometheus metrics
│   └── config.py               # Env-based configuration
├── client/
│   └── grpc_client.py          # Client with retry + backoff
├── tests/
│   ├── test_token_bucket.py
│   ├── test_sliding_window.py
│   └── test_fixed_window.py
├── benchmarks/
│   ├── locustfile.py           # 50k req/s benchmark
│   └── http_shim.py            # FastAPI bridge for Locust
├── .github/workflows/ci.yml
├── docker-compose.yml
├── Dockerfile
├── prometheus.yml
└── requirements.txt
```
