"""
DuckPools Off-Chain Bot - Main Bot Script

Monitors PendingBet boxes, verifies commitments, computes RNG from block
hash, submits reveal transactions, and updates bet history.

Architecture:
  main_loop (5s poll)
    -> poll_pending_boxes (UTXO scan by ErgoTree)
    -> for each box:
       1. decode_pending_bet_box (registers R4-R9)
       2. verify_commitment (blake2b256(secret||choice) == R6)
       3. get_current_block_header (for parentId entropy)
       4. compute_flip_outcome (blake2b256(parentId||secret)[0] % 2)
       5. build_reveal_transaction
       6. submit to node /wallet/transaction/send
       7. update bet history via backend API

Features:
- Retry logic with exponential backoff for Ergo node API calls
- Graceful shutdown on SIGINT/SIGTERM
- Heartbeat file for liveness monitoring
- Structured logging
- Deduplication via processed box tracking

MAT-182: Structured logging and error recovery
MAT-223: Add retry logic and graceful shutdown
MAT-419: Implement off-chain bot reveal logic
"""

import asyncio
import hashlib
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Set

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from logger import configure_logging, get_logger
from health_server import HealthServer
from ergo_box_decoder import PendingBetBox, decode_pending_bet_boxes
from commitment import verify_commitment
from rng import compute_flip_outcome
from tx_builder import build_reveal_request
from backend_client import BackendClient

# Configure structured logging
configure_logging()
logger = get_logger(__name__)

# ─── Configuration ─────────────────────────────────────────────────────────

# Load from environment variables
NODE_URL = os.getenv("NODE_URL", "http://localhost:9052")
NODE_API_KEY = os.getenv("NODE_API_KEY", "")
HEARTBEAT_FILE = os.getenv("HEARTBEAT_FILE", "/tmp/off-chain-bot-heartbeat.txt")
HEARTBEAT_INTERVAL_SECONDS = int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "30"))
HEALTH_SERVER_PORT = int(os.getenv("HEALTH_SERVER_PORT", "8001"))
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
HOUSE_ADDRESS = os.getenv("HOUSE_ADDRESS", "")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "5"))

# Compiled contract ErgoTree hex (from smart-contracts/coinflip_deployed.json)
COINFLIP_ERGO_TREE = os.getenv(
    "COINFLIP_ERGO_TREE",
    "19d8010c04000200020104000404040005c20105640400040004000564d805d601cdeee4c6a7040ed602e4c6a7090ed603e4c6a70704d604cdeee4c6a7050ed605c1a7eb02ea02ea027201d193cbb3720283010295937203730073017302e4c6a7060ed195939e7eb2cbb3db6902db6503fe72027303000473047203d801d606b2a5730500ed93c27206d0720492c172069d9c720573067307d801d606b2a5730800ed93c27206d0720192c172067205ea02ea02ea02d192a3e4c6a708047204d193c2b2a5730900d07204d192c1b2a5730a009972059d7205730b",
)

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
            message="Shutdown requested, will finish processing current bet",
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
            interval_seconds=interval_seconds,
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
                    exc_info=True,
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
        self.node_url = node_url.rstrip("/")
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
    """
    Main off-chain bot for DuckPools.

    Polls PendingBet boxes by ErgoTree, verifies commitments,
    computes RNG from block hash, submits reveal transactions,
    and updates bet history via the backend API.
    """

    def __init__(
        self,
        node_url: str,
        api_key: str,
        backend_url: str,
        house_address: str,
        ergo_tree_hex: str,
        heartbeat_file: str,
        heartbeat_interval_seconds: int = 30,
        health_server_port: int = 8001,
        poll_interval_seconds: int = 5,
    ):
        self.node_url = node_url
        self.api_key = api_key
        self.backend_url = backend_url
        self.house_address = house_address
        self.ergo_tree_hex = ergo_tree_hex
        self.poll_interval_seconds = poll_interval_seconds

        self.shutdown_manager = ShutdownManager()
        self.heartbeat_manager = HeartbeatManager(heartbeat_file)
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self.client: Optional[ErgoNodeClient] = None
        self.backend_client: Optional[BackendClient] = None
        self.health_server = HealthServer(port=health_server_port)

        # Track already-processed box IDs to avoid double-settlement
        self._processed_boxes: Set[str] = set()
        # Track boxes we've seen but couldn't process (transient errors)
        self._failed_boxes: Dict[str, int] = {}  # box_id -> failure count
        self._max_failures = 5

    async def run(self):
        """Run the off-chain bot main loop."""
        logger.info(
            "bot_starting",
            node_url=self.node_url,
            backend_url=self.backend_url,
            house_address=self.house_address[:16] + "..." if self.house_address else "NOT_SET",
            ergo_tree=self.ergo_tree_hex[:32] + "...",
        )

        if not self.house_address:
            logger.error(
                "house_address_not_configured",
                message="HOUSE_ADDRESS env var required for reveal txs",
            )

        # Setup graceful shutdown
        self.shutdown_manager.setup_signal_handlers()

        # Start health server
        await self.health_server.start()

        # Create Ergo node client
        async with ErgoNodeClient(self.node_url, self.api_key) as client:
            self.client = client

            # Create backend client
            async with BackendClient(self.backend_url) as backend:
                self.backend_client = backend

                # Start heartbeat
                await self.heartbeat_manager.start(
                    self.heartbeat_interval_seconds
                )

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
                await self.process_bets()

                # Check for shutdown before sleeping
                if self.shutdown_manager.is_shutdown_requested():
                    logger.info("main_loop_shutdown_requested")
                    break

                # Sleep before next iteration
                await asyncio.sleep(self.poll_interval_seconds)

            except asyncio.CancelledError:
                logger.info("main_loop_cancelled")
                break
            except Exception as e:
                logger.error(
                    "main_loop_error",
                    error=str(e),
                    exc_info=True,
                )
                # Sleep briefly before retrying to avoid tight error loop
                await asyncio.sleep(self.poll_interval_seconds)

    async def poll_pending_boxes(self) -> list:
        """
        Poll the Ergo node for unspent boxes matching the coinflip contract ErgoTree.

        Uses /utxo/byErgoTree/{ergoTreeHex} to find all PendingBet boxes
        that haven't been spent yet.

        Returns:
            List of raw box dicts from the node API
        """
        try:
            # Encode the ergo tree hex for the URL (already hex-encoded)
            ergo_tree_encoded = self.ergo_tree_hex

            boxes = await self.client.get(
                f"/utxo/byErgoTree/{ergo_tree_encoded}"
            )

            if isinstance(boxes, list):
                return boxes

            logger.warning(
                "unexpected_utxo_response_type",
                response_type=type(boxes).__name__,
            )
            return []

        except httpx.HTTPError as e:
            logger.error("poll_boxes_error", error=str(e))
            return []

    async def get_block_header_at(self, height: int) -> Optional[dict]:
        """
        Get a block header at a specific height.

        Args:
            height: Block height

        Returns:
            Block header dict with 'header' field, or None
        """
        try:
            headers = await self.client.get(f"/blocks/at/{height}")
            if isinstance(headers, list) and len(headers) > 0:
                return headers[0]
            return None
        except httpx.HTTPError as e:
            logger.error("get_block_header_error", height=height, error=str(e))
            return None

    async def get_current_tip_header(self) -> Optional[dict]:
        """
        Get the current best block header.

        The parentId of the tip block becomes the preHeader.parentId
        used by the contract for RNG (CONTEXT.preHeader.parentId).

        Returns:
            Block header dict, or None
        """
        try:
            info = await self.client.get("/info")
            full_height = info.get("fullHeight", 0)

            if full_height == 0:
                logger.warning("node_full_height_zero")
                return None

            # Get the header at the current height
            # preHeader.parentId in the reveal tx will be this block's ID
            return await self.get_block_header_at(full_height)

        except httpx.HTTPError as e:
            logger.error("get_tip_header_error", error=str(e))
            return None

    async def submit_reveal_transaction(self, tx_request: dict) -> Optional[str]:
        """
        Submit a reveal transaction via the node wallet.

        Uses /wallet/transaction/send which:
        1. Adds the house wallet's UTXOs as additional inputs
        2. Signs the transaction with the house key
        3. Broadcasts to the network

        Args:
            tx_request: Transaction request dict

        Returns:
            Transaction ID if successful, None otherwise
        """
        try:
            result = await self.client.post(
                "/wallet/transaction/send",
                data=tx_request,
            )
            tx_id = result.get("id", "")
            if tx_id:
                logger.info("reveal_tx_submitted", tx_id=tx_id)
                return tx_id
            else:
                logger.warning("reveal_tx_no_id", result=result)
                return None
        except httpx.HTTPStatusError as e:
            body = e.response.text[:500] if e.response else ""
            logger.error(
                "reveal_tx_submit_error",
                status=e.response.status_code if e.response else 0,
                body=body,
            )
            return None
        except httpx.HTTPError as e:
            logger.error("reveal_tx_connection_error", error=str(e))
            return None

    async def process_single_bet(
        self, bet_box: PendingBetBox, current_height: int
    ) -> bool:
        """
        Process a single PendingBet box through the full reveal pipeline.

        Steps:
        1. Skip if already processed or timed out
        2. Verify commitment hash
        3. Get block header for RNG entropy
        4. Compute flip outcome
        5. Build reveal transaction
        6. Submit transaction
        7. Update backend bet history

        Args:
            bet_box: Decoded PendingBet box
            current_height: Current block height

        Returns:
            True if bet was successfully processed
        """
        box_id = bet_box.box_id

        # Skip already-processed boxes
        if box_id in self._processed_boxes:
            logger.debug("box_already_processed", box_id=box_id[:16] + "...")
            return False

        # Skip boxes past timeout — player should use refund path
        if current_height >= bet_box.timeout_height:
            logger.info(
                "box_past_timeout",
                box_id=box_id[:16] + "...",
                timeout_height=bet_box.timeout_height,
                current_height=current_height,
            )
            self._processed_boxes.add(box_id)
            return False

        # Step 1: Verify commitment
        commitment_ok, commitment_msg = verify_commitment(
            secret_bytes=bet_box.player_secret,
            choice=bet_box.player_choice,
            commitment_hash=bet_box.commitment_hash,
        )

        if not commitment_ok:
            logger.error(
                "commitment_verification_failed",
                box_id=box_id[:16] + "...",
                reason=commitment_msg,
            )
            # Don't retry — commitment mismatch is a permanent error
            self._processed_boxes.add(box_id)
            return False

        # Step 2: Get block header for RNG entropy
        header = await self.get_current_tip_header()
        if not header:
            logger.error("no_block_header_for_rng")
            return False  # Transient — will retry

        parent_block_id_hex = header.get("header", {}).get("id", "")
        if not parent_block_id_hex:
            logger.error("block_header_missing_id", header=header)
            return False

        parent_block_id = bytes.fromhex(parent_block_id_hex)

        # Step 3: Compute flip outcome
        try:
            flip_result, player_wins, outcome_str = compute_flip_outcome(
                parent_block_id=parent_block_id,
                player_secret=bet_box.player_secret,
                player_choice=bet_box.player_choice,
            )
        except ValueError as e:
            logger.error("rng_computation_error", error=str(e))
            return False

        # Step 4: Build reveal transaction
        if not self.house_address:
            logger.error("cannot_build_tx_no_house_address")
            return False

        # Derive player address from their public key (R5)
        # For PoC, we'll use a simplified approach — in production,
        # the node wallet handles address derivation
        player_address = _derive_address_from_pk(bet_box.player_pk_bytes)

        tx_request = build_reveal_request(
            bet_box=bet_box,
            player_wins=player_wins,
            player_address=player_address,
            house_address=self.house_address,
        )

        if not tx_request:
            logger.error("tx_build_failed", box_id=box_id[:16] + "...")
            return False

        # Step 5: Submit reveal transaction
        tx_id = await self.submit_reveal_transaction(tx_request)
        if not tx_id:
            # Track failure for backoff
            failures = self._failed_boxes.get(box_id, 0) + 1
            self._failed_boxes[box_id] = failures
            if failures >= self._max_failures:
                logger.error(
                    "box_max_failures_reached",
                    box_id=box_id[:16] + "...",
                    failures=failures,
                )
                self._processed_boxes.add(box_id)
            return False

        # Step 6: Update backend bet history
        payout_nanoerg = (
            bet_box.value * 97 // 50 if player_wins else 0
        )

        if self.backend_client:
            await self.backend_client.update_bet_outcome(
                bet_id=box_id,  # Using box_id as bet_id for on-chain bets
                player_address=player_address,
                outcome="win" if player_wins else "loss",
                payout_nanoerg=payout_nanoerg,
                rng_result=outcome_str,
                player_choice=bet_box.player_choice_str,
                resolved_at_height=current_height,
                tx_id=tx_id,
                box_id=box_id,
            )

        # Mark as processed
        self._processed_boxes.add(box_id)
        self._failed_boxes.pop(box_id, None)

        # Increment health counter
        self.health_server.increment_bets_processed()

        logger.info(
            "bet_processed_successfully",
            box_id=box_id[:16] + "...",
            outcome=outcome_str,
            player_wins=player_wins,
            payout=payout_nanoerg / 1e9 if player_wins else 0,
            tx_id=tx_id[:16] + "...",
        )

        return True

    async def process_bets(self):
        """
        Main bet processing pipeline.

        1. Poll PendingBet boxes by ErgoTree
        2. Decode registers from each box
        3. Process each unprocessed box through the reveal pipeline
        """
        logger.debug("checking_for_pending_bets")

        # Get current height for timeout checks
        try:
            info = await self.client.get("/info")
            current_height = info.get("fullHeight", 0)
        except httpx.HTTPError:
            logger.warning("cannot_get_node_height")
            return

        # Step 1: Poll for PendingBet boxes
        raw_boxes = await self.poll_pending_boxes()

        if not raw_boxes:
            logger.debug("no_pending_boxes_found")
            return

        logger.info(
            "pending_boxes_found",
            count=len(raw_boxes),
            already_processed=sum(
                1 for b in raw_boxes
                if b.get("boxId", "") in self._processed_boxes
            ),
        )

        # Step 2: Decode boxes
        decoded_boxes = decode_pending_bet_boxes(raw_boxes)

        if not decoded_boxes:
            logger.debug("no_boxes_decoded_successfully")
            return

        # Step 3: Process each box
        processed_count = 0
        error_count = 0

        for bet_box in decoded_boxes:
            if self.shutdown_manager.is_shutdown_requested():
                logger.info("shutdown_during_processing")
                break

            try:
                success = await self.process_single_bet(
                    bet_box, current_height
                )
                if success:
                    processed_count += 1
                else:
                    error_count += 1
            except Exception as e:
                error_count += 1
                logger.error(
                    "process_single_bet_exception",
                    box_id=bet_box.box_id[:16] + "...",
                    error=str(e),
                    exc_info=True,
                )

        if processed_count > 0 or error_count > 0:
            logger.info(
                "processing_cycle_complete",
                processed=processed_count,
                errors=error_count,
                total_boxes=len(decoded_boxes),
                tracked_processed=len(self._processed_boxes),
            )

        # Periodic cleanup of old failed box entries (keep memory bounded)
        if len(self._failed_boxes) > 100:
            self._failed_boxes.clear()
            logger.debug("failed_boxes_cache_cleared")


# ─── Utility Functions ──────────────────────────────────────────────────

def _derive_address_from_pk(pk_bytes: bytes) -> str:
    """
    Derive an Ergo P2PK address from compressed public key bytes.

    Ergo P2PK address encoding:
    1. Construct proveDlog(groupElement) SigmaProp
    2. Serialize to ErgoTree bytes
    3. Base58-encode with network prefix (0x00 for mainnet, 0x10 for testnet)

    For PoC purposes, we return a placeholder. In production, use
    sigma-rust or ergo-lib to properly encode the address.

    Args:
        pk_bytes: 33-byte compressed public key

    Returns:
        Ergo address string
    """
    # In production, this would use ergo-lib:
    #   address = P2PKAddress(pk_bytes).to_base58()
    # For PoC, return a formatted placeholder
    logger.warning(
        "using_placeholder_address",
        message="Production: use ergo-lib for proper P2PK address derivation",
        pk=pk_bytes.hex()[:16] + "...",
    )
    # Return the PK hex as a recognizable placeholder
    return f"3{pk_bytes.hex()}"


# ─── Main ────────────────────────────────────────────────────────────────

async def main():
    """Main entry point."""
    bot = OffChainBot(
        node_url=NODE_URL,
        api_key=NODE_API_KEY,
        backend_url=BACKEND_URL,
        house_address=HOUSE_ADDRESS,
        ergo_tree_hex=COINFLIP_ERGO_TREE,
        heartbeat_file=HEARTBEAT_FILE,
        heartbeat_interval_seconds=HEARTBEAT_INTERVAL_SECONDS,
        health_server_port=HEALTH_SERVER_PORT,
        poll_interval_seconds=POLL_INTERVAL_SECONDS,
    )

    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt")
    except Exception as e:
        logger.error(
            "bot_fatal_error",
            error=str(e),
            exc_info=True,
        )
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
