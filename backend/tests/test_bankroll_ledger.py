"""
DuckPools - Unit tests for bankroll ledger service.

Tests deposit/withdrawal recording, balance calculation,
and entry retrieval with filtering.
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.bankroll_ledger import (
    init_db,
    record_entry,
    get_entries,
    get_balance,
)


@pytest.fixture
def db_path():
    """Create a temporary database for each test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    yield path
    if path.exists():
        path.unlink()


class TestBankrollLedgerInit:
    """Test database initialization."""

    def test_init_creates_tables(self, db_path):
        """init_db should create the bankroll_ledger table."""
        init_db(db_path)
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        conn.close()
        table_names = [t[0] for t in tables]
        assert "bankroll_ledger" in table_names

    def test_init_idempotent(self, db_path):
        """init_db should be safe to call multiple times."""
        init_db(db_path)
        init_db(db_path)  # Should not raise


class TestRecordEntry:
    """Test ledger entry recording."""

    def test_record_deposit(self, db_path):
        """Should record a deposit and return an ID."""
        init_db(db_path)
        entry_id = record_entry(
            entry_type="deposit",
            amount_nanoerg=100_000_000_000,  # 100 ERG
            tx_id="a" * 64,
            address="9hGmWb9v8k7j6F5d4s3a2Z1xcV8n7M6p5Q4r3T2y1Uh",
            notes="Test deposit",
            db_path=db_path,
        )
        assert entry_id > 0

    def test_record_withdrawal(self, db_path):
        """Should record a withdrawal."""
        init_db(db_path)
        entry_id = record_entry(
            entry_type="withdrawal",
            amount_nanoerg=50_000_000_000,
            tx_id="b" * 64,
            address="9hGmWb9v8k7j6F5d4s3a2Z1xcV8n7M6p5Q4r3T2y1Uh",
            db_path=db_path,
        )
        assert entry_id > 0

    def test_record_bet_fee(self, db_path):
        """Should record a bet fee."""
        init_db(db_path)
        entry_id = record_entry(
            entry_type="bet_fee",
            amount_nanoerg=3_000_000,  # 0.003 ERG (3% of 0.1 ERG bet)
            bet_id="test-bet-001",
            db_path=db_path,
        )
        assert entry_id > 0

    def test_record_bet_payout(self, db_path):
        """Should record a bet payout."""
        init_db(db_path)
        entry_id = record_entry(
            entry_type="bet_payout",
            amount_nanoerg=97_000_000,
            bet_id="test-bet-001",
            address="3Wx6TkZU8dENHf4moAv3GgYqTs3fbpsk6DFnJr9WQgZ72MxtQbV",
            db_path=db_path,
        )
        assert entry_id > 0

    def test_record_bet_refund(self, db_path):
        """Should record a bet refund."""
        init_db(db_path)
        entry_id = record_entry(
            entry_type="bet_refund",
            amount_nanoerg=98_000_000,
            bet_id="test-bet-002",
            address="3Wx6TkZU8dENHf4moAv3GgYqTs3fbpsk6DFnJr9WQgZ72MxtQbV",
            db_path=db_path,
        )
        assert entry_id > 0

    def test_auto_incrementing_ids(self, db_path):
        """Each entry should get a unique, incrementing ID."""
        init_db(db_path)
        id1 = record_entry("deposit", 100, db_path=db_path)
        id2 = record_entry("deposit", 200, db_path=db_path)
        id3 = record_entry("withdrawal", 50, db_path=db_path)
        assert id2 == id1 + 1
        assert id3 == id2 + 1


class TestGetEntries:
    """Test ledger entry retrieval."""

    def _seed_data(self, db_path):
        """Seed some test data."""
        init_db(db_path)
        record_entry("deposit", 100_000_000_000, tx_id="a" * 64, address="addr1", db_path=db_path)
        record_entry("deposit", 50_000_000_000, tx_id="b" * 64, address="addr2", db_path=db_path)
        record_entry("withdrawal", 20_000_000_000, tx_id="c" * 64, address="addr3", db_path=db_path)
        record_entry("bet_fee", 3_000_000, bet_id="bet1", db_path=db_path)
        record_entry("bet_payout", 97_000_000, bet_id="bet1", address="addr1", db_path=db_path)

    def test_get_all_entries(self, db_path):
        """Should return all entries."""
        self._seed_data(db_path)
        entries, total = get_entries(db_path=db_path)
        assert total == 5
        assert len(entries) == 5

    def test_filter_by_type(self, db_path):
        """Should filter entries by type."""
        self._seed_data(db_path)
        entries, total = get_entries(entry_type="deposit", db_path=db_path)
        assert total == 2
        assert all(e["type"] == "deposit" for e in entries)

    def test_filter_by_address(self, db_path):
        """Should filter entries by address."""
        self._seed_data(db_path)
        entries, total = get_entries(address="addr1", db_path=db_path)
        assert total == 2

    def test_filter_by_bet_id(self, db_path):
        """Should filter entries by bet ID."""
        self._seed_data(db_path)
        entries, total = get_entries(bet_id="bet1", db_path=db_path)
        assert total == 2

    def test_pagination(self, db_path):
        """Should respect limit and offset."""
        self._seed_data(db_path)
        entries, total = get_entries(limit=2, offset=0, db_path=db_path)
        assert total == 5
        assert len(entries) == 2

        entries2, total2 = get_entries(limit=2, offset=2, db_path=db_path)
        assert len(entries2) == 2
        # Should be different entries
        assert entries[0]["id"] != entries2[0]["id"]

    def test_entry_format(self, db_path):
        """Entries should have amount_erg field."""
        self._seed_data(db_path)
        entries, _ = get_entries(db_path=db_path)
        for e in entries:
            assert "amount_erg" in e
            assert "amount_nanoerg" in e
            assert "type" in e
            assert "timestamp" in e

    def test_amount_erg_format(self, db_path):
        """amount_erg should be a decimal string with 9 decimal places."""
        init_db(db_path)
        record_entry("deposit", 1_500_000_000, db_path=db_path)  # 1.5 ERG
        entries, _ = get_entries(db_path=db_path)
        assert entries[0]["amount_erg"] == "1.500000000"


class TestGetBalance:
    """Test balance calculation from ledger."""

    def test_empty_ledger(self, db_path):
        """Empty ledger should show zero balance."""
        init_db(db_path)
        balance = get_balance(db_path=db_path)
        assert balance["net_balance_nanoerg"] == 0
        assert balance["total_deposits_nanoerg"] == 0
        assert balance["total_withdrawals_nanoerg"] == 0

    def test_deposit_only(self, db_path):
        """Single deposit should show positive balance."""
        init_db(db_path)
        record_entry("deposit", 100_000_000_000, db_path=db_path)
        balance = get_balance(db_path=db_path)
        assert balance["net_balance_nanoerg"] == 100_000_000_000
        assert balance["total_deposits_nanoerg"] == 100_000_000_000
        assert balance["deposit_count"] == 1

    def test_deposit_and_withdrawal(self, db_path):
        """Balance = deposits - withdrawals."""
        init_db(db_path)
        record_entry("deposit", 100_000_000_000, db_path=db_path)
        record_entry("withdrawal", 30_000_000_000, db_path=db_path)
        balance = get_balance(db_path=db_path)
        assert balance["net_balance_nanoerg"] == 70_000_000_000
        assert balance["withdrawal_count"] == 1

    def test_bet_payouts_reduce_balance(self, db_path):
        """Bet payouts reduce the net balance."""
        init_db(db_path)
        record_entry("deposit", 100_000_000_000, db_path=db_path)
        record_entry("bet_payout", 97_000_000, db_path=db_path)
        balance = get_balance(db_path=db_path)
        assert balance["net_balance_nanoerg"] == 100_000_000_000 - 97_000_000

    def test_bet_fees_increase_balance(self, db_path):
        """Bet fees (house edge) increase the net balance."""
        init_db(db_path)
        record_entry("deposit", 100_000_000_000, db_path=db_path)
        record_entry("bet_fee", 3_000_000, db_path=db_path)
        balance = get_balance(db_path=db_path)
        assert balance["net_balance_nanoerg"] == 100_000_000_000 + 3_000_000

    def test_full_lifecycle(self, db_path):
        """
        Full lifecycle: deposit -> bet_fee -> bet_payout -> refund.

        Deposit 100 ERG, bet 1 ERG:
        - Fee income: 0.03 ERG (3% house edge)
        - Player wins: payout 0.97 ERG
        - Refund: 0.98 ERG returned, 0.02 ERG fee

        Net balance should be:
          100 - 0.97 - 0.98 + 0.03 + 0.02 = 98.1 ERG
        """
        init_db(db_path)
        record_entry("deposit", 100_000_000_000, db_path=db_path)
        record_entry("bet_fee", 3_000_000, bet_id="bet1", db_path=db_path)
        record_entry("bet_payout", 97_000_000, bet_id="bet1", db_path=db_path)
        record_entry("bet_fee", 2_000_000, bet_id="bet2", db_path=db_path)
        record_entry("bet_refund", 98_000_000, bet_id="bet2", db_path=db_path)

        balance = get_balance(db_path=db_path)
        expected = 100_000_000_000 - 97_000_000 - 98_000_000 + 3_000_000 + 2_000_000
        assert balance["net_balance_nanoerg"] == expected
        assert balance["total_bet_fees_nanoerg"] == 5_000_000
        assert balance["total_bet_payouts_nanoerg"] == 97_000_000
        assert balance["total_bet_refunds_nanoerg"] == 98_000_000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
