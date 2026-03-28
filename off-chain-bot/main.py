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
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

import httpx
from dotenv import load_dotenv

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
API_KEY = os.getenv("API_KEY", "")
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


# Type variable for decorator
F = TypeVar("F", bound=Callable[..., Any])


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    retry_exceptions: tuple = (
        httpx.ConnectError,
        httpx.TimeoutException,
        httpx.HTTPStatusError,
    ),
    retry_status_codes: tuple = (500, 502, 503),
) -> Callable[[F], F]:
    """
    Decorator for retrying HTTP calls with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (doubled after each retry)
        retry_exceptions: Exception types to retry on
        retry_status_codes: HTTP status codes to retry on

    Returns:
        Decorator function
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None

            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except httpx.HTTPStatusError as e:
                    last_exception = e
                    if e.response.status_code in retry_status_codes:
                        if attempt < max_retries:
                            delay = base_delay * (2 ** (attempt - 1))
                            logger.warning(
                                "http_retry",
                                function=func.__name__,
                                attempt=attempt,
                                max_retries=max_retries,
                                status_code=e.response.status_code,
                                delay_seconds=delay,
                            )
                            await asyncio.sleep(delay)
                        else:
                            logger.error(
                                "http_retry_exhausted",
                                function=func.__name__,
                                attempts=max_retries,
                                last_status_code=e.response.status_code,
                            )
                    else:
                        # Don't retry on non-retryable status codes
                        raise
                except retry_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** (attempt - 1))
                        logger.warning(
                            "http_retry",
                            function=func.__name__,
                            attempt=attempt,
                            max_retries=max_retries,
                            exception_type=type(e).__name__,
                            exception_msg=str(e),
                            delay_seconds=delay,
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            "http_retry_exhausted",
                            function=func.__name__,
                            attempts=max_retries,
                            last_exception_type=type(e).__name__,
                            last_exception_msg=str(e),
                        )
                except Exception as e:
                    # Don't retry on unexpected exceptions
                    logger.error(
                        "unexpected_error",
                        function=func.__name__,
                        exception_type=type(e).__name__,
                        exception_msg=str(e),
                    )
                    raise

            # All retries exhausted, raise the last exception
            if last_exception:
                raise last_exception

            # Should never reach here, but just in case
            raise RuntimeError(f"Function {func.__name__} failed after {max_retries} retries")

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None

            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except httpx.HTTPStatusError as e:
                    last_exception = e
                    if e.response.status_code in retry_status_codes:
                        if attempt < max_retries:
                            delay = base_delay * (2 ** (attempt - 1))
                            logger.warning(
                                "http_retry",
                                function=func.__name__,
                                attempt=attempt,
                                max_retries=max_retries,
                                status_code=e.response.status_code,
                                delay_seconds=delay,
                            )
                            time.sleep(delay)
                        else:
                            logger.error(
                                "http_retry_exhausted",
                                function=func.__name__,
                                attempts=max_retries,
                                last_status_code=e.response.status_code,
                            )
                    else:
                        raise
                except retry_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** (attempt - 1))
                        logger.warning(
                            "http_retry",
                            function=func.__name__,
                            attempt=attempt,
                            max_retries=max_retries,
                            exception_type=type(e).__name__,
                            exception_msg=str(e),
                            delay_seconds=delay,
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            "http_retry_exhausted",
                            function=func.__name__,
                            attempts=max_retries,
                            last_exception_type=type(e).__name__,
                            last_exception_msg=str(e),
                        )
                except Exception as e:
                    logger.error(
                        "unexpected_error",
                        function=func.__name__,
                        exception_type=type(e).__name__,
                        exception_msg=str(e),
                    )
                    raise

            if last_exception:
                raise last_exception

            raise RuntimeError(f"Function {func.__name__} failed after {max_retries} retries")

        # Check if the function is async to return the appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        else:
            return sync_wrapper  # type: ignore[return-value]

    return decorator


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

    @retry_with_backoff(max_retries=3, base_delay=1.0)
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

    @retry_with_backoff(max_retries=3, base_delay=1.0)
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

    @retry_with_backoff(max_retries=3, base_delay=1.0)
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
