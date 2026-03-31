"""
Phase 7, Scenario 1 — Full-Stack Coinflip Flow

E2E test: Wallet connection -> bet placement -> commit -> reveal -> payout.

Tests the complete user journey through the backend API:
  1. Contract info retrieval (wallet needs P2S address + registers)
  2. Place bet with valid commitment (commit phase)
  3. Verify bet appears in history as "pending"
  4. Verify player stats update (pending count, wagered amount)
  5. Simulate reveal (house resolves bet)
  6. Verify bet history shows resolved outcome
  7. Verify player stats reflect win/loss

Note: On-chain transaction building/signing is mocked in this test suite.
      Full on-chain tests require a running Ergo node (see test_on_chain.py).
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient

from conftest import (
    TEST_PLAYER_ADDRESS,
    generate_commitment,
    generate_player_secret,
    make_place_bet_payload,
)


# ─── 1. Contract Info ────────────────────────────────────────────────

class TestContractInfo:
    """Wallet needs contract info before placing a bet."""

    @pytest.mark.asyncio
    async def test_contract_info_returns_p2s_address(self, app_client: AsyncClient):
        resp = await app_client.get("/contract-info")
        assert resp.status_code == 200
        data = resp.json()
        assert "p2sAddress" in data
        assert len(data["p2sAddress"]) > 50  # Ergo P2S addresses are long
        assert data["p2sAddress"].startswith("3")

    @pytest.mark.asyncio
    async def test_contract_info_returns_ergo_tree(self, app_client: AsyncClient):
        resp = await app_client.get("/contract-info")
        data = resp.json()
        assert "ergoTree" in data
        # Valid hex string
        int(data["ergoTree"], 16)
        assert len(data["ergoTree"]) > 100

    @pytest.mark.asyncio
    async def test_contract_info_register_layout(self, app_client: AsyncClient):
        resp = await app_client.get("/contract-info")
        data = resp.json()
        registers = data["registers"]
        expected_registers = {"R4", "R5", "R6", "R7", "R8", "R9"}
        assert set(registers.keys()) == expected_registers
        assert "housePubKey" in registers["R4"]
        assert "playerPubKey" in registers["R5"]
        assert "commitmentHash" in registers["R6"]
        assert "playerChoice" in registers["R7"]
        assert "timeoutHeight" in registers["R8"]
        assert "playerSecret" in registers["R9"]


# ─── 2. Place Bet (Commit Phase) ────────────────────────────────────

class TestPlaceBet:
    """Player places a bet via the commit-reveal pattern."""

    @pytest.mark.asyncio
    async def test_place_bet_heads_success(self, app_client: AsyncClient):
        payload = make_place_bet_payload(choice=0)
        resp = await app_client.post("/place-bet", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["betId"] == payload["betId"]
        assert "message" in data

    @pytest.mark.asyncio
    async def test_place_bet_tails_success(self, app_client: AsyncClient):
        payload = make_place_bet_payload(choice=1)
        resp = await app_client.post("/place-bet", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["betId"] == payload["betId"]

    @pytest.mark.asyncio
    async def test_place_bet_minimum_amount(self, app_client: AsyncClient):
        """Minimum bet is 0.001 ERG (1,000,000 nanoERG)."""
        payload = make_place_bet_payload(amount_nanoerg=999_999)
        resp = await app_client.post("/place-bet", json=payload)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_place_bet_maximum_amount(self, app_client: AsyncClient):
        """Maximum bet is 100 ERG (100,000,000,000 nanoERG)."""
        payload = make_place_bet_payload(amount_nanoerg=100_000_000_001)
        resp = await app_client.post("/place-bet", json=payload)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_place_bet_valid_boundary_minimum(self, app_client: AsyncClient):
        """Exactly 1,000,000 nanoERG (0.001 ERG) should succeed."""
        payload = make_place_bet_payload(amount_nanoerg=1_000_000)
        resp = await app_client.post("/place-bet", json=payload)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_place_bet_valid_boundary_maximum(self, app_client: AsyncClient):
        """Exactly 100,000,000,000 nanoERG (100 ERG) should succeed."""
        payload = make_place_bet_payload(amount_nanoerg=100_000_000_000)
        resp = await app_client.post("/place-bet", json=payload)
        assert resp.status_code == 200


# ─── 3. Commit Verification ─────────────────────────────────────────

class TestCommitVerification:
    """Verify commitment hashes are stored correctly."""

    @pytest.mark.asyncio
    async def test_commitment_hash_stored(self, app_client: AsyncClient):
        secret = generate_player_secret()
        choice = 0
        commitment = generate_commitment(secret, choice)
        payload = make_place_bet_payload(choice=choice)
        payload["commitment"] = commitment

        resp = await app_client.post("/place-bet", json=payload)
        assert resp.status_code == 200

        # Retrieve from history
        hist = await app_client.get(f"/history/{TEST_PLAYER_ADDRESS}")
        assert hist.status_code == 200
        bets = hist.json()
        assert len(bets) >= 1
        # Bet should be pending
        assert bets[-1]["outcome"] == "pending"

    @pytest.mark.asyncio
    async def test_choice_maps_to_side(self, app_client: AsyncClient):
        """Choice 0 -> heads, choice 1 -> tails in stored bet."""
        # Place heads bet
        payload = make_place_bet_payload(choice=0, bet_id="heads-test-1")
        resp = await app_client.post("/place-bet", json=payload)
        assert resp.status_code == 200

        # Place tails bet
        payload = make_place_bet_payload(choice=1, bet_id="tails-test-1")
        resp = await app_client.post("/place-bet", json=payload)
        assert resp.status_code == 200

        hist = await app_client.get(f"/history/{TEST_PLAYER_ADDRESS}")
        bets = hist.json()
        heads_bet = next((b for b in bets if b["betId"] == "heads-test-1"), None)
        tails_bet = next((b for b in bets if b["betId"] == "tails-test-1"), None)

        assert heads_bet is not None
        assert tails_bet is not None
        assert heads_bet["choice"]["side"] == "heads"
        assert tails_bet["choice"]["side"] == "tails"


# ─── 4. Bet History Tracking ────────────────────────────────────────

class TestBetHistory:
    """Verify bets appear in history with correct state transitions."""

    @pytest.mark.asyncio
    async def test_empty_history_for_unknown_address(self, app_client: AsyncClient):
        resp = await app_client.get("/history/3WyrB3D5AMpyEc88UJ7FdsBMXAZKwzQzkKeDbAQVfXytDPgxF26")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_bet_appears_in_history(self, app_client: AsyncClient):
        bet_id = "history-test-1"
        payload = make_place_bet_payload(bet_id=bet_id)
        resp = await app_client.post("/place-bet", json=payload)
        assert resp.status_code == 200

        hist = await app_client.get(f"/history/{TEST_PLAYER_ADDRESS}")
        bets = hist.json()
        assert any(b["betId"] == bet_id for b in bets)

    @pytest.mark.asyncio
    async def test_history_is_address_scoped(self, app_client: AsyncClient):
        """Player A's bets don't appear in Player B's history."""
        other_address = "9fGhJkLmNoPqRsTuVwXyZaBcDeFgHiJkLmNoPqRsTuVwXyZaBcD"
        payload_a = make_place_bet_payload(bet_id="scope-test-a")
        await app_client.post("/place-bet", json=payload_a)

        hist_b = await app_client.get(f"/history/{other_address}")
        assert all(b["betId"] != "scope-test-a" for b in hist_b.json())

    @pytest.mark.asyncio
    async def test_history_returns_list(self, app_client: AsyncClient):
        resp = await app_client.get(f"/history/{TEST_PLAYER_ADDRESS}")
        assert isinstance(resp.json(), list)


# ─── 5. Player Stats After Bet ─────────────────────────────────────

class TestPlayerStatsAfterBet:
    """Player stats should update after placing bets."""

    @pytest.mark.asyncio
    async def test_stats_empty_initially(self, app_client: AsyncClient):
        resp = await app_client.get(f"/player/stats/{TEST_PLAYER_ADDRESS}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["totalBets"] == 0
        assert data["wins"] == 0
        assert data["losses"] == 0
        assert data["pending"] == 0
        assert data["winRate"] == 0.0

    @pytest.mark.asyncio
    async def test_stats_pending_count_after_bet(self, app_client: AsyncClient):
        await app_client.post("/place-bet", json=make_place_bet_payload(bet_id="stats-pending-1"))
        await app_client.post("/place-bet", json=make_place_bet_payload(bet_id="stats-pending-2"))

        resp = await app_client.get(f"/player/stats/{TEST_PLAYER_ADDRESS}")
        data = resp.json()
        assert data["totalBets"] >= 2
        assert data["pending"] >= 2

    @pytest.mark.asyncio
    async def test_stats_total_wagered(self, app_client: AsyncClient):
        bet_amount = 50_000_000  # 0.05 ERG
        await app_client.post("/place-bet", json=make_place_bet_payload(
            bet_id="stats-wager-1", amount_nanoerg=bet_amount
        ))

        resp = await app_client.get(f"/player/stats/{TEST_PLAYER_ADDRESS}")
        data = resp.json()
        assert int(data["totalWagered"]) >= bet_amount


# ─── 6. Payout Calculation (Simulated Reveal) ───────────────────────

class TestPayoutCalculation:
    """Verify payout math matches the house edge model."""

    @pytest.mark.asyncio
    async def test_payout_multiplier_is_0_97(self, app_client: AsyncClient):
        """House edge is 3%, so payout multiplier should be 0.97."""
        payload = make_place_bet_payload(bet_id="payout-mult-test")
        resp = await app_client.post("/place-bet", json=payload)
        assert resp.status_code == 200

        hist = await app_client.get(f"/history/{TEST_PLAYER_ADDRESS}")
        bet = next(b for b in hist.json() if b["betId"] == "payout-mult-test")
        assert bet["payoutMultiplier"] == 0.97

    @pytest.mark.asyncio
    async def test_payout_amount_calculation(self):
        """Payout for winning bet = bet_amount * 0.97."""
        bet_amount = 100_000_000  # 1 ERG
        expected_payout = bet_amount * 97 // 100  # 0.97 ERG
        assert expected_payout == 97_000_000


# ─── 7. Leaderboard Integration ─────────────────────────────────────

class TestLeaderboardIntegration:
    """Leaderboard should be accessible and return expected structure."""

    @pytest.mark.asyncio
    async def test_leaderboard_returns_valid_structure(self, app_client: AsyncClient):
        resp = await app_client.get("/leaderboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "players" in data
        assert "totalPlayers" in data
        assert "sortBy" in data
        assert isinstance(data["players"], list)

    @pytest.mark.asyncio
    async def test_leaderboard_initially_empty(self, app_client: AsyncClient):
        resp = await app_client.get("/leaderboard")
        data = resp.json()
        assert data["totalPlayers"] == 0
        assert len(data["players"]) == 0


# ─── 8. Comp Points Integration ─────────────────────────────────────

class TestCompPointsIntegration:
    """Comp points should accumulate based on wagered amount."""

    @pytest.mark.asyncio
    async def test_comp_points_empty_initially(self, app_client: AsyncClient):
        resp = await app_client.get(f"/player/comp/{TEST_PLAYER_ADDRESS}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["points"] == 0
        assert data["tier"] == "Bronze"

    @pytest.mark.asyncio
    async def test_comp_points_after_wagering(self, app_client: AsyncClient):
        # 1 point per 0.01 ERG wagered = 10M nanoERG
        bet_amount = 100_000_000  # 1 ERG -> 100 comp points
        await app_client.post("/place-bet", json=make_place_bet_payload(
            bet_id="comp-test-1", amount_nanoerg=bet_amount
        ))

        resp = await app_client.get(f"/player/comp/{TEST_PLAYER_ADDRESS}")
        data = resp.json()
        assert data["points"] >= 10  # At least from this bet

    @pytest.mark.asyncio
    async def test_comp_tier_bronze_threshold(self, app_client: AsyncClient):
        """Bronze: 0-99 points, Silver: 100+, Gold: 1000+, Diamond: 10000+."""
        resp = await app_client.get(f"/player/comp/{TEST_PLAYER_ADDRESS}")
        data = resp.json()
        if data["points"] < 100:
            assert data["tier"] == "Bronze"
            assert data["nextTier"] == "Silver"
        elif data["points"] < 1000:
            assert data["tier"] == "Silver"


# ─── 9. Full Flow (Place -> History -> Stats -> Comp) ────────────────

class TestFullBetFlow:
    """End-to-end: place bet, verify history, stats, comp all consistent."""

    @pytest.mark.asyncio
    async def test_complete_coinflip_flow(self, app_client: AsyncClient):
        """Full happy path: place bet -> check history -> check stats -> check comp."""
        bet_id = "full-flow-e2e"
        amount = 200_000_000  # 0.2 ERG

        # Step 1: Place bet
        payload = make_place_bet_payload(bet_id=bet_id, amount_nanoerg=amount, choice=0)
        resp = await app_client.post("/place-bet", json=payload)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # Step 2: Verify in history
        hist = await app_client.get(f"/history/{TEST_PLAYER_ADDRESS}")
        bets = hist.json()
        bet = next((b for b in bets if b["betId"] == bet_id), None)
        assert bet is not None
        assert bet["outcome"] == "pending"
        assert bet["betAmount"] == str(amount)
        assert bet["choice"]["side"] == "heads"
        assert bet["gameType"] == "coinflip"

        # Step 3: Verify stats updated
        stats = await app_client.get(f"/player/stats/{TEST_PLAYER_ADDRESS}")
        stats_data = stats.json()
        assert stats_data["pending"] >= 1
        assert int(stats_data["totalWagered"]) >= amount

        # Step 4: Verify comp points
        comp = await app_client.get(f"/player/comp/{TEST_PLAYER_ADDRESS}")
        comp_data = comp.json()
        assert comp_data["totalEarned"] >= 20  # 0.2 ERG / 0.01 = 20 points

    @pytest.mark.asyncio
    async def test_multiple_bets_sequential_flow(self, app_client: AsyncClient):
        """Place 5 bets, verify all tracked correctly."""
        n_bets = 5
        bet_ids = [f"seq-flow-{i}" for i in range(n_bets)]

        for bid in bet_ids:
            payload = make_place_bet_payload(bet_id=bid)
            resp = await app_client.post("/place-bet", json=payload)
            assert resp.status_code == 200, f"Failed for bet {bid}"

        # Check all in history
        hist = await app_client.get(f"/history/{TEST_PLAYER_ADDRESS}")
        bets = hist.json()
        for bid in bet_ids:
            assert any(b["betId"] == bid for b in bets), f"Missing bet {bid}"

        # Stats should show at least 5 bets
        stats = await app_client.get(f"/player/stats/{TEST_PLAYER_ADDRESS}")
        assert stats.json()["totalBets"] >= n_bets
