import time
import redis
from dataclasses import dataclass


@dataclass
class LimitResult:
    allowed: bool
    remaining: int
    retry_after_ms: int


class RateLimiter:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def check_token_bucket(self, key: str, capacity: int, window_seconds: int) -> LimitResult:
        """
        Token bucket: allows bursting up to capacity, refills at capacity/window_seconds rate.
        Uses Redis pipeline + WATCH for optimistic locking (atomic check-and-update).
        """
        bucket_key = f"tb:{key}"
        ts_key = f"tb:{key}:ts"
        refill_rate = capacity / window_seconds  # tokens per second

        for _ in range(10):  # retry on conflict
            try:
                with self.redis.pipeline() as pipe:
                    pipe.watch(bucket_key, ts_key)
                    tokens_raw = pipe.get(bucket_key)
                    last_ts_raw = pipe.get(ts_key)

                    now = time.time()
                    tokens = float(tokens_raw) if tokens_raw else float(capacity)
                    last_ts = float(last_ts_raw) if last_ts_raw else now

                    elapsed = max(0, now - last_ts)
                    tokens = min(capacity, tokens + elapsed * refill_rate)

                    if tokens >= 1:
                        pipe.multi()
                        pipe.set(bucket_key, tokens - 1, ex=window_seconds * 2)
                        pipe.set(ts_key, now, ex=window_seconds * 2)
                        pipe.execute()
                        return LimitResult(allowed=True, remaining=int(tokens - 1), retry_after_ms=0)
                    else:
                        wait_secs = (1 - tokens) / refill_rate
                        return LimitResult(allowed=False, remaining=0, retry_after_ms=int(wait_secs * 1000))
            except redis.WatchError:
                continue

        return LimitResult(allowed=False, remaining=0, retry_after_ms=100)

    def check_sliding_window(self, key: str, limit: int, window_seconds: int) -> LimitResult:
        """
        Sliding window log: stores request timestamps in a sorted set.
        Atomically removes expired entries and checks count.
        """
        sw_key = f"sw:{key}"
        now_ms = int(time.time() * 1000)
        window_ms = window_seconds * 1000
        cutoff = now_ms - window_ms

        with self.redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(sw_key, 0, cutoff)
            pipe.zcard(sw_key)
            pipe.zadd(sw_key, {str(now_ms): now_ms})
            pipe.expire(sw_key, window_seconds * 2)
            results = pipe.execute()

        count_before_add = results[1]

        if count_before_add < limit:
            return LimitResult(
                allowed=True,
                remaining=limit - count_before_add - 1,
                retry_after_ms=0
            )
        else:
            # Remove the entry we just added since we're blocking
            self.redis.zrem(sw_key, str(now_ms))
            oldest = self.redis.zrange(sw_key, 0, 0, withscores=True)
            if oldest:
                retry_ms = int(oldest[0][1]) + window_ms - now_ms
                retry_ms = max(0, retry_ms)
            else:
                retry_ms = window_ms
            return LimitResult(allowed=False, remaining=0, retry_after_ms=retry_ms)

    def check_fixed_window(self, key: str, limit: int, window_seconds: int) -> LimitResult:
        """
        Fixed window counter: simple INCR with TTL aligned to window boundaries.
        Fastest algorithm, slight burst risk at window boundary.
        """
        now = int(time.time())
        window_start = (now // window_seconds) * window_seconds
        fw_key = f"fw:{key}:{window_start}"

        with self.redis.pipeline(transaction=True) as pipe:
            pipe.incr(fw_key)
            pipe.expireat(fw_key, window_start + window_seconds + 1)
            results = pipe.execute()

        count = results[0]
        if count <= limit:
            return LimitResult(allowed=True, remaining=limit - count, retry_after_ms=0)
        else:
            next_window = window_start + window_seconds
            retry_ms = (next_window - now) * 1000
            return LimitResult(allowed=False, remaining=0, retry_after_ms=retry_ms)
