"""
DuckPools - Oracle Service

Service for managing Ergo Oracle Pool integrations with health monitoring,
stale feed detection, failover logic, and alerting.

MAT-31: Oracle health monitoring and failover
MAT-XXX: Oracle price feed integration module with Ergo oracle pool adapter
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import httpx
from pydantic import BaseModel, Field

from .ergo_oracle_adapter import (
    ErgoOraclePoolAdapter,
    OracleFeed,
    OracleDataType
)

# Configure logging
logger = logging.getLogger(__name__)


class OracleStatus(str, Enum):
    """Oracle health status."""
    HEALTHY = "healthy"
    STALE = "stale"
    UNREACHABLE = "unreachable"
    ERROR = "error"


@dataclass
class OracleEndpoint:
    """Oracle endpoint configuration."""
    url: str
    name: str
    is_primary: bool = False
    priority: int = 1  # Lower is higher priority


@dataclass
class OracleHealth:
    """Oracle health check result."""
    url: str
    status: OracleStatus
    last_updated: Optional[datetime]
    latency_ms: Optional[float]
    error: Optional[str]


class OracleConfig(BaseModel):
    """Oracle service configuration."""
    primary_oracle_url: str = Field(
        default="https://api.oraclepool.xyz",
        description="Primary oracle endpoint URL"
    )
    backup_oracle_urls: List[str] = Field(
        default_factory=list,
        description="Backup oracle endpoint URLs"
    )
    stale_threshold_seconds: int = Field(
        default=300,  # 5 minutes
        description="Time before considering feed stale"
    )
    health_check_interval_seconds: int = Field(
        default=30,
        description="Interval between health checks"
    )
    request_timeout_seconds: int = Field(
        default=10,
        description="Timeout for oracle requests"
    )
    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for failed requests"
    )
    enable_failover: bool = Field(
        default=True,
        description="Enable automatic failover to backup oracles"
    )
    alert_on_stale: bool = Field(
        default=True,
        description="Log alerts when feeds become stale"
    )
    alert_on_failure: bool = Field(
        default=True,
        description="Log alerts when oracles fail"
    )
    # Ergo oracle pool configuration
    ergo_node_url: str = Field(
        default="http://localhost:9052",
        description="Ergo node API URL for on-chain oracle data"
    )
    ergo_node_api_key: Optional[str] = Field(
        default=None,
        description="API key for Ergo node (if required)"
    )
    enable_on_chain_oracles: bool = Field(
        default=True,
        description="Enable fetching data from on-chain oracle pools"
    )


class OracleService:
    """
    Oracle service with health monitoring, stale feed detection, and failover.
    """

    def __init__(self, config: OracleConfig):
        self.config = config
        self._endpoints: List[OracleEndpoint] = self._init_endpoints()
        self._current_endpoint_index: int = 0
        self._health_status: Dict[str, OracleHealth] = {}
        self._last_feed_update: Optional[datetime] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()
        
        # Ergo oracle pool adapter
        self._ergo_adapter: Optional[ErgoOraclePoolAdapter] = None
        self._configured_feeds: List[OracleFeed] = []

    def _init_endpoints(self) -> List[OracleEndpoint]:
        """Initialize oracle endpoints with priority."""
        endpoints = [
            OracleEndpoint(
                url=self.config.primary_oracle_url,
                name="primary",
                is_primary=True,
                priority=1
            )
        ]

        for i, url in enumerate(self.config.backup_oracle_urls, start=2):
            endpoints.append(
                OracleEndpoint(
                    url=url,
                    name=f"backup-{i}",
                    is_primary=False,
                    priority=i
                )
            )

        # Sort by priority (lower = higher priority)
        return sorted(endpoints, key=lambda e: e.priority)

    async def start(self) -> None:
        """Start the oracle service and health monitoring."""
        if self._health_check_task and not self._health_check_task.done():
            return  # Already started

        self._client = httpx.AsyncClient(timeout=self.config.request_timeout_seconds)
        
        # Initialize Ergo oracle pool adapter if enabled
        if self.config.enable_on_chain_oracles:
            self._ergo_adapter = ErgoOraclePoolAdapter(
                node_url=self.config.ergo_node_url,
                api_key=self.config.ergo_node_api_key
            )
            await self._ergo_adapter.start()
            logger.info("Ergo oracle pool adapter initialized")
        
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info(f"Oracle service started with {len(self._endpoints)} endpoint(s)")

    async def stop(self) -> None:
        """Stop the oracle service and health monitoring."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None

        if self._client:
            await self._client.aclose()
            self._client = None
            
        # Stop Ergo oracle pool adapter
        if self._ergo_adapter:
            await self._ergo_adapter.stop()
            self._ergo_adapter = None

        logger.info("Oracle service stopped")

    @property
    def current_endpoint(self) -> Optional[OracleEndpoint]:
        """Get the currently active oracle endpoint."""
        if 0 <= self._current_endpoint_index < len(self._endpoints):
            return self._endpoints[self._current_endpoint_index]
        return None

    @property
    def all_endpoints(self) -> List[OracleEndpoint]:
        """Get all oracle endpoints."""
        return self._endpoints

    async def get_oracle_data(
        self,
        oracle_box_id: Optional[str] = None,
        feed_name: Optional[str] = None
    ) -> Optional[dict]:
        """
        Get data from the current oracle endpoint with automatic failover.

        Args:
            oracle_box_id: Specific oracle box ID (optional)
            feed_name: Specific feed name (optional)

        Returns:
            Oracle data as dict, or None if all endpoints fail
        """
        if not self._client:
            logger.warning("Oracle client not initialized, call start() first")
            return None

        async with self._lock:
            attempts = 0
            last_error: Optional[str] = None

            while attempts < len(self._endpoints):
                endpoint = self._endpoints[self._current_endpoint_index]

                try:
                    logger.debug(f"Fetching oracle data from {endpoint.name} ({endpoint.url})")

                    # Build request URL
                    url = endpoint.url
                    if oracle_box_id:
                        url = f"{url.rstrip('/')}/box/{oracle_box_id}"

                    response = await self._client.get(url)
                    response.raise_for_status()

                    data = response.json()

                    # Update last feed timestamp
                    self._last_feed_update = datetime.now(timezone.utc)
                    logger.info(f"Successfully fetched oracle data from {endpoint.name}")

                    return data

                except httpx.TimeoutException as e:
                    last_error = f"Timeout: {str(e)}"
                    logger.warning(f"{endpoint.name} timeout: {last_error}")

                except httpx.HTTPStatusError as e:
                    last_error = f"HTTP {e.response.status_code}: {e.response.text}"
                    logger.warning(f"{endpoint.name} HTTP error: {last_error}")

                except Exception as e:
                    last_error = str(e)
                    logger.warning(f"{endpoint.name} error: {last_error}")

                # Mark this endpoint as unhealthy and try next
                self._health_status[endpoint.url] = OracleHealth(
                    url=endpoint.url,
                    status=OracleStatus.UNREACHABLE,
                    last_updated=datetime.now(timezone.utc),
                    latency_ms=None,
                    error=last_error
                )

                if self.config.alert_on_failure:
                    logger.error(f"ORACLE ALERT: {endpoint.name} failed: {last_error}")

                # Try next endpoint if failover is enabled
                if self.config.enable_failover:
                    self._current_endpoint_index = (self._current_endpoint_index + 1) % len(self._endpoints)
                    next_endpoint = self._endpoints[self._current_endpoint_index]
                    logger.warning(f"Failing over to {next_endpoint.name}")

                attempts += 1

            logger.error(f"All oracle endpoints failed. Last error: {last_error}")
            return None

    async def _health_check_loop(self) -> None:
        """Background task for periodic health checks."""
        logger.info("Starting oracle health check loop")

        while True:
            try:
                await self._check_all_endpoints()
                await asyncio.sleep(self.config.health_check_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}", exc_info=True)
                await asyncio.sleep(self.config.health_check_interval_seconds)

    async def _check_all_endpoints(self) -> None:
        """Health check all oracle endpoints."""
        if not self._client:
            return

        tasks = [self._check_endpoint(endpoint) for endpoint in self._endpoints]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Check for stale feed
        if self._last_feed_update:
            time_since_update = datetime.now(timezone.utc) - self._last_feed_update
            if time_since_update > timedelta(seconds=self.config.stale_threshold_seconds):
                status = OracleStatus.STALE
                if self.config.alert_on_stale:
                    logger.warning(
                        f"ORACLE ALERT: Feed is stale. Last update: {self._last_feed_update} "
                        f"({int(time_since_update.total_seconds())}s ago)"
                    )
            else:
                status = OracleStatus.HEALTHY

            # Update current endpoint status with staleness check
            if self.current_endpoint:
                self._health_status[self.current_endpoint.url] = OracleHealth(
                    url=self.current_endpoint.url,
                    status=status,
                    last_updated=self._last_feed_update,
                    latency_ms=self._health_status.get(self.current_endpoint.url, OracleHealth(
                        url=self.current_endpoint.url,
                        status=status,
                        last_updated=self._last_feed_update,
                        latency_ms=None,
                        error=None
                    )).latency_ms,
                    error=None
                )

    async def _check_endpoint(self, endpoint: OracleEndpoint) -> None:
        """Check health of a single oracle endpoint."""
        if not self._client:
            return

        start_time = datetime.now(timezone.utc)

        try:
            # Simple health check - try to fetch oracle info
            response = await self._client.get(f"{endpoint.url.rstrip('/')}/info")
            response.raise_for_status()

            latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            self._health_status[endpoint.url] = OracleHealth(
                url=endpoint.url,
                status=OracleStatus.HEALTHY,
                last_updated=datetime.now(timezone.utc),
                latency_ms=latency_ms,
                error=None
            )

            logger.debug(f"{endpoint.name} health check: healthy ({latency_ms:.2f}ms)")

        except Exception as e:
            self._health_status[endpoint.url] = OracleHealth(
                url=endpoint.url,
                status=OracleStatus.UNREACHABLE,
                last_updated=datetime.now(timezone.utc),
                latency_ms=None,
                error=str(e)
            )

            logger.warning(f"{endpoint.name} health check: failed - {e}")

    def get_health_status(self) -> Dict[str, dict]:
        """Get health status of all oracle endpoints."""
        result = {}

        for endpoint in self._endpoints:
            health = self._health_status.get(endpoint.url)
            if health:
                result[endpoint.name] = {
                    "url": endpoint.url,
                    "is_primary": endpoint.is_primary,
                    "is_current": endpoint == self.current_endpoint,
                    "status": health.status.value,
                    "last_updated": health.last_updated.isoformat() if health.last_updated else None,
                    "latency_ms": health.latency_ms,
                    "error": health.error,
                }
            else:
                result[endpoint.name] = {
                    "url": endpoint.url,
                    "is_primary": endpoint.is_primary,
                    "is_current": endpoint == self.current_endpoint,
                    "status": "unknown",
                    "last_updated": None,
                    "latency_ms": None,
                    "error": "No health data yet",
                }

        return result

    def get_service_status(self) -> dict:
        """Get overall oracle service status."""
        current = self.current_endpoint
        health = self._health_status.get(current.url) if current else None

        # Determine overall status
        if health and health.status == OracleStatus.STALE:
            overall_status = "stale"
        elif health and health.status == OracleStatus.UNREACHABLE:
            overall_status = "degraded"
        elif current:
            overall_status = "ok"
        else:
            overall_status = "no_endpoints"

        return {
            "status": overall_status,
            "current_endpoint": current.name if current else None,
            "total_endpoints": len(self._endpoints),
            "last_feed_update": self._last_feed_update.isoformat() if self._last_feed_update else None,
            "config": {
                "stale_threshold_seconds": self.config.stale_threshold_seconds,
                "health_check_interval_seconds": self.config.health_check_interval_seconds,
                "enable_failover": self.config.enable_failover,
            },
        }

    def add_oracle_feed(self, feed: OracleFeed) -> None:
        """
        Add an oracle feed configuration.
        
        Args:
            feed: Oracle feed configuration
        """
        if not self.config.enable_on_chain_oracles:
            logger.warning("On-chain oracles are disabled, feed will not be used")
            return
            
        # Check if feed with same name already exists
        for existing_feed in self._configured_feeds:
            if existing_feed.name == feed.name:
                logger.warning(f"Feed with name '{feed.name}' already exists, updating")
                self._configured_feeds.remove(existing_feed)
                break
        
        self._configured_feeds.append(feed)
        logger.info(f"Added oracle feed: {feed.name} (box: {feed.box_id})")

    def remove_oracle_feed(self, feed_name: str) -> bool:
        """
        Remove an oracle feed configuration.
        
        Args:
            feed_name: Name of the feed to remove
            
        Returns:
            True if feed was removed, False if not found
        """
        for i, feed in enumerate(self._configured_feeds):
            if feed.name == feed_name:
                self._configured_feeds.pop(i)
                logger.info(f"Removed oracle feed: {feed_name}")
                return True
        
        logger.warning(f"Feed not found: {feed_name}")
        return False

    def get_configured_feeds(self) -> List[Dict[str, Any]]:
        """
        Get list of configured oracle feeds.
        
        Returns:
            List of feed configurations
        """
        return [
            {
                "name": feed.name,
                "box_id": feed.box_id,
                "data_type": feed.data_type.value,
                "register_indices": feed.register_indices,
                "description": feed.description,
                "decimals": feed.decimals,
                "base_asset": feed.base_asset,
                "quote_asset": feed.quote_asset
            }
            for feed in self._configured_feeds
        ]

    async def get_on_chain_oracle_data(
        self,
        feed_name: Optional[str] = None,
        box_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get data from on-chain oracle pools.
        
        Args:
            feed_name: Name of the configured feed to fetch (optional)
            box_id: Box ID of oracle to fetch (optional, overrides feed_name)
            
        Returns:
            Oracle data or None if failed
        """
        if not self.config.enable_on_chain_oracles:
            logger.warning("On-chain oracles are disabled")
            return None
            
        if not self._ergo_adapter:
            logger.error("Ergo oracle pool adapter not initialized")
            return None
        
        # If box_id is provided, fetch directly
        if box_id:
            return await self._ergo_adapter.get_oracle_pool_info(box_id)
        
        # If feed_name is provided, fetch from configured feed
        if feed_name:
            for feed in self._configured_feeds:
                if feed.name == feed_name:
                    return await self._ergo_adapter.get_oracle_feed_data(feed)
            
            logger.warning(f"Feed not found: {feed_name}")
            return None
        
        # If neither is provided, fetch all configured feeds
        if self._configured_feeds:
            return await self._ergo_adapter.get_multiple_feeds_data(self._configured_feeds)
        
        logger.warning("No feeds configured and no specific feed requested")
        return None

    async def get_latest_price_feed(self, base_asset: str, quote_asset: str) -> Optional[Dict[str, Any]]:
        """
        Get the latest price feed for a specific asset pair.
        
        Args:
            base_asset: Base asset (e.g., "ERG")
            quote_asset: Quote asset (e.g., "USD")
            
        Returns:
            Price feed data or None if not found
        """
        if not self.config.enable_on_chain_oracles:
            logger.warning("On-chain oracles are disabled")
            return None
            
        # Find feeds that match the asset pair
        matching_feeds = []
        for feed in self._configured_feeds:
            if (feed.base_asset == base_asset and feed.quote_asset == quote_asset and
                feed.data_type == OracleDataType.PRICE):
                matching_feeds.append(feed)
        
        if not matching_feeds:
            logger.warning(f"No price feeds found for {base_asset}/{quote_asset}")
            return None
        
        # Fetch data from the first matching feed
        # In a more sophisticated implementation, you might want to:
        # 1. Fetch from all matching feeds
        # 2. Apply some consensus mechanism
        # 3. Return the median or weighted average
        
        feed_data = await self._ergo_adapter.get_oracle_feed_data(matching_feeds[0])
        if feed_data:
            # Update last feed timestamp
            self._last_feed_update = datetime.now(timezone.utc)
        
        return feed_data
