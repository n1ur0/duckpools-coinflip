# Rate Limiting Configuration and Usage

This document explains how to configure and use the rate limiting functionality for external API calls.

## Overview

The DuckPools Coinflip backend includes a rate limiting system that handles:
- Rate limiting for external API providers (like z.ai)
- Automatic fallback to secondary providers when rate limits are exceeded
- Retry logic with exponential backoff
- Health monitoring and statistics

## Configuration

### Environment Variables

Configure the rate limiter using environment variables:

```bash
# z.ai provider configuration
export Z_AI_BASE_URL="https://api.z.ai/v1"
export Z_AI_API_KEY="your_z_ai_api_key"
export Z_AI_RATE_LIMIT="60"  # requests per minute

# Fallback provider configuration  
export FALLBACK_PROVIDER_URL="https://api.fallback.com/v1"
export FALLBACK_PROVIDER_API_KEY="your_fallback_api_key" 
export FALLBACK_PROVIDER_RATE_LIMIT="120"  # requests per minute
```

### Environment File Example

Create a `.env` file in the backend directory:

```env
# z.ai provider
Z_AI_BASE_URL=https://api.z.ai/v1
Z_AI_API_KEY=your_actual_z_ai_api_key
Z_AI_RATE_LIMIT=60

# Fallback provider
FALLBACK_PROVIDER_URL=https://api.fallback.com/v1
FALLBACK_PROVIDER_API_KEY=your_actual_fallback_api_key
FALLBACK_PROVIDER_RATE_LIMIT=120
```

## Usage

### Basic Usage

The rate limiter is automatically initialized when the API server starts. Use the `make_rate_limited_request` function to make API calls:

```python
from backend.rate_limited_client import make_rate_limited_request

# Make a GET request
response = make_rate_limited_request("GET", "some/endpoint", params={"param": "value"})

# Make a POST request
response = make_rate_limited_request("POST", "some/endpoint", json={"key": "value"})
```

### Advanced Usage

For more control, use the `RateLimitedClient` class directly:

```python
from backend.rate_limited_client import RateLimitedClient, ProviderConfig

# Create custom providers
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

# Create client
client = RateLimitedClient(providers)

# Make requests
response = client.get("some/endpoint", params={"param": "value"})
response = client.post("some/endpoint", json={"key": "value"})
```

## Monitoring

The rate limiter provides statistics about provider usage:

```python
from backend.rate_limited_client import rate_limited_client

# Get provider statistics
stats = rate_limited_client.rate_limiter.get_provider_stats()
print(stats)
```

## Troubleshooting

### Common Issues

1. **Rate limiter not initializing**: Check that environment variables are set correctly
2. **429 errors**: Verify that API keys are valid and rate limits are configured properly
3. **Connection errors**: Ensure the provider URLs are accessible

### Debugging

Enable debug logging to see detailed rate limiter activity:

```bash
export LOG_LEVEL=DEBUG
```

## Integration

The rate limiter is integrated into the API server and available throughout the backend. Any external API calls should use the rate-limited client to ensure proper rate limiting and fallback behavior.