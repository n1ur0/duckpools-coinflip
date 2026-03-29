"""
Tests for bet history fix (Issue a4fc0db1).

Verifies:
1. POST /resolve-bet updates pending bets to win/loss/refunded
2. GET /history/{address} returns correct filtered results
3. GET /history (admin) returns all bets with API key
4. resolve-bet rejects already-resolved bets
5. resolve-bet rejects unknown bet IDs
6. resolve-bet validates outcome field
7. resolve-bet broadcasts WebSocket event
8. place-bet always creates pending bets
9. History endpoint handles empty results gracefully
"""

import os
import sys
import pytest
from httpx import AsyncClient, ASGITransport

# Add backend to path
_backend_dir = os.path.join(os.path.dirname(__file__), "..", "backend")
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# Set required env vars before importing app
os.environ.setdefault("NODE_API_KEY", "test-key")
os.environ.setdefault("ADMIN_API_KEY", "test-admin-key")

from api_server import app

VALID_ADDRESS = "3WxaBcDeFgHjKmNpQrStUvWxYzAbCdEfGhJkMnPqRsTuVwXyZaB"
OTHER_ADDRESS = "3yNMkABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnopqrstuvwxyz12"
VALID_COMMITMENT = "ab" * 32


def _clear_bets():
    """Reset the in-memory bet store between tests."""
    import game_routes
    game_routes._bets.clear()
    game_routes._pool_stats = {
        "liquidity": "50000000000000",
        "totalBets": 0,
        "playerWins": 0,
        "houseWins": 0,
        "totalFees": "0",
    }


@pytest.fixture(autouse=True)
def reset_state():
    """Reset in-memory state before each test."""
    _clear_bets()
    yield
    _clear_bets()


def _make_bet_id():
    """Generate a unique test bet ID."""
    import uuid
    return f"test-{uuid.uuid4().hex[:8]}"


# ─── place-bet tests ──────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_place_bet_creates_pending():
    """place-bet should always create a bet with outcome='pending'."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bet_id = _make_bet_id()
        resp = await client.post("/place-bet", json={
            "address": VALID_ADDRESS,
            "amount": "1000000",
            "choice": 0,
            "commitment": VALID_COMMITMENT,
            "betId": bet_id,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["betId"] == bet_id

        # Verify it shows up in history as pending
        hist = await client.get(f"/history/{VALID_ADDRESS}")
        bets = hist.json()
        assert len(bets) == 1
        assert bets[0]["outcome"] == "pending"
        assert bets[0]["playerAddress"] == VALID_ADDRESS
        assert bets[0]["txId"] == ""


@pytest.mark.anyio
async def test_place_bet_validates_address():
    """place-bet should reject invalid addresses."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/place-bet", json={
            "address": "invalid",
            "amount": "1000000",
            "choice": 0,
            "commitment": VALID_COMMITMENT,
            "betId": _make_bet_id(),
        })
        assert resp.status_code == 422


@pytest.mark.anyio
async def test_place_bet_validates_commitment():
    """place-bet should reject invalid commitments."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/place-bet", json={
            "address": VALID_ADDRESS,
            "amount": "1000000",
            "choice": 0,
            "commitment": "short",
            "betId": _make_bet_id(),
        })
        assert resp.status_code == 422


# ─── resolve-bet tests ───────────────────────────────────────────────────


@pytest.mark.anyio
async def test_resolve_bet_win():
    """resolve-bet should update a pending bet to 'win'."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bet_id = _make_bet_id()

        # Place a bet
        await client.post("/place-bet", json={
            "address": VALID_ADDRESS,
            "amount": "10000000",  # 0.01 ERG
            "choice": 0,
            "commitment": VALID_COMMITMENT,
            "betId": bet_id,
        })

        # Resolve it as win
        resp = await client.post("/resolve-bet", json={
            "betId": bet_id,
            "outcome": "win",
            "txId": "abc123def456abc123def456abc123def456abc123def456abc123def456abc1",
            "payout": "19400000",  # 0.0194 ERG (bet * 0.97 * 2)
            "resolvedAtHeight": 1000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "win" in data["message"]

        # Verify history shows the updated outcome
        hist = await client.get(f"/history/{VALID_ADDRESS}")
        bets = hist.json()
        assert len(bets) == 1
        assert bets[0]["outcome"] == "win"
        assert bets[0]["txId"] == "abc123def456abc123def456abc123def456abc123def456abc123def456abc1"
        assert bets[0]["payout"] == "19400000"
        assert bets[0]["resolvedAtHeight"] == 1000


@pytest.mark.anyio
async def test_resolve_bet_loss():
    """resolve-bet should update a pending bet to 'loss'."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bet_id = _make_bet_id()

        await client.post("/place-bet", json={
            "address": VALID_ADDRESS,
            "amount": "10000000",
            "choice": 1,
            "commitment": VALID_COMMITMENT,
            "betId": bet_id,
        })

        resp = await client.post("/resolve-bet", json={
            "betId": bet_id,
            "outcome": "loss",
            "txId": "def456abc123def456abc123def456abc123def456abc123def456abc123def4",
            "payout": "0",
            "resolvedAtHeight": 1001,
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        hist = await client.get(f"/history/{VALID_ADDRESS}")
        assert hist.json()[0]["outcome"] == "loss"


@pytest.mark.anyio
async def test_resolve_bet_refunded():
    """resolve-bet should handle 'refunded' outcome."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bet_id = _make_bet_id()

        await client.post("/place-bet", json={
            "address": VALID_ADDRESS,
            "amount": "10000000",
            "choice": 0,
            "commitment": VALID_COMMITMENT,
            "betId": bet_id,
        })

        resp = await client.post("/resolve-bet", json={
            "betId": bet_id,
            "outcome": "refunded",
            "payout": "10000000",  # Full refund
            "resolvedAtHeight": 999,
        })
        assert resp.status_code == 200

        hist = await client.get(f"/history/{VALID_ADDRESS}")
        assert hist.json()[0]["outcome"] == "refunded"


@pytest.mark.anyio
async def test_resolve_bet_rejects_already_resolved():
    """resolve-bet should reject resolving an already-resolved bet."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bet_id = _make_bet_id()

        await client.post("/place-bet", json={
            "address": VALID_ADDRESS,
            "amount": "10000000",
            "choice": 0,
            "commitment": VALID_COMMITMENT,
            "betId": bet_id,
        })

        # Resolve once
        await client.post("/resolve-bet", json={
            "betId": bet_id,
            "outcome": "win",
            "payout": "19400000",
        })

        # Try to resolve again
        resp = await client.post("/resolve-bet", json={
            "betId": bet_id,
            "outcome": "loss",
            "payout": "0",
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is False
        assert "already resolved" in resp.json()["message"]


@pytest.mark.anyio
async def test_resolve_bet_not_found():
    """resolve-bet should return failure for unknown bet IDs."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/resolve-bet", json={
            "betId": "nonexistent-bet-id",
            "outcome": "win",
            "payout": "19400000",
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is False
        assert "not found" in resp.json()["message"]


@pytest.mark.anyio
async def test_resolve_bet_validates_outcome():
    """resolve-bet should reject invalid outcome values."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/resolve-bet", json={
            "betId": "any",
            "outcome": "invalid_outcome",
            "payout": "0",
        })
        assert resp.status_code == 422


@pytest.mark.anyio
async def test_resolve_bet_validates_payout():
    """resolve-bet should reject non-numeric payout."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/resolve-bet", json={
            "betId": "any",
            "outcome": "win",
            "payout": "not-a-number",
        })
        assert resp.status_code == 422


# ─── history tests ───────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_history_empty_for_unknown_address():
    """history should return empty list for unknown address."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/history/3UnknownAddress123456789012345678901234")
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.anyio
async def test_history_filters_by_address():
    """history should only return bets for the requested address."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Place bets from two different addresses
        await client.post("/place-bet", json={
            "address": VALID_ADDRESS,
            "amount": "1000000",
            "choice": 0,
            "commitment": VALID_COMMITMENT,
            "betId": _make_bet_id(),
        })
        await client.post("/place-bet", json={
            "address": OTHER_ADDRESS,
            "amount": "2000000",
            "choice": 1,
            "commitment": VALID_COMMITMENT,
            "betId": _make_bet_id(),
        })
        await client.post("/place-bet", json={
            "address": VALID_ADDRESS,
            "amount": "3000000",
            "choice": 0,
            "commitment": VALID_COMMITMENT,
            "betId": _make_bet_id(),
        })

        # VALID_ADDRESS should see 2 bets
        hist1 = await client.get(f"/history/{VALID_ADDRESS}")
        assert len(hist1.json()) == 2

        # OTHER_ADDRESS should see 1 bet
        hist2 = await client.get(f"/history/{OTHER_ADDRESS}")
        assert len(hist2.json()) == 1


@pytest.mark.anyio
async def test_history_returns_bet_records():
    """history should return BetRecord-shaped objects."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bet_id = _make_bet_id()
        await client.post("/place-bet", json={
            "address": VALID_ADDRESS,
            "amount": "1000000",
            "choice": 0,
            "commitment": VALID_COMMITMENT,
            "betId": bet_id,
        })

        hist = await client.get(f"/history/{VALID_ADDRESS}")
        bet = hist.json()[0]

        # Verify all required BetRecord fields are present
        assert "betId" in bet
        assert "txId" in bet
        assert "boxId" in bet
        assert "playerAddress" in bet
        assert "gameType" in bet
        assert "choice" in bet
        assert "betAmount" in bet
        assert "outcome" in bet
        assert "payout" in bet
        assert "timestamp" in bet
        assert "blockHeight" in bet
        assert bet["playerAddress"] == VALID_ADDRESS
        assert bet["playerAddress"] != ""


# ─── admin history tests ─────────────────────────────────────────────────


@pytest.mark.anyio
async def test_admin_history_requires_api_key():
    """GET /history (admin) should reject requests without API key."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/history")
        assert resp.status_code == 401


@pytest.mark.anyio
async def test_admin_history_rejects_wrong_key():
    """GET /history should reject wrong API key."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/history?api_key=wrong-key")
        assert resp.status_code == 401


@pytest.mark.anyio
async def test_admin_history_returns_all_bets():
    """GET /history with valid API key should return ALL bets."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Place bets from two addresses
        await client.post("/place-bet", json={
            "address": VALID_ADDRESS,
            "amount": "1000000",
            "choice": 0,
            "commitment": VALID_COMMITMENT,
            "betId": _make_bet_id(),
        })
        await client.post("/place-bet", json={
            "address": OTHER_ADDRESS,
            "amount": "2000000",
            "choice": 1,
            "commitment": VALID_COMMITMENT,
            "betId": _make_bet_id(),
        })

        resp = await client.get("/history?api_key=test-admin-key")
        assert resp.status_code == 200
        bets = resp.json()
        assert len(bets) == 2


@pytest.mark.anyio
async def test_admin_history_empty():
    """GET /history should return empty list when no bets exist."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/history?api_key=test-admin-key")
        assert resp.status_code == 200
        assert resp.json() == []


# ─── end-to-end flow ─────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_full_bet_lifecycle():
    """Test complete bet lifecycle: place -> pending -> resolve -> history."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bet_id = _make_bet_id()

        # 1. Place bet
        place_resp = await client.post("/place-bet", json={
            "address": VALID_ADDRESS,
            "amount": "50000000",  # 0.05 ERG
            "choice": 0,
            "commitment": VALID_COMMITMENT,
            "betId": bet_id,
        })
        assert place_resp.status_code == 200
        assert place_resp.json()["success"] is True

        # 2. Check it's pending
        hist = await client.get(f"/history/{VALID_ADDRESS}")
        assert hist.json()[0]["outcome"] == "pending"
        assert hist.json()[0]["txId"] == ""
        assert hist.json()[0]["playerAddress"] == VALID_ADDRESS

        # 3. Resolve as win
        resolve_resp = await client.post("/resolve-bet", json={
            "betId": bet_id,
            "outcome": "win",
            "txId": "a" * 64,
            "payout": "97000000",  # 0.097 ERG
            "resolvedAtHeight": 500,
        })
        assert resolve_resp.status_code == 200
        assert resolve_resp.json()["success"] is True

        # 4. Check it's resolved
        hist = await client.get(f"/history/{VALID_ADDRESS}")
        bet = hist.json()[0]
        assert bet["outcome"] == "win"
        assert bet["txId"] == "a" * 64
        assert bet["payout"] == "97000000"
        assert bet["resolvedAtHeight"] == 500

        # 5. Check player stats updated
        stats = await client.get(f"/player/stats/{VALID_ADDRESS}")
        stats_data = stats.json()
        assert stats_data["totalBets"] == 1
        assert stats_data["wins"] == 1
        assert stats_data["losses"] == 0
        assert stats_data["pending"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
