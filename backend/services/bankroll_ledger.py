"""
DuckPools - Bankroll Ledger Service

Tracks deposits and withdrawals to/from the house bankroll.
Provides the financial ledger for LP (liquidity provider) accounting.

Ledger entries are recorded when:
  - ERG is deposited into the house wallet (detected via node monitoring)
  - ERG is withdrawn from the house wallet (operator-initiated)
  - Bets are resolved (auto-generated entries: fee income, payouts)

Data model:
  bankroll_ledger table:
    - id: INTEGER PRIMARY KEY
    - tx_id: TEXT (on-chain transaction ID)
    - type: TEXT NOT NULL (deposit, withdrawal, bet_fee, bet_payout, bet_refund)
    - amount_nanoerg: INTEGER NOT NULL
    - address: TEXT (source/destination address)
    - bet_id: TEXT (associated bet, if applicable)
    - timestamp: TEXT NOT NULL (ISO 8601 UTC)
    - notes: TEXT (human-readable description)
"""

import logging
import os
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger("duckpools.ledger")

_DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "bankroll_ledger.db"


def _get_db_path() -> Path:
    return Path(os.getenv("LEDGER_DB_PATH", str(_DEFAULT_DB_PATH)))


def _get_connection(db_path=None) -> sqlite3.Connection:
    if db_path is not None:
        path = Path(db_path)
    else:
        path = _get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """Initialize the bankroll ledger database schema."""
    conn = _get_connection(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS bankroll_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_id TEXT,
                type TEXT NOT NULL CHECK(type IN ('deposit', 'withdrawal', 'bet_fee', 'bet_payout', 'bet_refund')),
                amount_nanoerg INTEGER NOT NULL,
                address TEXT,
                bet_id TEXT,
                timestamp TEXT NOT NULL,
                notes TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_ledger_type ON bankroll_ledger(type);
            CREATE INDEX IF NOT EXISTS idx_ledger_timestamp ON bankroll_ledger(timestamp);
            CREATE INDEX IF NOT EXISTS idx_ledger_address ON bankroll_ledger(address);
            CREATE INDEX IF NOT EXISTS idx_ledger_bet_id ON bankroll_ledger(bet_id);
            CREATE INDEX IF NOT EXISTS idx_ledger_tx_id ON bankroll_ledger(tx_id);
        """)
        conn.commit()
        logger.info("Bankroll ledger initialized at %s", db_path or _get_db_path())
    finally:
        conn.close()


def record_entry(
    entry_type: str,
    amount_nanoerg: int,
    tx_id: Optional[str] = None,
    address: Optional[str] = None,
    bet_id: Optional[str] = None,
    notes: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> int:
    """
    Record a ledger entry.

    Args:
        entry_type: 'deposit', 'withdrawal', 'bet_fee', 'bet_payout', 'bet_refund'
        amount_nanoerg: Amount in nanoERG (positive for deposits/fees, positive for payouts)
        tx_id: On-chain transaction ID
        address: Source/destination address
        bet_id: Associated bet (for bet_fee, bet_payout, bet_refund)
        notes: Human-readable description

    Returns:
        The row ID of the inserted entry
    """
    now = datetime.now(timezone.utc).isoformat()

    conn = _get_connection(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO bankroll_ledger (tx_id, type, amount_nanoerg, address, bet_id, timestamp, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (tx_id, entry_type, amount_nanoerg, address, bet_id, now, notes),
        )
        conn.commit()
        entry_id = cur.lastrowid
        logger.info(
            "Ledger entry: id=%d type=%s amount=%d tx=%s bet=%s",
            entry_id, entry_type, amount_nanoerg, tx_id, bet_id,
        )
        return entry_id
    finally:
        conn.close()


def get_entries(
    entry_type: Optional[str] = None,
    address: Optional[str] = None,
    bet_id: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db_path: Optional[Path] = None,
) -> Tuple[List[dict], int]:
    """Get paginated ledger entries with optional filters."""
    conn = _get_connection(db_path)
    try:
        where_clauses = []
        params: list = []

        if entry_type:
            where_clauses.append("type = ?")
            params.append(entry_type)
        if address:
            where_clauses.append("address = ?")
            params.append(address)
        if bet_id:
            where_clauses.append("bet_id = ?")
            params.append(bet_id)
        if since:
            where_clauses.append("timestamp >= ?")
            params.append(since)
        if until:
            where_clauses.append("timestamp <= ?")
            params.append(until)

        where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        total = conn.execute(f"SELECT COUNT(*) FROM bankroll_ledger {where}", params).fetchone()[0]

        rows = conn.execute(
            f"SELECT * FROM bankroll_ledger {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

        entries = [
            {
                "id": r["id"],
                "tx_id": r["tx_id"],
                "type": r["type"],
                "amount_nanoerg": r["amount_nanoerg"],
                "amount_erg": f"{r['amount_nanoerg'] / 1e9:.9f}",
                "address": r["address"],
                "bet_id": r["bet_id"],
                "timestamp": r["timestamp"],
                "notes": r["notes"],
            }
            for r in rows
        ]

        return entries, total
    finally:
        conn.close()


def get_balance(db_path: Optional[Path] = None) -> dict:
    """
    Calculate net bankroll balance from ledger entries.

    Balance = total_deposits - total_withdrawals - total_bet_payouts - total_bet_refunds + total_bet_fees
    """
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT type, SUM(amount_nanoerg) as total FROM bankroll_ledger GROUP BY type"
        ).fetchall()

        totals = {}
        for r in rows:
            totals[r["type"]] = r["total"] or 0

        deposits = totals.get("deposit", 0)
        withdrawals = totals.get("withdrawal", 0)
        bet_fees = totals.get("bet_fee", 0)
        bet_payouts = totals.get("bet_payout", 0)
        bet_refunds = totals.get("bet_refund", 0)

        net_balance = deposits - withdrawals - bet_payouts - bet_refunds + bet_fees

        return {
            "total_deposits_nanoerg": deposits,
            "total_deposits_erg": f"{deposits / 1e9:.9f}",
            "total_withdrawals_nanoerg": withdrawals,
            "total_withdrawals_erg": f"{withdrawals / 1e9:.9f}",
            "total_bet_fees_nanoerg": bet_fees,
            "total_bet_fees_erg": f"{bet_fees / 1e9:.9f}",
            "total_bet_payouts_nanoerg": bet_payouts,
            "total_bet_payouts_erg": f"{bet_payouts / 1e9:.9f}",
            "total_bet_refunds_nanoerg": bet_refunds,
            "total_bet_refunds_erg": f"{bet_refunds / 1e9:.9f}",
            "net_balance_nanoerg": net_balance,
            "net_balance_erg": f"{net_balance / 1e9:.9f}",
            "deposit_count": conn.execute("SELECT COUNT(*) FROM bankroll_ledger WHERE type='deposit'").fetchone()[0],
            "withdrawal_count": conn.execute("SELECT COUNT(*) FROM bankroll_ledger WHERE type='withdrawal'").fetchone()[0],
        }
    finally:
        conn.close()
