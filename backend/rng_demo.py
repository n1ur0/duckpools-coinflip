"""
DuckPools RNG Statistical Test Suite Demo
========================================

This script demonstrates how to use the RNG statistical test suite
to verify the fairness of the DuckPools RNG mechanism.

Usage:
    python3 rng_demo.py
"""

from rng_statistical_suite import RNGStatisticalSuite

def main():
    """Run the RNG demo with different sample sizes."""
    print("DuckPools RNG Statistical Test Suite Demo")
    print("=" * 50)
    
    # Create test suite with standard alpha (0.01 = 99% confidence)
    suite = RNGStatisticalSuite(alpha=0.01)
    
    # Test with different sample sizes
    sample_sizes = [1000, 10_000, 100_000]
    
    for n in sample_sizes:
        print(f"\n--- Testing with {n:,} samples ---")
        
        # Generate random outcomes using the DuckPools RNG scheme
        print(f"Generating {n:,} RNG outcomes...")
        outcomes = suite.simulate_outcomes(n)
        
        # Count outcomes
        heads_count = outcomes.count(0)
        tails_count = outcomes.count(1)
        heads_pct = heads_count / n * 100
        tails_pct = tails_count / n * 100
        
        print(f"Heads (0): {heads_count:,} ({heads_pct:.2f}%)")
        print(f"Tails (1): {tails_count:,} ({tails_pct:.2f}%)")
        
        # Run all statistical tests
        print("Running statistical tests...")
        results = suite.run_all_tests(outcomes)
        
        # Print results
        suite.print_test_results(results)
        
        # Additional analysis for large samples
        if n >= 10_000:
            print("\n--- Detailed Analysis ---")
            for result in results.test_results:
                if not result.passed:
                    print(f"⚠️  {result.test_name} FAILED")
                    print(f"    Statistic: {result.statistic:.4f}")
                    print(f"    P-value: {result.p_value:.6f}")
                    if result.details and 'note' in result.details:
                        print(f"    Note: {result.details['note']}")
        
        print("\n" + "=" * 80)
    
    # Test with a known biased RNG (for demonstration)
    print("\n--- Testing with Biased RNG (for demonstration) ---")
    
    # Create a biased RNG (70% heads)
    n_biased = 10_000
    biased_outcomes = [0] * int(n_biased * 0.7) + [1] * int(n_biased * 0.3)
    
    print(f"Biased RNG: 70% heads, 30% tails")
    print(f"Heads (0): {biased_outcomes.count(0):,} ({biased_outcomes.count(0)/n_biased*100:.1f}%)")
    print(f"Tails (1): {biased_outcomes.count(1):,} ({biased_outcomes.count(1)/n_biased*100:.1f}%)")
    
    # Run tests on biased RNG
    biased_results = suite.run_all_tests(biased_outcomes)
    suite.print_test_results(biased_results)
    
    print("\n" + "=" * 80)
    print("Demo completed!")

if __name__ == "__main__":
    main()