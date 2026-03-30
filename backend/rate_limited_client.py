"""
Rate Limited API Client

Provides a simple interface for making API calls with rate limiting and fallback support.
"""

import logging
from typing import Any, Dict, Optional, Callable
import requests
from rate_limiter import RateLimiter, ProviderConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RateLimitedClient:
    """Client for making rate-limited API calls with fallback support."""
    
    def __init__(self, providers: list[ProviderConfig]):
        """
        Initialize the rate-limited client.
        
        Args:
            providers: List of ProviderConfig objects for rate limiting
        """
        self.rate_limiter = RateLimiter(providers)
        self.session = requests.Session()
        
    def request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make a rate-limited API request.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            **kwargs: Additional request parameters
            
        Returns:
            JSON response as dictionary
            
        Raises:
            requests.exceptions.RequestException: If all retries fail
        """
        return self.rate_limiter.request(method, endpoint, **kwargs)
    
    def get(self, url: str, **kwargs) -> Dict[str, Any]:
        """Make a GET request with rate limiting."""
        return self.request("GET", url, **kwargs)
    
    def post(self, url: str, data: Optional[Dict] = None, json: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """Make a POST request with rate limiting."""
        return self.request("POST", url, data=data, json=json, **kwargs)
    
    def put(self, url: str, data: Optional[Dict] = None, json: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """Make a PUT request with rate limiting."""
        return self.request("PUT", url, data=data, json=json, **kwargs)
    
    def delete(self, url: str, **kwargs) -> Dict[str, Any]:
        """Make a DELETE request with rate limiting."""
        return self.request("DELETE", url, **kwargs)


# Global rate-limited client instance
try:
    from .rate_limiter_config import load_provider_config
    rate_limited_client = RateLimitedClient(load_provider_config())
    logger.info("Rate limited client initialized successfully")
except Exception as e:
    rate_limited_client = None
    logger.error(f"Failed to initialize rate limited client: {str(e)}")
    logger.warning("Rate limited client not available. External API calls may be rate limited.")


def make_rate_limited_request(
    method: str, 
    endpoint: str, 
    **kwargs
) -> Dict[str, Any]:
    """
    Make a rate-limited API request using the global client.
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        endpoint: API endpoint path
        **kwargs: Additional request parameters
        
    Returns:
        JSON response as dictionary
        
    Raises:
        requests.exceptions.RequestException: If all retries fail
    """
    if rate_limited_client is None:
        raise RuntimeError("Rate limited client is not available")
    
    return rate_limited_client.request(method, endpoint, **kwargs)


# Example usage
if __name__ == "__main__":
    # Example configuration
    providers = [
        ProviderConfig(
            name="z.ai",
            base_url="https://api.z.ai/v1",
            api_key="your_api_key",
            rate_limit=60,
            max_retries=3,
            timeout=30
        ),
        ProviderConfig(
            name="fallback_provider", 
            base_url="https://api.fallback.com/v1",
            api_key="your_fallback_api_key",
            rate_limit=120,
            max_retries=3,
            timeout=30
        )
    ]
    
    client = RateLimitedClient(providers)
    
    try:
        # Example GET request
        response = client.get("some/endpoint", params={"param": "value"})
        print("Response:", response)
        
        # Example POST request  
        response = client.post("some/endpoint", json={"key": "value"})
        print("Response:", response)
        
    except Exception as e:
        print("Request failed:", str(e))