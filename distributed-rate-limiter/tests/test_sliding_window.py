import pytest
import fakeredis

from server.limiter import RateLimiter


@pytest.fixture
def limiter():
    client = fakeredis.FakeRedis(decode_responses=True)
    return RateLimiter(client)


def test_sliding_window_allows_within_limit(limiter):
    result = limiter.check_sliding_window("sw:user:1", limit=5, window_seconds=60)
    assert result.allowed is True
    assert result.remaining == 4


def test_sliding_window_tracks_count(limiter):
    for i in range(4):
        r = limiter.check_sliding_window("sw:user:2", limit=5, window_seconds=60)
        assert r.allowed is True
        assert r.remaining == 4 - i


def test_sliding_window_blocks_at_limit(limiter):
    for _ in range(5):
        limiter.check_sliding_window("sw:user:3", limit=5, window_seconds=60)
    result = limiter.check_sliding_window("sw:user:3", limit=5, window_seconds=60)
    assert result.allowed is False
    assert result.remaining == 0


def test_sliding_window_retry_after_set_when_blocked(limiter):
    for _ in range(3):
        limiter.check_sliding_window("sw:user:4", limit=3, window_seconds=30)
    result = limiter.check_sliding_window("sw:user:4", limit=3, window_seconds=30)
    assert result.allowed is False
    assert result.retry_after_ms > 0


def test_sliding_window_independent_keys(limiter):
    for _ in range(5):
        limiter.check_sliding_window("sw:a", limit=5, window_seconds=60)
    r = limiter.check_sliding_window("sw:b", limit=5, window_seconds=60)
    assert r.allowed is True
