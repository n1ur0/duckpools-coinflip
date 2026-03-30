"""
Rate Limiter Configuration

Configuration for API providers used by the DuckPools team.
"""

from dataclasses import dataclass
from typing import List

@dataclass
class ProviderConfig:
    """Configuration for an API provider"""
    name: str
    base_url: str
    api_key: str
    rate_limit: int  # requests per minute
    max_retries: int = 3
    timeout: int = 30

# Default configuration - should be overridden by environment variables
DEFAULT_PROVIDERS = [
    ProviderConfig(
        name="z.ai",
        base_url="https://api.z.ai/v1",
        api_key="***",  # Replace with actual API key
        rate_limit=60,  # Default rate limit (60 requests per minute)
        max_retries=3,
        timeout=30
    ),
    ProviderConfig(
        name="fallback_provider",
        base_url="https://api.fallback.com/v1",
        api_key="***",  # Replace with actual API key
        rate_limit=120,  # Higher rate limit for fallback (120 requests per minute)
        max_retries=3,
        timeout=30
    )
]

# Environment variable mappings
ENV_VAR_MAPPINGS = {
    "Z_AI_BASE_URL": "base_url",
    "Z_AI_API_KEY": "api_key", 
    "Z_AI_RATE_LIMIT": "rate_limit",
    "FALLBACK_PROVIDER_URL": "base_url",
    "FALLBACK_PROVIDER_API_KEY": "api_key",
    "FALLBACK_PROVIDER_RATE_LIMIT": "rate_limit"
}

def load_provider_config() -> List[ProviderConfig]:
    """Load provider configuration from environment variables or use defaults"""
    import os
    
    # Initialize providers with defaults
    providers = []
    
    # Load z.ai provider configuration
    z_ai_config = DEFAULT_PROVIDERS[0].__dict__.copy()
    for env_var, config_key in ENV_VAR_MAPPINGS.items():
        if env_var.startswith("Z_AI_"):
            env_value = os.getenv(env_var)
            if env_value is not None:
                if config_key == "rate_limit":
                    z_ai_config[config_key] = int(env_value)
                else:
                    z_ai_config[config_key] = env_value
    providers.append(ProviderConfig(**z_ai_config))
    
    # Load fallback provider configuration  
    fallback_config = DEFAULT_PROVIDERS[1].__dict__.copy()
    for env_var, config_key in ENV_VAR_MAPPINGS.items():
        if env_var.startswith("FALLBACK_PROVIDER_"):
            env_value = os.getenv(env_var)
            if env_value is not None:
                if config_key == "rate_limit":
                    fallback_config[config_key] = int(env_value)
                else:
                    fallback_config[config_key] = env_value
    providers.append(ProviderConfig(**fallback_config))
    
    return providers

# Initialize rate limiter with configured providers
try:
    from .rate_limiter import RateLimiter
    rate_limiter = RateLimiter(load_provider_config())
except ImportError:
    # Fallback if rate_limiter module is not available
    rate_limiter = None
    logger = logging.getLogger(__name__)
    logger.warning("Rate limiter not available. API calls may be rate limited.")