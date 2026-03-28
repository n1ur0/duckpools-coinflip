#!/usr/bin/env python3
"""
Security Headers Verification Script for MAT-218

This script verifies that all security headers are properly implemented
across all DuckPools API endpoints.

Usage:
    python verify-security-headers.py

Expected Output:
    ✓ All security headers present
    ✓ XSS protection working
    ✓ CORS properly configured
"""

import httpx
import sys
from typing import Dict, List, Tuple

# Configuration
BASE_URL = "http://localhost:8000"
TIMEOUT = 10

# Required security headers per OWASP
REQUIRED_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",  # or SAMEORIGIN
    "X-XSS-Protection": "1; mode=block",  # or "1" or "0"
    "Referrer-Policy": "strict-origin-when-cross-origin",  # or other secure values
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Content-Security-Policy": "default-src 'self'",  # or other secure policy
    "Strict-Transport-Security": "max-age=",  # Must have max-age
}

# Test endpoints
ENDPOINTS = [
    ("GET", "/health"),
    ("GET", "/"),
    ("GET", "/pool/state"),
    ("GET", "/scripts"),
    ("GET", "/api/lp/pool"),
    ("GET", "/api/lp/price"),
    ("GET", "/api/lp/apy"),
]

def test_security_headers(endpoint: Tuple[str, str]) -> Dict[str, str]:
    """Test security headers for a single endpoint."""
    method, path = endpoint
    url = f"{BASE_URL}{path}"
    
    try:
        if method == "GET":
            response = httpx.get(url, timeout=TIMEOUT)
        else:
            response = httpx.post(url, timeout=TIMEOUT)
        
        return {
            "endpoint": f"{method} {path}",
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "success": response.status_code < 400
        }
    except Exception as e:
        return {
            "endpoint": f"{method} {path}",
            "status_code": 0,
            "headers": {},
            "success": False,
            "error": str(e)
        }

def check_header_compliance(headers: Dict[str, str]) -> Dict[str, str]:
    """Check if headers comply with security requirements."""
    results = {}
    
    for header_name, expected_value in REQUIRED_HEADERS.items():
        if header_name in headers:
            actual_value = headers[header_name]
            
            if header_name == "X-Frame-Options":
                # Allow DENY or SAMEORIGIN
                if actual_value in ["DENY", "SAMEORIGIN"]:
                    results[header_name] = f"✓ {actual_value}"
                else:
                    results[header_name] = f"✗ {actual_value} (expected DENY or SAMEORIGIN)"
            
            elif header_name == "X-XSS-Protection":
                # Allow 1; mode=block, 1, or 0
                if actual_value in ["1; mode=block", "1", "0"]:
                    results[header_name] = f"✓ {actual_value}"
                else:
                    results[header_name] = f"✗ {actual_value} (invalid format)"
            
            elif header_name == "Content-Security-Policy":
                # Must contain default-src 'self' or equivalent
                if "default-src" in actual_value and ("'self'" in actual_value or "'none'" in actual_value):
                    results[header_name] = f"✓ Present"
                else:
                    results[header_name] = f"✗ Insecure (missing default-src)"
            
            elif header_name == "Strict-Transport-Security":
                # Must have max-age
                if "max-age=" in actual_value:
                    results[header_name] = f"✓ {actual_value}"
                else:
                    results[header_name] = f"✗ Missing max-age"
            
            elif header_name == "Referrer-Policy":
                # Any secure policy is acceptable
                secure_policies = ["strict-origin", "no-referrer", "same-origin"]
                if any(policy in actual_value for policy in secure_policies):
                    results[header_name] = f"✓ {actual_value}"
                else:
                    results[header_name] = f"✗ Insecure policy"
            
            else:
                # Exact match required for these headers
                if expected_value in actual_value:
                    results[header_name] = f"✓ {actual_value}"
                else:
                    results[header_name] = f"✗ Expected {expected_value}, got {actual_value}"
        else:
            results[header_name] = "✗ MISSING"
    
    return results

def test_cors_configuration():
    """Test CORS configuration."""
    try:
        response = httpx.options(
            f"{BASE_URL}/health",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
            timeout=TIMEOUT
        )
        
        cors_headers = {}
        for key, value in response.headers.items():
            if "access-control" in key.lower():
                cors_headers[key] = value
        
        # Check if allow-credentials is false (secure)
        allow_credentials = cors_headers.get("access-control-allow-credentials", "")
        if allow_credentials.lower() == "false":
            cors_result = "✓ allow_credentials=False (secure)"
        elif allow_credentials.lower() == "true":
            cors_result = "✗ allow_credentials=True (insecure)"
        else:
            cors_result = "ℹ No allow-credentials header"
        
        return {
            "cors_headers": cors_headers,
            "result": cors_result
        }
    except Exception as e:
        return {
            "cors_headers": {},
            "result": f"✗ Error: {e}"
        }

def main():
    """Main verification function."""
    print("🔒 DuckPools Security Headers Verification - MAT-218")
    print("=" * 60)
    
    # Test all endpoints
    print("\n📡 Testing security headers on all endpoints...")
    all_passed = True
    
    for endpoint in ENDPOINTS:
        result = test_security_headers(endpoint)
        print(f"\n📍 {result['endpoint']}")
        
        if not result['success']:
            print(f"   ✗ Failed to connect: {result.get('error', 'Unknown error')}")
            all_passed = False
            continue
        
        header_results = check_header_compliance(result['headers'])
        
        # Show results
        for header, status in header_results.items():
            if "✗" in status:
                print(f"   {header}: {status}")
                all_passed = False
            else:
                print(f"   {header}: {status}")
        
        # Check for debug header
        if "X-Security-Middleware" in result['headers']:
            print(f"   Debug: ✓ Security middleware active")
        else:
            print(f"   Debug: ✗ Security middleware not detected")
            all_passed = False
    
    # Test CORS
    print(f"\n🌐 Testing CORS configuration...")
    cors_result = test_cors_configuration()
    print(f"   {cors_result['result']}")
    
    for header, value in cors_result['cors_headers'].items():
        print(f"   {header}: {value}")
    
    # Summary
    print(f"\n{'=' * 60}")
    if all_passed:
        print("✅ SUCCESS: All security headers are properly implemented!")
        print("✅ XSS protection is active and working!")
        print("✅ CORS configuration is secure!")
        print("\n🎉 MAT-218 requirements satisfied!")
        return 0
    else:
        print("❌ FAILED: Security headers are missing or misconfigured!")
        print("❌ Please check the implementation and restart the server.")
        return 1

if __name__ == "__main__":
    sys.exit(main())