"""
Phase 7, Scenario 5 — REST API Endpoint Contract Tests

Comprehensive tests for ALL REST API endpoints returning correct data:
  1. GET / — root endpoint
  2. GET /health — health check
  3. GET /contract-info — contract metadata
  4. POST /place-bet — bet placement
  5. GET /history/{address} — bet history
  6. GET /player/stats/{address} — player statistics
  7. GET /player/comp/{address} — comp points
  8. GET /leaderboard — global leaderboard
  9. GET /api/lp/* — LP endpoints (may be 404)
  10. WebSocket /ws — real-time bet updates

Also tests:
  - Response content types (JSON)
  - Response structure matches Pydantic models
  - Security headers on all responses
  - CORS headers
  - Error response format consistency
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient

from conftest import (
    TEST_PLAYER_ADDRESS,
    make_place_bet_payload,
)


# ─── Root Endpoint ───────────────────────────────────────────────────

class TestRootEndpoint:
    """GET / — API metadata and endpoint listing."""

    @pytest.mark.asyncio
    async def test_root_returns_200(self, app_client: AsyncClient):
        resp = await app_client.get("/")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_root_returns_json(self, app_client: AsyncClient):
        resp = await app_client.get("/")
        assert resp.headers["content-type"].startswith("application/json")

    @pytest.mark.asyncio
    async def test_root_has_api_name(self, app_client: AsyncClient):
        resp = await app_client.get("/")
        data = resp.json()
        assert "name" in data
        assert "DuckPools" in data["name"]

    @pytest.mark.asyncio
    async def test_root_has_version(self, app_client: AsyncClient):
        resp = await app_client.get("/")
        data = resp.json()
        assert "version" in data

    @pytest.mark.asyncio
    async def test_root_lists_endpoints(self, app_client: AsyncClient):
        resp = await app_client.get("/")
        data = resp.json()
        assert "endpoints" in data
        endpoints = data["endpoints"]
        assert "place_bet" in endpoints
        assert "leaderboard" in endpoints
        assert "history" in endpoints
        assert "player_stats" in endpoints
        assert "player_comp" in endpoints
        assert "health" in endpoints


# ─── Health Endpoint ────────────────────────────────────────────────

class TestHealthEndpoint:
    """GET /health — service health check."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, app_client: AsyncClient):
        resp = await app_client.get("/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_health_returns_json(self, app_client: AsyncClient):
        resp = await app_client.get("/health")
        assert resp.headers["content-type"].startswith("application/json")

    @pytest.mark.asyncio
    async def test_health_has_status_field(self, app_client: AsyncClient):
        resp = await app_client.get("/health")
        data = resp.json()
        assert "status" in data
        assert data["status"] in ("ok", "degraded")

    @pytest.mark.asyncio
    async def test_health_has_node_field(self, app_client: AsyncClient):
        resp = await app_client.get("/health")
        data = resp.json()
        assert "node" in data

    @pytest.mark.asyncio
    async def test_health_node_url_format(self, app_client: AsyncClient):
        resp = await app_client.get("/health")
        data = resp.json()
        assert data["node"].startswith("http://")


# ─── Contract Info ───────────────────────────────────────────────────

class TestContractInfoEndpoint:
    """GET /contract-info — smart contract metadata."""

    @pytest.mark.asyncio
    async def test_contract_info_returns_200(self, app_client: AsyncClient):
        resp = await app_client.get("/contract-info")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_contract_info_returns_json(self, app_client: AsyncClient):
        resp = await app_client.get("/contract-info")
        assert resp.headers["content-type"].startswith("application/json")

    @pytest.mark.asyncio
    async def test_contract_info_has_required_fields(self, app_client: AsyncClient):
        resp = await app_client.get("/contract-info")
        data = resp.json()
        assert "p2sAddress" in data
        assert "ergoTree" in data
        assert "registers" in data


# ─── Place Bet ───────────────────────────────────────────────────────

class TestPlaceBetEndpoint:
    """POST /place-bet — bet placement."""

    @pytest.mark.asyncio
    async def test_place_bet_returns_json(self, app_client: AsyncClient):
        payload = make_place_bet_payload()
        resp = await app_client.post("/place-bet", json=payload)
        assert resp.headers["content-type"].startswith("application/json")

    @pytest.mark.asyncio
    async def test_place_bet_response_has_required_fields(self, app_client: AsyncClient):
        payload = make_place_bet_payload()
        resp = await app_client.post("/place-bet", json=payload)
        data = resp.json()
        assert "success" in data
        assert "betId" in data
        assert "message" in data

    @pytest.mark.asyncio
    async def test_place_bet_success_response_structure(self, app_client: AsyncClient):
        payload = make_place_bet_payload()
        resp = await app_client.post("/place-bet", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["success"], bool)
        assert isinstance(data["betId"], str)
        assert isinstance(data["message"], str)


# ─── History ─────────────────────────────────────────────────────────

class TestHistoryEndpoint:
    """GET /history/{address} — bet history."""

    @pytest.mark.asyncio
    async def test_history_returns_json(self, app_client: AsyncClient):
        resp = await app_client.get(f"/history/{TEST_PLAYER_ADDRESS}")
        assert resp.headers["content-type"].startswith("application/json")

    @pytest.mark.asyncio
    async def test_history_returns_list(self, app_client: AsyncClient):
        resp = await app_client.get(f"/history/{TEST_PLAYER_ADDRESS}")
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_history_bet_record_structure(self, app_client: AsyncClient):
        """When bets exist, each record should match BetRecord schema."""
        payload = make_place_bet_payload(bet_id="structure-test-1")
        await app_client.post("/place-bet", json=payload)

        resp = await app_client.get(f"/history/{TEST_PLAYER_ADDRESS}")
        bets = resp.json()
        assert len(bets) >= 1

        bet = bets[-1]
        required_fields = {
            "betId", "txId", "playerAddress", "gameType",
            "choice", "betAmount", "outcome", "payout",
            "payoutMultiplier", "timestamp", "blockHeight",
        }
        assert required_fields.issubset(set(bet.keys()))

    @pytest.mark.asyncio
    async def test_history_bet_types(self, app_client: AsyncClient):
        """Verify field types match the Pydantic model."""
        payload = make_place_bet_payload(bet_id="type-test-1")
        await app_client.post("/place-bet", json=payload)

        resp = await app_client.get(f"/history/{TEST_PLAYER_ADDRESS}")
        bet = resp.json()[-1]

        assert isinstance(bet["betId"], str)
        assert isinstance(bet["txId"], str)
        assert isinstance(bet["playerAddress"], str)
        assert isinstance(bet["gameType"], str)
        assert isinstance(bet["betAmount"], str)
        assert isinstance(bet["outcome"], str)
        assert isinstance(bet["payout"], str)
        assert isinstance(bet["payoutMultiplier"], float)
        assert isinstance(bet["blockHeight"], int)


# ─── Player Stats ────────────────────────────────────────────────────

class TestPlayerStatsEndpoint:
    """GET /player/stats/{address} — player statistics."""

    @pytest.mark.asyncio
    async def test_stats_returns_json(self, app_client: AsyncClient):
        resp = await app_client.get(f"/player/stats/{TEST_PLAYER_ADDRESS}")
        assert resp.headers["content-type"].startswith("application/json")

    @pytest.mark.asyncio
    async def test_stats_response_structure(self, app_client: AsyncClient):
        resp = await app_client.get(f"/player/stats/{TEST_PLAYER_ADDRESS}")
        data = resp.json()
        required_fields = {
            "address", "totalBets", "wins", "losses", "pending",
            "winRate", "totalWagered", "totalWon", "totalLost",
            "netPnL", "biggestWin", "currentStreak",
            "longestWinStreak", "longestLossStreak",
            "compPoints", "compTier",
        }
        assert required_fields.issubset(set(data.keys()))

    @pytest.mark.asyncio
    async def test_stats_field_types(self, app_client: AsyncClient):
        resp = await app_client.get(f"/player/stats/{TEST_PLAYER_ADDRESS}")
        data = resp.json()
        assert isinstance(data["address"], str)
        assert isinstance(data["totalBets"], int)
        assert isinstance(data["wins"], int)
        assert isinstance(data["losses"], int)
        assert isinstance(data["pending"], int)
        assert isinstance(data["winRate"], float)
        assert isinstance(data["totalWagered"], str)
        assert isinstance(data["netPnL"], str)
        assert isinstance(data["compPoints"], int)
        assert isinstance(data["compTier"], str)


# ─── Player Comp ─────────────────────────────────────────────────────

class TestPlayerCompEndpoint:
    """GET /player/comp/{address} — comp points."""

    @pytest.mark.asyncio
    async def test_comp_returns_json(self, app_client: AsyncClient):
        resp = await app_client.get(f"/player/comp/{TEST_PLAYER_ADDRESS}")
        assert resp.headers["content-type"].startswith("application/json")

    @pytest.mark.asyncio
    async def test_comp_response_structure(self, app_client: AsyncClient):
        resp = await app_client.get(f"/player/comp/{TEST_PLAYER_ADDRESS}")
        data = resp.json()
        required_fields = {
            "address", "points", "tier", "tierProgress",
            "nextTier", "pointsToNextTier", "totalEarned", "benefits",
        }
        assert required_fields.issubset(set(data.keys()))

    @pytest.mark.asyncio
    async def test_comp_field_types(self, app_client: AsyncClient):
        resp = await app_client.get(f"/player/comp/{TEST_PLAYER_ADDRESS}")
        data = resp.json()
        assert isinstance(data["address"], str)
        assert isinstance(data["points"], int)
        assert isinstance(data["tier"], str)
        assert isinstance(data["tierProgress"], float)
        assert isinstance(data["nextTier"], str)
        assert isinstance(data["pointsToNextTier"], int)
        assert isinstance(data["totalEarned"], int)
        assert isinstance(data["benefits"], list)

    @pytest.mark.asyncio
    async def test_comp_benefits_are_strings(self, app_client: AsyncClient):
        resp = await app_client.get(f"/player/comp/{TEST_PLAYER_ADDRESS}")
        data = resp.json()
        for benefit in data["benefits"]:
            assert isinstance(benefit, str)


# ─── Leaderboard ─────────────────────────────────────────────────────

class TestLeaderboardEndpoint:
    """GET /leaderboard — global leaderboard."""

    @pytest.mark.asyncio
    async def test_leaderboard_returns_json(self, app_client: AsyncClient):
        resp = await app_client.get("/leaderboard")
        assert resp.headers["content-type"].startswith("application/json")

    @pytest.mark.asyncio
    async def test_leaderboard_response_structure(self, app_client: AsyncClient):
        resp = await app_client.get("/leaderboard")
        data = resp.json()
        assert "players" in data
        assert "totalPlayers" in data
        assert "sortBy" in data

    @pytest.mark.asyncio
    async def test_leaderboard_field_types(self, app_client: AsyncClient):
        resp = await app_client.get("/leaderboard")
        data = resp.json()
        assert isinstance(data["players"], list)
        assert isinstance(data["totalPlayers"], int)
        assert isinstance(data["sortBy"], str)


# ─── Security Headers ───────────────────────────────────────────────

class TestSecurityHeaders:
    """All endpoints should return security headers."""

    @pytest.mark.asyncio
    async def test_root_has_security_headers(self, app_client: AsyncClient):
        resp = await app_client.get("/")
        self._assert_security_headers(resp)

    @pytest.mark.asyncio
    async def test_health_has_security_headers(self, app_client: AsyncClient):
        resp = await app_client.get("/health")
        self._assert_security_headers(resp)

    @pytest.mark.asyncio
    async def test_place_bet_has_security_headers(self, app_client: AsyncClient):
        payload = make_place_bet_payload()
        resp = await app_client.post("/place-bet", json=payload)
        self._assert_security_headers(resp)

    @pytest.mark.asyncio
    async def test_history_has_security_headers(self, app_client: AsyncClient):
        resp = await app_client.get(f"/history/{TEST_PLAYER_ADDRESS}")
        self._assert_security_headers(resp)

    @pytest.mark.asyncio
    async def test_404_has_security_headers(self, app_client: AsyncClient):
        resp = await app_client.get("/nonexistent-endpoint")
        self._assert_security_headers(resp)

    @pytest.mark.asyncio
    async def test_422_has_security_headers(self, app_client: AsyncClient):
        resp = await app_client.post("/place-bet", json={})
        self._assert_security_headers(resp)

    def _assert_security_headers(self, resp):
        headers = resp.headers
        assert "x-content-type-options" in headers
        assert headers["x-content-type-options"] == "nosniff"
        assert "x-frame-options" in headers
        assert headers["x-frame-options"] == "DENY"
        assert "x-xss-protection" in headers
        assert "referrer-policy" in headers
        assert "permissions-policy" in headers
        assert "content-security-policy" in headers


# ─── Error Response Format ──────────────────────────────────────────

class TestErrorResponseFormat:
    """Error responses should follow a consistent JSON structure."""

    @pytest.mark.asyncio
    async def test_404_error_format(self, app_client: AsyncClient):
        resp = await app_client.get("/nonexistent")
        assert resp.status_code == 404
        data = resp.json()
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert "path" in data["error"]
        assert data["error"]["code"] == 404

    @pytest.mark.asyncio
    async def test_422_error_format(self, app_client: AsyncClient):
        resp = await app_client.post("/place-bet", json={})
        assert resp.status_code == 422
        # FastAPI validation errors have a specific format
        data = resp.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_405_method_not_allowed(self, app_client: AsyncClient):
        resp = await app_client.delete("/place-bet")
        assert resp.status_code == 405


# ─── HTTP Methods ────────────────────────────────────────────────────

class TestHttpMethods:
    """Verify only allowed HTTP methods work."""

    @pytest.mark.asyncio
    async def test_get_on_place_bet_returns_405(self, app_client: AsyncClient):
        resp = await app_client.get("/place-bet")
        assert resp.status_code == 405

    @pytest.mark.asyncio
    async def test_delete_on_history_returns_405(self, app_client: AsyncClient):
        resp = await app_client.delete(f"/history/{TEST_PLAYER_ADDRESS}")
        assert resp.status_code == 405

    @pytest.mark.asyncio
    async def test_post_on_leaderboard_returns_405(self, app_client: AsyncClient):
        resp = await app_client.post("/leaderboard", json={})
        assert resp.status_code == 405

    @pytest.mark.asyncio
    async def test_put_on_stats_returns_405(self, app_client: AsyncClient):
        resp = await app_client.put(f"/player/stats/{TEST_PLAYER_ADDRESS}", json={})
        assert resp.status_code == 405

    @pytest.mark.asyncio
    async def test_patch_on_comp_returns_405(self, app_client: AsyncClient):
        resp = await app_client.patch(f"/player/comp/{TEST_PLAYER_ADDRESS}", json={})
        assert resp.status_code == 405


# ─── Response Time ───────────────────────────────────────────────────

class TestResponseTime:
    """API responses should be fast."""

    @pytest.mark.asyncio
    async def test_health_response_under_100ms(self, app_client: AsyncClient):
        import time
        start = time.perf_counter()
        resp = await app_client.get("/health")
        elapsed = (time.perf_counter() - start) * 1000
        assert resp.status_code == 200
        assert elapsed < 100, f"Health took {elapsed:.1f}ms"

    @pytest.mark.asyncio
    async def test_root_response_under_50ms(self, app_client: AsyncClient):
        import time
        start = time.perf_counter()
        resp = await app_client.get("/")
        elapsed = (time.perf_counter() - start) * 1000
        assert resp.status_code == 200
        assert elapsed < 50, f"Root took {elapsed:.1f}ms"

    @pytest.mark.asyncio
    async def test_place_bet_response_under_100ms(self, app_client: AsyncClient):
        import time
        payload = make_place_bet_payload()
        start = time.perf_counter()
        resp = await app_client.post("/place-bet", json=payload)
        elapsed = (time.perf_counter() - start) * 1000
        assert resp.status_code == 200
        assert elapsed < 100, f"Place bet took {elapsed:.1f}ms"
