"""
DuckPools - Shared rate limiter instance.

Single slowapi Limiter shared across all route modules to ensure
consistent rate limiting with a unified in-memory storage backend.

MAT-277: Implement rate limiting on all backend API endpoints
- 60 req/min for public GET endpoints
- 10 req/min for POST endpoints
- Stricter limits for /ergo-api/* proxy endpoints (20 req/min)
"""

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request

# Create limiter instance
# Default limits will be overridden by per-endpoint decorators
limiter = Limiter(key_func=get_remote_address, default_limits=[])


def get_limit_for_route(request: Request) -> str:
    """
    Determine rate limit based on request method and path.
    
    Args:
        request: Starlette request object
        
    Returns:
        Rate limit string (e.g., "60/minute", "10/minute")
    """
    # Stricter limits for Ergo API proxy endpoints
    if request.url.path.startswith("/ergo-api/"):
        return "20/minute"
    
    # POST endpoints: 10 req/min (write operations)
    if request.method == "POST":
        return "10/minute"
    
    # GET endpoints: 60 req/min (read operations)
    if request.method == "GET":
        return "60/minute"
    
    # Default fallback
    return "60/minute"
