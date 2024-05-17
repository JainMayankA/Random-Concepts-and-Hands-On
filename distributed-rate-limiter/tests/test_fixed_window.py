import pytest
import fakeredis

from server.limiter import RateLimiter


@pytest.fixture
def limiter():
    client = fakeredis.FakeRedis(decode_responses=True)
    return RateLimiter(client)


def test_fixed_window_allows_within_limit(limiter):
    result = limiter.check_fixed_window("fw:user:1", limit=10, window_seconds=60)
    assert result.allowed is True
    assert result.remaining == 9


def test_fixed_window_blocks_over_limit(limiter):
    for _ in range(10):
        limiter.check_fixed_window("fw:user:2", limit=10, window_seconds=60)
    result = limiter.check_fixed_window("fw:user:2", limit=10, window_seconds=60)
    assert result.allowed is False
    assert result.remaining == 0
    assert result.retry_after_ms > 0


def test_fixed_window_retry_after_within_window(limiter):
    for _ in range(5):
        limiter.check_fixed_window("fw:user:3", limit=5, window_seconds=10)
    result = limiter.check_fixed_window("fw:user:3", limit=5, window_seconds=10)
    assert 0 < result.retry_after_ms <= 11_000


class TestAllAlgorithmsTogether:
    """Smoke tests running all three algorithms back to back."""

    def test_all_allow_first_request(self, limiter):
        assert limiter.check_token_bucket("cmp:1", 10, 60).allowed is True
        assert limiter.check_sliding_window("cmp:1", 10, 60).allowed is True
        assert limiter.check_fixed_window("cmp:1", 10, 60).allowed is True

    def test_all_block_after_exhaustion(self, limiter):
        for _ in range(3):
            limiter.check_token_bucket("cmp:2", 3, 60)
            limiter.check_sliding_window("cmp:2", 3, 60)
            limiter.check_fixed_window("cmp:2", 3, 60)

        assert limiter.check_token_bucket("cmp:2", 3, 60).allowed is False
        assert limiter.check_sliding_window("cmp:2", 3, 60).allowed is False
        assert limiter.check_fixed_window("cmp:2", 3, 60).allowed is False
