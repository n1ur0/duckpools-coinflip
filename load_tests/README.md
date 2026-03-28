# DuckPools Load Testing Framework

Comprehensive load testing framework for DuckPools API endpoints, focusing on concurrent bet placement and bankroll stress testing.

## Overview

This framework uses [Locust](https://locust.io/) to simulate realistic player behavior and stress test the DuckPools API under various load conditions.

### Key Features

- **Concurrent Bet Placement**: Simulates multiple players placing Plinko bets simultaneously
- **Bankroll Stress Testing**: Aggressive betting patterns to test liquidity management
- **Response Time Monitoring**: Tracks API performance under different load levels
- **Predefined Scenarios**: Ready-to-use test profiles for different use cases
- **HTML Reports**: Generates detailed performance reports with statistics and charts

## Installation

### Prerequisites

- Python 3.8+
- DuckPools API running (default: http://localhost:8000)

### Setup

1. Install dependencies:
   ```bash
   cd /Users/n1ur0/projects/worktrees/agent/performance-tester-jr/8866682c-load-testing-framework/load_tests
   pip install -r requirements.txt
   ```

2. Ensure DuckPools API is running:
   ```bash
   cd /Users/n1ur0/projects/DuckPools
   pm2 start ecosystem.config.js
   ```

## Quick Start

### Using the Test Runner

The easiest way to run tests is using the provided runner script:

```bash
# List all available scenarios
python run_test.py list

# Run a smoke test (quick sanity check)
python run_test.py smoke

# Run a normal load test with web UI
python run_test.py normal

# Run a stress test in headless mode (no web UI)
python run_test.py stress --headless

# Run a peak load test with 4 workers (distributed testing)
python run_test.py peak --workers 4
```

### Using Locust Directly

For more control, you can run Locust directly:

```bash
# With web UI (recommended for development)
locust -f locustfile.py --host http://localhost:8000

# Headless mode (for CI/CD or automated testing)
locust -f locustfile.py --host http://localhost:8000 \
  --users 50 --spawn-rate 10 --run-time 5m --headless
```

## Test Scenarios

### Available Scenarios

| Scenario | Users | Duration | Description |
|----------|-------|----------|-------------|
| `smoke` | 10 | 1m | Quick sanity check with minimal load |
| `normal` | 50 | 10m | Simulates expected production traffic |
| `peak` | 200 | 15m | Simulates high-traffic periods |
| `stress` | 100 | 20m | Aggressive betting to test bankroll management |
| `burst` | 150 | 5m | Sudden traffic spike simulation |
| `endurance` | 50 | 1h | Long-duration test for memory leak detection |

### Scenario Details

#### Smoke Test
- **Purpose**: Quick sanity check after deployment
- **Load**: 10 concurrent users, 5 spawn rate
- **Duration**: 1 minute
- **User Classes**: DuckPoolsUser (normal pace)

#### Normal Load
- **Purpose**: Baseline performance measurement
- **Load**: 50 concurrent users, 10 spawn rate
- **Duration**: 10 minutes
- **User Classes**: DuckPoolsUser (normal pace)

#### Peak Load
- **Purpose**: Test system under high traffic
- **Load**: 200 concurrent users, 20 spawn rate
- **Duration**: 15 minutes
- **User Classes**: DuckPoolsUser (normal pace)

#### Bankroll Stress
- **Purpose**: Stress test bankroll management and liquidity checks
- **Load**: 100 concurrent users (mix of normal and aggressive), 25 spawn rate
- **Duration**: 20 minutes
- **User Classes**: DuckPoolsUser, BankrollStressUser
- **Focus**: Race conditions, liquidity exhaustion handling

#### Burst Test
- **Purpose**: Simulate sudden traffic spikes (e.g., after social media mention)
- **Load**: 150 concurrent users, 50 spawn rate (fast ramp-up)
- **Duration**: 5 minutes
- **User Classes**: DuckPoolsUser (normal pace)

#### Endurance Test
- **Purpose**: Detect memory leaks and stability issues over time
- **Load**: 50 concurrent users, 5 spawn rate
- **Duration**: 1 hour
- **User Classes**: DuckPoolsUser (normal pace)

## User Classes

### DuckPoolsUser (Normal Player)
Simulates realistic player behavior:
- **Wait Time**: 2-5 seconds between bets (simulates thinking time)
- **Betting**: Mix of small (0.1 ERG) to medium (5 ERG) bets
- **Workload**: 75% bet placement, 25% read operations (pool state, price, etc.)
- **Wallet**: Random selection from 3 test addresses

### BankrollStressUser (Aggressive Bettor)
Simulates high-frequency betting for stress testing:
- **Wait Time**: 0.5-1 seconds between bets (very aggressive)
- **Betting**: Fixed 0.5 ERG bets for predictable stress patterns
- **Workload**: 100% bet placement
- **Focus**: Test concurrency, race conditions, liquidity management

## Endpoints Tested

### Write Operations
- `POST /api/plinko/place-bet` - Place Plinko bets

### Read Operations
- `GET /api/lp/pool` - Get pool state
- `GET /api/lp/price` - Get LP token price
- `GET /api/plinko/multipliers` - Get Plinko multipliers

## Reports

Test results are automatically saved to the `reports/` directory:

### HTML Report
Interactive HTML report with:
- Request statistics (total, failures, RPS)
- Response time charts (min, avg, median, p95, p99)
- Response time distribution
- Percentile charts over time

### CSV Reports
Raw data files for custom analysis:
- `{scenario}_{run_time}_stats.csv` - Statistics summary
- `{scenario}_{run_time}_stats_history.csv` - Request history
- `{scenario}_{run_time}_failures.csv` - Failure details

### Console Output
Real-time statistics printed to console:
- Total requests
- Failed requests
- Success rate
- Response time (avg, p95, p99)
- Requests per second

## Key Metrics

### Performance Targets (Guidelines)

| Metric | Target | Notes |
|--------|--------|-------|
| Avg Response Time | < 200ms | For /api/plinko/place-bet |
| p95 Response Time | < 500ms | For /api/plinko/place-bet |
| p99 Response Time | < 1000ms | For /api/plinko/place-bet |
| Success Rate | > 99.5% | Under normal load |
| Concurrency | 200+ concurrent | Without degradation |

### What to Monitor

1. **Response Times**: Increasing times indicate bottlenecks
2. **Error Rates**: Spikes in errors suggest concurrency issues
3. **Success Rate**: Should stay >99.5% under normal load
4. **RPS**: Requests per second - higher is better
5. **Pool Liquidity**: API errors when bankroll is exhausted (expected in stress tests)

## Distributed Testing

For large-scale tests, run Locust in distributed mode:

### Master Node
```bash
locust -f locustfile.py --master --host http://localhost:8000
```

### Worker Nodes
```bash
locust -f locustfile.py --worker --master-host=<master-ip>
```

### Using the Runner Script
```bash
python run_test.py peak --workers 4
```

This automatically runs distributed mode with 4 worker processes.

## Troubleshooting

### Common Issues

**Connection Refused**
- Ensure DuckPools API is running: `pm2 status`
- Check API host/port in config

**Rate Limiting (429 errors)**
- Expected under heavy load
- Reduce spawn rate or user count

**Liquidity Errors**
- Normal in stress tests
- Pool bankroll may be exhausted
- Check `GET /api/lp/pool` for current liquidity

**Slow Response Times**
- Check database connection pool
- Monitor Ergo node latency
- Review transaction building performance

### Debug Mode

Enable debug logging:
```bash
locust -f locustfile.py --loglevel DEBUG
```

## CI/CD Integration

For automated testing in CI/CD pipelines:

```bash
# Run smoke test and fail if success rate < 99%
python run_test.py smoke --headless

# Check results (parse CSV or HTML report)
# Example: Fail if error rate > 1%
if grep -q "Failed requests: 0" reports/smoke_1m_stats.csv; then
  echo "✓ Smoke test passed"
else
  echo "✗ Smoke test failed"
  exit 1
fi
```

## Best Practices

1. **Start Small**: Always run smoke test before larger tests
2. **Monitor System Resources**: Use tools like `htop` to monitor CPU/memory during tests
3. **Test Against Production-like Data**: Use realistic bet amounts and patterns
4. **Review Logs**: Check DuckPools API logs for errors during tests
5. **Compare Results**: Track performance over time to detect regressions

## Contributing

When adding new test scenarios:
1. Update `config.py` with scenario definition
2. Add appropriate user classes to `locustfile.py` if needed
3. Document the scenario in this README
4. Test the scenario locally before committing

## License

This load testing framework is part of the DuckPools project.
