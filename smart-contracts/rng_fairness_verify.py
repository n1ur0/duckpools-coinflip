"""
DuckPools — RNG Fairness Verification Module

Verifies the provably-fair RNG used in the coinflip contract.
This module can be used by:
  - Security auditors to verify game fairness
  - Players to verify their game outcomes post-reveal
  - QA to validate the RNG implementation

RNG ALGORITHM (coinflip_v2_final.es):
  1. Player generates random secret (8-32 bytes)
  2. Player commits: blake2b256(secret || choice_byte)
  3. House reveals using: blake2b256(parentBlockId || secret)[0] % 2

SECURITY PROPERTIES:
  - Commitment binding: player cannot change choice after commit
  - Commitment hiding: house cannot learn choice from commitment alone
  - Entropy: 32 bytes block hash + 32 bytes secret = 64 bytes entropy
  - Verifiability: anyone can recompute RNG given block hash + secret

KNOWN LIMITATIONS:
  - House selects reveal block (block-hash grinding risk)
  - Player secret visible on-chain (honest house assumption)
  - Production should use ZK proofs + pre-committed block height
"""

import hashlib
import os
import struct
from dataclasses import dataclass
from typing import List, Tuple, Optional


def blake2b256(data: bytes) -> bytes:
    """Blake2b-256 hash — native Ergo opcode."""
    h = hashlib.blake2b(digest_size=32)
    h.update(data)
    return h.digest()


@dataclass
class RNGVerificationResult:
    """Result of an RNG verification check."""
    valid: bool
    flip_result: int          # 0=heads, 1=tails
    player_choice: int        # 0=heads, 1=tails
    player_wins: bool
    commitment_hash: str      # hex
    computed_commitment: str  # hex
    block_id: str             # hex
    rng_hash: str             # hex
    error: Optional[str] = None


def compute_commitment(secret: bytes, choice: int) -> bytes:
    """
    Compute player commitment: blake2b256(secret || choice_byte)
    Must match on-chain: blake2b256(playerSecret ++ Coll(choiceByte))
    """
    choice_byte = 0x00 if choice == 0 else 0x01
    return blake2b256(secret + bytes([choice_byte]))


def compute_flip(block_id: bytes, secret: bytes) -> int:
    """
    Compute coin flip result: blake2b256(blockId || secret)[0] % 2
    Must match on-chain: blake2b256(blockSeed ++ playerSecret)(0) % 2
    """
    rng_hash = blake2b256(block_id + secret)
    return rng_hash[0] % 2


def verify_game_outcome(
    secret: bytes,
    choice: int,
    commitment_hash: bytes,
    block_id: bytes,
    claimed_result: Optional[int] = None
) -> RNGVerificationResult:
    """
    Verify a complete game outcome.

    Args:
        secret: Player's random secret bytes
        choice: Player's choice (0=heads, 1=tails)
        commitment_hash: The commitment hash stored in R6 (32 bytes)
        block_id: The parent block ID used for RNG (32 bytes)
        claimed_result: Optional claimed flip result to verify against

    Returns:
        RNGVerificationResult with full verification details
    """
    # Verify commitment
    computed = compute_commitment(secret, choice)

    if computed != commitment_hash:
        return RNGVerificationResult(
            valid=False,
            flip_result=-1,
            player_choice=choice,
            player_wins=False,
            commitment_hash=commitment_hash.hex(),
            computed_commitment=computed.hex(),
            block_id=block_id.hex(),
            rng_hash='',
            error='COMMITMENT_MISMATCH: secret+choice does not produce stored hash'
        )

    # Compute RNG
    rng_hash = blake2b256(block_id + secret)
    flip_result = rng_hash[0] % 2

    # Verify claimed result if provided
    if claimed_result is not None and flip_result != claimed_result:
        return RNGVerificationResult(
            valid=False,
            flip_result=flip_result,
            player_choice=choice,
            player_wins=False,
            commitment_hash=commitment_hash.hex(),
            computed_commitment=computed.hex(),
            block_id=block_id.hex(),
            rng_hash=rng_hash.hex(),
            error=f'RESULT_MISMATCH: computed {flip_result} but claimed {claimed_result}'
        )

    return RNGVerificationResult(
        valid=True,
        flip_result=flip_result,
        player_choice=choice,
        player_wins=(flip_result == choice),
        commitment_hash=commitment_hash.hex(),
        computed_commitment=computed.hex(),
        block_id=block_id.hex(),
        rng_hash=rng_hash.hex()
    )


def run_statistical_fairness_test(
    num_samples: int = 10000,
    secret: Optional[bytes] = None,
    fixed_block_id: Optional[bytes] = None
) -> dict:
    """
    Run statistical fairness test on the RNG.

    Tests:
    1. Uniformity: heads/tails should be ~50/50
    2. Runs test: no long sequences of same outcome
    3. Serial correlation: consecutive flips should be independent

    Args:
        num_samples: Number of samples to test
        secret: Fixed secret (if None, varies per sample)
        fixed_block_id: Fixed block ID (if None, varies per sample)

    Returns:
        Dict with test results and p-values
    """
    results = []
    base_secret = secret or b'\x00' * 32
    base_block = fixed_block_id or b'\x00' * 32

    for i in range(num_samples):
        # Vary entropy source
        s = base_secret if secret else i.to_bytes(32, 'big')
        b = base_block if fixed_block_id else i.to_bytes(32, 'big')
        flip = compute_flip(b, s)
        results.append(flip)

    heads = results.count(0)
    tails = results.count(1)
    heads_ratio = heads / num_samples

    # Chi-squared test for uniformity (df=1, critical=3.841 at p=0.05)
    expected = num_samples / 2
    chi_squared = ((heads - expected) ** 2 / expected +
                   (tails - expected) ** 2 / expected)
    uniformity_pass = chi_squared < 3.841

    # Runs test (count consecutive same-outcome sequences)
    runs = 1
    for i in range(1, len(results)):
        if results[i] != results[i - 1]:
            runs += 1

    # Expected runs for n observations with p=0.5:
    # E(R) = 1 + 2*n0*n1/n, Var(R) = 2*n0*n1*(2*n0*n1 - n)/(n^2*(n-1))
    n0, n1 = heads, tails
    n = num_samples
    expected_runs = 1 + 2 * n0 * n1 / n
    if n > 1:
        var_runs = 2 * n0 * n1 * (2 * n0 * n1 - n) / (n * n * (n - 1))
        std_runs = var_runs ** 0.5 if var_runs > 0 else 1
        z_score = abs(runs - expected_runs) / std_runs if std_runs > 0 else 0
        runs_pass = z_score < 1.96  # 95% confidence
    else:
        z_score = 0
        runs_pass = True

    # Serial correlation (autocorrelation at lag=1)
    if num_samples > 1:
        mean = sum(results) / num_samples
        numerator = sum((results[i] - mean) * (results[i+1] - mean)
                        for i in range(num_samples - 1))
        denominator = sum((results[i] - mean) ** 2 for i in range(num_samples))
        autocorr = numerator / denominator if denominator > 0 else 0
        correlation_pass = abs(autocorr) < 0.05  # negligible correlation
    else:
        autocorr = 0
        correlation_pass = True

    return {
        'test_name': 'coinflip_v2_final_rng_fairness',
        'num_samples': num_samples,
        'results': {
            'heads': heads,
            'tails': tails,
            'heads_ratio': round(heads_ratio, 4),
            'runs': runs,
            'chi_squared': round(chi_squared, 4),
            'z_score': round(z_score, 4),
            'autocorrelation': round(autocorr, 6),
        },
        'tests': {
            'uniformity': {
                'pass': uniformity_pass,
                'chi_squared': round(chi_squared, 4),
                'threshold': 3.841,
                'description': 'Chi-squared test for 50/50 distribution'
            },
            'runs': {
                'pass': runs_pass,
                'z_score': round(z_score, 4),
                'observed_runs': runs,
                'expected_runs': round(expected_runs, 2),
                'description': 'Runs test for outcome independence'
            },
            'serial_correlation': {
                'pass': correlation_pass,
                'autocorrelation': round(autocorr, 6),
                'description': 'Autocorrelation at lag-1'
            }
        },
        'overall_pass': uniformity_pass and runs_pass and correlation_pass,
        'entropy_bits': 64,  # 32 bytes block + 32 bytes secret
        'hash_function': 'blake2b256',
        'extraction': 'first_byte % 2'
    }


if __name__ == '__main__':
    import json
    import sys

    # Quick verification demo
    secret = os.urandom(32)
    choice = 0
    commitment = compute_commitment(secret, choice)
    block_id = os.urandom(32)

    result = verify_game_outcome(secret, choice, commitment, block_id)
    print("=== Single Game Verification ===")
    print(f"  Valid:       {result.valid}")
    print(f"  Flip:        {'heads' if result.flip_result == 0 else 'tails'}")
    print(f"  Choice:      {'heads' if result.player_choice == 0 else 'tails'}")
    print(f"  Player wins: {result.player_wins}")
    print(f"  RNG hash:    {result.rng_hash}")
    print()

    # Statistical fairness test
    print("=== Statistical Fairness Test ===")
    stats = run_statistical_fairness_test(10000)
    print(json.dumps(stats, indent=2))
    print()
    print(f"Overall PASS: {stats['overall_pass']}")
