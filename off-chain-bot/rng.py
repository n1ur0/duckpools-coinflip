"""
DuckPools Off-Chain Bot - RNG Computation

Computes the coinflip outcome using block-hash RNG, matching the on-chain
logic in coinflip_v2.es.

On-chain RNG (coinflip_v2.es lines 63-66):
  val blockSeed  = CONTEXT.preHeader.parentId
  val rngHash    = blake2b256(blockSeed ++ playerSecret)
  val flipResult = rngHash(0) % 2
  val playerWins = (flipResult == playerChoice)

Off-chain, the bot uses the block header at the reveal height to get
the parentId (previous block hash). The block hash serves as the entropy
source combined with the player's secret.

IMPORTANT: The bot should use the block that will be the parent of the
reveal transaction's block. In practice, we use the current best block's
header as the preHeader, which means parentId = current tip hash.

MAT-419: Implement off-chain bot reveal logic
"""

import hashlib
from typing import Tuple

from logger import get_logger

logger = get_logger(__name__)


def compute_flip_outcome(
    parent_block_id: bytes,
    player_secret: bytes,
    player_choice: int,
) -> Tuple[int, bool, str]:
    """
    Compute coinflip outcome from block hash entropy.

    Matches coinflip_v2.es lines 63-66:
      val blockSeed  = CONTEXT.preHeader.parentId
      val rngHash    = blake2b256(blockSeed ++ playerSecret)
      val flipResult = rngHash(0) % 2
      val playerWins = (flipResult == playerChoice)

    Args:
        parent_block_id: 32-byte block hash (preHeader.parentId)
        player_secret: Player's secret bytes from R9
        player_choice: Player's choice (0=heads, 1=tails)

    Returns:
        Tuple of (flip_result, player_wins, outcome_str)
        - flip_result: 0 or 1 (raw RNG output)
        - player_wins: True if player wins
        - outcome_str: "heads" or "tails"
    """
    if len(parent_block_id) != 32:
        raise ValueError(
            f"parent_block_id must be 32 bytes, got {len(parent_block_id)}"
        )

    # blake2b256(blockSeed ++ playerSecret) — matches contract line 64
    rng_preimage = parent_block_id + player_secret
    rng_hash = hashlib.blake2b(rng_preimage, digest_size=32).digest()

    # rngHash(0) % 2 — contract line 65
    flip_result = rng_hash[0] % 2

    # playerWins = (flipResult == playerChoice) — contract line 66
    player_wins = flip_result == player_choice

    outcome_str = "heads" if flip_result == 0 else "tails"
    player_choice_str = "heads" if player_choice == 0 else "tails"

    logger.info(
        "rng_computed",
        block_hash=parent_block_id.hex()[:16] + "...",
        rng_hash=rng_hash.hex()[:16] + "...",
        flip_result=flip_result,
        flip_outcome=outcome_str,
        player_choice=player_choice_str,
        player_wins=player_wins,
    )

    return flip_result, player_wins, outcome_str
