"""
DuckPools Plinko Game Logic

This module contains the core mathematical calculations for Plinko game,
including probability calculations, multipliers, and expected return calculations.

MAT-251: Fixed compute_expected_return to use probability-weighted average
instead of arithmetic mean.
"""

from typing import List
import math

# Constants
PLINKO_MIN_ROWS = 8
PLINKO_MAX_ROWS = 16
PLINKO_DEFAULT_ROWS = 12
PLINKO_HOUSE_EDGE = 0.03  # 3% house edge


def binomial_coefficient(n: int, k: int) -> int:
    """
    Calculate binomial coefficient C(n, k) = n! / (k! * (n-k)!)
    Used to compute slot probabilities in Plinko.
    
    Args:
        n: Total number of trials (rows)
        k: Number of successes (slot)
        
    Returns:
        Binomial coefficient
    """
    if k < 0 or k > n:
        return 0
    if k == 0 or k == n:
        return 1
    
    # Use iterative calculation to avoid large factorials
    result = 1
    for i in range(min(k, n - k)):
        result = result * (n - i) // (i + 1)
    return result


def get_zone_probabilities(rows: int) -> List[float]:
    """
    Calculate the probability of landing in each slot given n rows.
    P(k) = C(n, k) / 2^n
    
    Args:
        rows: Number of rows (8-16)
        
    Returns:
        List of probabilities where index = slot number (0 to rows)
    """
    if rows < PLINKO_MIN_ROWS or rows > PLINKO_MAX_ROWS:
        raise ValueError(f"Rows must be between {PLINKO_MIN_ROWS} and {PLINKO_MAX_ROWS}")
    
    n = rows
    probabilities = []
    
    for slot in range(rows + 1):
        # P(k) = C(n, k) / 2^n
        prob = binomial_coefficient(n, slot) / (2 ** n)
        probabilities.append(prob)
    
    return probabilities


def get_multiplier_table(rows: int) -> List[float]:
    """
    Calculate payout multiplier for each slot using power-law parameterization.
    
    Uses a power-law parameterization to create an exciting risk/reward curve
    while maintaining the exact house edge:
    
      multiplier(k) = A * (1/P(k))^alpha
    
    where A = (1 - house_edge) / sum(P(j)^(1-alpha))
    
    Args:
        rows: Number of rows
        
    Returns:
        List of multipliers where index = slot number (0 to rows)
    """
    if rows < PLINKO_MIN_ROWS or rows > PLINKO_MAX_ROWS:
        raise ValueError(f"Rows must be between {PLINKO_MIN_ROWS} and {PLINKO_MAX_ROWS}")
    
    probabilities = get_zone_probabilities(rows)
    alpha = 0.5  # Risk parameter: 0.5 = balanced, 0.7 = high risk
    
    # Pre-compute normalization constant for this row count
    denom = 0
    for s in range(rows + 1):
        denom += probabilities[s] ** (1 - alpha)
    
    A = (1 - PLINKO_HOUSE_EDGE) / denom
    
    multipliers = []
    for slot in range(rows + 1):
        probability = probabilities[slot]
        multiplier = A * (1 / probability) ** alpha
        multipliers.append(multiplier)
    
    return multipliers


def get_expected_value_table(rows: int) -> List[float]:
    """
    Calculate the expected value contribution from each slot.
    E[k] = P(k) * multiplier(k)
    
    Args:
        rows: Number of rows
        
    Returns:
        List of expected value contributions where index = slot number (0 to rows)
    """
    if rows < PLINKO_MIN_ROWS or rows > PLINKO_MAX_ROWS:
        raise ValueError(f"Rows must be between {PLINKO_MIN_ROWS} and {PLINKO_MAX_ROWS}")
    
    probabilities = get_zone_probabilities(rows)
    multipliers = get_multiplier_table(rows)
    
    expected_values = []
    for slot in range(rows + 1):
        expected_values.append(probabilities[slot] * multipliers[slot])
    
    return expected_values


def compute_expected_return(rows: int) -> float:
    """
    Compute the expected return for Plinko using PROBABILITY-WEIGHTED sum.
    
    E[X] = sum(P(k) * multiplier(k)) for all slots k
         = sum(P(k) * A * (1/P(k))^alpha)
         = A * sum(P(k)^(1-alpha))
         = (1 - house_edge) / sum(P(j)^(1-alpha)) * sum(P(k)^(1-alpha))
         = (1 - house_edge)
    
    This returns the expected multiplier, not the edge.
    The house edge is: 1 - expected_return
    
    MAT-251 FIX: This was previously using arithmetic mean (sum(table) / len(table))
    which incorrectly treated each landing zone as equally probable. Now correctly
    uses probability-weighted calculation.
    
    Args:
        rows: Number of rows
        
    Returns:
        Expected return multiplier (should be 1 - house_edge = 0.97)
    """
    if rows < PLINKO_MIN_ROWS or rows > PLINKO_MAX_ROWS:
        raise ValueError(f"Rows must be between {PLINKO_MIN_ROWS} and {PLINKO_MAX_ROWS}")
    
    table = get_multiplier_table(rows)
    probs = get_zone_probabilities(rows)
    
    # CORRECT: Probability-weighted calculation (MAT-251 fix)
    # This replaces the previous incorrect arithmetic mean:
    # return sum(table) / len(table)  # WRONG - assumes equal probability
    return sum(m * p for m, p in zip(table, probs))


def compute_house_edge(rows: int) -> float:
    """
    Compute the house edge for Plinko.
    
    Args:
        rows: Number of rows
        
    Returns:
        House edge (should be 0.03)
    """
    expected_return = compute_expected_return(rows)
    return 1.0 - expected_return


def calculate_payout(bet_amount: int, rows: int, slot: int) -> int:
    """
    Calculate payout amount in nanoERG from bet amount and slot.
    
    Args:
        bet_amount: Bet amount in nanoERG
        rows: Number of rows
        slot: Landing slot
        
    Returns:
        Payout amount in nanoERG
    """
    if rows < PLINKO_MIN_ROWS or rows > PLINKO_MAX_ROWS:
        raise ValueError(f"Rows must be between {PLINKO_MIN_ROWS} and {PLINKO_MAX_ROWS}")
    
    if slot < 0 or slot > rows:
        raise ValueError(f"Slot {slot} out of range for {rows} rows (must be 0-{rows})")
    
    multipliers = get_multiplier_table(rows)
    multiplier = multipliers[slot]
    
    return int(bet_amount * multiplier)


def get_theoretical_rtp() -> float:
    """
    Get the theoretical RTP (Return to Player) for Plinko.
    
    RTP = (expected_payout / bet) * 100
         = (1 - house_edge) * 100
    
    For a 3% house edge, RTP = 97%
    
    Returns:
        RTP as percentage (e.g., 97.0 for 3% house edge)
    """
    return (1 - PLINKO_HOUSE_EDGE) * 100


# Validation functions
def validate_multiplier_table(rows: int) -> bool:
    """
    Validate that the multiplier table produces the correct expected return.
    
    Args:
        rows: Number of rows
        
    Returns:
        True if the expected return matches the theoretical value (within tolerance)
    """
    expected_return = compute_expected_return(rows)
    theoretical_return = 1.0 - PLINKO_HOUSE_EDGE
    
    # Allow for small floating point errors
    tolerance = 1e-10
    return abs(expected_return - theoretical_return) < tolerance


def validate_probability_sum(rows: int) -> bool:
    """
    Validate that probabilities sum to 1.
    
    Args:
        rows: Number of rows
        
    Returns:
        True if probabilities sum to 1 (within tolerance)
    """
    probabilities = get_zone_probabilities(rows)
    total = sum(probabilities)
    
    # Allow for small floating point errors
    tolerance = 1e-10
    return abs(total - 1.0) < tolerance


if __name__ == "__main__":
    # Test the implementation
    print("Plinko Logic Test")
    print("=" * 40)
    
    for rows in [8, 12, 16]:
        print(f"\nRows: {rows}")
        print("-" * 20)
        
        expected_return = compute_expected_return(rows)
        house_edge = compute_house_edge(rows)
        rtp = get_theoretical_rtp()
        
        print(f"Expected Return: {expected_return:.10f}")
        print(f"House Edge: {house_edge:.10f}")
        print(f"Theoretical RTP: {rtp:.1f}%")
        
        # Validate
        is_valid_return = validate_multiplier_table(rows)
        is_valid_prob = validate_probability_sum(rows)
        
        print(f"Return Validation: {'PASS' if is_valid_return else 'FAIL'}")
        print(f"Probability Validation: {'PASS' if is_valid_prob else 'FAIL'}")
        
        # Show sample of probabilities and multipliers
        probs = get_zone_probabilities(rows)
        multipliers = get_multiplier_table(rows)
        
        print(f"Center Zone: prob={probs[rows//2]:.4f}, mult={multipliers[rows//2]:.2f}")
        print(f"Edge Zone: prob={probs[0]:.4f}, mult={multipliers[0]:.2f}")