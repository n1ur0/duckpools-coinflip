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
- **Status**: Implementation in progress
