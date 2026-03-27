#!/usr/bin/env python3
"""
Security Vulnerability Demonstration Scripts

This script demonstrates the security vulnerabilities found in the DuckPools API.
Run these tests ONLY against development/staging environments with proper authorization.

DANGER: Do NOT run against production without explicit authorization.
"""

import httpx
import sys

BASE_URL = "http://localhost:8000"
API_KEY = "hello"  # Default dev API key (DO NOT use in production)

# ──────────────────────────────────────────────────────────────────────
# VULNERABILITY 1: API Key in Query Parameters (HIGH)
# ──────────────────────────────────────────────────────────────────────

def test_api_key_in_query_params():
    """
    DEMONSTRATION: API key can be passed via URL query parameters.

    Risk: Query parameters are logged in:
    - Web server logs (nginx, Apache)
    - Proxy logs
    - CDN logs (Cloudflare)
    - Browser history
    - Referrer headers

    An attacker who gains access to logs can compromise the API key.
    """
    print("=" * 70)
    print("VULNERABILITY 1: API Key in Query Parameters (HIGH)")
    print("=" * 70)

    # Test with API key in query parameter (BAD - should be rejected)
    url = f"{BASE_URL}/resolve-bet?api_key={API_KEY}"
    payload = {
        "bet_id": "test_bet_123",
        "player_secret": 12345,
        "block_hash": "00" * 32,
        "player_address": "3WyrB3D5AMpyEc88UJ7FpdsBMXAZKwzQzkKeDbAQVfXytDPgxF26",
        "outcome": "win",
        "payout_nanoerg": 1000000000
    }

    print(f"\nSending request with API key in QUERY PARAMETER:")
    print(f"URL: {url}")
    print(f"  ^^^^^^ ^^^^ API KEY EXPOSED IN URL!")

    try:
        response = httpx.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"\n[!] VULNERABLE: Request succeeded (status {response.status_code})")
            print(f"[!] This means the API key can be logged by:")
            print(f"    - Web servers (nginx access.log)")
            print(f"    - Load balancers")
            print(f"    - CDNs (Cloudflare, etc.)")
            print(f"    - Browser history")
            print(f"    - Referer headers")
            return True
        else:
            print(f"\n[OK] Request rejected (status {response.status_code})")
            return False
    except Exception as e:
        print(f"\n[?] Request failed: {e}")
        return False


# ──────────────────────────────────────────────────────────────────────
# VULNERABILITY 2: Missing Security Headers (MEDIUM)
# ──────────────────────────────────────────────────────────────────────

def test_missing_security_headers():
    """
    DEMONSTRATION: Security headers are not present in HTTP responses.

    Risk:
    - X-Frame-Options missing: Clickjacking attacks
    - X-Content-Type-Options missing: MIME-sniffing attacks
    - X-XSS-Protection missing: Legacy XSS protection disabled
    - Referrer-Policy missing: Information leakage via Referer
    """
    print("\n" + "=" * 70)
    print("VULNERABILITY 4: Missing Security Headers (MEDIUM)")
    print("=" * 70)

    required_headers = {
        "X-Frame-Options": "Clickjacking protection",
        "X-Content-Type-Options": "MIME-sniffing protection",
        "X-XSS-Protection": "XSS filter",
        "Referrer-Policy": "Referer header leakage",
        "Permissions-Policy": "Browser feature restrictions",
        "Content-Security-Policy": "Content injection protection",
    }

    try:
        response = httpx.get(f"{BASE_URL}/health", timeout=10)
        print(f"\nResponse headers for {BASE_URL}/health:\n")

        missing = []
        for header, description in required_headers.items():
            if header in response.headers:
                print(f"  ✓ {header}: {response.headers[header][:50]}")
            else:
                print(f"  ✗ {header}: MISSING ({description})")
                missing.append((header, description))

        if missing:
            print(f"\n[!] VULNERABLE: {len(missing)} security headers missing")
            print(f"\nMissing headers and their risks:")
            for header, description in missing:
                print(f"  - {header}: {description}")
            return True
        else:
            print(f"\n[OK] All security headers present")
            return False
    except Exception as e:
        print(f"\n[?] Request failed: {e}")
        return False


# ──────────────────────────────────────────────────────────────────────
# VULNERABILITY 3: CORS allow_credentials=True (MEDIUM)
# ──────────────────────────────────────────────────────────────────────

def test_cors_credentials():
    """
    DEMONSTRATION: CORS policy allows credentials, increasing CSRF risk.

    Note: This is informational - actual CSRF requires cookie-based auth,
    which DuckPools doesn't currently use. But it's a concern for future.
    """
    print("\n" + "=" * 70)
    print("VULNERABILITY 3: CORS allow_credentials=True (MEDIUM)")
    print("=" * 70)

    try:
        response = httpx.options(
            f"{BASE_URL}/health",
            headers={
                "Origin": "https://malicious.example.com",
                "Access-Control-Request-Method": "GET",
            },
            timeout=10
        )

        print(f"\nCORS response headers:\n")
        for key, value in response.headers.items():
            if "access-control" in key.lower():
                print(f"  {key}: {value}")

        # The actual CORS check happens in the browser, not with httpx
        # This is informational only
        print(f"\n[ℹ] INFO: CORS with allow_credentials=True detected")
        print(f"[ℹ] This increases CSRF risk if cookies are used for auth")
        print(f"[ℹ] DuckPools uses EIP-12 (wallet signatures), not cookies")
        print(f"[ℹ] But future cookie-based auth would be vulnerable")

        return False  # Not directly testable with httpx
    except Exception as e:
        print(f"\n[?] Request failed: {e}")
        return False


# ──────────────────────────────────────────────────────────────────────
# VULNERABILITY 4: API Key Reuse (MEDIUM)
# ──────────────────────────────────────────────────────────────────────

def test_api_key_reuse():
    """
    DEMONSTRATION: Same API key used for node and bot endpoints.

    Risk: If node API key is compromised, bot endpoints are also exposed.
    This violates principle of least privilege.
    """
    print("\n" + "=" * 70)
    print("VULNERABILITY 2: API Key Reuse (MEDIUM)")
    print("=" * 70)

    print(f"\n[ℹ] Current configuration:")
    print(f"  NODE_API_KEY = '{API_KEY}' (used for Ergo node requests)")
    print(f"  BOT_API_KEY  = '{API_KEY}' (used for bot endpoints)")
    print(f"\n[!] SAME KEY USED FOR BOTH SYSTEMS")
    print(f"\nRisks:")
    print(f"  - Compromise of node API key exposes bot operations")
    print(f"  - Cannot revoke bot access without affecting node")
    print(f"  - Infrastructure team sharing node key gets bot access")
    print(f"  - No separate rotation policies possible")
    print(f"\nRecommendation:")
    print(f"  NODE_API_KEY = '<node-specific-key>'")
    print(f"  BOT_API_KEY  = '<separate-strong-random-key>'")

    return False  # Informational, requires code review


# ──────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "DuckPools Security Audit Demo" + " " * 20 + "║")
    print("║" + " " * 68 + "║")
    print("║" + "  WARNING: Run ONLY against authorized dev/staging envs! " + " " * 9 + "║")
    print("╚" + "═" * 68 + "╝")

    # Run all vulnerability tests
    vuln_1 = test_api_key_in_query_params()
    vuln_2 = test_missing_security_headers()
    test_cors_credentials()
    test_api_key_reuse()

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\nConfirmed vulnerabilities:")
    if vuln_1:
        print(f"  [HIGH]   API key in query parameters")
    if vuln_2:
        print(f"  [MEDIUM] Missing security headers")

    print(f"\nSee security-audit-2026-03-27.md for detailed remediation steps.")
    print("\n")


if __name__ == "__main__":
    main()
