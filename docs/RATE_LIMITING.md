# Rate Limiting Solution

## Overview

The DuckPools team has implemented a robust rate limiting solution to address the critical rate limiting issues affecting team velocity. This solution provides:

- **Automatic provider fallback** - Switches to backup providers when rate limits are exceeded
- **Exponential backoff retries** - Smart retry mechanism for failed requests
- **Multiple provider support** - Configurable primary and fallback providers
- **Usage monitoring** - Track provider usage and rate limit status
- **Configurable rate limits** - Adjust limits per provider

## Configuration

### Environment Variables

Configure your API providers using environment variables:

```bash
# Z.AI Provider Configuration
Z_AI_BASE_URL=https://api.z.ai/v1
Z_AI_API_KEY=your_z_ai_api_key_here
Z_AI_RATE_LIMIT=60  # Requests per minute

# Fallback Provider Configuration  
FALLBACK_PROVIDER_URL=https://api.fallback.com/v1
FALLBACK_PROVIDER_API_KEY=your_fallback_api_key_here
FALLBACK_PROVIDER_RATE_LIMIT=120  # Requests per minute
```

### Configuration File

The rate limiter uses a configuration file at `backend/rate_limiter_config.py` that loads provider settings from environment variables.

## Usage

### Basic Usage

```python
from backend.rate_limiter import rate_limiter

# Make a request with automatic rate limiting and fallback
response = rate_limiter.request("GET", "some/endpoint", params={"param": "value"})

# Access response data
data = response.json()
```

### Advanced Usage

```python
from backend.rate_limiter import RateLimiter, ProviderConfig

# Create custom provider configuration
providers = [
    ProviderConfig(
        name="z.ai",
        base_url="https://api.z.ai/v1",
        api_key="your_api_key",
        rate_limit=60,
        max_retries=3
    ),
    ProviderConfig(
        name="backup_provider",
        base_url="https://api.backup.com/v1", 
        api_key="backup_api_key",
        rate_limit=120,
        max_retries=3
    )
]

# Initialize rate limiter
limiter = RateLimiter(providers)

# Make request with custom configuration
response = limiter.request("POST", "data/endpoint", json={"data": "value"})

# Get provider usage statistics
stats = limiter.get_provider_stats()
print("Provider usage:", stats)
```

## Provider Management

### Adding New Providers

To add a new provider, update the `rate_limiter_config.py` file:

```python
@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_key: str
    rate_limit: int
    max_retries: int = 3
    timeout: int = 30

# Add new provider to the list
providers = [
    ProviderConfig(
        name="z.ai",
        base_url="https://api.z.ai/v1",
        api_key="your_api_key",
        rate_limit=60
    ),
    ProviderConfig(
        name="backup_provider",
        base_url="https://api.backup.com/v1",
        api_key="backup_api_key", 
        rate_limit=120
    ),
    ProviderConfig(
        name="new_provider",
        base_url="https://api.new.com/v1",
        api_key="new_api_key",
        rate_limit=100
    )
]
```

### Monitoring Provider Usage

```python
from backend.rate_limiter import rate_limiter

# Get current usage statistics
stats = rate_limiter.get_provider_stats()

for provider_name, provider_stats in stats.items():
    print(f"{provider_name}:")
    print(f"  Usage: {provider_stats['usage']}/{provider_stats['rate_limit']} ({provider_stats['usage_percentage']:.1f}%)")
    print(f"  Status: {'OK' if provider_stats['usage_percentage'] < 90 else 'Approaching limit'}")
```

## Troubleshooting

### Common Issues

1. **Rate limit exceeded**: The system will automatically switch to the next available provider
2. **Provider unavailable**: The system will try the next provider in the list
3. **Configuration errors**: Check environment variables and provider configuration

### Debugging

Enable debug logging to see detailed request information:

```bash
export LOG_LEVEL=DEBUG
python your_script.py
```

### Resetting Rate Limits

The rate limiter automatically resets usage every 60 seconds. If you need to force a reset:

```python
from backend.rate_limiter import rate_limiter

# Force reset (not typically needed)
rate_limiter._reset_usage_if_needed()
```

## Integration

The rate limiter is integrated into the DuckPools backend and can be used by any service that needs to make API requests to external providers.

### Backend Integration

The rate limiter is available as `rate_limiter` in the backend module:

```python
from backend import rate_limiter

# Use in any backend service
response = rate_limiter.request("GET", "api/endpoint")
```

### Frontend Integration

For frontend services, you can create a wrapper service that uses the rate limiter:

```python
# In a separate service that handles API requests
from backend.rate_limiter import rate_limiter

def make_api_request(endpoint, **kwargs):
    return rate_limiter.request("GET", endpoint, **kwargs)
```

## Best Practices

1. **Configure appropriate rate limits** for each provider based on their documentation
2. **Use higher rate limits for fallback providers** to ensure availability
3. **Monitor provider usage** regularly to detect issues early
4. **Test fallback mechanisms** to ensure they work as expected
5. **Document provider configurations** and API keys securely

## Related Issues

- [MAT-280] - Team status report identifying rate limiting as critical blocker
- [MAT-195] - Security audit identifying rate limiting needs
- [MAT-113] - API security hardening including rate limiting

## Future Enhancements

- Dynamic provider selection based on real-time performance
- Automatic provider health checking
- More sophisticated rate limit algorithms
- Integration with monitoring systems
- Alerting for rate limit approaches

For more information, see the [rate limiter implementation](backend/rate_limiter.py) and [configuration](backend/rate_limiter_config.py).