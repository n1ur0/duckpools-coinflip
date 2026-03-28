"""
DuckPools - Oracle Routes

API endpoints for oracle health monitoring and status.

MAT-31: Oracle health monitoring with stale feed detection, failover logic, and alerting
MAT-XXX: Oracle price feed integration module with Ergo oracle pool adapter
SEC-A3: /switch endpoint requires admin API key authentication
"""

import os
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from oracle_service import OracleService
from ergo_oracle_adapter import OracleFeed, OracleDataType

# Request/Response models
class CreateOracleFeedRequest(BaseModel):
    """Request model for creating an oracle feed."""
    name: str = Field(..., description="Unique name for the feed")
    box_id: str = Field(..., description="Box ID of the oracle")
    data_type: str = Field(..., description="Type of data (price, timestamp, etc.)")
    register_indices: Dict[str, int] = Field(..., description="Map of field names to register indices")
    description: Optional[str] = Field(None, description="Description of the feed")
    decimals: int = Field(8, description="Number of decimals for numeric values")
    base_asset: Optional[str] = Field(None, description="Base asset symbol")
    quote_asset: Optional[str] = Field(None, description="Quote asset symbol")


class OracleFeedResponse(BaseModel):
    """Response model for oracle feed."""
    name: str
    box_id: str
    data_type: str
    register_indices: Dict[str, int]
    description: Optional[str] = None
    decimals: int
    base_asset: Optional[str] = None
    quote_asset: Optional[str] = None


# Create router
router = APIRouter(prefix="/api/oracle", tags=["oracle"])


async def get_oracle_service():
    """Dependency to get the oracle service from app state."""
    async def _get_oracle_service(request: Request):
        service = getattr(request.app.state, "oracle_service", None)
        if not service:
            raise HTTPException(status_code=503, detail="Oracle service not initialized")
        return service

    return _get_oracle_service


async def verify_admin_api_key(request: Request):
    """
    SEC-A3: Require admin API key for destructive operations.

    The /switch endpoint can redirect oracle traffic to a malicious endpoint.
    This dependency ensures only operators can trigger failover.
    """
    api_key = request.headers.get("X-Admin-API-Key", "")
    expected = os.getenv("ADMIN_API_KEY", "")
    if not expected:
        # Fail-closed: if ADMIN_API_KEY is not configured, block the endpoint
        raise HTTPException(
            status_code=503,
            detail="Admin API key not configured on server. Set ADMIN_API_KEY env var."
        )
    if not api_key or not hmac.compare_digest(api_key, expected):
        raise HTTPException(status_code=401, detail="Unauthorized: invalid or missing admin API key")
    return True


@router.get("/health")
async def get_oracle_health(oracle_service=Depends(get_oracle_service)):
    """
    Get health status of all oracle endpoints.

    Returns status for primary and backup oracles including:
    - Health status (healthy, stale, unreachable, error)
    - Last update time
    - Latency metrics
    - Error details if applicable
    """
    return oracle_service.get_health_status()


@router.get("/status")
async def get_oracle_status(oracle_service=Depends(get_oracle_service)):
    """
    Get overall oracle service status.

    Returns summary information about the oracle service:
    - Overall status (ok, stale, degraded, no_endpoints)
    - Currently active endpoint
    - Total number of configured endpoints
    - Last feed update timestamp
    - Configuration settings
    """
    return oracle_service.get_service_status()


@router.get("/endpoints")
async def get_oracle_endpoints(oracle_service=Depends(get_oracle_service)):
    """
    Get list of all configured oracle endpoints.

    Returns endpoint configuration details including:
    - Endpoint name
    - URL
    - Whether it's the primary endpoint
    - Whether it's currently active
    """
    endpoints = []
    for endpoint in oracle_service.all_endpoints:
        endpoints.append({
            "name": endpoint.name,
            "url": endpoint.url,
            "is_primary": endpoint.is_primary,
            "is_current": endpoint == oracle_service.current_endpoint,
            "priority": endpoint.priority,
        })
    return {"endpoints": endpoints}


@router.post("/data/{oracle_box_id}")
async def get_oracle_data(
    oracle_box_id: str,
    feed_name: Optional[str] = None,
    oracle_service=Depends(get_oracle_service)
):
    """
    Fetch data from the oracle with automatic failover.

    Args:
        oracle_box_id: The oracle box ID to fetch data from
        feed_name: Optional specific feed name to filter

    Returns:
        Oracle data as JSON, or 503 if all endpoints fail
    """
    data = await oracle_service.get_oracle_data(
        oracle_box_id=oracle_box_id,
        feed_name=feed_name
    )

    if data is None:
        raise HTTPException(
            status_code=503,
            detail="Failed to fetch oracle data from all endpoints"
        )

    return {"data": data}


@router.post("/switch", dependencies=[Depends(verify_admin_api_key)])
async def switch_oracle_endpoint(
    target_endpoint_name: str,
    oracle_service=Depends(get_oracle_service)
):
    """
    Manually switch to a different oracle endpoint.

    Args:
        target_endpoint_name: Name of the endpoint to switch to

    Returns:
        Confirmation of the switch or error if endpoint not found
    """
    # Find the endpoint by name
    target_index = None
    for i, endpoint in enumerate(oracle_service.all_endpoints):
        if endpoint.name == target_endpoint_name:
            target_index = i
            break

    if target_index is None:
        raise HTTPException(
            status_code=404,
            detail=f"Endpoint '{target_endpoint_name}' not found"
        )

    # Update the current endpoint index
    oracle_service._current_endpoint_index = target_index

    return {
        "message": f"Switched to endpoint '{target_endpoint_name}'",
        "current_endpoint": oracle_service.current_endpoint.name if oracle_service.current_endpoint else None
    }


@router.post("/feeds", response_model=OracleFeedResponse)
async def create_oracle_feed(
    feed_request: CreateOracleFeedRequest,
    oracle_service=Depends(get_oracle_service)
):
    """
    Create a new oracle feed configuration.
    
    Args:
        feed_request: Feed configuration data
        
    Returns:
        Created feed configuration
    """
    # Convert string data type to enum
    try:
        data_type = OracleDataType(feed_request.data_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid data type: {feed_request.data_type}. "
                   f"Must be one of: {[t.value for t in OracleDataType]}"
        )
    
    # Create OracleFeed object
    feed = OracleFeed(
        name=feed_request.name,
        box_id=feed_request.box_id,
        data_type=data_type,
        register_indices=feed_request.register_indices,
        description=feed_request.description,
        decimals=feed_request.decimals,
        base_asset=feed_request.base_asset,
        quote_asset=feed_request.quote_asset
    )
    
    # Add to oracle service
    oracle_service.add_oracle_feed(feed)
    
    return OracleFeedResponse(
        name=feed.name,
        box_id=feed.box_id,
        data_type=feed.data_type.value,
        register_indices=feed.register_indices,
        description=feed.description,
        decimals=feed.decimals,
        base_asset=feed.base_asset,
        quote_asset=feed.quote_asset
    )


@router.get("/feeds", response_model=List[OracleFeedResponse])
async def get_oracle_feeds(oracle_service=Depends(get_oracle_service)):
    """
    Get all configured oracle feeds.
    
    Returns:
        List of configured oracle feeds
    """
    feeds = oracle_service.get_configured_feeds()
    return [OracleFeedResponse(**feed) for feed in feeds]


@router.delete("/feeds/{feed_name}")
async def delete_oracle_feed(
    feed_name: str,
    oracle_service=Depends(get_oracle_service)
):
    """
    Delete an oracle feed configuration.
    
    Args:
        feed_name: Name of the feed to delete
        
    Returns:
        Success message or error
    """
    success = oracle_service.remove_oracle_feed(feed_name)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Feed '{feed_name}' not found"
        )
    
    return {"message": f"Feed '{feed_name}' deleted successfully"}


@router.get("/onchain/{feed_name}")
async def get_onchain_feed_data(
    feed_name: str,
    oracle_service=Depends(get_oracle_service)
):
    """
    Get data from an on-chain oracle feed.
    
    Args:
        feed_name: Name of the configured feed
        
    Returns:
        Oracle feed data
    """
    data = await oracle_service.get_on_chain_oracle_data(feed_name=feed_name)
    
    if data is None:
        raise HTTPException(
            status_code=404,
            detail=f"Feed '{feed_name}' not found or failed to fetch data"
        )
    
    return {"data": data}


@router.get("/onchain/box/{box_id}")
async def get_onchain_box_data(
    box_id: str,
    oracle_service=Depends(get_oracle_service)
):
    """
    Get data directly from an on-chain oracle box.
    
    Args:
        box_id: Box ID of the oracle
        
    Returns:
        Oracle box data
    """
    data = await oracle_service.get_on_chain_oracle_data(box_id=box_id)
    
    if data is None:
        raise HTTPException(
            status_code=404,
            detail=f"Oracle box '{box_id}' not found or failed to fetch data"
        )
    
    return {"data": data}


@router.get("/price/{base_asset}/{quote_asset}")
async def get_price_feed(
    base_asset: str,
    quote_asset: str,
    oracle_service=Depends(get_oracle_service)
):
    """
    Get the latest price feed for a specific asset pair.
    
    Args:
        base_asset: Base asset symbol (e.g., "ERG")
        quote_asset: Quote asset symbol (e.g., "USD")
        
    Returns:
        Price feed data
    """
    data = await oracle_service.get_latest_price_feed(base_asset, quote_asset)
    
    if data is None:
        raise HTTPException(
            status_code=404,
            detail=f"No price feed found for {base_asset}/{quote_asset}"
        )
    
    return {"data": data}
