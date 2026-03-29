"""
DuckPools Off-Chain Bot - Main Bot Script

Monitors PendingBet boxes, reveals secrets, calculates RNG, and settles bets.

MAT-355: Full reveal flow implementation
  - Polls /api/bot/pending-bets for commit boxes
  - Calls /api/bot/reveal-and-broadcast to settle bets
  - Skips boxes past timeout (player should refund)

Features:
- Retry logic with exponential backoff for Ergo node API calls
- Graceful shutdown on SIGINT/SIGTERM
- Heartbeat file for liveness monitoring
- Structured logging
"""

import asyncio
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
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
NODE_URL = os.getenv("NODE_URL", "http://localhost:9052")
NODE_API_KEY = os.getenv("NODE_API_KEY", "")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))  # seconds between polls
HEARTBEAT_FILE = os.getenv("HEARTBEAT_FILE", "/tmp/off-chain-bot-heartbeat.txt")
HEARTBEAT_INTERVAL_SECONDS = int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "30"))
HEALTH_SERVER_PORT = int(os.getenv("HEALTH_SERVER_PORT", "8001"))

# ─── Retry Configuration ────────────────────────────────────────────────────

RETRY_MAX_ATTEMPTS = 3
RETRY_MIN_WAIT_SECONDS = 1
RETRY_MAX_WAIT_SECONDS = 4


def is_retryable_error(exception: Exception) -> bool:
    """
    Check if an exception is retryable.
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
        """Start heartbeat file updates."""
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
        """Background task to update heartbeat file."""
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
                await asyncio.sleep(1)

    def update(self):
        """Update heartbeat file with current timestamp."""
        timestamp = datetime.now(timezone.utc).isoformat()
        self.heartbeat_file.write_text(timestamp)


# ─── Backend API Client ─────────────────────────────────────────────────

class BackendClient:
    """HTTP client for the DuckPools backend API."""

    def __init__(self, backend_url: str):
        self.backend_url = backend_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    async def start(self):
        timeout = httpx.Timeout(30.0)
        self._client = httpx.AsyncClient(timeout=timeout)
        logger.info("backend_client_started", url=self.backend_url)

    async def stop(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    @get_retry_decorator()
    async def get_pending_bets(self) -> list:
        """Fetch pending bets from the backend."""
        if not self._client:
            raise RuntimeError("Client not started")
        resp = await self._client.get(f"{self.backend_url}/api/bot/pending-bets")
        resp.raise_for_status()
        return resp.json()

    @get_retry_decorator()
    async def reveal_and_broadcast(self, box_id: str) -> dict:
        """Trigger reveal and broadcast for a commit box."""
        if not self._client:
            raise RuntimeError("Client not started")
        resp = await self._client.post(
            f"{self.backend_url}/api/bot/reveal-and-broadcast",
            json={"box_id": box_id},
        )
        resp.raise_for_status()
        return resp.json()


# ─── Bot Logic ───────────────────────────────────────────────────────────

class OffChainBot:
    """Main off-chain bot class."""

    def __init__(
        self,
        backend_url: str,
        heartbeat_file: str,
        heartbeat_interval_seconds: int = 30,
        health_server_port: int = 8001,
        poll_interval: int = 10,
    ):
        self.backend_url = backend_url
        self.shutdown_manager = ShutdownManager()
        self.heartbeat_manager = HeartbeatManager(heartbeat_file)
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self.health_server = HealthServer(port=health_server_port)
        self.poll_interval = poll_interval
        self.backend_client: Optional[BackendClient] = None

    async def run(self):
        """Run the off-chain bot main loop."""
        logger.info("bot_starting", backend_url=self.backend_url)

        # Setup graceful shutdown
        self.shutdown_manager.setup_signal_handlers()

        # Start health server
        await self.health_server.start()

        # Create backend client
        async with BackendClient(self.backend_url) as client:
            self.backend_client = client

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
        Process pending bets by:
        1. Fetching pending commit boxes from the backend
        2. Calling reveal-and-broadcast for each box
        """
        try:
            pending = await self.backend_client.get_pending_bets()
        except httpx.HTTPError as e:
            logger.error("fetch_pending_bets_error", error=str(e))
            return

        if not pending:
            logger.debug("no_pending_bets")
            return

        logger.info("found_pending_bets", count=len(pending))

        for bet in pending:
            if self.shutdown_manager.is_shutdown_requested():
                logger.info("shutdown_during_bet_processing")
                break

            box_id = bet.get("box_id", "")
            if not box_id:
                continue

            try:
                logger.info(
                    "processing_bet",
                    box_id=box_id[:16] + "...",
                    player_choice=bet.get("player_choice"),
                    value=bet.get("value"),
                )

                result = await self.backend_client.reveal_and_broadcast(box_id)

                if result.get("success"):
                    logger.info(
                        "bet_revealed",
                        box_id=box_id[:16] + "...",
                        tx_id=result.get("tx_id", ""),
                        player_wins=result.get("player_wins"),
                        payout=result.get("payout_amount"),
                    )
                    self.health_server.increment_bets_processed()
                else:
                    logger.error(
                        "reveal_failed",
                        box_id=box_id[:16] + "...",
                        message=result.get("message", "unknown error"),
                    )

            except httpx.HTTPStatusError as e:
                logger.error(
                    "reveal_http_error",
                    box_id=box_id[:16] + "...",
                    status=e.response.status_code,
                    body=e.response.text[:200],
                )
            except Exception as e:
                logger.error(
                    "reveal_error",
                    box_id=box_id[:16] + "...",
                    error=str(e),
                    exc_info=True,
                )


# ─── Main ────────────────────────────────────────────────────────────────

async def main():
    """Main entry point."""
    bot = OffChainBot(
        backend_url=BACKEND_URL,
        heartbeat_file=HEARTBEAT_FILE,
        heartbeat_interval_seconds=HEARTBEAT_INTERVAL_SECONDS,
        health_server_port=HEALTH_SERVER_PORT,
        poll_interval=POLL_INTERVAL,
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
