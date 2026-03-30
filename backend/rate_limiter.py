"""
Rate Limiter with Fallback Provider Support

Handles rate limiting for API providers with retry mechanisms and fallback support.
Supports multiple providers to prevent service disruptions due to rate limits.
"""

import time
import logging
import random
from typing import Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass
import requests
import backoff

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ProviderConfig:
    """Configuration for an API provider"""
    name: str
    base_url: str
    api_key: str
    rate_limit: int  # requests per minute
    max_retries: int = 3
    timeout: int = 30

class RateLimiter:
    """Rate limiter with provider fallback support"""
    
    def __init__(self, providers: List[ProviderConfig]):
        self.providers = providers
        self.current_provider_index = 0
        self.provider_usage = {provider.name: 0 for provider in providers}
        self.last_reset_time = time.time()
        self.reset_interval = 60  # Reset usage every minute
        
    def _reset_usage_if_needed(self):
        """Reset usage counters if reset interval has passed"""
        current_time = time.time()
        if current_time - self.last_reset_time >= self.reset_interval:
            self.provider_usage = {provider.name: 0 for provider in self.providers}
            self.last_reset_time = current_time
    
    def _select_provider(self) -> ProviderConfig:
        """Select the next available provider"""
        self._reset_usage_if_needed()
        
        # Try to find a provider that hasn't exceeded its rate limit
        for i in range(len(self.providers)):
            provider = self.providers[self.current_provider_index]
            if self.provider_usage[provider.name] < provider.rate_limit:
                return provider
            
            # Move to next provider if current one is over limit
            self.current_provider_index = (self.current_provider_index + 1) % len(self.providers)
        
        # If all providers are over limit, select random one and reset usage
        logger.warning(f"All providers over rate limit. Resetting usage and selecting random provider.")
        self.provider_usage = {provider.name: 0 for provider in self.providers}
        return random.choice(self.providers)
    
    @backoff.on_exception(
        backoff.expo,
        (requests.exceptions.RequestException, requests.exceptions.HTTPError),
        max_tries=3,
        giveup=lambda e: e.response and e.response.status_code not in (429, 500, 503)
    )
    def _make_request_with_retry(self, provider: ProviderConfig, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make request with exponential backoff retry"""
        headers = kwargs.get('headers', {})
        headers['Authorization'] = f"Bearer {provider.api_key}"
        kwargs['headers'] = headers
        
        url = f"{provider.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        logger.info(f"Making request to {provider.name}: {method} {url}")
        
        response = requests.request(method, url, **kwargs)
        
        # Track usage
        self.provider_usage[provider.name] += 1
        
        # Handle rate limiting
        if response.status_code == 429:
            reset_time = int(response.headers.get('X-RateLimit-Reset', 60))
            logger.warning(f"Rate limit exceeded for {provider.name}. Reset in {reset_time} seconds.")
            time.sleep(reset_time + 1)  # Wait for reset plus buffer
            raise requests.exceptions.HTTPError("Rate limit exceeded", response=response)
        
        response.raise_for_status()
        return response
    
    def request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make request using available provider with fallback support"""
        provider = self._select_provider()
        
        try:
            return self._make_request_with_retry(provider, method, endpoint, **kwargs)
        except Exception as e:
            logger.error(f"Request failed with {provider.name}: {str(e)}")
            
            # Try next provider on failure
            self.current_provider_index = (self.current_provider_index + 1) % len(self.providers)
            next_provider = self.providers[self.current_provider_index]
            logger.info(f"Trying fallback provider: {next_provider.name}")
            
            return self._make_request_with_retry(next_provider, method, endpoint, **kwargs)
    
    def get_provider_stats(self) -> Dict[str, Dict]:
        """Get current provider usage statistics"""
        self._reset_usage_if_needed()
        return {
            provider.name: {
                'usage': self.provider_usage[provider.name],
                'rate_limit': provider.rate_limit,
                'usage_percentage': (self.provider_usage[provider.name] / provider.rate_limit) * 100
            }
            for provider in self.providers
        }

# Example usage
if __name__ == "__main__":
    # Example provider configuration
    providers = [
        ProviderConfig(
            name="z.ai",
            base_url="https://api.z.ai/v1",
            api_key="your_z_ai_api_key",
            rate_limit=60  # 60 requests per minute
        ),
        ProviderConfig(
            name="fallback_provider",
            base_url="https://api.fallback.com/v1",
            api_key="your_fallback_api_key", 
            rate_limit=120  # Higher rate limit
        )
    ]
    
    limiter = RateLimiter(providers)
    
    try:
        # Example request
        response = limiter.request("GET", "some/endpoint", params={"param": "value"})
        print("Request successful:", response.json())
    except Exception as e:
        print("Request failed:", str(e))
    
    # Print provider stats
    print("Provider Stats:", limiter.get_provider_stats())