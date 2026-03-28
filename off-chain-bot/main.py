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

# Configure structured logging
configure_logging()
logger = get_logger(__name__)

# ─── Configuration ─────────────────────────────────────────────────────────

# Load from environment variables
NODE_URL = os.getenv("NODE_URL", "http://localhost:9052")
NODE_API_KEY=os.getenv("NODE_API_KEY", "")
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
        Process pending bets.

        This is a placeholder - real implementation will:
        1. Query for PendingBet boxes
        2. Reveal secrets
        3. Calculate RNG
        4. Settle bets
        """
        # Placeholder: log that we're checking for bets
        logger.debug("checking_for_pending_bets")

        # Example node API call with retry
        try:
            # Get node info to test connectivity
            info = await self.client.get("/info")
            logger.debug("node_info", full_height=info.get("fullHeight"))
            
            # In a real implementation, this would be where we:
            # 1. Query for PendingBet boxes
            # 2. Process each bet
            # 3. Increment the counter for each successful bet
            
            # For demo purposes, simulate a bet being processed
            # In the real implementation, this would be inside the bet processing loop
            self.health_server.increment_bets_processed()
            logger.debug("bet_processed_counter_incremented")
            
        except httpx.HTTPError as e:
            logger.error("node_api_error", error=str(e))
            raise


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
