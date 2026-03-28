"""
Plinko game logic implementation with symmetric multiplier tables.

Implements the power-law formula for calculating multipliers:
multiplier(k) = A * (1/P(k))^alpha
where:
- P(k) = C(n, k) / 2^n (binomial probability)
- A = (1 - house_edge) / sum(P(j)^(1-alpha)) (normalization constant)
- alpha = 0.5 (risk parameter)
"""

import math
from typing import List, Tuple


def binomial_coefficient(n: int, k: int) -> int:
    """
    Calculate binomial coefficient C(n, k).
    
    Args:
        n: Total number of trials (rows)
        k: Number of successes (landing slot)
        
    Returns:
        Binomial coefficient C(n, k)
    """
    if k < 0 or k > n:
        return 0
    if k == 0 or k == n:
        return 1
    
    # Use multiplicative formula for better numerical stability
    result = 1
    for i in range(1, min(k, n - k) + 1):
        result = result * (n - i + 1) // i
    
    return result


def binomial_probability(n: int, k: int) -> float:
    """
    Calculate binomial probability P(k) = C(n, k) / 2^n.
    
    Args:
        n: Total number of rows
        k: Landing slot index (0 to n)
        
    Returns:
        Probability of landing in slot k
    """
    return binomial_coefficient(n, k) / (2 ** n)


def calculate_multipliers(rows: int, house_edge: float = 0.03, alpha: float = 0.5) -> List[float]:
    """
    Calculate symmetric multipliers for Plinko game.
    
    Args:
        rows: Number of rows (8, 12, or 16)
        house_edge: House edge (default: 3%)
        alpha: Risk parameter (default: 0.5)
        
    Returns:
        List of multipliers for each slot (0 to rows)
    """
    if rows not in [8, 12, 16]:
        raise ValueError(f"Invalid number of rows: {rows}. Must be 8, 12, or 16.")
    
    n = rows
    slots = n + 1  # Number of landing slots
    
    # Calculate probabilities for each slot
    probabilities = []
    for k in range(slots):
        prob = binomial_probability(n, k)
        probabilities.append(prob)
    
    # Calculate normalization constant A
    numerator = 1.0 - house_edge
    denominator = 0.0
    
    for prob in probabilities:
        denominator += prob ** (1.0 - alpha)
    
    A = numerator / denominator
    
    # Calculate multipliers using power-law formula
    multipliers = []
    for k in range(slots):
        prob = probabilities[k]
        if prob > 0:
            multiplier = A * (1.0 / prob) ** alpha
        else:
            multiplier = 0.0
        multipliers.append(multiplier)
    
    # Verify symmetry: multiplier[i] should equal multiplier[rows-i]
    for i in range(slots // 2):
        if abs(multipliers[i] - multipliers[n - i]) > 1e-10:
            raise ValueError(f"Symmetry violation at slot {i}: {multipliers[i]} != {multipliers[n - i]}")
    
    return multipliers


def get_plinko_config() -> dict:
    """
    Get Plinko game configuration with multiplier tables.
    
    Returns:
        Dictionary with multiplier tables for different row counts
    """
    config = {
        "8": calculate_multipliers(8),
        "12": calculate_multipliers(12),
        "16": calculate_multipliers(16)
    }
    
    return config


def get_expected_value(multipliers: List[float], house_edge: float = 0.03) -> float:
    """
    Calculate expected value for a multiplier table.
    Should equal 1 - house_edge for a fair game.
    
    Args:
        multipliers: List of multipliers
        house_edge: Expected house edge
        
    Returns:
        Expected value
    """
    n = len(multipliers) - 1  # Number of rows
    expected_value = 0.0
    
    for k, multiplier in enumerate(multipliers):
        prob = binomial_probability(n, k)
        expected_value += prob * multiplier
    
    return expected_value


if __name__ == "__main__":
    # Test the implementation
    print("Plinko Multiplier Tables")
    print("=" * 50)
    
    for rows in [8, 12, 16]:
        print(f"\n{rows}-row Table:")
        multipliers = calculate_multipliers(rows)
        expected = get_expected_value(multipliers)
        
        # Print multipliers in pairs to show symmetry
        for i in range(len(multipliers) // 2):
            j = len(multipliers) - 1 - i
            if i == j:
                print(f"Slot {i:2d}: {multipliers[i]:6.2f}x")
            else:
                print(f"Slot {i:2d}: {multipliers[i]:6.2f}x  Slot {j:2d}: {multipliers[j]:6.2f}x")
        
        print(f"Expected Value: {expected:.4f} (should be {1-0.03:.4f})")
        print(f"House Edge: {(1 - expected) * 100:.2f}%")
        print()