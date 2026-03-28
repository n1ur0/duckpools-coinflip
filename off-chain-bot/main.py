"""
DuckPools - Off-Chain Bot

Bot for processing coinflip bets with retry logic and graceful shutdown.

MAT-223: Retry logic and graceful shutdown for off-chain bot
"""

import asyncio
import signal
import sys
import time
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Import local logger
from logger import configure_structured_logging, get_logger

# Load environment variables
load_dotenv()

# Configure structured logging
log_level = os.getenv("BACKEND_LOG_LEVEL", "INFO")
configure_structured_logging(log_level)
logger = get_logger(__name__)

# Bot configuration
NODE_URL = os.getenv("NODE_URL", "http://localhost:9052")
API_KEY=os.getenv("API_KEY", "")
HEARTBEAT_FILE = Path("/tmp/off-chain-bot.heartbeat")

# Shutdown flag
shutdown_requested = False


@dataclass
class BotConfig:
    """Bot configuration."""
    node_url: str
    api_key: str
    max_retries: int = 3
    base_delay: float = 1.0
    heartbeat_interval: int = 30  # seconds


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


def get_retry_decorator(max_retries: int = 3, base_delay: float = 1.0):
    """
    Get a tenacity retry decorator with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds

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
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(
            multiplier=base_delay,
            max=base_delay * (2 ** (max_retries - 1)),  # Max delay
        ),
        retry=retry_if_exception(is_retryable_error),
        before_sleep=log_retry_attempt,
        reraise=True,
    )


class ErgoNodeClient:
    """Client for interacting with Ergo node API."""

    def __init__(self, config: BotConfig):
        self.config = config
        self.session = httpx.Client(timeout=30.0)
        self.async_session: Optional[httpx.AsyncClient] = None

        # Set up authentication headers
        self.headers = {}
        if config.api_key:
            self.headers["api_key"] = config.api_key

    async def async_init(self) -> None:
        """Initialize async HTTP session."""
        self.async_session = httpx.AsyncClient(timeout=30.0)

    @get_retry_decorator(max_retries=3, base_delay=1.0)
    def get_node_info(self) -> dict:
        """
        Get node information with retry logic.

        Returns:
            Node info dict

        Raises:
            httpx.HTTPError: If all retries fail
        """
        url = f"{self.config.node_url}/info"
        logger.debug("node_request", url=url)
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    @get_retry_decorator(max_retries=3, base_delay=1.0)
    async def get_node_info_async(self) -> dict:
        """
        Get node information asynchronously with retry logic.

        Returns:
            Node info dict

        Raises:
            httpx.HTTPError: If all retries fail
        """
        if not self.async_session:
            await self.async_init()

        url = f"{self.config.node_url}/info"
        logger.debug("node_request_async", url=url)
        response = await self.async_session.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    @get_retry_decorator(max_retries=3, base_delay=1.0)
    def get_unspent_boxes(self, address: str) -> dict:
        """
        Get unspent boxes for an address with retry logic.

        Args:
            address: Ergo address

        Returns:
            Unspent boxes dict

        Raises:
            httpx.HTTPError: If all retries fail
        """
        url = f"{self.config.node_url}/wallet/boxes/unspent"
        params = {"address": address}
        logger.debug("node_request", url=url, address=address)
        response = self.session.get(url, params=params, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        """Close HTTP session."""
        if self.session:
            self.session.close()

    async def close_async(self) -> None:
        """Close async HTTP session."""
        if self.async_session:
            await self.async_session.aclose()


class OffChainBot:
    """Off-chain bot for processing bets with graceful shutdown."""

    def __init__(self, config: BotConfig):
        self.config = config
        self.client = ErgoNodeClient(config)
        self.running = False
        self.heartbeat_task: Optional[asyncio.Task] = None
        
        # Health server and metrics
        self.health_app = FastAPI(title="Off-Chain Bot Health")
        self.health_server: Optional[any] = None
        self.start_time = datetime.now(timezone.utc)
        self.bets_processed = 0
        self.last_processed_at: Optional[datetime] = None
        self.health_port = 8001
        
        # Setup health endpoint
        self._setup_health_endpoint()

    def _setup_health_endpoint(self) -> None:
        """Setup the health endpoint."""
        
        @self.health_app.get("/health")
        async def health_check():
            """Health check endpoint with bot metrics."""
            uptime_seconds = (datetime.now(timezone.utc) - self.start_time).total_seconds()
            
            health_data = {
                "status": "alive" if self.running else "stopped",
                "uptime_seconds": round(uptime_seconds, 2),
                "bets_processed": self.bets_processed,
                "last_processed_at": self.last_processed_at.isoformat() if self.last_processed_at else None,
                "start_time": self.start_time.isoformat(),
            }
            
            return JSONResponse(content=health_data)

    async def start_health_server(self) -> None:
        """Start the health server on port 8001."""
        import uvicorn
        
        logger.info("health_server_starting", port=self.health_port)
        
        # Configure uvicorn
        config = uvicorn.Config(
            app=self.health_app,
            host="127.0.0.1",
            port=self.health_port,
            log_level="warning",  # Reduce log noise
            access_log=False,  # Disable access logs for cleaner output
        )
        
        # Create and start server
        server = uvicorn.Server(config)
        self.health_server = server
        
        # Start server in background
        asyncio.create_task(server.serve())
        logger.info("health_server_started", port=self.health_port)

    async def stop_health_server(self) -> None:
        """Stop the health server."""
        if self.health_server:
            logger.info("health_server_stopping")
            self.health_server.should_exit = True
            # Give it a moment to shut down gracefully
            await asyncio.sleep(0.1)
            self.health_server = None
            logger.info("health_server_stopped")

    def write_heartbeat(self) -> None:
        """
        Write heartbeat file with current timestamp.

        This allows the backend to check bot liveness.
        """
        try:
            heartbeat_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "running",
            }
            HEARTBEAT_FILE.write_text(f"{heartbeat_data['timestamp']}\n")
            logger.debug("heartbeat_written", path=str(HEARTBEAT_FILE))
        except Exception as e:
            logger.error("heartbeat_write_failed", exception=str(e))

    def remove_heartbeat(self) -> None:
        """Remove heartbeat file on shutdown."""
        try:
            if HEARTBEAT_FILE.exists():
                HEARTBEAT_FILE.unlink()
                logger.debug("heartbeat_removed", path=str(HEARTBEAT_FILE))
        except Exception as e:
            logger.error("heartbeat_remove_failed", exception=str(e))

    async def heartbeat_loop(self) -> None:
        """Background task to update heartbeat file."""
        while self.running and not shutdown_requested:
            self.write_heartbeat()
            await asyncio.sleep(self.config.heartbeat_interval)

    async def process_bets(self) -> None:
        """
        Main bet processing loop.

        Processes bets from pending boxes and resolves games.
        This is a placeholder - actual implementation depends on game logic.
        """
        logger.info("bets_processing_started")

        while self.running and not shutdown_requested:
            try:
                # Process a batch of bets
                # This is a placeholder - replace with actual game logic
                logger.debug("processing_bet_batch")

                # Increment bets processed counter
                self.bets_processed += 1
                self.last_processed_at = datetime.now(timezone.utc)

                # Get node info as example API call
                try:
                    node_info = await self.client.get_node_info_async()
                    logger.info("node_connected", height=node_info.get("height"))
                except Exception as e:
                    logger.error("node_connection_failed", exception=str(e))

                # Wait before next iteration
                await asyncio.sleep(5)

            except Exception as e:
                logger.error("bet_processing_error", exception=str(e), exc_info=True)
                # Continue running even if there's an error
                await asyncio.sleep(1)

        logger.info("bets_processing_stopped")

    async def start(self) -> None:
        """Start the bot."""
        logger.info("bot_starting", node_url=self.config.node_url)

        # Initialize client
        await self.client.async_init()

        # Set running flag
        self.running = True

        # Start heartbeat task
        self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())

        # Start health server
        await self.start_health_server()

        # Start bet processing
        await self.process_bets()

    async def stop(self) -> None:
        """Stop the bot gracefully."""
        global shutdown_requested
        shutdown_requested = True

        logger.info("bot_stopping")

        # Stop running
        self.running = False

        # Wait for heartbeat task to finish
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass

        # Stop health server
        await self.stop_health_server()

        # Close client
        await self.client.close_async()

        # Remove heartbeat file
        self.remove_heartbeat()

        logger.info("bot_stopped")


# Global bot instance
bot_instance: Optional[OffChainBot] = None


def signal_handler(signum: int, frame: Any) -> None:
    """
    Handle SIGINT/SIGTERM for graceful shutdown.

    Args:
        signum: Signal number
        frame: Current stack frame
    """
    global shutdown_requested
    shutdown_requested = True

    signal_name = signal.Signals(signum).name
    logger.info("signal_received", signal=signal_name, signum=signum)

    # The actual shutdown happens in the main loop


async def main() -> int:
    """
    Main bot entry point.

    Returns:
        Exit code
    """
    global bot_instance

    logger.info(
        "off_chain_bot_startup",
        node_url=NODE_URL,
        heartbeat_file=str(HEARTBEAT_FILE),
    )

    # Configure signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create bot instance
    config = BotConfig(
        node_url=NODE_URL,
        api_key=API_KEY,
        max_retries=3,
        base_delay=1.0,
    )
    bot_instance = OffChainBot(config)

    try:
        # Start bot
        await bot_instance.start()
        return 0
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt")
        return 0
    except Exception as e:
        logger.error("fatal_error", exception=str(e), exc_info=True)
        return 1
    finally:
        # Ensure graceful shutdown
        if bot_instance:
            await bot_instance.stop()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
