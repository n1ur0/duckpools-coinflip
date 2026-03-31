"""
DuckPools Off-Chain Bot - Commitment Verification

Verifies player commitment hashes against the on-chain contract logic.

The contract (coinflip_v2.es) stores:
  R6 = blake2b256(playerSecret || choice_byte)
  R7 = playerChoice (Int): 0=heads, 1=tails
  R9 = playerSecret (Coll[Byte])

On-chain verification (line 57 of coinflip_v2.es):
  val computedHash = blake2b256(playerSecret ++ Coll(choiceByte))

This module replicates that verification off-chain before building reveal txs.

MAT-419: Implement off-chain bot reveal logic
"""

import hashlib
from typing import Tuple

from logger import get_logger

logger = get_logger(__name__)


def compute_commitment_hash(secret_bytes: bytes, choice: int) -> bytes:
    """
    Compute blake2b256(secret || choice_byte) matching coinflip_v2.es line 57.

    Args:
        secret_bytes: Player's secret (raw bytes from R9 register)
        choice: Player's choice (0=heads, 1=tails)

    Returns:
        32-byte blake2b256 hash
    """
    choice_byte = choice.to_bytes(1, byteorder="big")
    preimage = secret_bytes + choice_byte
    return hashlib.blake2b(preimage, digest_size=32).digest()


def verify_commitment(
    secret_bytes: bytes,
    choice: int,
    commitment_hash: bytes,
) -> Tuple[bool, str]:
    """
    Verify that blake2b256(secret || choice_byte) == commitment_hash.

    Matches the on-chain logic in coinflip_v2.es:
      val computedHash = blake2b256(playerSecret ++ Coll(choiceByte))
      val commitmentOk = (computedHash == commitmentHash)

    Args:
        secret_bytes: Player's secret from R9 (raw bytes)
        choice: Player's choice from R7 (0 or 1)
        commitment_hash: Commitment hash from R6 (raw bytes)

    Returns:
        Tuple of (is_valid, reason_string)
    """
    if choice not in (0, 1):
        return False, f"invalid choice value: {choice}, must be 0 or 1"

    if len(commitment_hash) != 32:
        return False, f"commitment_hash must be 32 bytes, got {len(commitment_hash)}"

    if len(secret_bytes) == 0:
        return False, "secret_bytes is empty"

    computed = compute_commitment_hash(secret_bytes, choice)

    if computed == commitment_hash:
        logger.info(
            "commitment_verified",
            commitment_hash=commitment_hash.hex(),
            choice="heads" if choice == 0 else "tails",
        )
        return True, "commitment verified"

    logger.warning(
        "commitment_mismatch",
        expected=commitment_hash.hex(),
        computed=computed.hex(),
        choice=choice,
    )
    return False, (
        f"commitment mismatch: computed={computed.hex()}, "
        f"expected={commitment_hash.hex()}"
    )
