"""
DuckPools - Game History Service

In-memory bet history tracking with search and aggregation.
Bets are stored from the time the backend starts; for production,
this should be backed by a database (SQLite/PostgreSQL).

MAT-167: Fix bet history showing all bets as pending with empty playerAddress
"""

import logging
import threading
import time
from typing import Dict, List, Optional

logger = logging.getLogger("duckpools.game_history")


class BetRecord:
    """A single bet record."""

    __slots__ = (
        "bet_id", "tx_id", "box_id", "player_address",
        "choice", "choice_label", "bet_amount_nanoerg",
        "outcome", "actual_outcome", "payout_nanoerg",
        "timestamp", "block_height", "resolved_at_height",
        "commitment", "created_at",
    )

    def __init__(
        self,
        bet_id: str,
        tx_id: str,
        box_id: str,
        player_address: str,
        choice: int,
        bet_amount_nanoerg: int,
        outcome: str = "pending",
        actual_outcome: Optional[int] = None,
        payout_nanoerg: int = 0,
        timestamp: Optional[str] = None,
        block_height: int = 0,
        resolved_at_height: Optional[int] = None,
        commitment: Optional[str] = None,
    ):
        self.bet_id = bet_id
        self.tx_id = tx_id
        self.box_id = box_id
        self.player_address = player_address
        self.choice = choice
        self.choice_label = "Heads" if choice == 0 else "Tails"
        self.bet_amount_nanoerg = bet_amount_nanoerg
        self.outcome = outcome
        self.actual_outcome = actual_outcome
        self.payout_nanoerg = payout_nanoerg
        self.timestamp = timestamp or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.block_height = block_height
        self.resolved_at_height = resolved_at_height
        self.commitment = commitment
        self.created_at = time.time()

    def to_api_dict(self) -> dict:
        """Convert to the BetRecord format expected by the frontend."""
        return {
            "betId": self.bet_id,
            "txId": self.tx_id,
            "boxId": self.box_id,
            "playerAddress": self.player_address,
            "choice": {
                "value": self.choice,
                "label": self.choice_label,
            },
            "betAmount": str(self.bet_amount_nanoerg),
            "outcome": self.outcome,
            "actualOutcome": self.actual_outcome,
            "payout": str(self.payout_nanoerg),
            "timestamp": self.timestamp,
            "blockHeight": self.block_height,
            "resolvedAtHeight": self.resolved_at_height,
        }


class GameHistoryService:
    """
    Thread-safe in-memory game history store.

    Stores bet records indexed by:
    - bet_id (primary key)
    - player_address (for history queries)
    """

    def __init__(self):
        self._bets: Dict[str, BetRecord] = {}  # bet_id -> BetRecord
        self._by_address: Dict[str, List[str]] = {}  # address -> [bet_ids]
        self._lock = threading.Lock()
        self._total_games = 0

    def add_bet(self, record: BetRecord) -> None:
        """Add a new bet record."""
        with self._lock:
            self._bets[record.bet_id] = record
            addr = record.player_address
            if addr not in self._by_address:
                self._by_address[addr] = []
            self._by_address[addr].append(record.bet_id)
            self._total_games += 1
            logger.info(
                "Bet added: bet_id=%s address=%s amount=%s choice=%s outcome=%s",
                record.bet_id[:12] + "...",
                addr[:10] + "...",
                record.bet_amount_nanoerg,
                record.choice_label,
                record.outcome,
            )

    def update_bet(
        self,
        bet_id: str,
        outcome: Optional[str] = None,
        actual_outcome: Optional[int] = None,
        payout_nanoerg: Optional[int] = None,
        tx_id: Optional[str] = None,
        resolved_at_height: Optional[int] = None,
    ) -> bool:
        """
        Update an existing bet (e.g., after resolution).

        Returns True if the bet was found and updated.
        """
        with self._lock:
            record = self._bets.get(bet_id)
            if not record:
                logger.warning("update_bet: bet_id=%s not found", bet_id)
                return False

            if outcome is not None:
                record.outcome = outcome
            if actual_outcome is not None:
                record.actual_outcome = actual_outcome
            if payout_nanoerg is not None:
                record.payout_nanoerg = payout_nanoerg
            if tx_id is not None:
                record.tx_id = tx_id
            if resolved_at_height is not None:
                record.resolved_at_height = resolved_at_height

            logger.info(
                "Bet updated: bet_id=%s outcome=%s payout=%s",
                record.bet_id[:12] + "...",
                record.outcome,
                record.payout_nanoerg,
            )
            return True

    def get_bet(self, bet_id: str) -> Optional[BetRecord]:
        """Get a single bet by ID."""
        with self._lock:
            return self._bets.get(bet_id)

    def get_history(
        self,
        address: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[dict]:
        """
        Get bet history for an address, most recent first.

        Returns list of API-format dicts.
        """
        with self._lock:
            bet_ids = self._by_address.get(address, [])
            # Reverse to get most recent first
            bet_ids = list(reversed(bet_ids))
            # Apply pagination
            bet_ids = bet_ids[offset : offset + limit]

            return [self._bets[bid].to_api_dict() for bid in bet_ids if bid in self._bets]

    def get_history_count(self, address: str) -> int:
        """Get total bet count for an address."""
        with self._lock:
            return len(self._by_address.get(address, []))

    def get_all_pending(self) -> List[BetRecord]:
        """Get all pending bets (for the bot to process)."""
        with self._lock:
            return [r for r in self._bets.values() if r.outcome == "pending"]

    def get_stats(self) -> dict:
        """Get aggregate statistics."""
        with self._lock:
            wins = sum(1 for r in self._bets.values() if r.outcome == "win")
            losses = sum(1 for r in self._bets.values() if r.outcome == "loss")
            refunded = sum(1 for r in self._bets.values() if r.outcome == "refunded")
            pending = sum(1 for r in self._bets.values() if r.outcome == "pending")
            total_wagered = sum(r.bet_amount_nanoerg for r in self._bets.values())
            total_payouts = sum(r.payout_nanoerg for r in self._bets.values() if r.outcome == "win")

            return {
                "total_games": self._total_games,
                "wins": wins,
                "losses": losses,
                "refunded": refunded,
                "pending": pending,
                "total_wagered_nanoerg": total_wagered,
                "total_payouts_nanoerg": total_payouts,
            }
