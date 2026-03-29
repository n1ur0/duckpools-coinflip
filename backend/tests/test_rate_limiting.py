"""
Tests for rate limiting (MAT-195).

Verify that:
1. Rate limiter is active and returns 429 when exceeded
2. Rate limit headers are present in responses
3. POST /place-bet has stricter limits (10/min) than default GET (60/min)
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Create test client with rate limiter disabled for setup, then re-enabled."""
    # Import must happen inside fixture to avoid module-level side effects
    from api_server import app

    with TestClient(app) as c:
        yield c


class TestRateLimitingHeaders:
    """Verify rate limit headers are present on responses."""

    def test_health_has_rate_limit_headers(self, client):
        """GET /health should include X-RateLimit headers."""
        resp = client.get("/health")
        assert resp.status_code == 200
        # slowapi adds these headers automatically
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers
        assert "X-RateLimit-Reset" in resp.headers

    def test_root_has_rate_limit_headers(self, client):
        """GET / should include X-RateLimit headers."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers


class TestRateLimitEnforcement:
    """Verify 429 is returned when limits are exceeded."""

    def test_get_endpoint_returns_429_after_burst(self, client):
        """Sending 70 rapid GET requests should trigger 429 (default: 60/min)."""
        hit_429 = False
        for i in range(70):
            resp = client.get("/")
            if resp.status_code == 429:
                hit_429 = True
                # Verify error response structure
                assert "error" in resp.json()
                break

        assert hit_429, "Expected 429 after exceeding 60 req/min limit"

    def test_post_place_bet_stricter_limit(self, client):
        """POST /place-bet should have 10/min limit (stricter than default 60)."""
        hit_429 = False
        for i in range(15):
            resp = client.post(
                "/place-bet",
                json={
                    "address": "3WvTka7H3jj5FsHXCSRGqozY4dmD5MhMHbXS3vJ5Qj2F3LM7JKNK",
                    "amount": "10000000",
                    "choice": 0,
                    "commitment": "a" * 64,
                    "betId": f"test-rate-limit-{i}",
                },
            )
            if resp.status_code == 429:
                hit_429 = True
                break

        assert hit_429, "Expected 429 after exceeding 10 req/min limit on /place-bet"

    def test_429_response_includes_retry_after(self, client):
        """429 response should include Retry-After header."""
        # Exhaust the limit first
        for i in range(70):
            resp = client.get("/")
            if resp.status_code == 429:
                assert "Retry-After" in resp.headers
                return

        pytest.fail("Never hit 429")
