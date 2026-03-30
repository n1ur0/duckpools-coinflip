#!/usr/bin/env python3
"""
RNG Fairness and Bias Analysis Script
Tests the SHA-256 based RNG scheme for statistical bias
"""

import hashlib
import random
import statistics
import math
from collections import Counter

def simulate_rng_outcomes(num_simulations=100000):
    """Simulate RNG outcomes using the SHA-256 scheme"""
    outcomes = []
    
    for _ in range(num_simulations):
        # Generate random inputs
        commitment = random.getrandbits(256)  # 32 bytes
        secret = random.getrandbits(256)      # 32 bytes  
        block_hash = random.getrandbits(256)   # 32 bytes (simulated)
        
        # Create the hash input
        hash_input = f"{commitment}{secret}{block_hash}".encode('utf-8')
        
        # Calculate SHA-256 hash
        sha256_hash = hashlib.sha256(hash_input).hexdigest()
        
        # Take first byte and convert to 0 or 1 (heads/tails)
        first_byte = int(sha256_hash[0:2], 16)
        outcome = first_byte % 2  # 0 for heads, 1 for tails
        
        outcomes.append(outcome)
    
    return outcomes

def run_chi_square_test(outcomes):
    """Run chi-square test for uniform distribution"""
    n = len(outcomes)
    heads = sum(1 for o in outcomes if o == 0)
    tails = sum(1 for o in outcomes if o == 1)
    
    expected = n / 2
    chi_square = ((heads - expected) ** 2 / expected) + ((tails - expected) ** 2 / expected)
    
    # For 1 degree of freedom, p-value calculation
    p_value = 1 - 0.6827 if chi_square <= 0.455 else \
             1 - 0.9545 if chi_square <= 1.386 else \
             1 - 0.9973 if chi_square <= 4.605 else 0.01
    
    return chi_square, p_value, heads, tails

def run_runs_test(outcomes):
    """Run runs test for independence"""
    runs = 1
    for i in range(1, len(outcomes)):
        if outcomes[i] != outcomes[i-1]:
            runs += 1
    
    n = len(outcomes)
    expected_runs = (2 * n - 1) / 3
    variance = (16 * n - 29) / 90
    
    z_score = (runs - expected_runs) / (variance ** 0.5)
    p_value = 2 * (1 - 0.6827) if abs(z_score) > 0.674 else \
             2 * (1 - 0.9545) if abs(z_score) > 1.96 else \
             2 * (1 - 0.9973) if abs(z_score) > 2.576 else 0.01
    
    return runs, expected_runs, z_score, p_value

def analyze_streaks(outcomes):
    """Analyze streaks in the outcomes"""
    max_streak = 0
    current_streak = 1
    
    for i in range(1, len(outcomes)):
        if outcomes[i] == outcomes[i-1]:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 1
    
    return max_streak

def main():
    print("RNG Fairness and Bias Analysis")
    print("=" * 50)
    
    # Run simulations
    print("Running 100,000 RNG simulations...")
    outcomes = simulate_rng_outcomes(100000)
    
    # Basic statistics
    total = len(outcomes)
    heads = sum(1 for o in outcomes if o == 0)
    tails = sum(1 for o in outcomes if o == 1)
    
    print(f"\nBasic Statistics:")
    print(f"Total simulations: {total}")
    print(f"Heads: {heads} ({heads/total*100:.2f}%)")
    print(f"Tails: {tails} ({tails/total*100:.2f}%)")
    print(f"Difference: {abs(heads-tails)} ({abs(heads-tails)/total*100:.4f}%)")
    
    # Chi-square test
    chi_square, chi_p, heads, tails = run_chi_square_test(outcomes)
    print(f"\nChi-Square Test:")
    print(f"Chi-square statistic: {chi_square:.4f}")
    print(f"P-value: {chi_p:.4f}")
    print(f"Interpretation: {'NO significant bias' if chi_p > 0.01 else 'SIGNIFICANT bias detected'}")
    
    # Runs test
    runs, expected_runs, z_score, runs_p = run_runs_test(outcomes)
    print(f"\nRuns Test:")
    print(f"Observed runs: {runs}")
    print(f"Expected runs: {expected_runs:.2f}")
    print(f"Z-score: {z_score:.4f}")
    print(f"P-value: {runs_p:.4f}")
    print(f"Interpretation: {'NO significant autocorrelation' if runs_p > 0.01 else 'SIGNIFICANT autocorrelation detected'}")
    
    # Streak analysis
    max_streak = analyze_streaks(outcomes)
    print(f"\nStreak Analysis:")
    print(f"Maximum consecutive same outcome: {max_streak}")
    print(f"Expected max streak for 100k trials: ~18")
    print(f"Interpretation: {'NORMAL' if max_streak <= 25 else 'POTENTIALLY ABNORMAL'}")
    
    # Entropy analysis
    entropy = -sum(p * math.log2(p) for p in [heads/total, tails/total])
    print(f"\nEntropy: {entropy:.4f} bits (max 1.0 for fair coin)")
    
    print("\n" + "=" * 50)
    print("RNG Fairness Assessment:")
    print(f"✓ Uniform distribution: {'PASS' if chi_p > 0.01 else 'FAIL'}")
    print(f"✓ Independence: {'PASS' if runs_p > 0.01 else 'FAIL'}")
    print(f"✓ Reasonable streaks: {'PASS' if max_streak <= 25 else 'FAIL'}")
    print(f"✓ Sufficient entropy: {'PASS' if entropy > 0.9 else 'FAIL'}")

if __name__ == "__main__":
    main()