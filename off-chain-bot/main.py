"""
DuckPools Off-Chain Bot - Main Bot Script

Monitors PendingBet boxes, reveals secrets, calculates RNG, and settles bets.

Flow:
  1. Poll /game/bets/pending-with-timeout to find bets needing reveal
  2. For each bet in the reveal window (timeoutHeight - 30 to timeoutHeight):
     a. Verify the PendingBetBox is still unspent on-chain
     b. Call /game/bot/build-reveal-tx to build and submit the reveal tx
  3. Report metrics via health server

Features:
- Retry logic with exponential backoff for Ergo node API calls
- Graceful shutdown on SIGINT/SIGTERM
- Heartbeat file for liveness monitoring
- Structured logging

MAT-394: Implement actual bet processing logic
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
NODE_URL = os.getenv("NODE_URL", "http://localhost:9052")
NODE_API_KEY = os.getenv("NODE_API_KEY", "")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
HEARTBEAT_FILE = os.getenv("HEARTBEAT_FILE", "/tmp/off-chain-bot-heartbeat.txt")
HEARTBEAT_INTERVAL_SECONDS = int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "30"))
HEALTH_SERVER_PORT = int(os.getenv("HEALTH_SERVER_PORT", "8001"))
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))

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


# ─── Backend API Client ──────────────────────────────────────────────────

class BackendClient:
    """HTTP client for DuckPools backend API."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    async def start(self):
        """Create HTTP client."""
        self._client = httpx.AsyncClient(timeout=30.0)
        logger.info("backend_client_started", url=self.base_url)

    async def stop(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_pending_bets(self) -> dict:
        """Fetch pending bets with timeout info from backend."""
        resp = await self._client.get(f"{self.base_url}/game/bets/pending-with-timeout")
        resp.raise_for_status()
        return resp.json()

    async def reveal_bet(self, box_id: str) -> dict:
        """Submit a reveal request for a specific bet box."""
        resp = await self._client.post(
            f"{self.base_url}/game/bot/build-reveal-tx",
            json={"box_id": box_id},
        )
        resp.raise_for_status()
        return resp.json()


# ─── Bot Logic ───────────────────────────────────────────────────────────

class OffChainBot:
    """Main off-chain bot class."""

    def __init__(
        self,
        node_url: str,
        api_key: str,
        backend_url: str,
        heartbeat_file: str,
        heartbeat_interval_seconds: int = 30,
        health_server_port: int = 8001,
        poll_interval_seconds: int = 10,
    ):
        self.node_url = node_url
        self.api_key = api_key
        self.backend_url = backend_url
        self.shutdown_manager = ShutdownManager()
        self.heartbeat_manager = HeartbeatManager(heartbeat_file)
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self.health_server = HealthServer(port=health_server_port)
        self.poll_interval = poll_interval_seconds
        self.backend: Optional[BackendClient] = None

    async def run(self):
        """Run the off-chain bot main loop."""
        logger.info("bot_starting", node_url=self.node_url, backend_url=self.backend_url)

        # Setup graceful shutdown
        self.shutdown_manager.setup_signal_handlers()

        # Start health server
        await self.health_server.start()

        # Create backend client
        self.backend = BackendClient(self.backend_url)
        await self.backend.start()

        # Start heartbeat
        await self.heartbeat_manager.start(self.heartbeat_interval_seconds)

        try:
            await self.main_loop()
        finally:
            # Stop heartbeat
            await self.heartbeat_manager.stop()

            # Stop backend client
            await self.backend.stop()

            # Stop health server
            await self.health_server.stop()

            # Restore signal handlers
            self.shutdown_manager.restore_signal_handlers()

        logger.info("bot_stopped")

    async def main_loop(self):
        """Main bot processing loop."""
        logger.info("main_loop_started", poll_interval=self.poll_interval)

        while not self.shutdown_manager.is_shutdown_requested():
            try:
                await self.process_bets()

                # Check for shutdown before sleeping
                if self.shutdown_manager.is_shutdown_requested():
                    logger.info("main_loop_shutdown_requested")
                    break

                # Sleep before next iteration
                await asyncio.sleep(self.poll_interval)

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
                await asyncio.sleep(self.poll_interval)

    async def process_bets(self):
        """
        Process pending bets that are within the reveal window.

        Flow:
        1. Fetch all pending bets from backend
        2. Filter to bets within the reveal window (urgency: normal or critical)
        3. For each bet, attempt to reveal via /bot/build-reveal-tx
        4. Log results and update health server metrics
        """
        if not self.backend:
            return

        try:
            pending_data = await self.backend.get_pending_bets()
        except httpx.HTTPError as e:
            logger.error("failed_to_fetch_pending_bets", error=str(e))
            return

        bets = pending_data.get("bets", [])
        total_pending = pending_data.get("totalPending", 0)

        if total_pending == 0:
            logger.debug("no_pending_bets")
            return

        logger.info(
            "pending_bets_found",
            total=total_pending,
            expired=sum(1 for b in bets if b.get("isExpired")),
            critical=sum(1 for b in bets if b.get("urgency") == "critical"),
            normal=sum(1 for b in bets if b.get("urgency") == "normal"),
        )

        for bet in bets:
            if self.shutdown_manager.is_shutdown_requested():
                break

            urgency = bet.get("urgency", "normal")
            bet_id = bet.get("betId", "unknown")
            box_id = bet.get("boxId", "")

            # Only process bets that are in the reveal window or expired
            # "normal" = not yet in reveal window (more than 30 blocks before timeout)
            # "warning" = approaching reveal window (within 30 blocks)
            # "critical" = in reveal window (within 10 blocks of timeout)
            # "expired" = past timeout (player should refund, not house reveal)
            if urgency == "expired":
                logger.info(
                    "bet_expired_skipping",
                    bet_id=bet_id,
                    message="Bet expired — player must use refund path"
                )
                continue

            if urgency == "normal":
                logger.debug(
                    "bet_not_yet_revealable",
                    bet_id=bet_id,
                    blocks_remaining=bet.get("blocksRemaining", "?"),
                )
                continue

            if not box_id:
                logger.warning(
                    "bet_missing_box_id",
                    bet_id=bet_id,
                    message="Cannot reveal bet without on-chain box ID"
                )
                continue

            # Attempt to reveal the bet
            try:
                logger.info(
                    "attempting_reveal",
                    bet_id=bet_id,
                    box_id=box_id,
                    urgency=urgency,
                )

                result = await self.backend.reveal_bet(box_id)

                if result.get("success"):
                    self.health_server.increment_bets_processed()
                    logger.info(
                        "reveal_success",
                        bet_id=bet_id,
                        tx_id=result.get("tx_id", ""),
                        player_wins=result.get("player_wins", False),
                        payout=result.get("payout_amount", "0"),
                        rng_value=result.get("rng_value", "?"),
                    )
                else:
                    logger.warning(
                        "reveal_failed",
                        bet_id=bet_id,
                        message=result.get("message", "Unknown error"),
                    )

            except httpx.HTTPStatusError as e:
                # 400 = bet not ready (reveal window not open, expired, etc.)
                # 404 = bet not found
                # 410 = box already spent
                # These are expected and should not be retried immediately
                if e.response.status_code in (400, 404, 410):
                    try:
                        error_body = e.response.json()
                        detail = error_body.get("detail", str(e))
                    except Exception:
                        detail = str(e)
                    logger.warning(
                        "reveal_skipped",
                        bet_id=bet_id,
                        status_code=e.response.status_code,
                        detail=detail,
                    )
                else:
                    logger.error(
                        "reveal_error",
                        bet_id=bet_id,
                        status_code=e.response.status_code,
                        error=str(e),
                    )
            except httpx.HTTPError as e:
                logger.error(
                    "reveal_network_error",
                    bet_id=bet_id,
                    error=str(e),
                )
            except Exception as e:
                logger.error(
                    "reveal_unexpected_error",
                    bet_id=bet_id,
                    error=str(e),
                    exc_info=True,
                )


# ─── Main ────────────────────────────────────────────────────────────────

async def main():
    """Main entry point."""
    bot = OffChainBot(
        node_url=NODE_URL,
        api_key=NODE_API_KEY,
        backend_url=BACKEND_URL,
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
            exc_info=True
        )
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
