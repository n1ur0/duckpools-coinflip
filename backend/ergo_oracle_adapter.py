"""
DuckPools - Ergo Oracle Pool Adapter

Adapter for integrating with Ergo blockchain oracle pools.
Fetches oracle data directly from on-chain boxes and parses register values.

MAT-4f3e5a68: Oracle price feed integration module with Ergo oracle pool adapter
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
from enum import Enum

import httpx
from pydantic import BaseModel, Field

# Configure logging
logger = logging.getLogger(__name__)


class OracleDataType(str, Enum):
    """Types of data that can be stored in oracle pools."""
    PRICE = "price"
    EXCHANGE_RATE = "exchange_rate"
    TIMESTAMP = "timestamp"
    BLOCK_HEIGHT = "block_height"
    CUSTOM = "custom"


@dataclass
class OracleFeed:
    """Oracle feed configuration."""
    name: str
    box_id: str
    data_type: OracleDataType
    register_indices: Dict[str, int]  # Maps field names to register indices (R4, R5, etc.)
    description: Optional[str] = None
    decimals: int = 8  # Default decimals for price data
    base_asset: Optional[str] = None
    quote_asset: Optional[str] = None


class ErgoOraclePoolAdapter:
    """
    Adapter for fetching and parsing data from Ergo oracle pools.
    
    This adapter:
    1. Fetches oracle boxes from the blockchain
    2. Parses register values containing oracle data
    3. Converts data to standardized format
    """

    def __init__(self, node_url: str, api_key: Optional[str] = None):
        """
        Initialize the Ergo oracle pool adapter.
        
        Args:
            node_url: URL of the Ergo node API
            api_key: API key for the node (if required)
        """
        self.node_url = node_url.rstrip('/')
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()

    async def start(self):
        """Start the adapter and initialize HTTP client."""
        if self._client:
            return

        headers = {}
        if self.api_key:
            headers['api_key'] = self.api_key

        self._client = httpx.AsyncClient(
            base_url=self.node_url,
            headers=headers,
            timeout=30.0
        )
        logger.info(f"Ergo oracle pool adapter started for {self.node_url}")

    async def stop(self):
        """Stop the adapter and close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("Ergo oracle pool adapter stopped")

    async def get_oracle_box(self, box_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch an oracle box by ID from the blockchain.
        
        Args:
            box_id: The box ID to fetch
            
        Returns:
            Box data or None if not found
        """
        if not self._client:
            raise RuntimeError("Adapter not started. Call start() first.")

        try:
            response = await self._client.get(f"/blockchain/box/byId/{box_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to fetch oracle box {box_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching oracle box {box_id}: {e}")
            return None

    def _parse_register_value(self, register_data: Any, data_type: OracleDataType, decimals: int = 8) -> Any:
        """
        Parse a register value based on the expected data type.
        
        Args:
            register_data: Raw register data from the box
            data_type: Expected type of the data
            decimals: Number of decimals for numeric values
            
        Returns:
            Parsed value
        """
        if not register_data:
            return None

        try:
            if data_type in [OracleDataType.PRICE, OracleDataType.EXCHANGE_RATE]:
                # Price data is typically stored as a Long representing the value * 10^decimals
                if isinstance(register_data, dict) and 'value' in register_data:
                    value = int(register_data['value'])
                    return value / (10 ** decimals)
                elif isinstance(register_data, int):
                    return register_data / (10 ** decimals)
                
            elif data_type == OracleDataType.TIMESTAMP:
                # Timestamp data is typically stored as a Long
                if isinstance(register_data, dict) and 'value' in register_data:
                    return int(register_data['value'])
                elif isinstance(register_data, int):
                    return register_data
                    
            elif data_type == OracleDataType.BLOCK_HEIGHT:
                # Block height is typically stored as an Int
                if isinstance(register_data, dict) and 'value' in register_data:
                    return int(register_data['value'])
                elif isinstance(register_data, int):
                    return register_data
                    
            elif data_type == OracleDataType.CUSTOM:
                # Custom data - return as-is
                return register_data
                
            # Default case: try to extract value if it's a dict
            if isinstance(register_data, dict) and 'value' in register_data:
                return register_data['value']
            
            return register_data
            
        except Exception as e:
            logger.warning(f"Failed to parse register value {register_data} as {data_type}: {e}")
            return None

    async def get_oracle_feed_data(self, feed: OracleFeed) -> Optional[Dict[str, Any]]:
        """
        Get data from a specific oracle feed.
        
        Args:
            feed: Oracle feed configuration
            
        Returns:
            Parsed oracle data or None if failed
        """
        # Fetch the oracle box
        box_data = await self.get_oracle_box(feed.box_id)
        if not box_data:
            return None

        try:
            # Extract registers
            registers = box_data.get('additionalRegisters', {})
            if not registers:
                logger.warning(f"No additional registers found in oracle box {feed.box_id}")
                return None

            # Parse each field according to the feed configuration
            parsed_data = {
                'feed_name': feed.name,
                'box_id': feed.box_id,
                'data_type': feed.data_type.value,
                'timestamp': int(box_data.get('creationTimestamp', 0))
            }

            for field_name, register_index in feed.register_indices.items():
                register_key = f'R{register_index}'
                register_data = registers.get(register_key)
                
                if register_data:
                    # Determine the data type for this field
                    if field_name in ['price', 'rate', 'value']:
                        field_data_type = OracleDataType.PRICE
                    elif field_name == 'timestamp':
                        field_data_type = OracleDataType.TIMESTAMP
                    elif field_name == 'block_height':
                        field_data_type = OracleDataType.BLOCK_HEIGHT
                    else:
                        field_data_type = OracleDataType.CUSTOM
                    
                    parsed_value = self._parse_register_value(
                        register_data, 
                        field_data_type, 
                        feed.decimals
                    )
                    
                    if parsed_value is not None:
                        parsed_data[field_name] = parsed_value

            # Add metadata if available
            if feed.base_asset:
                parsed_data['base_asset'] = feed.base_asset
            if feed.quote_asset:
                parsed_data['quote_asset'] = feed.quote_asset

            logger.debug(f"Successfully parsed oracle feed {feed.name}: {parsed_data}")
            return parsed_data

        except Exception as e:
            logger.error(f"Failed to parse oracle feed {feed.name} from box {feed.box_id}: {e}")
            return None

    async def get_multiple_feeds_data(self, feeds: List[OracleFeed]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Get data from multiple oracle feeds concurrently.
        
        Args:
            feeds: List of oracle feed configurations
            
        Returns:
            Dictionary mapping feed names to their data (or None if failed)
        """
        if not feeds:
            return {}

        results = {}
        
        # Create tasks for all feeds
        tasks = []
        for feed in feeds:
            task = self.get_oracle_feed_data(feed)
            tasks.append((feed.name, task))

        # Execute all tasks concurrently
        for feed_name, task in tasks:
            try:
                result = await task
                results[feed_name] = result
            except Exception as e:
                logger.error(f"Error fetching oracle feed {feed_name}: {e}")
                results[feed_name] = None

        return results

    async def get_oracle_pool_info(self, pool_box_id: str) -> Optional[Dict[str, Any]]:
        """
        Get general information about an oracle pool.
        
        Args:
            pool_box_id: The pool box ID
            
        Returns:
            Pool information or None if failed
        """
        box_data = await self.get_oracle_box(pool_box_id)
        if not box_data:
            return None

        try:
            return {
                'box_id': pool_box_id,
                'address': box_data.get('address'),
                'value': int(box_data.get('value', 0)),
                'assets': box_data.get('assets', []),
                'creation_height': box_data.get('creationHeight'),
                'creation_timestamp': int(box_data.get('creationTimestamp', 0)),
                'transaction_id': box_data.get('transactionId'),
                'ergo_tree': box_data.get('ergoTree'),
            }
        except Exception as e:
            logger.error(f"Failed to parse oracle pool info for {pool_box_id}: {e}")
            return None