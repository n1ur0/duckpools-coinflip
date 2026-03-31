"""
DuckPools Off-Chain Bot - Main Bot Script

Monitors PendingBet boxes, reveals secrets, calculates RNG, and settles bets.

Complete lifecycle per bet:
  1. Scan UTXO set for boxes matching CONTRACT_ERGO_TREE (with R4-R9 populated)
  2. Verify commitment: blake2b256(R9 || R7_choice_byte) == R6
  3. Fetch parent block header for RNG entropy
  4. Determine outcome: blake2b256(blockId || R9)[0] % 2
  5. Build reveal transaction (house signs, pays winner)
  6. Broadcast transaction via node
  7. Report settlement to backend API for bet history
  8. Track processed box IDs to avoid double-settlement

Dependencies:
  - Ergo node with wallet unlocked and API access
  - CONTRACT_ERGO_TREE, HOUSE_ADDRESS, ERGO_API_KEY env vars
  - Optional: BACKEND_API_URL for bet history sync

MAT-182: Structured logging and error recovery
MAT-223: Add retry logic and graceful shutdown
MAT-416: Reveal flow, byErgoTree polling, register mapping R4-R9
"""

import asyncio
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from logger import configure_logging, get_logger
from health_server import HealthServer
from bet_processor import (
    BetOutcome,
    PendingBet,
    SettlementResult,
    build_reveal_transaction,
    calculate_payout,
    determine_outcome,
    parse_pending_bet,
    pk_bytes_to_address,
    report_settlement,
    verify_commitment,
)

# Configure structured logging
configure_logging()
logger = get_logger(__name__)

# ─── Configuration ─────────────────────────────────────────────────────────

NODE_URL = os.getenv("NODE_URL", "http://localhost:9052")
ERGO_API_KEY = os.getenv("ERGO_API_KEY", "")
CONTRACT_ERGO_TREE = os.getenv(
    "CONTRACT_ERGO_TREE",
    "19d8010c04000200020104000404040005c20105640400040004000564d805d601cdeee4c6a7040ed602e4c6a7090ed603e4c6a70704d604cdeee4c6a7050ed605c1a7eb02ea02ea027201d193cbb3720283010295937203730073017302e4c6a7060ed195939e7eb2cbb3db6503fe72027303000473047203d801d606b2a5730500ed93c27206d0720492c172069d9c720573067307d801d606b2a5730800ed93c27206d0720192c172067205ea02ea02ea02d192a3e4c6a708047204d193c2b2a5730900d07204d192c1b2a5730a009972059d7205730b",
)
HOUSE_ADDRESS = os.getenv("HOUSE_ADDRESS", "")
WALLET_PASS = os.getenv("WALLET_PASS", "")
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "5"))
REVEAL_DELAY_BLOCKS = int(os.getenv("REVEAL_DELAY_BLOCKS", "2"))
HEARTBEAT_FILE = os.getenv("HEARTBEAT_FILE", "/tmp/off-chain-bot-heartbeat.txt")
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "30"))
HEALTH_PORT = int(os.getenv("HEALTH_SERVER_PORT", "8001"))
HOUSE_EDGE_BPS = int(os.getenv("HOUSE_EDGE_BPS", "300"))

# ─── Retry Configuration ────────────────────────────────────────────────────

RETRY_MAX = 3
RETRY_MIN_WAIT = 1
RETRY_MAX_WAIT = 4

# ─── State ──────────────────────────────────────────────────────────────────

# Track processed box IDs to avoid double-settlement
_processed_box_ids: Set[str] = set()


def is_retryable_error(exception: Exception) -> bool:
    """Check if an exception is retryable (network/timeout/5xx)."""
    if isinstance(exception, (httpx.ConnectError, httpx.ConnectTimeout)):
        return True
    if isinstance(exception, httpx.TimeoutException):
        return True
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in (500, 502, 503)
    return False


def _retry_decorator():
    """Return a tenacity retry decorator with exponential backoff."""

    def _log_retry(retry_state):
        logger.warning(
            "api_retry",
            attempt=retry_state.attempt_number,
            error=str(retry_state.outcome.exception()) if retry_state.outcome else "",
            elapsed_s=retry_state.seconds_since_start,
        )

    return retry(
        stop=stop_after_attempt(RETRY_MAX),
        wait=wait_exponential(multiplier=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
        retry=retry_if_exception(is_retryable_error),
        before_sleep=_log_retry,
        reraise=True,
    )


# ─── Graceful Shutdown ──────────────────────────────────────────────────────

class ShutdownManager:
    def __init__(self):
        self.shutdown_requested = False
        self._original_handlers: Dict = {}

    def setup_signal_handlers(self):
        for sig in (signal.SIGINT, signal.SIGTERM):
            self._original_handlers[sig] = signal.signal(
                sig, self._handle_shutdown_signal
            )

    def _handle_shutdown_signal(self, signum, frame):
        sig_name = signal.Signals(signum).name
        logger.info(
            "shutdown_signal_received",
            signal=sig_name,
            message="Will finish current bet then stop",
        )
        self.shutdown_requested = True

    def restore_signal_handlers(self):
        for sig, handler in self._original_handlers.items():
            signal.signal(sig, handler)

    def is_shutdown_requested(self) -> bool:
        return self.shutdown_requested


# ─── Heartbeat ──────────────────────────────────────────────────────────────

class HeartbeatManager:
    def __init__(self, heartbeat_file: str):
        self.heartbeat_file = Path(heartbeat_file)
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def start(self, interval_seconds: int = 30):
        self._stop_event.clear()
        self._task = asyncio.create_task(self._heartbeat_loop(interval_seconds))
        logger.info("heartbeat_started", file=str(self.heartbeat_file))

    async def stop(self):
        if self._task:
            self._stop_event.set()
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            if self.heartbeat_file.exists():
                self.heartbeat_file.unlink()
                logger.info("heartbeat_removed")

    async def _heartbeat_loop(self, interval_seconds: int):
        while not self._stop_event.is_set():
            try:
                ts = datetime.now(timezone.utc).isoformat()
                self.heartbeat_file.write_text(ts)
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("heartbeat_error", error=str(e))
                await asyncio.sleep(1)


# ─── Ergo Node Client ──────────────────────────────────────────────────────

class ErgoNodeClient:
    """HTTP client for Ergo node API with retry logic."""

    def __init__(self, node_url: str, api_key: str = ""):
        self.node_url = node_url.rstrip("/")
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    async def start(self):
        self._client = httpx.AsyncClient(timeout=30.0)
        logger.info("ergo_client_started", node_url=self.node_url)

    async def stop(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> dict:
        h = {}
        if self.api_key:
            h["api_key"] = self.api_key
        return h

    @_retry_decorator()
    async def get(self, endpoint: str, **kwargs) -> dict:
        if not self._client:
            raise RuntimeError("Client not started")
        url = f"{self.node_url}{endpoint}"
        logger.debug("ergo_get", url=url)
        resp = await self._client.get(url, headers=self._headers(), **kwargs)
        resp.raise_for_status()
        return resp.json()

    @_retry_decorator()
    async def post(self, endpoint: str, data: dict = None, **kwargs) -> dict:
        if not self._client:
            raise RuntimeError("Client not started")
        url = f"{self.node_url}{endpoint}"
        logger.debug("ergo_post", url=url)
        resp = await self._client.post(url, json=data, headers=self._headers(), **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def get_node_height(self) -> int:
        """Get current full block height."""
        info = await self.get("/info")
        return info.get("fullHeight", 0)

    async def get_blocks_at_height(self, height: int) -> List[dict]:
        """Get block headers at a given height."""
        headers = await self.get(f"/blocks/at/{height}")
        if isinstance(headers, list):
            return headers
        return [headers]

    async def get_block_header(self, block_id: str) -> dict:
        """Get a specific block header by ID."""
        return await self.get(f"/blocks/{block_id}/header")

    async def scan_utxo_by_tree(self, ergo_tree: str) -> List[dict]:
        """
        Scan UTXO set for boxes matching an ErgoTree.

        Uses /utxo/withUnspentOutputs which returns all unspent boxes.
        We filter client-side for boxes matching our contract tree.
        """
        utxo_response = await self.get("/utxo/withUnspentOutputs")
        boxes = utxo_response.get("unspentOutputs", [])
        if not isinstance(boxes, list):
            boxes = []
        return [b for b in boxes if b.get("ergoTree", "") == ergo_tree]

    async def send_transaction(self, tx: dict) -> str:
        """
        Submit a transaction to the node for signing and broadcasting.

        The node signs with the house wallet if inputs require it.

        Returns:
            Transaction ID string
        """
        result = await self.post("/transactions", data=tx)
        return result.get("txId", "")

    async def check_wallet_unlocked(self) -> bool:
        """Check if the node wallet is unlocked and ready."""
        try:
            status = await self.get("/wallet/status")
            return status.get("isUnlocked", False)
        except httpx.HTTPStatusError:
            return False


# ─── Bet Settlement Engine ─────────────────────────────────────────────────

class BetSettler:
    """
    Orchestrates the full bet settlement flow for a single PendingBet box.
    """

    def __init__(
        self,
        node_client: ErgoNodeClient,
        house_address: str,
        house_edge_bps: int = 300,
    ):
        self.node = node_client
        self.house_address = house_address
        self.house_edge_bps = house_edge_bps
        self._backend_client: Optional[httpx.AsyncClient] = None

    async def _get_backend_client(self) -> httpx.AsyncClient:
        if self._backend_client is None and BACKEND_API_URL:
            self._backend_client = httpx.AsyncClient(timeout=10.0)
        return self._backend_client

    async def settle(self, bet: PendingBet) -> SettlementResult:
        """
        Full settlement flow for a single PendingBet.

        Steps:
          1. Verify commitment hash (R6 == blake2b256(R9 || R7_choice_byte))
          2. Get parent block header for RNG entropy
          3. Determine outcome via blake2b256(blockId || R9)[0] % 2
          4. Calculate payout amount
          5. Build reveal transaction
          6. Broadcast via node
          7. Report to backend

        Returns:
            SettlementResult with outcome and tx_id
        """
        box_id = bet.box_id

        # Step 1: Verify commitment
        if not verify_commitment(
            bet.player_secret, bet.player_choice, bet.commitment_hash
        ):
            logger.error(
                "commitment_verification_failed",
                box_id=box_id,
                player_choice=bet.player_choice,
            )
            return SettlementResult(
                box_id=box_id,
                outcome=BetOutcome.LOSE,
                rng_result=-1,
                player_choice=bet.player_choice,
                player_address="",
                bet_amount_nanoerg=bet.value,
                payout_nanoerg=0,
                error="Commitment hash mismatch",
            )

        logger.info(
            "commitment_verified",
            box_id=box_id,
            choice=bet.choice_label,
        )

        # Step 2: Get current height and parent block header for RNG
        current_height = await self.node.get_node_height()
        # Use the tip block's header — CONTEXT.preHeader.parentId is the
        # block at (currentHeight - 1). We fetch the header at currentHeight
        # to get its parentId.
        try:
            tip_blocks = await self.node.get_blocks_at_height(current_height)
            if not tip_blocks:
                logger.error("no_tip_block", height=current_height)
                return SettlementResult(
                    box_id=box_id,
                    outcome=BetOutcome.LOSE,
                    rng_result=-1,
                    player_choice=bet.player_choice,
                    player_address="",
                    bet_amount_nanoerg=bet.value,
                    payout_nanoerg=0,
                    error=f"No block at height {current_height}",
                )

            tip_block = tip_blocks[0]
            parent_block_id = tip_block.get("header", {}).get(
                "parentId", tip_block.get("parentId", "")
            )
            if not parent_block_id:
                # Fallback: use the tip block ID itself
                parent_block_id = tip_block.get("header", {}).get(
                    "id", tip_block.get("id", "")
                )
        except Exception as e:
            logger.error("block_header_fetch_failed", error=str(e))
            return SettlementResult(
                box_id=box_id,
                outcome=BetOutcome.LOSE,
                rng_result=-1,
                player_choice=bet.player_choice,
                player_address="",
                bet_amount_nanoerg=bet.value,
                payout_nanoerg=0,
                error=f"Block header fetch failed: {e}",
            )

        # Step 3: Determine outcome
        rng_result, outcome = determine_outcome(
            parent_block_id, bet.player_secret, bet.player_choice
        )

        logger.info(
            "outcome_determined",
            box_id=box_id,
            rng_result=rng_result,
            outcome=outcome.value,
            player_choice=bet.choice_label,
            parent_block=parent_block_id[:16] + "...",
        )

        # Step 4: Calculate payout
        payout = calculate_payout(bet.value, outcome, self.house_edge_bps)

        # Step 5: Derive player address for backend reporting
        player_address = ""
        try:
            player_address = pk_bytes_to_address(bet.player_pk_bytes)
        except Exception as e:
            logger.warning("player_address_derivation_failed", error=str(e))

        # Step 6: Build and send reveal transaction
        tx = build_reveal_transaction(
            bet=bet,
            outcome=outcome,
            payout_amount=payout,
            house_address=self.house_address,
            current_height=current_height,
        )

        if not tx:
            logger.error("tx_build_failed", box_id=box_id)
            return SettlementResult(
                box_id=box_id,
                outcome=outcome,
                rng_result=rng_result,
                player_choice=bet.player_choice,
                player_address=player_address,
                bet_amount_nanoerg=bet.value,
                payout_nanoerg=payout,
                error="Failed to build transaction",
            )

        try:
            tx_id = await self.node.send_transaction(tx)
            logger.info(
                "reveal_tx_broadcast",
                box_id=box_id,
                tx_id=tx_id,
                outcome=outcome.value,
                payout=payout,
            )
        except Exception as e:
            logger.error(
                "reveal_tx_failed",
                box_id=box_id,
                error=str(e),
            )
            return SettlementResult(
                box_id=box_id,
                outcome=outcome,
                rng_result=rng_result,
                player_choice=bet.player_choice,
                player_address=player_address,
                bet_amount_nanoerg=bet.value,
                payout_nanoerg=payout,
                error=f"Transaction broadcast failed: {e}",
            )

        result = SettlementResult(
            box_id=box_id,
            outcome=outcome,
            rng_result=rng_result,
            player_choice=bet.player_choice,
            player_address=player_address,
            bet_amount_nanoerg=bet.value,
            payout_nanoerg=payout,
            tx_id=tx_id,
        )

        # Step 7: Report to backend
        backend_client = await self._get_backend_client()
        if backend_client:
            await report_settlement(BACKEND_API_URL, result, backend_client)

        return result


# ─── Main Bot ───────────────────────────────────────────────────────────────

class OffChainBot:
    def __init__(
        self,
        node_url: str,
        api_key: str,
        contract_ergo_tree: str,
        house_address: str,
        house_edge_bps: int = 300,
        heartbeat_file: str = "/tmp/off-chain-bot-heartbeat.txt",
        heartbeat_interval: int = 30,
        health_port: int = 8001,
        poll_interval: int = 5,
    ):
        self.node_url = node_url
        self.api_key = api_key
        self.contract_ergo_tree = contract_ergo_tree
        self.house_address = house_address
        self.house_edge_bps = house_edge_bps
        self.poll_interval = poll_interval
        self.shutdown_mgr = ShutdownManager()
        self.heartbeat_mgr = HeartbeatManager(heartbeat_file)
        self.health_server = HealthServer(port=health_port)
        self.node_client: Optional[ErgoNodeClient] = None
        self.settler: Optional[BetSettler] = None
        self._bets_settled = 0
        self._bets_failed = 0

    async def run(self):
        logger.info(
            "bot_starting",
            node_url=self.node_url,
            has_api_key=bool(self.api_key),
            has_contract_tree=bool(self.contract_ergo_tree),
            has_house_address=bool(self.house_address),
        )

        # Validate configuration
        self._validate_config()

        self.shutdown_mgr.setup_signal_handlers()
        await self.health_server.start()

        async with ErgoNodeClient(self.node_url, self.api_key) as client:
            self.node_client = client
            self.settler = BetSettler(
                node_client=client,
                house_address=self.house_address,
                house_edge_bps=self.house_edge_bps,
            )

            await self.heartbeat_mgr.start(HEARTBEAT_INTERVAL)

            try:
                await self.main_loop()
            finally:
                await self.heartbeat_mgr.stop()
                await self.health_server.stop()
                self.shutdown_mgr.restore_signal_handlers()

        logger.info(
            "bot_stopped",
            bets_settled=self._bets_settled,
            bets_failed=self._bets_failed,
        )

    def _validate_config(self):
        """Fail fast on missing required configuration."""
        missing = []
        if not self.api_key:
            missing.append("ERGO_API_KEY")
        if not self.contract_ergo_tree:
            missing.append("CONTRACT_ERGO_TREE")
        if not self.house_address:
            missing.append("HOUSE_ADDRESS")

        if missing:
            logger.error(
                "config_missing",
                vars=missing,
                message="Bot cannot operate without these env vars",
            )
            # Log but don't exit — allow health endpoint to still work
            # for monitoring. The main loop will skip actual processing.

    async def main_loop(self):
        logger.info("main_loop_started", poll_interval=self.poll_interval)

        while not self.shutdown_mgr.is_shutdown_requested():
            try:
                await self.process_pending_bets()

                if self.shutdown_mgr.is_shutdown_requested():
                    break

                await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                logger.info("main_loop_cancelled")
                break
            except Exception as e:
                logger.error("main_loop_error", error=str(e), exc_info=True)
                await asyncio.sleep(self.poll_interval)

    async def process_pending_bets(self):
        """Scan UTXO set and settle any pending bet boxes."""
        if not self.node_client or not self.settler:
            logger.debug("process_bets_skipped", reason="clients_not_initialized")
            return

        if not self.api_key or not self.house_address:
            logger.debug("process_bets_skipped", reason="missing_config")
            return

        # Scan for PendingBet boxes
        try:
            boxes = await self.node_client.scan_utxo_by_tree(self.contract_ergo_tree)
        except Exception as e:
            logger.error("utxo_scan_failed", error=str(e))
            return

        logger.debug("utxo_scan_complete", matching_boxes=len(boxes))

        for box in boxes:
            box_id = box.get("boxId", "")

            # Skip already-processed boxes
            if box_id in _processed_box_ids:
                continue

            # Parse box registers
            bet = parse_pending_bet(box)
            if bet is None:
                continue

            # Check if bet has timed out (player should refund, not house)
            current_height = await self.node_client.get_node_height()
            if current_height >= bet.timeout_height:
                logger.info(
                    "bet_timed_out",
                    box_id=box_id,
                    timeout_height=bet.timeout_height,
                    current_height=current_height,
                )
                _processed_box_ids.add(box_id)
                continue

            # Check reveal delay — don't reveal immediately to prevent
            # front-running by watching mempool
            height_since_creation = current_height - bet.creation_height
            if height_since_creation < REVEAL_DELAY_BLOCKS:
                logger.debug(
                    "bet_too_fresh",
                    box_id=box_id,
                    created_at=bet.creation_height,
                    current_height=current_height,
                    delay_needed=REVEAL_DELAY_BLOCKS,
                )
                continue

            # Verify house PK matches our expected key
            # (we check the first byte prefix of our address vs R4)
            # In production, compare full PK from wallet

            # Settle the bet
            logger.info("settling_bet", box_id=box_id, amount=bet.value)
            result = await self.settler.settle(bet)

            if result.success:
                self._bets_settled += 1
                self.health_server.increment_bets_processed()
                logger.info(
                    "bet_settled",
                    box_id=box_id,
                    outcome=result.outcome.value,
                    tx_id=result.tx_id,
                )
            else:
                self._bets_failed += 1
                logger.warning(
                    "bet_settlement_failed",
                    box_id=box_id,
                    error=result.error,
                )

            # Mark as processed regardless of success to avoid infinite retry
            _processed_box_ids.add(box_id)


# ─── Main ──────────────────────────────────────────────────────────────────

async def main():
    bot = OffChainBot(
        node_url=NODE_URL,
        api_key=ERGO_API_KEY,
        contract_ergo_tree=CONTRACT_ERGO_TREE,
        house_address=HOUSE_ADDRESS,
        house_edge_bps=HOUSE_EDGE_BPS,
        heartbeat_file=HEARTBEAT_FILE,
        heartbeat_interval=HEARTBEAT_INTERVAL,
        health_port=HEALTH_PORT,
        poll_interval=POLL_INTERVAL,
    )

    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt")
    except Exception as e:
        logger.error("bot_fatal_error", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
