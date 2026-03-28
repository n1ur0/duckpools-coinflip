"""
DuckPools - Oracle Routes

API endpoints for oracle health monitoring and status.

MAT-31: Oracle health monitoring and failover
"""

from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

# Create router
router = APIRouter(prefix="/api/oracle", tags=["oracle"])


async def get_oracle_service():
    """Dependency to get the oracle service from app state."""
    from fastapi import Request

    async def _get_oracle_service(request: Request):
        service = getattr(request.app.state, "oracle_service", None)
        if not service:
            raise HTTPException(status_code=503, detail="Oracle service not initialized")
        return service

    return _get_oracle_service


@router.get("/health")
async def get_oracle_health(oracle_service=Depends(get_oracle_service())):
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
async def get_oracle_status(oracle_service=Depends(get_oracle_service())):
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
async def get_oracle_endpoints(oracle_service=Depends(get_oracle_service())):
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
    oracle_service=Depends(get_oracle_service())
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


@router.post("/switch")
async def switch_oracle_endpoint(
    target_endpoint_name: str,
    oracle_service=Depends(get_oracle_service())
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
