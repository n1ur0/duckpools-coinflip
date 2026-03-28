# DuckPools Penetration Test Suite

Comprehensive security testing suite for the DuckPools API endpoints.

## Overview

This test suite validates the security posture of the DuckPools API by testing for common vulnerabilities including:

- **SQL Injection** - Attempts to inject SQL commands into inputs
- **XSS (Cross-Site Scripting)** - Tests for reflected and stored XSS
- **CSRF (Cross-Site Request Forgery)** - Validates CSRF protections
- **Authentication Bypass** - Tests for auth bypass vulnerabilities
- **Input Validation** - Tests for malicious input handling
- **Security Headers** - Verifies proper HTTP security headers
- **Rate Limiting** - Tests DoS protection mechanisms
- **Information Disclosure** - Checks for sensitive data leaks
- **WebSocket Security** - Validates WebSocket connection security
- **CORS Configuration** - Ensures safe CORS policies
- **API-Specific Vulnerabilities** - Tests for pool and staking issues

## Quick Start

### Run all tests:

```bash
python -m pytest tests/test_penetration_suite.py -v
```

### Run specific test categories:

```bash
# SQL Injection tests only
python -m pytest tests/test_penetration_suite.py::TestSQLInjection -v

# XSS tests only
python -m pytest tests/test_penetration_suite.py::TestXSS -v

# Auth bypass tests only
python -m pytest tests/test_penetration_suite.py::TestAuthBypass -v
```

### Run with coverage:

```bash
python -m pytest tests/test_penetration_suite.py --cov=backend --cov-report=html
```

## Test Configuration

### Environment Variables

- `API_BASE_URL` - API base URL (default: `http://localhost:8000`)
- `API_KEY` - Development API key for testing (default: `hello`)

Example:

```bash
export API_BASE_URL=http://localhost:8000
export API_KEY=hello
python -m pytest tests/test_penetration_suite.py -v
```

## Test Categories

### 1. SQL Injection Tests (`TestSQLInjection`)

Tests various SQL injection payloads in:

- Path parameters (address)
- Query parameters
- POST body fields
- Time-based SQL injection detection

**Expected Results:**
- No SQL error messages in responses
- No server crashes (500 errors)
- Proper rejection of malformed input (400/404)

### 2. XSS Tests (`TestXSS`)

Tests XSS payloads in:

- Path parameters
- POST body
- Various XSS vectors (script tags, event handlers, etc.)

**Expected Results:**
- XSS payloads properly escaped/encoded
- `<script>` tags not reflected in responses
- Event handlers (onload, onerror) not reflected
- Proper Content-Type headers

### 3. CSRF Tests (`TestCSRF`)

Note: DuckPools uses EIP-12 wallet signatures for authentication, which significantly reduces CSRF risk. These tests are for future cookie-based authentication.

Tests:

- CSRF token requirements
- SameSite cookie attributes
- Origin/Referer header validation

**Expected Results:**
- CSRF tokens required for state-changing operations (if using cookies)
- SameSite=Strict or SameSite=Lax on cookies
- Origin validation on sensitive endpoints

### 4. Authentication Bypass Tests (`TestAuthBypass`)

Tests:

- Missing API key rejection
- Invalid API key rejection
- API key in URL params (HIGH severity issue)
- Header-based bypass attempts
- Path traversal bypass
- Sensitive endpoint enforcement

**Expected Results:**
- API keys required for protected endpoints
- Invalid keys rejected (401/403)
- API keys NOT accepted in URL params (security issue)
- No bypass via alternative headers

### 5. Input Validation Tests (`TestInputValidation`)

Tests:

- Path traversal attacks
- Template injection
- Null byte injection
- CRLF injection
- Oversized inputs
- Special characters in JSON
- JSON structure validation

**Expected Results:**
- Malicious inputs rejected (400/404)
- No filesystem path leaks
- Size limits enforced
- Proper JSON validation

### 6. Security Headers Tests (`TestSecurityHeaders`)

Tests required HTTP security headers:

- `X-Frame-Options` - Clickjacking protection
- `X-Content-Type-Options` - MIME-sniffing protection
- `X-XSS-Protection` - XSS filter
- `Referrer-Policy` - Referer header control
- `Content-Security-Policy` - Content injection protection
- `Strict-Transport-Security` - HSTS (HTTPS only)

**Expected Results:**
- All required headers present
- Proper values for each header
- No security headers missing

### 7. Rate Limiting Tests (`TestRateLimiting`)

Tests:

- Brute force protection
- Request size limits
- Slowloris protection (informational)

**Expected Results:**
- 429 responses after repeated failed attempts
- Large requests rejected (413)
- Reasonable timeout values

### 8. Information Disclosure Tests (`TestInformationDisclosure`)

Tests:

- Error message sensitivity
- Directory listing
- Debug mode status
- Sensitive HTML comments

**Expected Results:**
- No stack traces in error messages
- Directory listing disabled
- Debug mode off in production
- No sensitive comments in HTML

### 9. WebSocket Security Tests (`TestWebSocketSecurity`)

Tests:

- Authentication requirements
- Origin validation

**Expected Results:**
- WebSocket connections require auth
- Origin headers validated

### 10. CORS Tests (`TestCORS`)

Tests:

- Wildcard origins (*) security issue
- Credentials + origins mismatch

**Expected Results:**
- Origins should not be `*` if credentials allowed
- Specific origins configured
- Safe CORS policies

### 11. API-Specific Tests (`TestAPISpecificVulnerabilities`)

Tests DuckPools-specific issues:

- Negative amounts
- Zero amounts
- Integer overflow (max int64)
- Box ID injection
- Staking position ID validation

**Expected Results:**
- Invalid amounts rejected
- No overflow crashes
- Box IDs validated properly

## Vulnerability Severity Guide

| Severity | Impact | Examples |
|----------|--------|----------|
| **CRITICAL** | Complete system compromise | Remote code execution, auth bypass |
| **HIGH** | Major security breach | SQL injection, XSS, auth bypass |
| **MEDIUM** | Limited impact | CSRF, missing security headers |
| **LOW** | Minor security issue | Information disclosure, CORS config |
| **INFO** | Best practice | Security recommendations |

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Security Tests

on: [push, pull_request]

jobs:
  penetration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install pytest httpx pytest-asyncio

      - name: Run penetration tests
        run: |
          python -m pytest tests/test_penetration_suite.py -v

      - name: Upload results
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: penetration-test-results
          path: test-results/
```

## Troubleshooting

### Tests fail with "Connection refused"

The API server is not running. Start it first:

```bash
cd backend
python api_server.py
```

### Tests timeout

Increase timeout by setting `TEST_TIMEOUT` in the test file, or use:

```bash
export PYTEST_TIMEOUT=30
```

### "API key rejected" errors

Ensure the API key is set correctly:

```bash
export API_KEY=hello  # or your dev API key
```

## Security Best Practices

Based on test results, implement these practices:

1. **Never accept API keys in URL parameters** - Use headers only
2. **Validate all input** - Type, length, format checks
3. **Sanitize all output** - HTML encode user data
4. **Use security headers** - CSP, HSTS, X-Frame-Options, etc.
5. **Implement rate limiting** - Prevent brute force and DoS
6. **Validate CORS origins** - Don't use `*` with credentials
7. **Disable debug mode** - Especially in production
8. **Use parameterized queries** - Prevent SQL injection (if using SQL)
9. **Implement CSRF tokens** - If using cookie-based auth
10. **Regular security audits** - Run this suite frequently

## Reporting Vulnerabilities

If this test suite discovers vulnerabilities:

1. **Do NOT commit vulnerabilities to public repos**
2. **Report to security team immediately**
3. **Create private issue** describing the vulnerability
4. **Provide proof of concept** from test output
5. **Follow responsible disclosure** process

## Contributing

To add new tests:

1. Add test class to `test_penetration_suite.py`
2. Follow naming convention: `TestVulnerabilityType`
3. Use descriptive test method names
4. Add docstrings explaining what's tested
5. Include expected results in comments

Example:

```python
class TestNewVulnerability:
    """Tests for new vulnerability type."""

    async def test_specific_scenario(self, client, api_headers):
        """
        Test description of what this tests.

        Expected: Specific behavior
        Should NOT: What should not happen
        """
        # Test implementation
        pass
```

## License

This test suite is part of DuckPools project.

## Credits

Developed by Security & Compliance Team, Matsuzaka (DuckPools)
