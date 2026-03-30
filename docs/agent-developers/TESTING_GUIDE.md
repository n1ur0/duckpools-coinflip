# DuckPools CoinFlip - Testing Guide

This guide provides comprehensive testing procedures for the DuckPools CoinFlip system.

## Testing Overview

The DuckPools CoinFlip system has multiple testing layers:
1. **Unit Tests**: Individual component testing
2. **Integration Tests**: Component interaction testing
3. **E2E Tests**: Full system workflow testing
4. **Contract Tests**: Smart contract validation
5. **Performance Tests**: Load and stress testing

## Testing Setup

### Prerequisites

- Python 3.8+
- Node.js 16+
- Docker
- Testing frameworks (pytest, Jest, etc.)

### Test Environment

```bash
# Start test environment
docker-compose -f docker-compose.test.yml up -d

# Run tests
pytest backend/tests/
npm test frontend/
```

## Unit Testing

### Backend Unit Tests

#### Python Tests

```python
# backend/tests/test_game_routes.py example
import pytest
from fastapi.testclient import TestClient
from api_server import app

client = TestClient(app)

def test_place_bet():
    response = client.post(
        "/place-bet",
        json={
            "player_address": "test_address",
            "amount": 1000000,
            "choice": 0,
            "secret": "test_secret"
        }
    )
    assert response.status_code == 200
    assert "bet_id" in response.json()
```

#### Test Structure

```
backend/tests/
├── test_game_routes.py    # Game API endpoints
├── test_rng_module.py    # RNG functionality
├── test_utils.py        # Utility functions
└── conftest.py          # Test fixtures
```

### Frontend Unit Tests

#### JavaScript Tests

```javascript
// frontend/src/components/CoinFlipGame.test.tsx
import { render, screen } from '@testing-library/react';
import CoinFlipGame from './CoinFlipGame';

test('renders coin flip game', () => {
  render(<CoinFlipGame />);
  expect(screen.getByText('Coin Flip Game')).toBeInTheDocument();
});
```

#### Test Structure

```
frontend/src/
├── components/
│   ├── CoinFlipGame.test.tsx
│   └── WalletContext.test.tsx
└── tests/
    ├── unit/
    │   ├── components/
    │   └── utils/
    └── e2e/
        ├── coinflip.spec.ts
        └── regression.spec.ts
```

## Integration Testing

### Backend Integration Tests

```python
# backend/tests/test_integration.py
import pytest
import requests

def test_backend_integration():
    # Test API endpoints
    response = requests.get("http://localhost:8000/health")
    assert response.status_code == 200
    
    # Test database connection
    response = requests.get("http://localhost:8000/history/test_address")
    assert response.status_code == 200
```

### Contract Integration Tests

```python
# backend/tests/test_contract_integration.py
from ergo_py_sdk import ErgoClient

def test_contract_integration():
    client = ErgoClient("http://localhost:9052", "api_key")
    
    # Test contract deployment
    contract_address = client.deploy_contract("coinflip_v1.es")
    assert contract_address is not None
    
    # Test contract interaction
    result = client.test_contract("coinflip_v1.es", "test_commitment")
    assert result.success
```

## E2E Testing

### Frontend E2E Tests

```javascript
// frontend/tests/e2e/coinflip.spec.ts
describe('Coin Flip Game', () => {
  test('complete game flow', async () => {
    // Connect wallet
    await page.goto('http://localhost:3000');
    await page.click('button:has-text("Connect Wallet")');
    
    // Place bet
    await page.fill('#bet-amount', '1');
    await page.selectOption('#bet-choice', 'heads');
    await page.click('button:has-text("Place Bet")');
    
    // Verify bet placed
    await expect(page.locator('.bet-status')).toContainText('pending');
  });
});
```

### Test Scenarios

1. **Happy Path**: Complete game flow from bet to reveal
2. **Timeout Scenario**: Bet expires and player refunds
3. **Error Handling**: Invalid inputs and error responses
4. **Wallet Integration**: Wallet connection and transaction signing
5. **API Integration**: Backend API endpoint testing

## Contract Testing

### ErgoScript Tests

```ergoscript
# smart-contracts/coinflip_commit_reveal_tests.rs
#[test]
fn test_commitment_verification() {
    let secret = 12345678;
    let choice = 0; // heads
    let commitment = blake2b256(secret ++ choice);
    
    // Test commitment verification
    assert(blake2b256(secret ++ choice) == commitment);
}

#[test]
fn test_rng_outcome() {
    let block_hash = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6";
    let secret = 12345678;
    
    let outcome = blake2b256(block_hash ++ secret)[0] % 2;
    assert(outcome == 0 || outcome == 1);
}
```

### Test Coverage

- Commitment verification
- RNG outcome generation
- Timeout protection
- Refund functionality
- NFT preservation
- Guard clause validation

## Performance Testing

### Load Testing

```python
# backend/tests/test_performance.py
import pytest
import requests
import time

def test_api_performance():
    start_time = time.time()
    
    # Simulate 100 concurrent requests
    for _ in range(100):
        requests.post(
            "http://localhost:8000/place-bet",
            json={
                "player_address": "test_address",
                "amount": 1000000,
                "choice": 0,
                "secret": "test_secret"
            }
        )
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Should complete within 5 seconds
    assert duration < 5
```

### Stress Testing

```bash
# Use locust for load testing
locust -f load_test.py --host=http://localhost:8000
```

### Performance Metrics

- API response time (< 200ms)
- Database query performance
- Transaction processing speed
- Memory usage
- CPU utilization

## Testing Best Practices

### Test Organization

1. **Unit Tests**: Test individual functions and components
2. **Integration Tests**: Test component interactions
3. **E2E Tests**: Test complete user workflows
4. **Contract Tests**: Test smart contract logic
5. **Performance Tests**: Test under load conditions

### Test Naming Conventions

- Clear and descriptive test names
- Include scenario and expected outcome
- Use consistent naming patterns

### Test Data Management

- Use test-specific data
- Clean up test data after tests
- Avoid test data contamination

### Test Environment

- Isolated test environment
- Consistent test data
- Proper test setup and teardown

## Continuous Integration

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.8'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          npm install
      - name: Run backend tests
        run: pytest backend/tests/
      - name: Run frontend tests
        run: npm test
      - name: Run contract tests
        run: ergo-cli test smart-contracts/coinflip_commit_reveal_tests.rs
```

### Test Coverage

- Maintain test coverage > 80%
- Monitor test failures
- Automate test execution
- Integrate with CI/CD pipeline

## Troubleshooting Tests

### Common Test Issues

1. **Flaky Tests**: Non-deterministic behavior
2. **Test Data Issues**: Inconsistent test data
3. **Environment Problems**: Test environment configuration
4. **Timeouts**: Slow test execution

### Debugging Tips

1. **Enable verbose logging**: Use `--verbose` flag
2. **Check test data**: Verify test data integrity
3. **Monitor test environment**: Track resource usage
4. **Isolate failing tests**: Run individual tests for debugging

## Test Reporting

### Test Results

- Test execution summary
- Failed tests with error messages
- Test coverage reports
- Performance metrics
- Environment information

### Reporting Tools

- pytest-html for HTML reports
- Allure for detailed test reporting
- GitHub Actions for CI/CD integration

## Further Resources

- [pytest Documentation](https://docs.pytest.org/)
- [Jest Documentation](https://jestjs.io/)
- [ErgoScript Testing](https://ergoplatform.org/en/ergoscript/testing/)
- [DuckPools Architecture](../ARCHITECTURE.md)

--- 
*Comprehensive testing ensures system reliability and security. Always test before deployment.*