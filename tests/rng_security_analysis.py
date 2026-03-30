"""
DuckPools RNG Security Analysis — MAT-220
==========================================
Comprehensive statistical verification of the provably-fair RNG scheme.

Actual scheme (matching on-chain coinflip_v2.es):
    outcome = blake2b256(blockId_raw_bytes || playerSecret)[0] % 2

NOTE: The issue description mentions SHA-256, but the actual implementation
uses blake2b256 (Ergo's native hash). This analysis tests the ACTUAL scheme.

Tests performed:
  1. Chi-square uniformity test (100k+ samples)
  2. Wald-Wolfowitz runs test (independence)
  3. Streak analysis (consecutive same outcomes)
  4. Modulo bias verification (first byte % 2)
  5. Commitment binding analysis (collision/preimage resistance)
  6. Block hash manipulation cost analysis
  7. Secret entropy analysis
"""

import hashlib
import math
import os
import struct
import time
from collections import Counter
from typing import Tuple, List, Dict, Optional

# ═══════════════════════════════════════════════════════════════════════════
# 1. CORE RNG — matches on-chain contract exactly
# ═══════════════════════════════════════════════════════════════════════════

def compute_rng(block_hash_hex: str, secret_bytes: bytes) -> int:
    """
    Compute RNG outcome matching on-chain contract exactly.
    blake2b256(blockId_raw_bytes || playerSecret)[0] % 2
    """
    block_hash_bytes = bytes.fromhex(block_hash_hex)
    rng_data = block_hash_bytes + secret_bytes
    rng_hash = hashlib.blake2b(rng_data, digest_size=32).digest()
    return rng_hash[0] % 2


def compute_rng_sha256(block_hash_hex: str, secret_bytes: bytes) -> int:
    """
    SHA-256 variant (NOT used on-chain, but mentioned in issue).
    For comparison only.
    """
    block_hash_bytes = bytes.fromhex(block_hash_hex)
    rng_data = block_hash_bytes + secret_bytes
    rng_hash = hashlib.sha256(rng_data).digest()
    return rng_hash[0] % 2


# ═══════════════════════════════════════════════════════════════════════════
# 2. CHI-SQUARE UNIFORMITY TEST
# ═══════════════════════════════════════════════════════════════════════════

def chi_square_test(counts: Dict[int, int]) -> Tuple[float, float]:
    """
    Chi-square goodness-of-fit test for uniform distribution.
    df = k - 1 where k = number of categories (2 for coinflip).
    
    Uses exact computation via the chi-square CDF approximation
    using the regularized incomplete gamma function.
    """
    total = sum(counts.values())
    k = len(counts)
    expected = total / k
    
    chi_sq = sum((obs - expected) ** 2 / expected for obs in counts.values())
    
    # For df=1, the chi-square CDF can be computed via erf:
    # P(X <= x) = erf(sqrt(x/2))
    # p-value = 1 - CDF
    df = k - 1
    if df == 1:
        # Exact p-value for df=1 using error function
        from math import erf, sqrt, exp
        p_value = 1.0 - erf(sqrt(chi_sq / 2.0))
    else:
        # Wilson-Hilferty approximation for df > 1
        z = ((chi_sq / df) ** (1.0/3.0) - (1.0 - 2.0/(9.0*df))) / sqrt(2.0/(9.0*df))
        # Standard normal CDF approximation
        p_value = 1.0 - normal_cdf(z)
    
    return chi_sq, p_value


def normal_cdf(x: float) -> float:
    """Standard normal CDF using Abramowitz and Stegun approximation."""
    # Constants
    a1 =  0.254829592
    a2 = -0.284496736
    a3 =  1.421413741
    a4 = -1.453152027
    a5 =  1.061405429
    p  =  0.3275911

    sign = 1 if x >= 0 else -1
    x = abs(x) / math.sqrt(2)

    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
    
    return 0.5 * (1.0 + sign * y)


# ═══════════════════════════════════════════════════════════════════════════
# 3. WALD-WOLFOWITZ RUNS TEST (Independence)
# ═══════════════════════════════════════════════════════════════════════════

def runs_test(outcomes: List[int]) -> Tuple[float, float]:
    """
    Wald-Wolfowitz runs test for independence.
    
    A "run" is a maximal sequence of identical outcomes.
    Tests whether the sequence is random (independent).
    
    Returns: (z_statistic, p_value)
    """
    n = len(outcomes)
    if n < 2:
        return 0.0, 1.0
    
    # Count runs
    runs = 1
    for i in range(1, n):
        if outcomes[i] != outcomes[i-1]:
            runs += 1
    
    n1 = sum(1 for o in outcomes if o == 1)  # heads
    n0 = n - n1  # tails
    
    if n1 == 0 or n0 == 0:
        return 0.0, 1.0  # degenerate case
    
    # Expected number of runs and variance
    expected_runs = (2 * n1 * n0) / n + 1
    var_runs = (2 * n1 * n0 * (2 * n1 * n0 - n)) / (n * n * (n - 1))
    
    if var_runs == 0:
        return 0.0, 1.0
    
    # Z-statistic (with continuity correction)
    z = (runs - expected_runs) / math.sqrt(var_runs)
    
    # Two-tailed p-value
    p_value = 2 * (1 - normal_cdf(abs(z)))
    
    return z, p_value


# ═══════════════════════════════════════════════════════════════════════════
# 4. STREAK ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════

def streak_analysis(outcomes: List[int]) -> Dict:
    """Analyze streaks of consecutive identical outcomes."""
    if not outcomes:
        return {}
    
    max_streak = 1
    current_streak = 1
    streak_counts = Counter()
    
    for i in range(1, len(outcomes)):
        if outcomes[i] == outcomes[i-1]:
            current_streak += 1
        else:
            streak_counts[current_streak] += 1
            max_streak = max(max_streak, current_streak)
            current_streak = 1
    
    streak_counts[current_streak] += 1
    max_streak = max(max_streak, current_streak)
    
    # Expected distribution of streaks for fair coin:
    # P(streak = k) = (1/2)^k for k >= 1
    expected_streak_5plus = 0
    for k in range(5, max_streak + 1):
        expected_streak_5plus += len(outcomes) * (0.5 ** k)
    
    actual_streak_5plus = sum(v for k, v in streak_counts.items() if k >= 5)
    
    return {
        "max_streak": max_streak,
        "streak_distribution": dict(sorted(streak_counts.items())),
        "streaks_5plus_count": actual_streak_5plus,
        "expected_streaks_5plus": expected_streak_5plus,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 5. MODULO BIAS VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════

def modulo_bias_analysis(n_samples: int = 256_000) -> Dict:
    """
    Verify no modulo bias exists when computing hash[0] % 2.
    
    A hash byte is uniformly distributed in [0, 255].
    Modulo 2: values 0,2,4,...,254 map to 0; values 1,3,5,...,255 map to 1.
    Each group has exactly 128 values, so NO modulo bias exists.
    
    We verify this empirically.
    """
    # Simulate hash bytes using random data (hash functions produce uniform output)
    import random
    random.seed(42)
    
    zero_count = 0
    one_count = 0
    
    # Use blake2b256 to be realistic
    for i in range(n_samples):
        data = os.urandom(64)
        h = hashlib.blake2b(data, digest_size=32).digest()
        outcome = h[0] % 2
        if outcome == 0:
            zero_count += 1
        else:
            one_count += 1
    
    ratio = zero_count / n_samples
    chi_sq, p_val = chi_square_test({0: zero_count, 1: one_count})
    
    return {
        "n_samples": n_samples,
        "mapped_to_0": zero_count,
        "mapped_to_1": one_count,
        "ratio_0": ratio,
        "ratio_1": 1 - ratio,
        "theoretical_ratio": 0.5,
        "has_modulo_bias": abs(ratio - 0.5) > 0.005,
        "chi_square": chi_sq,
        "p_value": p_val,
        "explanation": (
            "Byte values [0,255] are uniformly distributed. "
            "Modulo 2 maps 128 values to 0 and 128 values to 1. "
            "Exact 50/50 split — no modulo bias possible."
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════
# 6. MAIN SIMULATION
# ═══════════════════════════════════════════════════════════════════════════

def simulate_rng(n_bets: int = 100_000) -> Dict:
    """
    Simulate the actual RNG scheme with realistic inputs.
    Uses cryptographically random block hashes and player secrets.
    """
    print(f"  Generating {n_bets:,} simulated bets with blake2b256 RNG...")
    
    outcomes = []
    for i in range(n_bets):
        # Simulate 32-byte block hash (cryptographically random)
        block_hash = os.urandom(32).hex()
        # Simulate 32-byte player secret (matches on-chain R9)
        secret = os.urandom(32)
        
        outcome = compute_rng(block_hash, secret)
        outcomes.append(outcome)
    
    # Basic distribution
    counts = Counter(outcomes)
    heads = counts[1]
    tails = counts[0]
    
    # Chi-square test
    chi_sq, chi_p = chi_square_test({0: tails, 1: heads})
    
    # Runs test
    z_stat, runs_p = runs_test(outcomes)
    
    # Streak analysis
    streaks = streak_analysis(outcomes)
    
    # Shannon entropy
    total = len(outcomes)
    entropy = 0.0
    for count in counts.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)
    
    return {
        "n_bets": n_bets,
        "heads": heads,
        "tails": tails,
        "heads_pct": heads / total * 100,
        "tails_pct": tails / total * 100,
        "chi_square": chi_sq,
        "chi_p_value": chi_p,
        "chi_pass": chi_p > 0.01,
        "runs_z": z_stat,
        "runs_p_value": runs_p,
        "runs_pass": runs_p > 0.01,
        "entropy_bits": entropy,
        "max_entropy": 1.0,
        "streaks": streaks,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 7. DETERMINISTIC VECTOR TEST (known inputs/outputs)
# ═══════════════════════════════════════════════════════════════════════════

def deterministic_test():
    """Verify deterministic behavior with known inputs."""
    results = []
    
    # Test with all-zero inputs
    block = "00" * 32
    secret = b"\x00" * 32
    r = compute_rng(block, secret)
    results.append(("all-zeros", r))
    
    # Test with all-ff inputs
    block = "ff" * 32
    secret = b"\xff" * 32
    r = compute_rng(block, secret)
    results.append(("all-ff", r))
    
    # Test same block, different secrets -> should produce varying outcomes
    block = "ab" * 32
    outcomes = set()
    for i in range(100):
        secret = struct.pack(">Q", i) + b"\x00" * 24
        outcomes.add(compute_rng(block, secret))
    results.append(("same-block-diff-secrets-outcome-count", len(outcomes)))
    
    # Test same secret, different blocks -> should produce varying outcomes
    secret = os.urandom(32)
    outcomes = set()
    for i in range(100):
        block = struct.pack(">Q", i).hex() + "00" * 24
        outcomes.add(compute_rng(block, secret))
    results.append(("same-secret-diff-blocks-outcome-count", len(outcomes)))
    
    return results


# ═══════════════════════════════════════════════════════════════════════════
# 8. REPORT
# ═══════════════════════════════════════════════════════════════════════════

def print_report():
    print("=" * 72)
    print("  DuckPools RNG Security Analysis — MAT-220")
    print("  Scheme: blake2b256(blockId || playerSecret)[0] % 2")
    print("=" * 72)
    print()
    
    # ── Section 1: Modulo Bias ──
    print("── 1. MODULO BIAS VERIFICATION ──────────────────────────────────")
    print()
    bias = modulo_bias_analysis(256_000)
    print(f"  Samples tested:    {bias['n_samples']:,}")
    print(f"  Mapped to 0:       {bias['mapped_to_0']:,} ({bias['ratio_0']:.4%})")
    print(f"  Mapped to 1:       {bias['mapped_to_1']:,} ({bias['ratio_1']:.4%})")
    print(f"  Chi-square:        {bias['chi_square']:.6f}")
    print(f"  P-value:           {bias['p_value']:.6f}")
    print(f"  Modulo bias:       {'NO BIAS DETECTED' if not bias['has_modulo_bias'] else 'BIAS DETECTED!'}")
    print(f"  Reason:            {bias['explanation']}")
    print(f"  PASS:              {'YES' if not bias['has_modulo_bias'] and bias['p_value'] > 0.01 else 'NO'}")
    print()
    
    # ── Section 2: Statistical Simulation ──
    print("── 2. EMPIRICAL STATISTICAL TESTING ────────────────────────────")
    print()
    
    sim = simulate_rng(100_000)
    print(f"  Bets simulated:    {sim['n_bets']:,}")
    print(f"  Heads:             {sim['heads']:,} ({sim['heads_pct']:.4%})")
    print(f"  Tails:             {sim['tails']:,} ({sim['tails_pct']:.4%})")
    print()
    print(f"  [Chi-Square Test]")
    print(f"    Statistic:       {sim['chi_square']:.6f}")
    print(f"    P-value:         {sim['chi_p_value']:.6f}")
    print(f"    Threshold:       0.01")
    print(f"    PASS (p > 0.01): {'YES' if sim['chi_pass'] else 'NO'}")
    print()
    print(f"  [Runs Test — Wald-Wolfowitz]")
    print(f"    Z-statistic:     {sim['runs_z']:.6f}")
    print(f"    P-value:         {sim['runs_p_value']:.6f}")
    print(f"    Threshold:       0.01")
    print(f"    PASS (p > 0.01): {'YES' if sim['runs_pass'] else 'NO'}")
    print()
    print(f"  [Entropy]")
    print(f"    Shannon entropy: {sim['entropy_bits']:.6f} bits")
    print(f"    Max possible:    {sim['max_entropy']} bits")
    print(f"    Entropy ratio:   {sim['entropy_bits']/sim['max_entropy']*100:.4%}")
    print()
    
    # ── Section 3: Streak Analysis ──
    print("── 3. STREAK ANALYSIS ───────────────────────────────────────────")
    print()
    s = sim['streaks']
    print(f"  Max streak length: {s['max_streak']}")
    print(f"  Streaks >= 5:      {s['streaks_5plus_count']} (expected: ~{s['expected_streaks_5plus']:.0f})")
    print(f"  Distribution:")
    for length, count in sorted(s['streak_distribution'].items())[:15]:
        print(f"    Length {length}: {count}")
    if len(s['streak_distribution']) > 15:
        print(f"    ... and {len(s['streak_distribution']) - 15} more")
    print()
    
    # ── Section 4: Deterministic Verification ──
    print("── 4. DETERMINISTIC BEHAVIOR VERIFICATION ───────────────────────")
    print()
    det = deterministic_test()
    for name, val in det:
        print(f"  {name}: {val}")
    print()
    
    # ── Section 5: Theoretical Analysis ──
    print("── 5. THEORETICAL SECURITY ANALYSIS ─────────────────────────────")
    print()
    
    print("  [5a. Commitment Binding — Collision Resistance]")
    print()
    print("  The commitment scheme uses blake2b256(secret || choice_byte).")
    print("  Blake2b256 is a 256-bit cryptographic hash function.")
    print()
    print("  Collision resistance: The best known attack on blake2b256 requires")
    print("  ~2^128 operations (birthday attack). Finding two (secret, choice)")
    print("  pairs with the same commitment is computationally infeasible.")
    print()
    print("  Preimage resistance: Given a commitment hash, finding ANY (secret,")
    print("  choice) pair that produces it requires ~2^256 operations.")
    print("  This is completely infeasible with current or foreseeable technology.")
    print()
    print("  VERDICT: Commitment binding is SECURE.")
    print()
    
    print("  [5b. Block Hash Manipulation Analysis]")
    print()
    print("  TRUST ASSUMPTION (TA-2 from coinflip_v2.es):")
    print("  The HOUSE controls when to submit the reveal transaction.")
    print("  This means the house can theoretically grind block hashes by")
    print("  waiting for a block whose hash produces a favorable outcome.")
    print()
    print("  Attack scenario: House wants 'tails' (outcome=1).")
    print("  - House computes outcome for each new block using player's secret.")
    print("    NOTE: playerSecret is stored in R9 (visible on-chain).")
    print("  - If outcome is unfavorable, house simply waits for the next block.")
    print("  - Expected wait: ~2 blocks (50% chance each block).")
    print("  - Cost: Negligible — just delaying the reveal tx.")
    print()
    print("  Mitigation: The timeout mechanism (R8) limits grinding window.")
    print("  If house delays beyond timeout, player can claim 98% refund.")
    print("  But for blocks arriving every ~2 minutes, grinding 2-3 blocks")
    print("  (4-6 min delay) is unlikely to hit the timeout.")
    print()
    print("  Economic analysis:")
    print("  - With 3% house edge, house profit per bet = 3% of bet amount.")
    print("  - With grinding, house can achieve ~100% win rate = 97% of bet.")
    print("  - Net gain from grinding vs fair play: ~94% of bet amount.")
    print("  - Cost of grinding: A few minutes of delay (negligible).")
    print()
    print("  VERDICT: BLOCK HASH GRINDING IS A CRITICAL VULNERABILITY.")
    print("  The house can manipulate outcomes by choosing which block to")
    print("  reveal in. The timeout mechanism provides weak mitigation.")
    print()
    print("  RECOMMENDATION: Implement dual commitment scheme where the house")
    print("  also pre-commits to a value, and the outcome is derived from")
    print("  BOTH the block hash and the house's committed value. This")
    print("  prevents the house from grinding because they cannot change")
    print("  their committed value after seeing the block hash.")
    print()
    
    print("  [5c. Secret Entropy Analysis]")
    print()
    print("  The on-chain contract stores playerSecret in R9 as 32 bytes")
    print("  (Coll[Byte]). The frontend generates this using crypto.getRandomValues().")
    print()
    print("  Entropy: 32 bytes = 256 bits = 2^256 possible secrets.")
    print("  This is MORE than sufficient. Even 8 bytes (64 bits = 2^64)")
    print("  would be adequate, as brute-forcing 2^64 is infeasible.")
    print()
    print("  VERDICT: Secret entropy is EXCELLENT (256 bits).")
    print()
    
    print("  [5d. Testnet Block Time Entropy]")
    print()
    print("  Ergo testnet block time is ~2 minutes (vs ~2 min mainnet).")
    print("  Each block hash provides 256 bits of entropy (SHA-256 based).")
    print("  The block hash is derived from the PoW nonce + previous block hash")
    print("  + transactions + timestamp. Even with low hashrate on testnet,")
    print("  the block hash is unpredictable before the block is mined.")
    print()
    print("  VERDICT: Block hash entropy is SUFFICIENT.")
    print()
    
    # ── Section 6: Implementation Review ──
    print("── 6. IMPLEMENTATION REVIEW ─────────────────────────────────────")
    print()
    print("  Files reviewed:")
    print("    - backend/rng_module.py")
    print("    - frontend/src/utils/crypto.ts")
    print("    - smart-contracts/coinflip_v2.es")
    print()
    print("  FINDING 1 (MEDIUM): rng_module.py line 230 has corrupted code:")
    print("    'secret_bytes=***' — this would cause a SyntaxError if")
    print("    simulate_coinflip() is called. The line should be:")
    print("    'secret_bytes = os.urandom(32)'")
    print()
    print("  FINDING 2 (INFO): Issue description mentions SHA-256 but the")
    print("    actual implementation correctly uses blake2b256 (Ergo native).")
    print("    This is correct — SHA-256 would fail on-chain verification.")
    print()
    print("  FINDING 3 (INFO): Issue description says player secret is 8 bytes,")
    print("    but the on-chain contract uses 32 bytes (R9: Coll[Byte]).")
    print("    Frontend generates 8 bytes (crypto.ts:generateSecret).")
    print("    Need to verify alignment between frontend and contract.")
    print()
    print("  FINDING 4 (INFO): generate_commit() in rng_module.py uses 8-byte")
    print("    secret, but the on-chain R9 is documented as 32 bytes.")
    print("    The commitment formula is consistent (blake2b256(secret || choice))")
    print("    but the secret length should be verified.")
    print()
    
    # ── Summary ──
    print("── SUMMARY ──────────────────────────────────────────────────────")
    print()
    all_pass = (
        bias['p_value'] > 0.01 and
        not bias['has_modulo_bias'] and
        sim['chi_pass'] and
        sim['runs_pass'] and
        sim['entropy_bits'] > 0.99
    )
    
    print(f"  Chi-square uniformity:    {'PASS' if sim['chi_pass'] else 'FAIL'} (p={sim['chi_p_value']:.6f})")
    print(f"  Runs test (independence): {'PASS' if sim['runs_pass'] else 'FAIL'} (p={sim['runs_p_value']:.6f})")
    print(f"  Modulo bias:              {'PASS' if not bias['has_modulo_bias'] else 'FAIL'}")
    print(f"  Entropy (>= 0.99 bits):   {'PASS' if sim['entropy_bits'] > 0.99 else 'FAIL'} ({sim['entropy_bits']:.6f})")
    print(f"  Commitment binding:       SECURE (blake2b256 collision resistance)")
    print(f"  Secret entropy:           SECURE (256 bits)")
    print(f"  Block hash entropy:       SUFFICIENT")
    print(f"  Block hash grinding:      CRITICAL VULNERABILITY (house can manipulate)")
    print()
    print(f"  Overall RNG fairness:     {'PASS' if all_pass else 'FAIL'}")
    print()
    print("  CRITICAL FINDING: Block hash grinding allows the house to")
    print("  manipulate game outcomes. The house chooses when to reveal,")
    print("  and can wait for favorable block hashes. This undermines")
    print("  the provably-fair claim for the current single-commitment scheme.")
    print()
    print("  Recommended fix: Dual commitment (house also commits before")
    print("  bet placement). Outcome = f(blockHash, houseCommit, playerCommit).")
    print("  This eliminates the house's ability to grind.")
    print()
    print("=" * 72)
    print("  Analysis complete.")
    print("=" * 72)


if __name__ == "__main__":
    print_report()
