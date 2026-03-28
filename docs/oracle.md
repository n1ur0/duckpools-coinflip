# DuckPools Oracle Service

## Overview

The DuckPools Oracle Service provides health monitoring, stale feed detection, automatic failover, and alerting for Ergo Oracle Pool integrations.

## Features

### Health Monitoring
- Periodic health checks for all configured oracle endpoints
- Latency measurement for each endpoint
- Real-time health status tracking

### Stale Feed Detection
- Monitors time since last successful feed update
- Configurable stale threshold (default: 5 minutes)
- Automatic alerts when feeds become stale

### Automatic Failover
- Transparent failover to backup oracle endpoints
- Endpoint priority-based selection
- Returns to primary endpoint when available

### Alerting
- Logs alerts on oracle failures
- Logs alerts when feeds become stale
- Can be extended to external notification systems

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ORACLE_PRIMARY_URL` | `https://api.oraclepool.xyz` | Primary oracle endpoint URL |
| `ORACLE_BACKUP_URLS` | (empty) | Comma-separated backup oracle URLs |
| `ORACLE_STALE_THRESHOLD_SECONDS` | `300` | Time before considering feed stale (seconds) |
| `ORACLE_HEALTH_CHECK_INTERVAL_SECONDS` | `30` | Health check interval (seconds) |

### Example Configuration

```bash
ORACLE_PRIMARY_URL=https://api.oraclepool.xyz
ORACLE_BACKUP_URLS=https://backup1.oraclepool.com,https://backup2.oraclepool.com
ORACLE_STALE_THRESHOLD_SECONDS=300
ORACLE_HEALTH_CHECK_INTERVAL_SECONDS=30
```

## API Endpoints

### GET /api/oracle/health

Get health status of all oracle endpoints.

**Response:**
```json
{
  "primary": {
    "url": "https://api.oraclepool.xyz",
    "is_primary": true,
    "is_current": true,
    "status": "healthy",
    "last_updated": "2026-03-28T00:00:00Z",
    "latency_ms": 123.45,
    "error": null
  },
  "backup-2": {
    "url": "https://backup1.oraclepool.com",
    "is_primary": false,
    "is_current": false,
    "status": "healthy",
    "last_updated": "2026-03-28T00:00:00Z",
    "latency_ms": 156.78,
    "error": null
  }
}
```

**Status Values:**
- `healthy`: Endpoint is responding normally
- `stale`: Feed hasn't been updated within threshold
- `unreachable`: Endpoint is not responding
- `error`: Endpoint returned an error

### GET /api/oracle/status

Get overall oracle service status.

**Response:**
```json
{
  "status": "ok",
  "current_endpoint": "primary",
  "total_endpoints": 3,
  "last_feed_update": "2026-03-28T00:00:00Z",
  "config": {
    "stale_threshold_seconds": 300,
    "health_check_interval_seconds": 30,
    "enable_failover": true
  }
}
```

**Status Values:**
- `ok`: Service operating normally
- `stale`: Feed is stale but endpoint reachable
- `degraded`: Current endpoint is unreachable
- `no_endpoints`: No endpoints configured

### GET /api/oracle/endpoints

Get list of all configured oracle endpoints.

**Response:**
```json
{
  "endpoints": [
    {
      "name": "primary",
      "url": "https://api.oraclepool.xyz",
      "is_primary": true,
      "is_current": true,
      "priority": 1
    },
    {
      "name": "backup-2",
      "url": "https://backup1.oraclepool.com",
      "is_primary": false,
      "is_current": false,
      "priority": 2
    }
  ]
}
```

### POST /api/oracle/data/{oracle_box_id}

Fetch data from the oracle with automatic failover.

**Parameters:**
- `oracle_box_id` (path): The oracle box ID to fetch data from
- `feed_name` (query, optional): Specific feed name to filter

**Response:**
```json
{
  "data": {
    "price": "1.23",
    "timestamp": 1234567890
  }
}
```

**Error Response (503):**
```json
{
  "detail": "Failed to fetch oracle data from all endpoints"
}
```

### POST /api/oracle/switch

Manually switch to a different oracle endpoint.

**Parameters:**
- `target_endpoint_name` (query): Name of the endpoint to switch to

**Response:**
```json
{
  "message": "Switched to endpoint 'backup-2'",
  "current_endpoint": "backup-2"
}
```

**Error Response (404):**
```json
{
  "detail": "Endpoint 'nonexistent' not found"
}
```

## Usage Examples

### Fetching Oracle Data

```python
from backend.oracle_service import OracleService, OracleConfig

config = OracleConfig(
    primary_oracle_url="https://api.oraclepool.xyz",
    backup_oracle_urls=["https://backup1.oraclepool.com"],
)

service = OracleService(config=config)
await service.start()

# Fetch oracle data with automatic failover
data = await service.get_oracle_data(
    oracle_box_id="your-oracle-box-id",
    feed_name="ERG_USD"
)

if data:
    print(f"Oracle data: {data}")
else:
    print("All endpoints failed")

await service.stop()
```

### Checking Health Status

```python
from backend.oracle_service import OracleService, OracleConfig

config = OracleConfig()
service = OracleService(config=config)

# Get health status for all endpoints
health_status = service.get_health_status()
for name, health in health_status.items():
    print(f"{name}: {health['status']} ({health['latency_ms']}ms)")

# Get overall service status
service_status = service.get_service_status()
print(f"Service status: {service_status['status']}")
```

### Monitoring with Alerts

The oracle service logs alerts automatically:

```
2026-03-28 00:00:00 WARNING ORACLE ALERT: primary failed: Timeout
2026-03-28 00:00:01 WARNING Failing over to backup-2
2026-03-28 00:30:00 WARNING ORACLE ALERT: Feed is stale. Last update: 2026-03-28T00:00:00Z (1800s ago)
```

## Integration with Health Check

The oracle service is integrated into the main `/health` endpoint:

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "ok",
  "node": "http://localhost:9052",
  "node_height": 123456,
  "pool_configured": true,
  "oracle_status": "ok",
  "oracle_endpoint": "primary"
}
```

When oracle is degraded:
```json
{
  "status": "degraded",
  "oracle_status": "stale",
  "oracle_endpoint": "primary",
  "oracle_error": "Feed is stale"
}
```

## Testing

Run the oracle service tests:

```bash
cd tests
pytest test_oracle.py -v
```

## Troubleshooting

### All endpoints failing

1. Check network connectivity:
   ```bash
   curl https://api.oraclepool.xyz/info
   ```

2. Verify oracle endpoint URLs are correct in `.env`

3. Check logs for specific error messages

### Frequent failovers

1. Check endpoint health status via `/api/oracle/health`

2. Review latency metrics - high latency may indicate network issues

3. Consider adjusting `health_check_interval_seconds`

### Stale feed alerts

1. Verify oracle pool is publishing updates

2. Check `stale_threshold_seconds` is appropriate for your use case

3. Review oracle documentation for expected update frequency

## Architecture

### Components

- **OracleService**: Main service class managing endpoints and health checks
- **OracleConfig**: Configuration model with validation
- **OracleEndpoint**: Dataclass for endpoint configuration
- **OracleHealth**: Dataclass for health check results
- **oracle_routes**: FastAPI router with oracle endpoints

### Health Check Loop

1. Periodically checks all endpoints (default: every 30 seconds)
2. Measures latency for each endpoint
3. Checks if feed is stale (no updates within threshold)
4. Updates health status for each endpoint
5. Logs alerts on failures or staleness

### Failover Logic

1. When current endpoint fails, service tries next endpoint in priority order
2. Health check continues to monitor failed endpoints
3. If primary becomes healthy again, it can be manually switched back
4. Automatic return to primary can be added if needed

## Security Considerations

- Oracle endpoint URLs should be kept secure
- Consider using HTTPS endpoints for production
- Implement rate limiting if exposing oracle data endpoints publicly
- Monitor for unusual failover patterns (may indicate attacks)

## Future Enhancements

- Automatic return to primary endpoint when healthy
- External notification systems (Discord, email, PagerDuty)
- Oracle data caching with TTL
- Metrics export (Prometheus, OpenTelemetry)
- Circuit breaker pattern for failing endpoints
- Oracle reputation/scoring system
