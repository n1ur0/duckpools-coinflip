# DuckPools Regression Test Suite

This directory contains regression and smoke tests for the DuckPools application.

## Test Categories

### 1. Backend API Regression Tests (`test_backend_api.py`)
Smoke tests for critical backend API endpoints using HTTP requests.

**Coverage:**
- BR-1: Health Check - `/health` endpoint
- BR-2: Pool State - `/api/lp/pool` endpoint
- BR-3: Scripts Endpoint - `/api/lp/scripts` endpoint
- BR-4: History Endpoint - `/history` endpoint
- BR-5: Invalid Bet Rejection - `/place-bet` validation
- Additional LP endpoints (price, APY, balance)
- Oracle endpoints (health, status)

### 2. Frontend Smoke Tests (`test_frontend_smoke.py`)
Browser-based tests to verify the frontend loads correctly.

**Coverage:**
- FR-1: Page Load - Loads without console errors
- FR-2: Wallet Connection - UI elements present
- FR-3: API Proxy - Routes proxy correctly to backend
- Basic responsiveness checks

## Prerequisites

### For Backend Tests
- Backend server running on `http://localhost:8000`
- Ergo node running on `http://localhost:9052`

### For Frontend Tests
- Frontend server running on `http://localhost:3000`
- Backend server running on `http://localhost:8000`
- Playwright Python package installed

## Installation

```bash
cd /Users/n1ur0/projects/worktrees/agent/regression-tester-jr/55-regression-test-suite

# Install dependencies
pip install httpx pytest pytest-asyncio playwright

# Install Playwright browsers
playwright install chromium
```

## Running Tests

### Run All Tests
```bash
cd /Users/n1ur0/projects/worktrees/agent/regression-tester-jr/55-regression-test-suite
python3 -m pytest regression_tests/ -v
```

### Run Only Backend Tests
```bash
python3 -m pytest regression_tests/test_backend_api.py -v
```

### Run Only Frontend Tests
```bash
python3 -m pytest regression_tests/test_frontend_smoke.py -v
```

### Run Specific Test
```bash
python3 -m pytest regression_tests/test_backend_api.py::TestHealthCheck::test_health_returns_200 -v
```

## Test Exit Codes

- `0`: All tests passed
- `1`: One or more tests failed

## CI/CD Integration

These tests should run as part of the CI/CD pipeline:

```yaml
- name: Run Backend Regression Tests
  run: |
    cd tests
    python -m pytest regression_tests/test_backend_api.py -v

- name: Run Frontend Smoke Tests
  run: |
    cd tests
    python -m pytest regression_tests/test_frontend_smoke.py -v
```

## Test Results

### Latest Test Status (MAT-55 Completion)

#### Backend API Regression Tests
- **13/16 tests passing** (81.25% success rate)
- **3 failures**:
  1. `test_history_invalid_address`: API accepts invalid addresses (returns 200 instead of 400/404)
  2. `test_oracle_health_endpoint`: Oracle endpoint not implemented (returns 404)
  3. `test_oracle_status_endpoint`: Oracle endpoint not implemented (returns 404)

#### Frontend Smoke Tests
- **All tested scenarios passing** 
- Verified page load, UI elements, and API proxy functionality

#### Existing Python Test Suite
- **177/231 tests passing** (76.62% success rate)
- **54 failures** primarily due to:
  - Missing backend services (404 errors)
  - Module import issues (off_chain_bot)
  - Penetration test expectations

Run with `--tb=short` for shorter error output:
```bash
python3 -m pytest regression_tests/ -v --tb=short
```

Run with `--cov` for coverage report:
```bash
python3 -m pytest regression_tests/ --cov=. --cov-report=html
```

## Issue Tracking

- **Issue**: MAT-55 - Regression test suite: backend API + frontend smoke tests
- **Assigned**: Regression Tester Jr (b682ea47)
- **Status**: ✅ COMPLETED - Regression test suite implemented and executed
- **Backend Coverage**: 81.25% pass rate
- **Frontend Coverage**: 100% pass rate on tested scenarios
- **Full Test Suite**: 76.62% pass rate (231 total tests)

### Recommendations

1. **High Priority**: Fix history endpoint validation - should reject invalid addresses
2. **Medium Priority**: Implement oracle endpoints or update tests to expect 404
3. **Documentation**: Update test expectations based on current API behavior
4. **CI/CD**: Integrate regression tests into deployment pipeline
