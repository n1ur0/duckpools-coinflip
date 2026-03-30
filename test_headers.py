#!/usr/bin/env python3
import requests
import sys

def test_headers():
    endpoints = [
        "http://localhost:3101/health",
        "http://localhost:3101/pool/state", 
        "http://localhost:3101/scripts"
    ]
    
    print("Testing security headers...\n")
    
    for endpoint in endpoints:
        try:
            response = requests.get(endpoint)
            print(f"Endpoint: {endpoint}")
            print(f"Status: {response.status_code}")
            print("Headers:")
            
            for header, value in response.headers.items():
                print(f"  {header}: {value}")
            
            print("\n" + "="*50 + "\n")
            
        except Exception as e:
            print(f"Error testing {endpoint}: {e}\n")

if __name__ == "__main__":
    test_headers()