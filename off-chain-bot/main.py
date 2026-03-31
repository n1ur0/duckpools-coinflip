"""
DuckPools Off-Chain Bot - Main Bot Script

Monitors PendingBet boxes, reveals secrets, calculates RNG, and settles bets.

Features:
- Retry logic with exponential backoff for Ergo node API calls
- Graceful shutdown on SIGINT/SIGTERM
- Heartbeat file for liveness monitoring
- Structured logging

MAT-182: Structured logging and error recovery
MAT-223: Add retry logic and graceful shutdown
"""

import asyncio
import json
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from logger import configure_logging, get_logger
from health_server import HealthServer

# Configure structured logging
configure_logging()
logger = get_logger(__name__)

# ─── Configuration ─────────────────────────────────────────────────────────

# Load from environment variables
NODE_URL = os.getenv("NODE_URL", "http://127.0.0.1:9052")
NODE_API_KEY = os.getenv("NODE_API_KEY", "")
HEARTBEAT_FILE = os.getenv("HEARTBEAT_FILE", "/tmp/off-chain-bot-heartbeat.txt")
HEARTBEAT_INTERVAL_SECONDS = int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "30"))
HEALTH_SERVER_PORT = int(os.getenv("HEALTH_SERVER_PORT", "8001"))

# Data directory for shared files (pending_txs.json, pending_boxes.json).
# Defaults to the bot's own directory so it matches where the backend writes.
DATA_DIR = Path(os.getenv("DATA_DIR", str(Path(__file__).parent)))

# Backend API URL for reporting bet resolutions (MAT-419)
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
BOT_API_KEY = os.getenv("BOT_API_KEY", "")
# ─── Retry Configuration ────────────────────────────────────────────────────

RETRY_MAX_ATTEMPTS = 3
RETRY_MIN_WAIT_SECONDS = 1
RETRY_MAX_WAIT_SECONDS = 4


def is_retryable_error(exception: Exception) -> bool:
    """
    Check if an exception is retryable.

    Args:
        exception: The exception to check

    Returns:
        True if retryable, False otherwise
    """
    # Connection errors
    if isinstance(exception, (httpx.ConnectError, httpx.ConnectTimeout)):
        return True

    # Timeout errors
    if isinstance(exception, httpx.TimeoutException):
        return True

    # HTTP status errors (500, 502, 503)
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in (500, 502, 503)

    return False


def get_retry_decorator():
    """
    Get a tenacity retry decorator with exponential backoff.

    Returns:
        Configured retry decorator
    """

    def log_retry_attempt(retry_state):
        """Log retry attempt using structlog."""
        logger.warning(
            "api_retry_attempt",
            attempt_number=retry_state.attempt_number,
            exception=str(retry_state.outcome.exception()),
            seconds_since_start=retry_state.seconds_since_start,
        )

    return retry(
        stop=stop_after_attempt(RETRY_MAX_ATTEMPTS),
        wait=wait_exponential(
            multiplier=RETRY_MIN_WAIT_SECONDS,
            max=RETRY_MAX_WAIT_SECONDS,
        ),
        retry=retry_if_exception(is_retryable_error),
        before_sleep=log_retry_attempt,
        reraise=True,
    )


# ─── Graceful Shutdown ───────────────────────────────────────────────────

class ShutdownManager:
    """Manages graceful shutdown signals."""

    def __init__(self):
        self.shutdown_requested = False
        self._original_handlers = {}

    def setup_signal_handlers(self):
        """Setup signal handlers for SIGINT and SIGTERM."""
        for sig in (signal.SIGINT, signal.SIGTERM):
            self._original_handlers[sig] = signal.signal(
                sig, self._handle_shutdown_signal
            )

    def _handle_shutdown_signal(self, signum, frame):
        """Handle shutdown signal."""
        sig_name = signal.Signals(signum).name
        logger.info(
            "shutdown_signal_received",
            signal=sig_name,
            message="Shutdown requested, will finish processing current bet"
        )
        self.shutdown_requested = True

    def restore_signal_handlers(self):
        """Restore original signal handlers."""
        for sig, handler in self._original_handlers.items():
            signal.signal(sig, handler)

    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self.shutdown_requested


# ─── Heartbeat ────────────────────────────────────────────────────────────

class HeartbeatManager:
    """Manages heartbeat file for liveness monitoring."""

    def __init__(self, heartbeat_file: str):
        self.heartbeat_file = Path(heartbeat_file)
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def start(self, interval_seconds: int = 30):
        """
        Start heartbeat file updates.

        Args:
            interval_seconds: Interval between heartbeat updates
        """
        self._stop_event.clear()
        self._task = asyncio.create_task(
            self._heartbeat_loop(interval_seconds)
        )
        logger.info(
            "heartbeat_started",
            file=str(self.heartbeat_file),
            interval_seconds=interval_seconds
        )

    async def stop(self):
        """Stop heartbeat file updates."""
        if self._task:
            self._stop_event.set()
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

            # Remove heartbeat file on shutdown
            if self.heartbeat_file.exists():
                self.heartbeat_file.unlink()
                logger.info("heartbeat_removed", file=str(self.heartbeat_file))

    async def _heartbeat_loop(self, interval_seconds: int):
        """
        Background task to update heartbeat file.

        Args:
            interval_seconds: Interval between updates
        """
        while not self._stop_event.is_set():
            try:
                self.update()
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "heartbeat_update_error",
                    error=str(e),
                    exc_info=True
                )
                await asyncio.sleep(1)  # Brief pause before retry

    def update(self):
        """Update heartbeat file with current timestamp."""
        timestamp = datetime.now(timezone.utc).isoformat()
        self.heartbeat_file.write_text(timestamp)


# ─── Ergo Node Client ───────────────────────────────────────────────────

class ErgoNodeClient:
    """HTTP client for Ergo node API with retry logic."""

    def __init__(self, node_url: str, api_key: str = ""):
        self.node_url = node_url
        self.api_key = api_key
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Enter context manager and create client."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager and close client."""
        await self.stop()

    async def start(self):
        """Create HTTP client."""
        timeout = httpx.Timeout(30.0)
        self._client = httpx.AsyncClient(timeout=timeout)
        logger.info("ergo_client_started", node_url=self.node_url)

    async def stop(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("ergo_client_stopped")

    @get_retry_decorator()
    async def get(self, endpoint: str) -> dict:
        """
        Make GET request to Ergo node API with retry.

        Args:
            endpoint: API endpoint path

        Returns:
            JSON response as dict

        Raises:
            httpx.HTTPError: If all retries fail
        """
        if not self._client:
            raise RuntimeError("Client not started")

        url = f"{self.node_url}{endpoint}"
        headers = {}
        if self.api_key:
            headers["api_key"] = self.api_key

        logger.debug("ergo_api_request", method="GET", url=url)

        response = await self._client.get(url, headers=headers)
        response.raise_for_status()

        return response.json()

    @get_retry_decorator()
    async def post(self, endpoint: str, data: dict = None) -> dict:
        """
        Make POST request to Ergo node API with retry.

        Args:
            endpoint: API endpoint path
            data: Request body data

        Returns:
            JSON response as dict

        Raises:
            httpx.HTTPError: If all retries fail
        """
        if not self._client:
            raise RuntimeError("Client not started")

        url = f"{self.node_url}{endpoint}"
        headers = {}
        if self.api_key:
            headers["api_key"] = self.api_key

        logger.debug("ergo_api_request", method="POST", url=url)

        response = await self._client.post(url, json=data, headers=headers)
        response.raise_for_status()

        return response.json()


# ─── Bot Logic ───────────────────────────────────────────────────────────

class OffChainBot:
    """Main off-chain bot class."""

    def __init__(
        self,
        node_url: str,
        api_key: str,
        heartbeat_file: str,
        heartbeat_interval_seconds: int = 30,
        health_server_port: int = 8001,
    ):
        self.node_url = node_url
        self.api_key = api_key
        self.api_key = api_key
        self.shutdown_manager = ShutdownManager()
        self.heartbeat_manager = HeartbeatManager(heartbeat_file)
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self.client: Optional[ErgoNodeClient] = None
        self.health_server = HealthServer(port=health_server_port)

    async def run(self):
        """Run the off-chain bot main loop."""
        logger.info("bot_starting", node_url=self.node_url)

        # Setup graceful shutdown
        self.shutdown_manager.setup_signal_handlers()

        # Start health server
        await self.health_server.start()

        # Create Ergo node client
        async with ErgoNodeClient(self.node_url, self.api_key) as client:
            self.client = client

            # Start heartbeat
            await self.heartbeat_manager.start(self.heartbeat_interval_seconds)

            try:
                await self.main_loop()
            finally:
                # Stop heartbeat
                await self.heartbeat_manager.stop()

                # Stop health server
                await self.health_server.stop()

                # Restore signal handlers
                self.shutdown_manager.restore_signal_handlers()

        logger.info("bot_stopped")

    async def main_loop(self):
        """Main bot processing loop."""
        logger.info("main_loop_started")

        while not self.shutdown_manager.is_shutdown_requested():
            try:
                # TODO: Implement actual bet monitoring logic
                # This is a placeholder that will be replaced with real bet processing
                await self.process_bets()

                # Check for shutdown before sleeping
                if self.shutdown_manager.is_shutdown_requested():
                    logger.info("main_loop_shutdown_requested")
                    break

                # Sleep before next iteration
                await asyncio.sleep(5)

            except asyncio.CancelledError:
                logger.info("main_loop_cancelled")
                break
            except Exception as e:
                logger.error(
                    "main_loop_error",
                    error=str(e),
                    exc_info=True
                )
                # Sleep briefly before retrying to avoid tight error loop
                await asyncio.sleep(5)

    async def process_bets(self):
        """
        Process pending bets — real implementation.

        Workflow:
        1. Check node is synced (fullHeight must not be null)
        2. Get current best block header (for RNG seed: CONTEXT.preHeader.parentId)
        3. Scan for unspent boxes with coinflip contract ergoTree
        4. For each PendingBet box:
           a. Extract registers R4-R9 (pubkeys, commitment, choice, timeout, secret)
           b. Compute RNG: blake2b256(blockId || playerSecret)[0] % 2
           c. Determine winner (player_wins = rng_outcome == playerChoice)
           d. Build reveal tx with correct output (pay player or house)
           e. Submit via /wallet/transaction/send with rawInputs
        5. Handle failures: retry on block change, skip timed-out boxes

        MAT-416: Fix "bet transaction submitted but no after effect"
        """
        # ── Step 1: Check node sync ────────────────────────────────
        try:
            info = await self.client.get("/info")
        except httpx.HTTPError as e:
            logger.warning("node_unreachable", error=str(e))
            return

        full_height = info.get("fullHeight")
        if full_height is None:
            logger.info(
                "node_not_synced",
                headers_height=info.get("headersHeight"),
                message="UTXO state not downloaded, skipping bet scan",
            )
            return

        current_height = int(full_height)
        logger.debug("node_synced", height=current_height)

        # ── Step 2: Get best block header ID (RNG seed) ────────────
        try:
            # /blocks/lastHeaders/1 returns a list of header IDs
            header_ids = await self.client.get("/blocks/lastHeaders/1")
            if isinstance(header_ids, list) and len(header_ids) > 0:
                best_header_id = header_ids[0]
            elif isinstance(header_ids, dict) and "id" in header_ids:
                best_header_id = header_ids["id"]
            else:
                logger.warning("no_block_headers", response=header_ids)
                return
        except httpx.HTTPError as e:
            logger.warning("failed_get_headers", error=str(e))
            return

        # The RNG uses CONTEXT.preHeader.parentId.
        # When the reveal tx is included in the next block,
        # preHeader.parentId = current best header ID.
        # If a new block arrives before inclusion, the tx may fail
        # and we retry on the next loop iteration.
        rng_block_hash = best_header_id
        logger.debug("rng_seed_set", block_id=rng_block_hash[:16] + "...")

        # ── Step 3: Find PendingBet boxes ──────────────────────────
        # Strategy 1: byErgoTree scan (requires node extraIndex=true)
        # Strategy 2: Track box IDs off-chain in pending_boxes.json
        # Strategy 3: Look up tx outputs from known bet tx IDs
        boxes = await self._scan_pending_boxes()

        if not boxes:
            logger.debug("no_pending_boxes")
            return

        logger.info("pending_boxes_found", count=len(boxes))

        # ── Step 4: Process each PendingBet box ────────────────────
        for box in boxes:
            box_id = box.get("boxId", "")
            value = int(box.get("value", 0))
            registers = box.get("additionalRegisters", {})
            bet_tx_id = box.get("_betTxId", "")  # Original bet tx ID for backend matching

            if not box_id or value == 0:
                logger.warning("invalid_box", box_id=box_id, value=value)
                continue

            try:
                result = await self._reveal_bet(
                    box_id=box_id,
                    value=value,
                    registers=registers,
                    rng_block_hash=rng_block_hash,
                    current_height=current_height,
                )

                if result.get("success"):
                    result["boxId"] = box_id  # Attach box ID for backend notification
                    result["betTxId"] = bet_tx_id  # Original bet tx ID for precise matching
                    self.health_server.increment_bets_processed()
                    # Clean up tracked box
                    self._remove_pending_box(box_id)
                    # Clean up tracked bet tx ID
                    if bet_tx_id:
                        self._remove_pending_tx(bet_tx_id)
                    logger.info(
                        "bet_revealed",
                        box_id=box_id[:16] + "...",
                        tx_id=result.get("txId", "")[:16] + "...",
                        player_wins=result.get("player_wins"),
                        payout=result.get("payout_amount"),
                    )
                    # Notify backend to update bet history + fire WebSocket events (MAT-419)
                    await self._notify_backend(result, box, current_height)
                else:
                    logger.warning(
                        "reveal_failed",
                        box_id=box_id[:16] + "...",
                        reason=result.get("message", "unknown"),
                    )

            except Exception as e:
                logger.error(
                    "reveal_error",
                    box_id=box_id[:16] + "...",
                    error=str(e),
                    exc_info=True,
                )

    async def _scan_pending_boxes(self) -> list:
        """
        Find PendingBet boxes using multiple strategies.

        Strategy 1: /blockchain/box/unspent/byErgoTree (requires node extraIndex=true)
        Strategy 2: Load tracked box IDs from pending_boxes.json and verify each
        Strategy 3: Look up tx outputs from tracked bet tx IDs

        Returns list of box dicts from the node, or empty list.
        """
        ergo_tree_hex = (
            "19d8010c04000200020104000404040005c20105640400040004000564d805d601"
            "cdeee4c6a7040ed602e4c6a7090ed603e4c6a70704d604cdeee4c6a7050ed605c1"
            "a7eb02ea02ea027201d193cbb3720283010295937203730073017302e4c6a7060ed"
            "195939e7eb2cbb3db6902db6503fe72027303000473047203d801d606b2a5730500e"
            "d93c27206d0720492c172069d9c720573067307d801d606b2a5730800ed93c27206"
            "d0720192c172067205ea02ea02ea02d192a3e4c6a708047204d193c2b2a5730900d"
            "07204d192c1b2a5730a009972059d7205730b"
        )

        # ── Strategy 1: byErgoTree scan ────────────────────────────
        try:
            boxes = await self.client.post(
                "/blockchain/box/unspent/byErgoTree",
                ergo_tree_hex,
            )
            if isinstance(boxes, list) and len(boxes) > 0:
                logger.info("scan_strategy_ergotree", count=len(boxes))
                return boxes
        except httpx.HTTPStatusError as e:
            if e.response.status_code not in (404, 500):
                logger.debug("ergotree_scan_failed", status=e.response.status_code)
        except Exception:
            pass

        # ── Strategy 2: Tracked box IDs ────────────────────────────
        tracked = self._load_pending_boxes()
        if tracked:
            valid_boxes = []
            for box_id in tracked:
                try:
                    box = await self.client.get(f"/blockchain/box/{box_id}")
                    if box and box.get("boxId"):
                        valid_boxes.append(box)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        # Box already spent (reveal or refund happened)
                        logger.debug("box_already_spent", box_id=box_id[:16] + "...")
                        continue
            if valid_boxes:
                logger.info("scan_strategy_tracked", count=len(valid_boxes))
                return valid_boxes

        # ── Strategy 3: Look up tx outputs from tracked bet tx IDs ──
        tracked_txs = self._load_pending_tx_ids()
        if tracked_txs:
            valid_boxes = []
            for tx_id in tracked_txs:
                try:
                    tx = await self.client.get(f"/transactions/{tx_id}")
                    outputs = tx.get("outputs", [])
                    for out in outputs:
                        if out.get("ergoTree") == ergo_tree_hex:
                            box_id = out.get("boxId", "")
                            if box_id:
                                # Verify it's still unspent
                                try:
                                    box = await self.client.get(f"/blockchain/box/{box_id}")
                                    if box and box.get("boxId"):
                                        box["_betTxId"] = tx_id  # Tag with original bet tx
                                        valid_boxes.append(box)
                                except httpx.HTTPStatusError as e:
                                    if e.response.status_code == 404:
                                        continue
                except httpx.HTTPStatusError:
                    continue
            if valid_boxes:
                logger.info("scan_strategy_tx_outputs", count=len(valid_boxes))
                return valid_boxes

        return []

    def _load_pending_boxes(self) -> list:
        """Load tracked PendingBet box IDs from pending_boxes.json."""
        path = DATA_DIR / "pending_boxes.json"
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text())
            return data.get("box_ids", [])
        except Exception as e:
            logger.warning("failed_load_pending_boxes", error=str(e))
            return []

    def _save_pending_box(self, box_id: str):
        """Track a PendingBet box ID in pending_boxes.json."""
        path = DATA_DIR / "pending_boxes.json"
        tracked = self._load_pending_boxes()
        if box_id not in tracked:
            tracked.append(box_id)
            path.write_text(json.dumps({"box_ids": tracked}))
            logger.info("tracked_box", box_id=box_id[:16] + "...")

    def _remove_pending_box(self, box_id: str):
        """Remove a resolved box from tracking."""
        path = DATA_DIR / "pending_boxes.json"
        tracked = self._load_pending_boxes()
        if box_id in tracked:
            tracked.remove(box_id)
            path.write_text(json.dumps({"box_ids": tracked}))

    def _load_pending_tx_ids(self) -> list:
        """Load tracked bet transaction IDs from pending_txs.json."""
        path = DATA_DIR / "pending_txs.json"
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text())
            return data.get("tx_ids", [])
        except Exception:
            return []

    def _save_pending_tx(self, tx_id: str):
        """Track a bet transaction ID for later box lookup."""
        path = DATA_DIR / "pending_txs.json"
        tracked = self._load_pending_tx_ids()
        if tx_id not in tracked:
            tracked.append(tx_id)
            path.write_text(json.dumps({"tx_ids": tracked}))
            logger.info("tracked_tx", tx_id=tx_id[:16] + "...")

    def _remove_pending_tx(self, tx_id: str):
        """Remove a resolved tx from tracking."""
        path = DATA_DIR / "pending_txs.json"
        tracked = self._load_pending_tx_ids()
        if tx_id in tracked:
            tracked.remove(tx_id)
            path.write_text(json.dumps({"tx_ids": tracked}))

    async def _reveal_bet(
        self,
        box_id: str,
        value: int,
        registers: dict,
        rng_block_hash: str,
        current_height: int,
    ) -> dict:
        """
        Reveal a single PendingBet box.

        1. Decode registers R4-R9
        2. Verify commitment
        3. Compute RNG
        4. Build and submit reveal tx

        Returns dict with success, txId, player_wins, payout_amount, message.
        """
        # ── Decode registers ───────────────────────────────────────
        # Node returns registers as {"R4": {"serializedValue": "...", "sigmaType": "..."}, ...}
        def get_reg_bytes(reg_name: str) -> str:
            reg = registers.get(reg_name, {})
            sv = reg.get("serializedValue", "")
            if not sv:
                raise ValueError(f"Missing register {reg_name}")
            # Remove leading type byte (0x04 for SByte coll elements) per decode_coll_byte_from_node
            raw = bytes.fromhex(sv)
            if len(raw) < 2:
                raise ValueError(f"Register {reg_name} too short: {sv}")
            return raw[1:].hex()

        def get_reg_int(reg_name: str) -> int:
            reg = registers.get(reg_name, {})
            sv = reg.get("serializedValue", "")
            if not sv:
                raise ValueError(f"Missing register {reg_name}")
            # Decode VLQ integer from node serialization
            raw = bytes.fromhex(sv)
            if not raw:
                return 0
            # VLQ with sign: bit 6 of last byte is sign
            value = 0
            for b in raw:
                value = (value << 7) | (b & 0x7F)
            negative = bool(raw[-1] & 0x40)
            return -value if negative else value

        house_pubkey_hex = get_reg_bytes("R4")
        player_pubkey_hex = get_reg_bytes("R5")
        commitment_hex = get_reg_bytes("R6")
        player_choice = get_reg_int("R7")
        timeout_height = get_reg_int("R8")
        player_secret_hex = get_reg_bytes("R9")

        logger.debug(
            "box_decoded",
            box_id=box_id[:16] + "...",
            value=value,
            choice=player_choice,
            timeout=timeout_height,
        )

        # ── Check timeout ──────────────────────────────────────────
        if current_height >= timeout_height:
            logger.info(
                "box_timed_out",
                box_id=box_id[:16] + "...",
                timeout=timeout_height,
                current=current_height,
                message="Skipping — player must claim refund",
            )
            return {
                "success": False,
                "txId": "",
                "player_wins": None,
                "payout_amount": "0",
                "message": f"Box timed out (timeout={timeout_height}, current={current_height}). Player must claim refund.",
            }

        # ── Verify commitment ──────────────────────────────────────
        # commitment = blake2b256(secret || choice_byte)
        import hashlib
        secret_data = bytes.fromhex(player_secret_hex) + bytes([player_choice])
        computed_hash = hashlib.blake2b(secret_data, digest_size=32).digest().hex()

        if computed_hash != commitment_hex:
            logger.error(
                "commitment_mismatch",
                box_id=box_id[:16] + "...",
                computed=computed_hash[:16] + "...",
                expected=commitment_hex[:16] + "...",
            )
            return {
                "success": False,
                "txId": "",
                "player_wins": None,
                "payout_amount": "0",
                "message": f"Commitment mismatch: computed {computed_hash[:16]} != stored {commitment_hex[:16]}",
            }

        # ── Compute RNG ────────────────────────────────────────────
        # blake2b256(blockId_raw_bytes || playerSecret_raw_bytes)[0] % 2
        block_hash_bytes = bytes.fromhex(rng_block_hash)
        secret_bytes = bytes.fromhex(player_secret_hex)
        rng_hash = hashlib.blake2b(block_hash_bytes + secret_bytes, digest_size=32).digest()
        rng_outcome = rng_hash[0] % 2  # 0 or 1

        # playerWins = (flipResult == playerChoice)
        player_wins = (rng_outcome == player_choice)

        logger.info(
            "rng_computed",
            box_id=box_id[:16] + "...",
            rng_outcome=rng_outcome,
            player_choice=player_choice,
            player_wins=player_wins,
        )

        # ── Derive addresses from pubkeys ──────────────────────────
        # For P2PK addresses, we need to construct them from the pubkey.
        # The simplest approach: use /wallet/transaction/send with rawInputs
        # and specify the output address. The house wallet signs.
        # We need the player's P2PK address — we can derive it or store it.
        #
        # Actually, the contract checks OUTPUTS(0).propositionBytes == playerProp.propBytes
        # which means the output must be a P2PK to the player's pubkey.
        # The node's /wallet/transaction/send handles this if we provide
        # the correct P2PK address.
        #
        # Derive P2PK address from pubkey bytes:
        player_address = self._pubkey_to_p2pk(player_pubkey_hex, testnet=True)
        house_address = self._pubkey_to_p2pk(house_pubkey_hex, testnet=True)

        # ── Build and submit reveal tx ─────────────────────────────
        if player_wins:
            # Player wins: 1.94x payout (betAmount * 97 / 50)
            payout = value * 97 // 50
            recipient = player_address
        else:
            # House wins: gets full bet amount back
            payout = value
            recipient = house_address

        fee = 1_000_000  # 0.001 ERG

        tx_request = {
            "requests": [{
                "address": recipient,
                "value": str(payout),
                "creationHeight": current_height,
            }],
            "rawInputs": [box_id],
            "fee": str(fee),
        }

        logger.info(
            "submitting_reveal_tx",
            box_id=box_id[:16] + "...",
            player_wins=player_wins,
            payout=payout,
            recipient=recipient[:20] + "...",
        )

        try:
            result = await self.client.post("/wallet/transaction/send", tx_request)
            tx_id = result.get("id", "")

            return {
                "success": True,
                "txId": tx_id,
                "player_wins": player_wins,
                "payout_amount": str(payout),
                "message": f"Reveal tx submitted: {tx_id}",
            }
        except httpx.HTTPStatusError as e:
            error_body = ""
            try:
                error_body = e.response.text
            except Exception:
                pass
            return {
                "success": False,
                "txId": "",
                "player_wins": player_wins,
                "payout_amount": "0",
                "message": f"Reveal tx failed (HTTP {e.response.status_code}): {error_body}",
            }

    async def _notify_backend(self, result: dict, box: dict, current_height: int):
        """
        Report bet resolution to the DuckPools backend API (MAT-419).

        POSTs to /bot/resolve-bet so the backend can:
        1. Update the in-memory bet record (pending -> win/loss)
        2. Fire WebSocket events (bet_revealed + bet_settled) to the frontend
        3. Untrack the bet tx ID

        This is non-blocking: failures are logged but don't affect the reveal.
        """
        if not BACKEND_URL:
            return

        # Derive player address from R5 register (same logic as _reveal_bet)
        player_address = ""
        try:
            registers = box.get("additionalRegisters", {})
            r5 = registers.get("R5", {})
            sv = r5.get("serializedValue", "")
            if sv and len(sv) > 4:
                # Decode Coll[Byte]: strip leading type bytes (0x0e Coll, 0x01 SByte)
                raw = bytes.fromhex(sv)
                # Same decoding as get_reg_bytes in _reveal_bet
                if len(raw) >= 2:
                    player_pubkey_hex = raw[1:].hex()
                    player_address = self._pubkey_to_p2pk(player_pubkey_hex, testnet=True)
        except Exception:
            pass

        payload = {
            "boxId": result.get("boxId", ""),
            "txId": result.get("betTxId", ""),  # Original place-bet tx ID for backend matching
            "playerWins": result.get("player_wins"),
            "payoutAmount": result.get("payout_amount", "0"),
            "playerAddress": player_address,
            "betAmount": str(box.get("value", 0)),
            "blockHeight": current_height,
            "revealTxId": result.get("txId", ""),  # The reveal transaction ID
        }

        headers = {"Content-Type": "application/json"}
        if BOT_API_KEY:
            headers["X-Api-Key"] = BOT_API_KEY

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{BACKEND_URL}/bot/resolve-bet",
                    json=payload,
                    headers=headers,
                )
                if resp.status_code == 200:
                    logger.info(
                        "backend_notified",
                        box_id=result.get("boxId", "")[:16] + "...",
                        status=resp.status_code,
                    )
                else:
                    logger.warning(
                        "backend_notify_failed",
                        box_id=result.get("boxId", "")[:16] + "...",
                        status=resp.status_code,
                        body=resp.text[:200],
                    )
        except Exception as e:
            logger.warning(
                "backend_notify_error",
                box_id=result.get("boxId", "")[:16] + "...",
                error=str(e),
            )

    @staticmethod
    def _pubkey_to_p2pk(pubkey_hex: str, testnet: bool = True) -> str:
        """
        Convert a 33-byte compressed public key to an Ergo P2PK address.

        Ergo P2PK address = Base58Check(0x01 || pubkey || checksum)
        where checksum = blake2b256(payload)[:4]
        Network prefix: 0x10 for testnet, 0x00 for mainnet
        """
        import hashlib

        # Build payload: network_prefix | address_type | pubkey
        network_byte = 0x10 if testnet else 0x00
        addr_type = 0x01  # P2PK
        first_byte = network_byte | addr_type
        pubkey_bytes = bytes.fromhex(pubkey_hex)

        payload = bytes([first_byte]) + pubkey_bytes
        checksum = hashlib.blake2b(payload, digest_size=32).digest()[:4]
        full = payload + checksum

        # Base58 encode
        ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        num = int.from_bytes(full, byteorder="big")
        result = []
        while num > 0:
            num, rem = divmod(num, 58)
            result.append(ALPHABET[rem])
        # Handle leading zeros
        for byte in full:
            if byte == 0:
                result.append(ALPHABET[0])
            else:
                break
        return "".join(reversed(result))


# ─── Main ────────────────────────────────────────────────────────────────

async def main():
    """Main entry point."""
    bot = OffChainBot(
        node_url=NODE_URL,
        api_key=NODE_API_KEY,
        heartbeat_file=HEARTBEAT_FILE,
        heartbeat_interval_seconds=HEARTBEAT_INTERVAL_SECONDS,
        health_server_port=HEALTH_SERVER_PORT,
    )

    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt")
    except Exception as e:
        logger.error(
            "bot_fatal_error",
            error=str(e),
            exc_info=True
        )
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())