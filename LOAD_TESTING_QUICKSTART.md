# Load Testing Framework - Quick Start

This directory contains a comprehensive load testing framework for DuckPools API endpoints.

## What's Included

- **locustfile.py** - Main load test definitions with realistic user behavior
- **config.py** - Predefined test scenarios (smoke, normal, peak, stress, burst, endurance)
- **run_test.py** - Convenient test runner script
- **test_data_generator.py** - Unit tests for test data generation
- **setup.sh** - One-command setup script
- **README.md** - Complete documentation

## Quick Start (3 Steps)

### 1. Install Dependencies

```bash
cd load_tests
./setup.sh
```

Or manually:
```bash
pip install -r requirements.txt
```

### 2. Start DuckPools API

```bash
cd /Users/n1ur0/projects/DuckPools
pm2 start ecosystem.config.js
```

### 3. Run Your First Test

```bash
# List available test scenarios
python run_test.py list

# Run a quick smoke test
python run_test.py smoke
```

That's it! The test will open a web UI at http://localhost:8089 where you can start the test.

## Available Test Scenarios

| Scenario | Users | Duration | Purpose |
|----------|-------|----------|---------|
| smoke | 10 | 1m | Quick sanity check |
| normal | 50 | 10m | Baseline performance |
| peak | 200 | 15m | High traffic simulation |
| stress | 100 | 20m | Bankroll stress testing |
| burst | 150 | 5m | Sudden traffic spike |
| endurance | 50 | 1h | Memory leak detection |

## Examples

### Run smoke test with web UI
```bash
python run_test.py smoke
```

### Run normal test in headless mode (CLI only)
```bash
python run_test.py normal --headless
```

### Run stress test with 4 workers (distributed)
```bash
python run_test.py stress --workers 4
```

### Run endurance test overnight
```bash
nohup python run_test.py endurance --headless > endurance.log 2>&1 &
```

## Test Reports

All test results are automatically saved to the `reports/` directory:
- HTML reports (interactive)
- CSV files (for analysis)
- Console output (real-time)

## What Gets Tested

### Core Functionality
- **Concurrent Bet Placement**: Multiple players placing Plinko bets simultaneously
- **Bankroll Stress Testing**: Aggressive betting patterns to test liquidity management
- **Pool State Queries**: Read operations on pool liquidity and pricing

### API Endpoints
- `POST /api/plinko/place-bet` - Bet placement (write operations)
- `GET /api/lp/pool` - Pool state (read operations)
- `GET /api/lp/price` - Token pricing (read operations)
- `GET /api/plinko/multipliers` - Game metadata (read operations)

### User Classes
- **DuckPoolsUser**: Normal player (2-5s between bets)
- **BankrollStressUser**: Aggressive bettor (0.5-1s between bets)

## Performance Targets

| Metric | Target |
|--------|--------|
| Avg Response Time | < 200ms |
| p95 Response Time | < 500ms |
| p99 Response Time | < 1000ms |
| Success Rate | > 99.5% |
| Max Concurrent Users | 200+ |

## Using Locust Directly

For advanced usage, you can run Locust directly:

```bash
# With web UI
locust -f locustfile.py --host http://localhost:8000

# Headless mode
locust -f locustfile.py --host http://localhost:8000 \
  --users 50 --spawn-rate 10 --run-time 5m --headless

# Distributed mode (master)
locust -f locustfile.py --master --host http://localhost:8000

# Distributed mode (worker)
locust -f locustfile.py --worker --master-host=<master-ip>
```

## Need Help?

See the complete documentation in `load_tests/README.md` for:
- Detailed scenario descriptions
- Troubleshooting guide
- CI/CD integration examples
- Best practices
- Custom configuration

## Integration with CI/CD

For automated testing:

```bash
# Run smoke test and check results
python run_test.py smoke --headless

# Check success rate (example)
if grep -q "Failed requests: 0" reports/smoke_1m_stats.csv; then
  echo "✓ Smoke test passed"
else
  echo "✗ Smoke test failed"
  exit 1
fi
```

## Support

For issues or questions:
1. Check `load_tests/README.md` for detailed documentation
2. Review `test_data_generator.py` for test data generation examples
3. Use `python run_test.py list` to see all available scenarios
