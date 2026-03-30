"""
DuckPools - Bankroll P&L Tracking Service

Tracks house profit/loss for every resolved game round.
Provides aggregation and time-period filtering.

MAT-231: P&L tracking per game round

Data model:
  pnl_rounds table:
    - id: INTEGER PRIMARY KEY
    - bet_id: TEXT UNIQUE NOT NULL
    - timestamp: TEXT NOT NULL (ISO 8601 UTC)
    - resolved_at: TEXT (ISO 8601 UTC, when bet was resolved)
    - player_address: TEXT NOT NULL
    - bet_amount_nanoerg: INTEGER NOT NULL
    - outcome: TEXT NOT NULL (win, loss, refunded)
    - house_payout_nanoerg: INTEGER NOT NULL (0 for losses, payout for wins/refunds)
    - house_fee_nanoerg: INTEGER NOT NULL (house edge or refund fee)
    - net_pnl_nanoerg: INTEGER NOT NULL (bet_amount - house_payout - house_fee for losses;
                                          house_fee for wins; house_fee - refund for refunds)
    - game_type: TEXT NOT NULL DEFAULT 'coinflip'
"""

import logging
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger("duckpools.pnl")

# Default DB path — alongside api_server.py
_DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "bankroll_pnl.db"

# House edge: 3% (300 bps) for coinflip
HOUSE_EDGE_BPS = int(os.getenv("HOUSE_EDGE_BPS", "300"))
# Refund fee: 2% (200 bps) for expired bets
REFUND_FEE_BPS = int(os.getenv("REFUND_FEE_BPS", "200"))


def _get_db_path() -> Path:
    """Get the database path from env or default."""
    return Path(os.getenv("PNL_DB_PATH", str(_DEFAULT_DB_PATH)))


def _get_connection(db_path=None) -> sqlite3.Connection:
    """Get a connection to the P&L SQLite database."""
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
    """Initialize the P&L database schema."""
    conn = _get_connection(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS pnl_rounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bet_id TEXT UNIQUE NOT NULL,
                timestamp TEXT NOT NULL,
                resolved_at TEXT NOT NULL,
                player_address TEXT NOT NULL,
                bet_amount_nanoerg INTEGER NOT NULL,
                outcome TEXT NOT NULL CHECK(outcome IN ('win', 'loss', 'refunded')),
                house_payout_nanoerg INTEGER NOT NULL DEFAULT 0,
                house_fee_nanoerg INTEGER NOT NULL DEFAULT 0,
                net_pnl_nanoerg INTEGER NOT NULL DEFAULT 0,
                game_type TEXT NOT NULL DEFAULT 'coinflip'
            );

            CREATE INDEX IF NOT EXISTS idx_pnl_timestamp ON pnl_rounds(timestamp);
            CREATE INDEX IF NOT EXISTS idx_pnl_resolved_at ON pnl_rounds(resolved_at);
            CREATE INDEX IF NOT EXISTS idx_pnl_player ON pnl_rounds(player_address);
            CREATE INDEX IF NOT EXISTS idx_pnl_outcome ON pnl_rounds(outcome);
        """)
        conn.commit()
        logger.info("P&L database initialized at %s", db_path or _get_db_path())
    finally:
        conn.close()


def record_round(
    bet_id: str,
    player_address: str,
    bet_amount_nanoerg: int,
    outcome: str,
    house_payout_nanoerg: int = 0,
    house_fee_nanoerg: int = 0,
    bet_timestamp: Optional[str] = None,
    game_type: str = "coinflip",
    db_path: Optional[Path] = None,
) -> bool:
    """
    Record a resolved game round's P&L.

    House P&L calculation:
      - Player LOSS:  house receives bet_amount, pays 0 -> net = +bet_amount
      - Player WIN:   house receives bet_amount, pays payout -> net = bet_amount - payout
        (the 3% edge is already baked into the 1.94x payout multiplier)
      - REFUNDED:     house returns bet minus fee -> net = +fee
        (fee = bet_amount * refund_fee_bps / 10000)

    Args:
        bet_id: Unique bet identifier
        player_address: Player's Ergo address
        bet_amount_nanoerg: Amount wagered in nanoERG
        outcome: 'win', 'loss', or 'refunded'
        house_payout_nanoerg: Amount paid to player (0 for losses)
        house_fee_nanoerg: Fee kept by house
        bet_timestamp: ISO 8601 timestamp of bet placement
        game_type: Game type (default 'coinflip')

    Returns:
        True if recorded, False if duplicate bet_id
    """
    now = datetime.now(timezone.utc).isoformat()

    if outcome == "loss":
        # House keeps the full bet. Net = +bet_amount.
        net_pnl = bet_amount_nanoerg
    elif outcome == "win":
        # House received bet, paid out to player. Net = bet - payout.
        # The 3% edge is already reflected in the reduced payout (1.94x vs 2x).
        net_pnl = bet_amount_nanoerg - house_payout_nanoerg
    elif outcome == "refunded":
        # House returns bet minus refund fee. Net = +fee only.
        net_pnl = house_fee_nanoerg
    else:
        raise ValueError(f"Invalid outcome: {outcome}")

    conn = _get_connection(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO pnl_rounds
                (bet_id, timestamp, resolved_at, player_address,
                 bet_amount_nanoerg, outcome, house_payout_nanoerg,
                 house_fee_nanoerg, net_pnl_nanoerg, game_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                bet_id,
                bet_timestamp or now,
                now,
                player_address,
                bet_amount_nanoerg,
                outcome,
                house_payout_nanoerg,
                house_fee_nanoerg,
                net_pnl,
                game_type,
            ),
        )
        conn.commit()
        logger.info(
            "P&L recorded: bet=%s outcome=%s amount=%d net_pnl=%d",
            bet_id, outcome, bet_amount_nanoerg, net_pnl,
        )
        return cur.rowcount > 0
    except sqlite3.IntegrityError:
        logger.debug("Duplicate bet_id %s — skipping", bet_id)
        return False
    finally:
        conn.close()


def get_summary(
    since: Optional[str] = None,
    until: Optional[str] = None,
    game_type: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> dict:
    """
    Get aggregated P&L summary.

    Returns:
        {
            "total_rounds": int,
            "wins": int,
            "losses": int,
            "refunds": int,
            "win_rate_pct": float,
            "total_wagered_nanoerg": int,
            "total_payout_nanoerg": int,
            "total_fees_nanoerg": int,
            "net_pnl_nanoerg": int,
            "avg_house_edge_realized_pct": float,
            "biggest_round_win_nanoerg": int,
            "biggest_round_loss_nanoerg": int,
        }
    """
    conn = _get_connection(db_path)
    try:
        query = "SELECT * FROM pnl_rounds WHERE 1=1"
        params: list = []

        if since:
            query += " AND resolved_at >= ?"
            params.append(since)
        if until:
            query += " AND resolved_at <= ?"
            params.append(until)
        if game_type:
            query += " AND game_type = ?"
            params.append(game_type)

        query += " ORDER BY resolved_at ASC"

        rows = conn.execute(query, params).fetchall()

        if not rows:
            return {
                "total_rounds": 0,
                "wins": 0,
                "losses": 0,
                "refunds": 0,
                "win_rate_pct": 0.0,
                "total_wagered_nanoerg": 0,
                "total_payout_nanoerg": 0,
                "total_fees_nanoerg": 0,
                "net_pnl_nanoerg": 0,
                "avg_house_edge_realized_pct": 0.0,
                "biggest_round_win_nanoerg": 0,
                "biggest_round_loss_nanoerg": 0,
            }

        total_rounds = len(rows)
        wins = sum(1 for r in rows if r["outcome"] == "win")
        losses = sum(1 for r in rows if r["outcome"] == "loss")
        refunds = sum(1 for r in rows if r["outcome"] == "refunded")
        total_wagered = sum(r["bet_amount_nanoerg"] for r in rows)
        total_payout = sum(r["house_payout_nanoerg"] for r in rows)
        total_fees = sum(r["house_fee_nanoerg"] for r in rows)
        net_pnl = sum(r["net_pnl_nanoerg"] for r in rows)

        # Realized house edge = total_fees / total_wagered * 100
        avg_edge = (total_fees / total_wagered * 100) if total_wagered > 0 else 0.0

        # Win rate from house perspective (how often house wins)
        house_win_rate = (losses / total_rounds * 100) if total_rounds > 0 else 0.0

        biggest_win = max((r["net_pnl_nanoerg"] for r in rows), default=0)
        biggest_loss = min((r["net_pnl_nanoerg"] for r in rows), default=0)

        return {
            "total_rounds": total_rounds,
            "wins": wins,         # player wins (house losses)
            "losses": losses,     # player losses (house wins)
            "refunds": refunds,
            "win_rate_pct": round(house_win_rate, 2),
            "total_wagered_nanoerg": total_wagered,
            "total_payout_nanoerg": total_payout,
            "total_fees_nanoerg": total_fees,
            "net_pnl_nanoerg": net_pnl,
            "avg_house_edge_realized_pct": round(avg_edge, 4),
            "biggest_round_win_nanoerg": biggest_win,
            "biggest_round_loss_nanoerg": biggest_loss,
        }
    finally:
        conn.close()


def get_rounds(
    limit: int = 50,
    offset: int = 0,
    player_address: Optional[str] = None,
    outcome: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Tuple[List[dict], int]:
    """
    Get paginated list of individual round P&L.

    Returns:
        (rounds_list, total_count)
    """
    conn = _get_connection(db_path)
    try:
        where_clauses = []
        params: list = []

        if player_address:
            where_clauses.append("player_address = ?")
            params.append(player_address)
        if outcome:
            where_clauses.append("outcome = ?")
            params.append(outcome)
        if since:
            where_clauses.append("resolved_at >= ?")
            params.append(since)
        if until:
            where_clauses.append("resolved_at <= ?")
            params.append(until)

        where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        # Get total count
        total = conn.execute(f"SELECT COUNT(*) FROM pnl_rounds {where}", params).fetchone()[0]

        # Get paginated rows
        rows = conn.execute(
            f"SELECT * FROM pnl_rounds {where} ORDER BY resolved_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

        rounds = [
            {
                "bet_id": r["bet_id"],
                "timestamp": r["timestamp"],
                "resolved_at": r["resolved_at"],
                "player_address": r["player_address"],
                "bet_amount_nanoerg": r["bet_amount_nanoerg"],
                "bet_amount_erg": f"{r['bet_amount_nanoerg'] / 1e9:.9f}",
                "outcome": r["outcome"],
                "house_payout_nanoerg": r["house_payout_nanoerg"],
                "house_payout_erg": f"{r['house_payout_nanoerg'] / 1e9:.9f}",
                "house_fee_nanoerg": r["house_fee_nanoerg"],
                "house_fee_erg": f"{r['house_fee_nanoerg'] / 1e9:.9f}",
                "net_pnl_nanoerg": r["net_pnl_nanoerg"],
                "net_pnl_erg": f"{r['net_pnl_nanoerg'] / 1e9:.9f}",
                "game_type": r["game_type"],
            }
            for r in rows
        ]

        return rounds, total
    finally:
        conn.close()


def get_period_pnl(
    period: str = "day",
    db_path: Optional[Path] = None,
) -> List[dict]:
    """
    Get P&L aggregated by time period.

    Args:
        period: 'hour', 'day', or 'week'

    Returns:
        List of dicts with {period_start, period_end, rounds, net_pnl_nanoerg, wagered, fees}
    """
    # Map period to SQLite strftime format
    if period == "hour":
        fmt = "%Y-%m-%d %H:00:00"
    elif period == "day":
        fmt = "%Y-%m-%d 00:00:00"
    elif period == "week":
        # SQLite doesn't have week truncation natively, use day and group client-side
        fmt = "%Y-%m-%d 00:00:00"
    else:
        raise ValueError(f"Invalid period: {period}. Must be 'hour', 'day', or 'week'")

    conn = _get_connection(db_path)
    try:
        query = f"""
            SELECT
                strftime('{fmt}', resolved_at) as period_start,
                COUNT(*) as rounds,
                SUM(CASE WHEN outcome = 'loss' THEN 1 ELSE 0 END) as house_wins,
                SUM(CASE WHEN outcome = 'win' THEN 1 ELSE 0 END) as player_wins,
                SUM(CASE WHEN outcome = 'refunded' THEN 1 ELSE 0 END) as refunds,
                SUM(bet_amount_nanoerg) as total_wagered,
                SUM(house_payout_nanoerg) as total_payout,
                SUM(house_fee_nanoerg) as total_fees,
                SUM(net_pnl_nanoerg) as net_pnl
            FROM pnl_rounds
            WHERE resolved_at IS NOT NULL
            GROUP BY period_start
            ORDER BY period_start DESC
            LIMIT 100
        """
        rows = conn.execute(query).fetchall()

        results = []
        for r in rows:
            results.append({
                "period_start": r["period_start"],
                "rounds": r["rounds"],
                "house_wins": r["house_wins"],
                "player_wins": r["player_wins"],
                "refunds": r["refunds"],
                "total_wagered_nanoerg": r["total_wagered"] or 0,
                "total_payout_nanoerg": r["total_payout"] or 0,
                "total_fees_nanoerg": r["total_fees"] or 0,
                "net_pnl_nanoerg": r["net_pnl"] or 0,
                "total_wagered_erg": f"{(r['total_wagered'] or 0) / 1e9:.9f}",
                "total_payout_erg": f"{(r['total_payout'] or 0) / 1e9:.9f}",
                "total_fees_erg": f"{(r['total_fees'] or 0) / 1e9:.9f}",
                "net_pnl_erg": f"{(r['net_pnl'] or 0) / 1e9:.9f}",
            })

        # If week period, re-aggregate into weekly buckets
        if period == "week" and results:
            weekly = {}
            for r in results:
                dt = datetime.fromisoformat(r["period_start"])
                # Find the Monday of that week
                monday = dt - timedelta(days=dt.weekday())
                week_key = monday.strftime("%Y-%m-%d")
                if week_key not in weekly:
                    weekly[week_key] = {
                        "period_start": week_key,
                        "rounds": 0,
                        "house_wins": 0,
                        "player_wins": 0,
                        "refunds": 0,
                        "total_wagered_nanoerg": 0,
                        "total_payout_nanoerg": 0,
                        "total_fees_nanoerg": 0,
                        "net_pnl_nanoerg": 0,
                    }
                w = weekly[week_key]
                w["rounds"] += r["rounds"]
                w["house_wins"] += r["house_wins"]
                w["player_wins"] += r["player_wins"]
                w["refunds"] += r["refunds"]
                w["total_wagered_nanoerg"] += r["total_wagered_nanoerg"]
                w["total_payout_nanoerg"] += r["total_payout_nanoerg"]
                w["total_fees_nanoerg"] += r["total_fees_nanoerg"]
                w["net_pnl_nanoerg"] += r["net_pnl_nanoerg"]

            for w in weekly.values():
                w["total_wagered_erg"] = f"{w['total_wagered_nanoerg'] / 1e9:.9f}"
                w["total_payout_erg"] = f"{w['total_payout_nanoerg'] / 1e9:.9f}"
                w["total_fees_erg"] = f"{w['total_fees_nanoerg'] / 1e9:.9f}"
                w["net_pnl_erg"] = f"{w['net_pnl_nanoerg'] / 1e9:.9f}"

            results = sorted(weekly.values(), key=lambda x: x["period_start"], reverse=True)

        return results
    finally:
        conn.close()


def get_player_pnl(
    player_address: str,
    db_path: Optional[Path] = None,
) -> dict:
    """
    Get P&L summary for a specific player.

    Returns player-centric P&L (inverse of house P&L).
    """
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM pnl_rounds WHERE player_address = ? ORDER BY resolved_at DESC",
            (player_address,),
        ).fetchall()

        if not rows:
            return {
                "player_address": player_address,
                "total_rounds": 0,
                "wins": 0,
                "losses": 0,
                "refunds": 0,
                "total_wagered_nanoerg": 0,
                "total_won_nanoerg": 0,
                "net_player_pnl_nanoerg": 0,
            }

        wins = sum(1 for r in rows if r["outcome"] == "win")
        losses = sum(1 for r in rows if r["outcome"] == "loss")
        refunds = sum(1 for r in rows if r["outcome"] == "refunded")
        total_wagered = sum(r["bet_amount_nanoerg"] for r in rows)
        total_won = sum(r["house_payout_nanoerg"] for r in rows if r["outcome"] == "win")
        # Player P&L = total won - total wagered (simplified; refunds return most of bet)
        net_player = total_won - total_wagered + sum(
            r["house_payout_nanoerg"] for r in rows if r["outcome"] == "refunded"
        )

        return {
            "player_address": player_address,
            "total_rounds": len(rows),
            "wins": wins,
            "losses": losses,
            "refunds": refunds,
            "total_wagered_nanoerg": total_wagered,
            "total_wagered_erg": f"{total_wagered / 1e9:.9f}",
            "total_won_nanoerg": total_won,
            "total_won_erg": f"{total_won / 1e9:.9f}",
            "net_player_pnl_nanoerg": net_player,
            "net_player_pnl_erg": f"{net_player / 1e9:.9f}",
        }
    finally:
        conn.close()
