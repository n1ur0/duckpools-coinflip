"""
Load Test Configuration

Defines various load test scenarios for DuckPools API testing.
Each scenario targets different aspects of the system.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class LoadTestScenario:
    """Defines a load test scenario."""
    name: str
    description: str
    users: int
    spawn_rate: int
    run_time: str  # e.g., "5m", "1h", "30s"
    user_classes: List[str]
    host: str = "http://localhost:8000"


# ─── Predefined Scenarios ───────────────────────────────────────────────

SCENARIOS = {
    # Light load: 10 users, normal pace
    "smoke": LoadTestScenario(
        name="Smoke Test",
        description="Quick sanity check with minimal load",
        users=10,
        spawn_rate=5,
        run_time="1m",
        user_classes=["DuckPoolsUser"],
        host="http://localhost:8000",
    ),
    
    # Normal load: 50 concurrent users
    "normal": LoadTestScenario(
        name="Normal Load",
        description="Simulates expected production traffic",
        users=50,
        spawn_rate=10,
        run_time="10m",
        user_classes=["DuckPoolsUser"],
        host="http://localhost:8000",
    ),
    
    # Peak load: 200 concurrent users
    "peak": LoadTestScenario(
        name="Peak Load",
        description="Simulates high-traffic periods (e.g., sports events)",
        users=200,
        spawn_rate=20,
        run_time="15m",
        user_classes=["DuckPoolsUser"],
        host="http://localhost:8000",
    ),
    
    # Stress test: Mix of normal and aggressive users
    "stress": LoadTestScenario(
        name="Bankroll Stress",
        description="Aggressive betting to test bankroll management",
        users=100,
        spawn_rate=25,
        run_time="20m",
        user_classes=["DuckPoolsUser", "BankrollStressUser"],
        host="http://localhost:8000",
    ),
    
    # Burst test: Rapid ramp-up
    "burst": LoadTestScenario(
        name="Burst Test",
        description="Simulates sudden traffic spike",
        users=150,
        spawn_rate=50,  # Fast ramp-up
        run_time="5m",
        user_classes=["DuckPoolsUser"],
        host="http://localhost:8000",
    ),
    
    # Endurance test: Long running
    "endurance": LoadTestScenario(
        name="Endurance Test",
        description="Long-duration test to check for memory leaks",
        users=50,
        spawn_rate=5,
        run_time="1h",
        user_classes=["DuckPoolsUser"],
        host="http://localhost:8000",
    ),
}


def get_scenario(name: str) -> LoadTestScenario:
    """Get a scenario by name."""
    if name not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {name}. Available: {list(SCENARIOS.keys())}")
    return SCENARIOS[name]


def list_scenarios() -> None:
    """Print all available scenarios."""
    print("\nAvailable Load Test Scenarios:")
    print("="*70)
    
    for key, scenario in SCENARIOS.items():
        print(f"\n[{key}] {scenario.name}")
        print(f"  {scenario.description}")
        print(f"  Users: {scenario.users}")
        print(f"  Spawn Rate: {scenario.spawn_rate}")
        print(f"  Duration: {scenario.run_time}")
        print(f"  User Classes: {', '.join(scenario.user_classes)}")


if __name__ == "__main__":
    list_scenarios()
