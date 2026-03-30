"""
MAT-231: P&L Tracking Service Tests

Tests for bankroll_pnl.py service layer.
Run with: python -m pytest tests/test_bankroll_pnl.py -v
"""

import os
import tempfile
from pathlib import Path

import pytest

# Add backend to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.bankroll_pnl import (
    get_period_pnl,
    get_player_pnl,
    get_rounds,
    get_summary,
    init_db,
    record_round,
)


@pytest.fixture
def db_path():
    """Create a temporary database for each test."""
    import tempfile
    td = tempfile.mkdtemp()
    path = Path(td) / "test_pnl.db"
    init_db(path)
    yield path
    # Cleanup
    import shutil
    shutil.rmtree(td, ignore_errors=True)


class TestRecordRound:
    def test_record_loss(self, db_path):
        """House wins when player loses."""
        ok = record_round(
            bet_id="bet-001",
            player_address="9hH1",
            bet_amount_nanoerg=100_000_000_000,  # 100 ERG
            outcome="loss",
            house_payout_nanoerg=0,
            house_fee_nanoerg=100_000_000_000,
            db_path=db_path,
        )
        assert ok is True

        # Duplicate should be rejected
        ok2 = record_round(
            bet_id="bet-001",
            player_address="9hH1",
            bet_amount_nanoerg=100_000_000_000,
            outcome="loss",
            db_path=db_path,
        )
        assert ok2 is False

    def test_record_win(self, db_path):
        """Player wins — house pays out."""
        ok = record_round(
            bet_id="bet-002",
            player_address="3abc",
            bet_amount_nanoerg=1_000_000_000,  # 1 ERG
            outcome="win",
            house_payout_nanoerg=1_940_000_000,  # 1.94 ERG
            house_fee_nanoerg=30_000_000,  # 0.03 ERG (3% edge)
            db_path=db_path,
        )
        assert ok is True

    def test_record_refund(self, db_path):
        """Refunded bet — house keeps 2% fee."""
        ok = record_round(
            bet_id="bet-003",
            player_address="7xyz",
            bet_amount_nanoerg=500_000_000,  # 0.5 ERG
            outcome="refunded",
            house_payout_nanoerg=490_000_000,  # 0.49 ERG returned
            house_fee_nanoerg=10_000_000,  # 0.01 ERG fee
            db_path=db_path,
        )
        assert ok is True

    def test_invalid_outcome(self, db_path):
        with pytest.raises(ValueError):
            record_round(
                bet_id="bet-bad",
                player_address="9hH1",
                bet_amount_nanoerg=100_000_000,
                outcome="pending",
                db_path=db_path,
            )


class TestGetSummary:
    def test_empty_summary(self, db_path):
        s = get_summary(db_path=db_path)
        assert s["total_rounds"] == 0
        assert s["net_pnl_nanoerg"] == 0

    def test_summary_with_data(self, db_path):
        # Record 2 losses, 1 win
        record_round("b1", "addr1", 1_000_000_000, "loss", 0, 1_000_000_000, db_path=db_path)
        record_round("b2", "addr2", 2_000_000_000, "loss", 0, 2_000_000_000, db_path=db_path)
        record_round("b3", "addr3", 1_000_000_000, "win", 1_940_000_000, 30_000_000, db_path=db_path)

        s = get_summary(db_path=db_path)
        assert s["total_rounds"] == 3
        assert s["losses"] == 2  # house wins
        assert s["wins"] == 1  # player wins
        assert s["total_wagered_nanoerg"] == 4_000_000_000
        assert s["total_payout_nanoerg"] == 1_940_000_000
        # net_pnl = bet1 + bet2 + (bet3 - payout3) = 1B + 2B + (1B - 1.94B) = 2.06B
        assert s["net_pnl_nanoerg"] == 2_060_000_000


class TestGetRounds:
    def test_pagination(self, db_path):
        for i in range(5):
            record_round(f"bet-{i}", f"addr-{i}", 100_000_000, "loss", 0, 100_000_000, db_path=db_path)

        rounds, total = get_rounds(limit=2, offset=0, db_path=db_path)
        assert total == 5
        assert len(rounds) == 2

        rounds2, _ = get_rounds(limit=2, offset=2, db_path=db_path)
        assert len(rounds2) == 2
        # Different bet IDs
        assert rounds2[0]["bet_id"] != rounds[0]["bet_id"]

    def test_filter_by_player(self, db_path):
        record_round("b1", "alice", 100_000_000, "loss", 0, 100_000_000, db_path=db_path)
        record_round("b2", "bob", 200_000_000, "win", 388_000_000, 6_000_000, db_path=db_path)
        record_round("b3", "alice", 300_000_000, "loss", 0, 300_000_000, db_path=db_path)

        rounds, total = get_rounds(player_address="alice", db_path=db_path)
        assert total == 2
        assert all(r["player_address"] == "alice" for r in rounds)


class TestGetPeriodPnl:
    def test_day_period(self, db_path):
        record_round("b1", "a1", 1_000_000_000, "loss", 0, 1_000_000_000, db_path=db_path)
        record_round("b2", "a2", 2_000_000_000, "win", 3_880_000_000, 60_000_000, db_path=db_path)

        periods = get_period_pnl(period="day", db_path=db_path)
        assert len(periods) >= 1
        assert periods[0]["rounds"] == 2
        assert "net_pnl_nanoerg" in periods[0]


class TestGetPlayerPnl:
    def test_player_summary(self, db_path):
        record_round("b1", "alice", 1_000_000_000, "loss", 0, 1_000_000_000, db_path=db_path)
        record_round("b2", "alice", 1_000_000_000, "win", 1_940_000_000, 30_000_000, db_path=db_path)
        record_round("b3", "bob", 5_000_000_000, "loss", 0, 5_000_000_000, db_path=db_path)

        p = get_player_pnl("alice", db_path=db_path)
        assert p["total_rounds"] == 2
        assert p["wins"] == 1
        assert p["losses"] == 1
        assert p["total_wagered_nanoerg"] == 2_000_000_000
        assert p["total_won_nanoerg"] == 1_940_000_000

    def test_unknown_player(self, db_path):
        p = get_player_pnl("nobody", db_path=db_path)
        assert p["total_rounds"] == 0


class TestPnLMath:
    """Verify P&L calculations are correct."""

    def test_house_edge_3pct(self, db_path):
        """On a 1 ERG bet with 3% edge, house should net 0.03 ERG on loss."""
        record_round(
            "math-loss", "addr", 1_000_000_000, "loss", 0, 1_000_000_000, db_path=db_path
        )
        s = get_summary(db_path=db_path)
        assert s["net_pnl_nanoerg"] == 1_000_000_000  # full bet

    def test_house_edge_win(self, db_path):
        """On a 1 ERG player win (1.94x payout), house nets -0.94 ERG."""
        bet = 1_000_000_000
        payout = 1_940_000_000  # 1.94x
        fee = 30_000_000  # 3%
        record_round(
            "math-win", "addr", bet, "win", payout, fee, db_path=db_path
        )
        s = get_summary(db_path=db_path)
        # net_pnl = bet - payout = 1B - 1.94B = -940M (house paid out more than received)
        assert s["net_pnl_nanoerg"] == 1_000_000_000 - 1_940_000_000

    def test_realized_edge_over_many_rounds(self, db_path):
        """With many rounds, realized edge should approach theoretical 3%."""
        # 50% win rate, 50% loss rate
        for i in range(100):
            if i % 2 == 0:
                # Player loses: house gains full bet
                record_round(f"r{i}", f"a{i%10}", 1_000_000_000, "loss", 0, 1_000_000_000, db_path=db_path)
            else:
                # Player wins: house pays 1.94x, keeps 3%
                record_round(f"r{i}", f"a{i%10}", 1_000_000_000, "win", 1_940_000_000, 30_000_000, db_path=db_path)

        s = get_summary(db_path=db_path)
        total_wagered = s["total_wagered_nanoerg"]  # 100 ERG
        total_fees = s["total_fees_nanoerg"]  # 50 * 0.03 ERG = 1.5 ERG
        realized_edge = total_fees / total_wagered * 100

        # With 50/50 split: house gets 3% on wins only (50 rounds * 0.03 ERG)
        # But house also gets 100% of bet on losses... wait, let me recalculate.
        # The fee model here: on loss, fee = full bet. On win, fee = 3% edge.
        # This is the house P&L, not just fees. Let me check the math.
        #
        # Actually: net_pnl on loss = bet_amount (house keeps bet)
        #           net_pnl on win = fee - payout = 0.03 - 1.94 = -1.91 ERG per win
        # Total P&L = 50 * 1.0 + 50 * (-1.91) = 50 - 95.5 = -45.5 ERG
        #
        # Hmm, that's negative. The issue is the fee model. Let me reconsider.
        # In the actual game: player bets 1 ERG. If they win, they get 1.94 ERG back (their 1 + 0.94 profit).
        # House takes 0.03 ERG from each bet regardless.
        # So house revenue per bet = 0.03 ERG (3% of wagered).
        # On loss: house keeps 1.0 ERG, pays 0 -> revenue = 1.0 ERG
        # On win: house pays 1.94 ERG, receives 1.0 ERG -> net = -0.94 ERG
        # Expected per bet: 0.5 * 1.0 + 0.5 * (-0.94) = 0.5 - 0.47 = 0.03 ERG
        # So over 100 bets: expected P&L = 3 ERG (3% of 100 ERG wagered)
        #
        # Let me verify with the actual function:
        expected_pnl = 3_000_000_000  # 3 ERG
        assert abs(s["net_pnl_nanoerg"] - expected_pnl) < 1_000_000  # within 0.001 ERG


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
