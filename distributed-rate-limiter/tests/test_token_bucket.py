import time
import pytest
import fakeredis

from server.limiter import RateLimiter


@pytest.fixture
def limiter():
    client = fakeredis.FakeRedis(decode_responses=True)
    return RateLimiter(client)


def test_token_bucket_allows_within_limit(limiter):
    result = limiter.check_token_bucket("user:1", capacity=10, window_seconds=60)
    assert result.allowed is True
    assert result.remaining == 9


def test_token_bucket_decrements_remaining(limiter):
    for i in range(5):
        r = limiter.check_token_bucket("user:2", capacity=10, window_seconds=60)
        assert r.allowed is True
        assert r.remaining == 9 - i


def test_token_bucket_blocks_when_exhausted(limiter):
    for _ in range(5):
        limiter.check_token_bucket("user:3", capacity=5, window_seconds=60)
    result = limiter.check_token_bucket("user:3", capacity=5, window_seconds=60)
    assert result.allowed is False
    assert result.remaining == 0
    assert result.retry_after_ms > 0


def test_token_bucket_different_keys_independent(limiter):
    for _ in range(5):
        limiter.check_token_bucket("user:4a", capacity=5, window_seconds=60)
    # user:4b is untouched — should still be allowed
    r = limiter.check_token_bucket("user:4b", capacity=5, window_seconds=60)
    assert r.allowed is True


def test_token_bucket_retry_after_reasonable(limiter):
    for _ in range(3):
        limiter.check_token_bucket("user:5", capacity=3, window_seconds=10)
    result = limiter.check_token_bucket("user:5", capacity=3, window_seconds=10)
    assert result.allowed is False
    assert 0 < result.retry_after_ms <= 10_000
