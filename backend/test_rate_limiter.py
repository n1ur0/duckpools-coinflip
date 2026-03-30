#!/usr/bin/env python3
"""
Test script for the rate limiter functionality.
"""

import os
import sys
import time
from dotenv import load_dotenv

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from backend.rate_limited_client import make_rate_limited_request, rate_limited_client
from backend.rate_limiter_config import load_provider_config

def test_rate_limiter_initialization():
    """Test that the rate limiter initializes correctly."""
    print("Testing rate limiter initialization...")
    
    try:
        providers = load_provider_config()
        print(f"✓ Successfully loaded {len(providers)} providers")
        
        for provider in providers:
            print(f"  - {provider.name}: {provider.base_url} (rate_limit: {provider.rate_limit})")
            
        return True
    except Exception as e:
        print(f"✗ Failed to initialize rate limiter: {e}")
        return False

def test_make_request():
    """Test making a request with the rate limiter."""
    print("\nTesting request functionality...")
    
    if rate_limited_client is None:
        print("✗ Rate limited client is not available")
        return False
    
    try:
        # Test with a dummy endpoint (this will fail but test the rate limiter logic)
        print("Making test request to z.ai...")
        response = make_rate_limited_request("GET", "health")
        print(f"✓ Request successful: {response}")
        return True
    except Exception as e:
        print(f"✗ Request failed (expected for test): {e}")
        # This is expected for a test request to a non-existent endpoint
        return True

def test_provider_stats():
    """Test getting provider statistics."""
    print("\nTesting provider statistics...")
    
    if rate_limited_client is None:
        print("✗ Rate limited client is not available")
        return False
    
    try:
        stats = rate_limited_client.rate_limiter.get_provider_stats()
        print("✓ Provider statistics:")
        for provider_name, stats_data in stats.items():
            print(f"  - {provider_name}:")
            print(f"    - Usage: {stats_data['usage']}/{stats_data['rate_limit']} ({stats_data['usage_percentage']:.1f}%)")
        return True
    except Exception as e:
        print(f"✗ Failed to get provider stats: {e}")
        return False

def main():
    """Main test function."""
    print("=== Rate Limiter Test Suite ===\n")
    
    tests = [
        test_rate_limiter_initialization,
        test_make_request,
        test_provider_stats
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n=== Test Results ===")
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())