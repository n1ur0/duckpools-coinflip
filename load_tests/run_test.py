#!/usr/bin/env python3
"""
DuckPools Load Test Runner

Convenient script to run preconfigured load test scenarios.

Usage:
    python run_test.py smoke
    python run_test.py normal
    python run_test.py stress
    python run_test.py list  # List all scenarios
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Add load_tests directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config import get_scenario, SCENARIOS


def run_scenario(scenario_name: str, headless: bool = False, workers: int = 1):
    """
    Run a load test scenario using Locust.
    
    Args:
        scenario_name: Name of the scenario to run
        headless: Run without web UI (CLI mode)
        workers: Number of worker processes (for distributed testing)
    """
    scenario = get_scenario(scenario_name)
    
    print(f"\n{'='*70}")
    print(f"Running Scenario: {scenario.name}")
    print(f"{'='*70}")
    print(f"Description: {scenario.description}")
    print(f"Target Host: {scenario.host}")
    print(f"Concurrent Users: {scenario.users}")
    print(f"Spawn Rate: {scenario.spawn_rate} users/sec")
    print(f"Duration: {scenario.run_time}")
    print(f"User Classes: {', '.join(scenario.user_classes)}")
    print(f"Headless: {headless}")
    print(f"Workers: {workers}")
    print(f"{'='*70}\n")
    
    # Build Locust command
    cmd = [
        "locust",
        "-f", str(Path(__file__).parent / "locustfile.py"),
        "--host", scenario.host,
        "--users", str(scenario.users),
        "--spawn-rate", str(scenario.spawn_rate),
        "--run-time", scenario.run_time,
        "--html", f"reports/{scenario_name}_{scenario.run_time}.html",
        "--csv", f"reports/{scenario_name}_{scenario.run_time}",
    ]
    
    # Add headless flag
    if headless:
        cmd.append("--headless")
    
    # Add user classes filter
    if scenario.user_classes:
        user_classes = ",".join(scenario.user_classes)
        cmd.extend(["--user-class", user_classes])
    
    # Create reports directory if it doesn't exist
    reports_dir = Path(__file__).parent.parent / "load_tests" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\nStarting Locust...")
    print(f"Command: {' '.join(cmd)}\n")
    
    try:
        subprocess.run(cmd, check=True)
        print("\n✓ Load test completed successfully!")
        print(f"Reports saved to: {reports_dir}")
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Load test failed with exit code {e.returncode}")
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run DuckPools load test scenarios",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_test.py smoke              # Run smoke test with web UI
  python run_test.py normal --headless   # Run normal test in CLI mode
  python run_test.py stress --workers 4  # Run stress test with 4 workers
  python run_test.py list                # List all available scenarios
        """
    )
    
    parser.add_argument(
        "scenario",
        nargs="?",
        help="Name of the scenario to run (or 'list' to show scenarios)",
    )
    
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without web UI (CLI mode)",
    )
    
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes for distributed testing",
    )
    
    args = parser.parse_args()
    
    # List scenarios if requested
    if args.scenario == "list":
        from config import list_scenarios
        list_scenarios()
        return
    
    # Validate scenario
    if not args.scenario:
        parser.print_help()
        print("\nError: No scenario specified. Use 'list' to see available scenarios.")
        sys.exit(1)
    
    if args.scenario not in SCENARIOS:
        print(f"\nError: Unknown scenario '{args.scenario}'")
        print("Use 'list' to see available scenarios.")
        sys.exit(1)
    
    # Run the scenario
    run_scenario(args.scenario, args.headless, args.workers)


if __name__ == "__main__":
    main()
