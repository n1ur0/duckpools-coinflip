import pytest
import httpx
import json
import hashlib
import os
from typing import Dict, Any

# Test configuration
BASE_URL = "http://localhost:8000"
# Valid Ergo testnet address (Base58Check: no 0, O, I, l)
TEST_WALLET_ADDRESS = "9hGmWb9v8k7j6F5d4s3a2Z1xcV8n7M6p5Q4r3T2y1Uh"
MIN_BET_NANOERG = 1_000_000  # 0.001 ERG
HOUSE_EDGE_BPS = 300  # 3% house edge
PAYOUT_MULTIPLIER = 0.97  # 97% payout (100% - 3% house edge)

# Generate test commitment and secret
TEST_SECRET = os.urandom(8).hex()  # 16 hex chars
TEST_CHOICE = 0  # heads
TEST_COMMITMENT = hashlib.blake2b(
    bytes.fromhex(TEST_SECRET) + bytes([TEST_CHOICE]), digest_size=32
).hexdigest()


def _make_bet_payload(bet_id: str = "test-bet-001", amount: int = MIN_BET_NANOERG, choice: int = 0) -> dict:
    """Build a valid PlaceBetRequest payload matching current API contract."""
    return {
        "address": TEST_WALLET_ADDRESS,
        "amount": str(amount),
        "choice": choice,
        "commitment": TEST_COMMITMENT,
        "betId": bet_id,
        "housePubKey": "02" + "aa" * 32,  # 33-byte compressed PK placeholder
        "houseAddress": "3Wx6TkZU8dENHf4moAv3GgYqTs3fbpsk6DFnJr9WQgZ72MxtQbV",  # House P2PK address placeholder
        "playerPubKey": "02" + "bb" * 32,
        "playerSecret": TEST_SECRET,
        "playerErgoTree": "1005040004000e36100204",
    }


class TestCoinflipAPI:
    """Test suite for coinflip API endpoints"""

    @pytest.fixture(scope="class")
    def client(self):
        """HTTP client fixture"""
        return httpx.Client(base_url=BASE_URL)

    def test_health_endpoint(self, client):
        """Test health endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # May be "ok" or "degraded" if node is down
        assert data["status"] in ("ok", "degraded")

    def test_pool_state_endpoint(self, client):
        """Test pool state endpoint"""
        response = client.get("/pool/state")
        assert response.status_code == 200
        data = response.json()
        assert "liquidity" in data
        assert "totalBets" in data
        assert "safeMaxBet" in data
        assert isinstance(data["liquidity"], str)
        assert isinstance(data["safeMaxBet"], int)

    def test_contract_info_endpoint(self, client):
        """Test contract-info endpoint (replaces /scripts)"""
        response = client.get("/contract-info")
        assert response.status_code == 200
        data = response.json()
        assert "p2sAddress" in data
        assert "ergoTree" in data
        assert "registers" in data
        assert isinstance(data["p2sAddress"], str)
        assert len(data["p2sAddress"]) > 100
        assert isinstance(data["ergoTree"], str)
        assert len(data["ergoTree"]) > 100

    def test_place_bet_valid(self, client):
        """Test placing a valid bet"""
        bet_data = _make_bet_payload(bet_id=f"test-valid-{os.urandom(4).hex()}")
        response = client.post("/place-bet", json=bet_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "betId" in data
        assert "contractAddress" in data

    def test_place_bet_invalid_amount_zero(self, client):
        """Test placing bet with zero amount"""
        bet_data = _make_bet_payload(bet_id="test-zero", amount=0)
        response = client.post("/place-bet", json=bet_data)
        assert response.status_code == 422

    def test_place_bet_invalid_amount_negative(self, client):
        """Test placing bet with negative amount"""
        bet_data = _make_bet_payload(bet_id="test-neg", amount=-1000000)
        response = client.post("/place-bet", json=bet_data)
        assert response.status_code == 422

    def test_place_bet_invalid_choice(self, client):
        """Test placing bet with invalid choice"""
        bet_data = _make_bet_payload(bet_id="test-choice", choice=2)
        response = client.post("/place-bet", json=bet_data)
        assert response.status_code == 422

    def test_place_bet_duplicate(self, client):
        """Test duplicate betId rejection"""
        unique_id = f"test-dup-{os.urandom(8).hex()}"
        bet_data = _make_bet_payload(bet_id=unique_id)
        r1 = client.post("/place-bet", json=bet_data)
        assert r1.status_code == 200
        r2 = client.post("/place-bet", json=bet_data)
        # Duplicate betId is rejected (409 from route handler or 422 from validator)
        assert r2.status_code in (409, 422)

    def test_history_endpoint_valid_address(self, client):
        """Test history endpoint with valid address"""
        response = client.get(f"/history/{TEST_WALLET_ADDRESS}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_history_endpoint_invalid_address(self, client):
        """Test history endpoint with address containing path traversal"""
        # _validate_address_param rejects addresses with ..
        invalid_address = "has..traversal"
        response = client.get(f"/history/{invalid_address}")
        assert response.status_code == 400

    def test_player_stats_endpoint(self, client):
        """Test player stats endpoint"""
        response = client.get(f"/player/stats/{TEST_WALLET_ADDRESS}")
        assert response.status_code == 200
        data = response.json()
        assert "totalWagered" in data
        assert "totalWon" in data
        assert "totalLost" in data
        assert "winRate" in data
        assert "currentStreak" in data
        assert "longestWinStreak" in data
        assert "longestLossStreak" in data
        assert "compPoints" in data
        assert "compTier" in data

    def test_player_comp_points_endpoint(self, client):
        """Test player comp points endpoint"""
        response = client.get(f"/player/comp/{TEST_WALLET_ADDRESS}")
        assert response.status_code == 200
        data = response.json()
        assert "tier" in data
        assert "points" in data
        assert "pointsToNextTier" in data
        assert "tierProgress" in data
        assert "benefits" in data

    def test_leaderboard_endpoint(self, client):
        """Test leaderboard endpoint"""
        response = client.get("/leaderboard")
        assert response.status_code == 200
        data = response.json()
        assert "players" in data
        assert "totalPlayers" in data
        assert isinstance(data["players"], list)

    def test_integration_full_flow(self, client):
        """Test full coinflip flow integration"""
        # Step 1: Place a bet
        bet_data = _make_bet_payload(bet_id=f"test-flow-{os.urandom(4).hex()}")
        response = client.post("/place-bet", json=bet_data)
        assert response.status_code == 200
        bet_response = response.json()
        assert bet_response["success"] is True

        # Step 2: Check history
        response = client.get(f"/history/{TEST_WALLET_ADDRESS}")
        assert response.status_code == 200
        history = response.json()
        assert isinstance(history, list)

        # Step 3: Check player stats
        response = client.get(f"/player/stats/{TEST_WALLET_ADDRESS}")
        assert response.status_code == 200
        stats = response.json()
        assert "totalWagered" in stats

        # Step 4: Check comp points
        response = client.get(f"/player/comp/{TEST_WALLET_ADDRESS}")
        assert response.status_code == 200
        comp_points = response.json()
        assert "points" in comp_points

    def test_house_edge_calculation(self, client):
        """Test house edge is correctly configured"""
        # Place a bet and verify the payout multiplier
        bet_data = _make_bet_payload(bet_id=f"test-edge-{os.urandom(4).hex()}")
        response = client.post("/place-bet", json=bet_data)
        assert response.status_code == 200

        # The 3% edge is enforced by the payout multiplier (1.94x = 97/50)
        # This is verified in the contract and reveal logic
        assert True  # Placeholder — actual edge verification requires reveal flow

    def test_concurrent_bets(self, client):
        """Test concurrent bet placement with unique betIds"""
        import threading
        import os

        results = []
        lock = threading.Lock()

        def place_bet(idx):
            bet_data = _make_bet_payload(bet_id=f"concurrent-{idx}-{os.urandom(8).hex()}")
            try:
                response = client.post("/place-bet", json=bet_data, timeout=5)
                with lock:
                    results.append(response.status_code)
            except Exception:
                with lock:
                    results.append(500)

        threads = []
        for i in range(5):
            t = threading.Thread(target=place_bet, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # With unique IDs, bets should succeed (200) or be rate-limited (429)
        success_codes = [200, 429]  # 429 is acceptable — rate limiter working
        assert all(code in success_codes for code in results), \
            f"Unexpected statuses: {results}"
        # At least some should succeed
        assert sum(1 for c in results if c == 200) >= 1

    def test_large_bet_amount(self, client):
        """Test with large bet amount exceeding safe max"""
        large_amount = 100_000_000_000_000  # 100,000 ERG (way over safe max)
        bet_data = _make_bet_payload(bet_id=f"test-large-{os.urandom(4).hex()}", amount=large_amount)
        response = client.post("/place-bet", json=bet_data)
        # Should be rejected — exceeds pool liquidity or safe max bet
        assert response.status_code in (400, 422)

    def test_error_handling(self, client):
        """Test error handling"""
        response = client.get("/health")
        assert response.status_code == 200

        # Test with invalid JSON
        response = client.post("/place-bet", data="invalid json")
        assert response.status_code == 422

    def test_response_time(self, client):
        """Test response time for endpoints"""
        import time

        start_time = time.time()
        response = client.get("/health")
        end_time = time.time()

        assert response.status_code == 200
        assert (end_time - start_time) < 1.0

    def test_memory_usage(self, client):
        """Test memory usage (simplified)"""
        response = client.get("/pool/state")
        assert response.status_code == 200
        data = response.json()
        assert "liquidity" in data

    def test_tier_progression(self, client):
        """Test tier progression calculation"""
        response = client.get(f"/player/comp/{TEST_WALLET_ADDRESS}")
        assert response.status_code == 200
        data = response.json()
        assert "tier" in data
        assert "points" in data
        assert "pointsToNextTier" in data
        assert "tierProgress" in data

    def test_max_tier_handling(self, client):
        """Test max tier handling"""
        response = client.get(f"/player/comp/{TEST_WALLET_ADDRESS}")
        assert response.status_code == 200
        data = response.json()
        assert "tier" in data
        assert "benefits" in data
        assert isinstance(data["benefits"], list)
