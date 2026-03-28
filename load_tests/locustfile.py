"""
DuckPools Load Testing Framework

Performance test suite for DuckPools API endpoints, focusing on:
1. Concurrent bet placement (Plinko game)
2. Bankroll stress testing
3. API endpoint response times under load

Usage:
    locust -f locustfile.py --host http://localhost:8000 --users 50 --spawn-rate 10
"""

import hashlib
import random
import time
from datetime import datetime
from typing import Dict, Any

from locust import HttpUser, task, between, events
from locust.runners import MasterRunner


# ─── Constants ───────────────────────────────────────────────────────

MIN_BET_AMOUNT = 0.1  # ERG
MAX_BET_AMOUNT = 5.0  # ERG
WALLET_ADDRESSES = [
    "9iDqY3bZ7yZ5bZ7yZ5bZ7yZ5bZ7yZ5bZ7yZ5bZ7yZ5bZ7yZ5bZ7yZ5b",
    "8hCpX2aY6aY4aY6aY4aY6aY4aY6aY4aY6aY4aY6aY4aY6aY4aY6aY4aY6",
    "7gBoW1zX5zX3zX5zX3zX5zX3zX5zX3zX5zX3zX5zX3zX5zX3zX5zX3zX5",
]

# ─── Test Data Generation ─────────────────────────────────────────────

def generate_wallet_address() -> str:
    """Generate a test wallet address."""
    return random.choice(WALLET_ADDRESSES)


def generate_bet_amount() -> float:
    """Generate a random bet amount within reasonable limits."""
    return round(random.uniform(MIN_BET_AMOUNT, MAX_BET_AMOUNT), 4)


def generate_secret() -> str:
    """Generate a random 2-byte secret (4 hex characters)."""
    return random.randint(0, 65535).to_bytes(2, byteorder='big').hex()


def generate_commitment(secret: str) -> str:
    """Generate SHA256 commitment from secret."""
    secret_bytes = bytes.fromhex(secret)
    return hashlib.sha256(secret_bytes).hexdigest()


def generate_bet_id() -> str:
    """Generate a unique bet ID."""
    return f"bet_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"


def create_bet_payload() -> Dict[str, Any]:
    """Create a complete bet placement request payload."""
    secret = generate_secret()
    commitment = generate_commitment(secret)
    
    return {
        "address": generate_wallet_address(),
        "amount": str(int(generate_bet_amount() * 1e9)),  # Convert to nanoERG
        "commitment": commitment,
        "secret": secret,
        "betId": generate_bet_id(),
        "gameType": "plinko",
    }


# ─── Locust User Classes ───────────────────────────────────────────────

class DuckPoolsUser(HttpUser):
    """
    Simulates a DuckPools player placing bets.
    
    Default behavior:
    - Places Plinko bets every 2-5 seconds (simulating realistic player pace)
    - Mixes of small, medium, and large bets
    - Multiple simulated wallet addresses
    """
    
    wait_time = between(2, 5)
    
    def on_start(self):
        """Called when a user starts. Initialize any session state."""
        self.bet_count = 0
        self.total_amount = 0.0
        self.errors = 0
    
    @task(weight=3)
    def place_plinko_bet(self):
        """
        Place a Plinko bet (primary workload).
        
        This is the core load test for the betting system. It tests:
        - API endpoint responsiveness
        - Request validation
        - Pool liquidity checks
        - Transaction submission (mocked)
        """
        self.bet_count += 1
        
        payload = create_bet_payload()
        bet_amount_erg = int(payload["amount"]) / 1e9
        self.total_amount += bet_amount_erg
        
        with self.client.post(
            "/api/plinko/place-bet",
            json=payload,
            catch_response=True,
            name="/api/plinko/place-bet"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    response.success()
                else:
                    error_msg = data.get("error", "Unknown error")
                    response.failure(f"API returned error: {error_msg}")
                    self.errors += 1
            elif response.status_code == 400:
                # Business logic error (insufficient funds, invalid bet, etc.)
                response.failure(f"Validation error: {response.text}")
                self.errors += 1
            elif response.status_code == 429:
                # Rate limiting - expected under heavy load
                response.failure("Rate limited")
                self.errors += 1
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
                self.errors += 1
    
    @task(weight=1)
    def get_pool_state(self):
        """
        Check pool state (secondary workload).
        
        This tests the read-only endpoints that monitor pool liquidity.
        """
        self.client.get("/api/lp/pool", name="/api/lp/pool")
    
    @task(weight=1)
    def get_price(self):
        """
        Get LP token price (secondary workload).
        
        This tests the price calculation endpoint.
        """
        self.client.get("/api/lp/price", name="/api/lp/price")
    
    @task(weight=1)
    def get_multipliers(self):
        """
        Get Plinko multipliers (secondary workload).
        
        This tests game metadata endpoint.
        """
        self.client.get("/api/plinko/multipliers", name="/api/plinko/multipliers")


class BankrollStressUser(HttpUser):
    """
    Simulates high-frequency bet placement to stress test bankroll management.
    
    This user type is more aggressive, designed to find race conditions and
    liquidity management issues under concurrent load.
    """
    
    wait_time = between(0.5, 1)  # Much faster pace
    
    def on_start(self):
        """Initialize aggressive bettor state."""
        self.bet_count = 0
        self.fixed_amount = 0.5  # Fixed bet amount for consistent stress
    
    @task
    def stress_place_bet(self):
        """
        Place bets at high frequency to stress bankroll management.
        
        Focuses on:
        - Concurrent transaction building
        - Race conditions in liquidity checks
        - Database contention
        """
        self.bet_count += 1
        
        payload = create_bet_payload()
        # Use fixed amount to create predictable stress patterns
        payload["amount"] = str(int(self.fixed_amount * 1e9))
        
        with self.client.post(
            "/api/plinko/place-bet",
            json=payload,
            catch_response=True,
            name="/api/plinko/place-bet (stress)"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    response.success()
                else:
                    error_msg = data.get("error", "Unknown error")
                    # For stress testing, liquidity errors are expected
                    if "liquidity" in error_msg.lower():
                        response.failure("Insufficient liquidity (expected in stress)")
                    else:
                        response.failure(f"API error: {error_msg}")
            elif response.status_code == 400:
                error_text = response.text.lower()
                if "liquidity" in error_text:
                    response.failure("Liquidity exhaustion (expected)")
                else:
                    response.failure(f"Validation error: {response.text}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")


# ─── Test Events & Reporting ────────────────────────────────────────────

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when the load test starts."""
    print("\n" + "="*60)
    print("DUCKPOOLS LOAD TEST STARTING")
    print("="*60)
    print(f"Start time: {datetime.utcnow().isoformat()}")
    
    if isinstance(environment.runner, MasterRunner):
        print("Running in distributed mode (master)")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when the load test stops."""
    print("\n" + "="*60)
    print("DUCKPOOLS LOAD TEST COMPLETED")
    print("="*60)
    print(f"End time: {datetime.utcnow().isoformat()}")
    
    # Print statistics summary
    stats = environment.stats
    print(f"\nTotal requests: {stats.total.num_requests}")
    print(f"Failed requests: {stats.total.num_failures}")
    print(f"Success rate: {(1 - stats.total.fail_ratio) * 100:.2f}%")
    print(f"Response time avg: {stats.total.avg_response_time:.0f}ms")
    print(f"Response time p95: {stats.total.get_response_time_percentile(0.95):.0f}ms")
    print(f"Response time p99: {stats.total.get_response_time_percentile(0.99):.0f}ms")
    print(f"RPS (avg): {stats.total.total_rps:.2f}")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """
    Called for each request. Can be used for custom logging or monitoring.
    
    This is useful for:
    - Logging to external monitoring systems
    - Triggering alerts on error thresholds
    - Collecting custom metrics
    """
    # Example: Log slow requests (>1000ms)
    if response_time > 1000:
        print(f"\n[WARNING] Slow request: {name} took {response_time}ms")
    
    # Example: Log failures
    if exception:
        print(f"\n[ERROR] Failed request: {name} - {exception}")
