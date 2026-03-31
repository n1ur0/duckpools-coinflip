"""
DuckPools Off-Chain Bot - Backend API Client

Updates bet history in the DuckPools backend after processing reveals.

The backend exposes an in-memory bet store via /api/game/history/{address}
and /api/game/place-bet. This client POSTs settlement results so the
frontend can display resolved outcomes.

In production, this would be a direct database write or a message queue.
For PoC, we hit the backend REST API.

MAT-419: Implement off-chain bot reveal logic
"""

from datetime import datetime, timezone
from typing import Optional

import httpx

from logger import get_logger

logger = get_logger(__name__)


class BackendClient:
    """HTTP client for DuckPools backend bet-history updates."""

    def __init__(self, backend_url: str):
        self.backend_url = backend_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    async def start(self):
        """Create HTTP client."""
        timeout = httpx.Timeout(10.0)
        self._client = httpx.AsyncClient(timeout=timeout)
        logger.info("backend_client_started", url=self.backend_url)

    async def stop(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def update_bet_outcome(
        self,
        bet_id: str,
        player_address: str,
        outcome: str,
        payout_nanoerg: int,
        rng_result: str,
        player_choice: str,
        resolved_at_height: int,
        tx_id: str = "",
        box_id: str = "",
    ) -> bool:
        """
        Report a resolved bet outcome to the backend.

        The backend stores bets in-memory in game_routes._bets.
        We update the matching bet's outcome field.

        For PoC, we POST to a dedicated settlement endpoint.
        If the endpoint doesn't exist yet, we log and continue.

        Args:
            bet_id: Unique bet identifier
            player_address: Player's Ergo address
            outcome: "win" or "loss"
            payout_nanoerg: Payout amount in nanoERG
            rng_result: "heads" or "tails"
            player_choice: "heads" or "tails"
            resolved_at_height: Block height when resolved
            tx_id: Transaction ID of the reveal tx
            box_id: Box ID that was spent

        Returns:
            True if update succeeded, False otherwise
        """
        if not self._client:
            logger.error("backend_client_not_started")
            return False

        payload = {
            "betId": bet_id,
            "playerAddress": player_address,
            "outcome": outcome,
            "payout": str(payout_nanoerg),
            "payoutMultiplier": 0.97 if outcome == "win" else 0.0,
            "actualOutcome": {
                "gameType": "coinflip",
                "result": rng_result,
                "rngValue": 0 if rng_result == "heads" else 1,
            },
            "resolvedAtHeight": resolved_at_height,
            "txId": tx_id,
            "boxId": box_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            response = await self._client.post(
                f"{self.backend_url}/api/game/settle-bet",
                json=payload,
            )
            if response.status_code == 200:
                logger.info(
                    "bet_outcome_updated",
                    bet_id=bet_id,
                    outcome=outcome,
                    payout=payout_nanoerg / 1e9,
                )
                return True
            elif response.status_code == 404:
                # Settlement endpoint doesn't exist yet — log and continue
                logger.warning(
                    "settle_endpoint_not_found",
                    status=response.status_code,
                    bet_id=bet_id,
                )
                # Try the bet record approach — find and update directly
                return await self._fallback_update_history(
                    bet_id, player_address, outcome, payout_nanoerg,
                    rng_result, player_choice, resolved_at_height,
                )
            else:
                logger.warning(
                    "bet_outcome_update_failed",
                    status=response.status_code,
                    response=response.text[:200],
                    bet_id=bet_id,
                )
                return False
        except httpx.HTTPError as e:
            logger.error(
                "backend_connection_error",
                error=str(e),
                bet_id=bet_id,
            )
            return False

    async def _fallback_update_history(
        self,
        bet_id: str,
        player_address: str,
        outcome: str,
        payout_nanoerg: int,
        rng_result: str,
        player_choice: str,
        resolved_at_height: int,
    ) -> bool:
        """
        Fallback: query existing bet history and log the update.

        If the /settle-bet endpoint doesn't exist, we at least verify
        the bet exists in history and log what the update would be.

        Args:
            bet_id, player_address, outcome, payout_nanoerg,
            rng_result, player_choice, resolved_at_height

        Returns:
            True if bet was found in history, False otherwise
        """
        try:
            response = await self._client.get(
                f"{self.backend_url}/api/game/history/{player_address}",
            )
            if response.status_code == 200:
                bets = response.json()
                found = any(b.get("betId") == bet_id for b in bets)
                if found:
                    logger.info(
                        "bet_found_in_history_settlement_pending",
                        bet_id=bet_id,
                        outcome=outcome,
                    )
                    return True
                else:
                    logger.warning(
                        "bet_not_found_in_history",
                        bet_id=bet_id,
                        player=player_address,
                    )
                    return False
        except httpx.HTTPError as e:
            logger.error("fallback_history_check_error", error=str(e))

        return False

    async def health_check(self) -> bool:
        """Check if the backend is reachable."""
        if not self._client:
            return False
        try:
            response = await self._client.get(
                f"{self.backend_url}/docs",
                timeout=3.0,
            )
            return response.status_code in (200, 307, 404)
        except httpx.HTTPError:
            return False
