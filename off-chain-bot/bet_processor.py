"""
DuckPools Off-Chain Bot - Bet Processor

Core bet lifecycle logic:
  1. Scan for PendingBet UTXOs matching CONTRACT_ERGO_TREE
  2. Verify commitment: blake2b256(R9_secret || choice_byte) == R6_commitment
  3. Determine outcome: blake2b256(prevBlockId || R9_secret)[0] % 2
  4. Build & sign reveal transaction (house spends, pays winner)
  5. Broadcast transaction via node /transactions endpoint
  6. Report settlement to backend API for bet history

Matches on-chain contract (coinflip_v2.es) exactly.
See backend/rng_module.py for the canonical RNG spec.
"""

import hashlib
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import httpx

from logger import get_logger

logger = get_logger(__name__)


# ─── Constants ────────────────────────────────────────────────────────────

# Register indices in Ergo box (Ergo node API uses 0-based)
# R4=4, R5=5, R6=6, R7=7, R8=8, R9=9
REG_HOUSE_PK = 4
REG_PLAYER_PK = 5
REG_COMMITMENT = 6
REG_PLAYER_CHOICE = 7
REG_TIMEOUT_HEIGHT = 8
REG_PLAYER_SECRET = 9

# Ergo node API register type hints (Sigma type IDs)
SIGMA_TYPE_COLL_BYTE = "SColl(SByte)"
SIGMA_TYPE_INT = "SInt"


class BetOutcome(str, Enum):
    WIN = "win"
    LOSE = "lose"


@dataclass
class PendingBet:
    """A parsed PendingBet box from the Ergo UTXO set."""
    box_id: str
    transaction_id: str
    value: int  # nanoERG
    house_pk_bytes: bytes  # R4
    player_pk_bytes: bytes  # R5
    commitment_hash: bytes  # R6
    player_choice: int  # R7: 0=heads, 1=tails
    timeout_height: int  # R8
    player_secret: bytes  # R9
    creation_height: int  # box inclusion height

    @property
    def choice_label(self) -> str:
        return "heads" if self.player_choice == 0 else "tails"


@dataclass
class SettlementResult:
    """Result of processing a single bet."""
    box_id: str
    outcome: BetOutcome
    rng_result: int  # 0=heads, 1=tails
    player_choice: int
    player_address: str
    bet_amount_nanoerg: int
    payout_nanoerg: int
    tx_id: Optional[str] = None
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.tx_id is not None


# ─── Register Decoding ────────────────────────────────────────────────────

def _extract_coll_byte(register: dict) -> bytes:
    """
    Extract bytes from an Ergo register value.

    Ergo node API returns registers as:
      {"type": "SColl(SByte)", "rawValue": "hex...", "value": "[base64...]"}

    We use rawValue (hex-encoded) for exact byte reconstruction.
    """
    reg_type = register.get("type", "")
    if reg_type != SIGMA_TYPE_COLL_BYTE:
        raise ValueError(
            f"Expected register type {SIGMA_TYPE_COLL_BYTE}, got {reg_type}"
        )
    raw_hex = register.get("rawValue", "")
    if not raw_hex:
        raise ValueError("Register rawValue is empty")
    return bytes.fromhex(raw_hex)


def _extract_int(register: dict) -> int:
    """
    Extract int from an Ergo register value.

    Ergo node API returns:
      {"type": "SInt", "rawValue": "hex...", "value": "42"}
    """
    reg_type = register.get("type", "")
    if reg_type != SIGMA_TYPE_INT:
        raise ValueError(f"Expected register type {SIGMA_TYPE_INT}, got {reg_type}")
    return int(register.get("value", "0"))


# ─── Commitment Verification ──────────────────────────────────────────────

def verify_commitment(
    player_secret: bytes,
    player_choice: int,
    commitment_hash: bytes,
) -> bool:
    """
    Verify that blake2b256(secret || choice_byte) == commitment_hash.

    This MUST match coinflip_v2.es on-chain verification exactly:
        val choiceByte = if (playerChoice == 0) (0.toByte) else (1.toByte)
        val computedHash = blake2b256(playerSecret ++ Coll(choiceByte))
        val commitmentOk = (computedHash == commitmentHash)
    """
    choice_byte = bytes([player_choice])
    computed = hashlib.blake2b(
        player_secret + choice_byte, digest_size=32
    ).digest()
    return computed == commitment_hash


# ─── RNG Determination ────────────────────────────────────────────────────

def determine_outcome(
    prev_block_id: str,
    player_secret: bytes,
    player_choice: int,
) -> Tuple[int, BetOutcome]:
    """
    Determine coinflip outcome using block-hash RNG.

    Matches on-chain contract exactly (coinflip_v2.es):
        val blockSeed = CONTEXT.preHeader.parentId
        val rngHash = blake2b256(blockSeed ++ playerSecret)
        val flipResult = rngHash(0) % 2
        val playerWins = (flipResult == playerChoice)

    Args:
        prev_block_id: 64-char hex block ID (CONTEXT.preHeader.parentId)
        player_secret: Raw secret bytes (R9)
        player_choice: 0=heads, 1=tails

    Returns:
        (flip_result, outcome) where flip_result is 0/1 and
        outcome is BetOutcome.WIN or BetOutcome.LOSE from player's perspective.
    """
    block_bytes = bytes.fromhex(prev_block_id)
    rng_hash = hashlib.blake2b(
        block_bytes + player_secret, digest_size=32
    ).digest()
    flip_result = rng_hash[0] % 2
    player_wins = flip_result == player_choice
    outcome = BetOutcome.WIN if player_wins else BetOutcome.LOSE
    return flip_result, outcome


# ─── Box Scanning ─────────────────────────────────────────────────────────

def decode_registers(registers: Dict[int, dict]) -> Dict[str, object]:
    """
    Decode all known registers from a PendingBet box.

    Args:
        registers: Dict mapping register index to register dict from node API.

    Returns:
        Dict with keys: house_pk_bytes, player_pk_bytes, commitment_hash,
        player_choice, timeout_height, player_secret
    """
    house_pk_bytes = _extract_coll_byte(registers[REG_HOUSE_PK])
    player_pk_bytes = _extract_coll_byte(registers[REG_PLAYER_PK])
    commitment_hash = _extract_coll_byte(registers[REG_COMMITMENT])
    player_choice = _extract_int(registers[REG_PLAYER_CHOICE])
    timeout_height = _extract_int(registers[REG_TIMEOUT_HEIGHT])
    player_secret = _extract_coll_byte(registers[REG_PLAYER_SECRET])

    return {
        "house_pk_bytes": house_pk_bytes,
        "player_pk_bytes": player_pk_bytes,
        "commitment_hash": commitment_hash,
        "player_choice": player_choice,
        "timeout_height": timeout_height,
        "player_secret": player_secret,
    }


def parse_pending_bet(box: dict) -> Optional[PendingBet]:
    """
    Parse an Ergo UTXO box into a PendingBet if it matches our contract.

    Args:
        box: Box dict from /utxo/withUnspentOutputs response.

    Returns:
        PendingBet if valid, None if box doesn't match expected layout.
    """
    # Check if box has all 6 required registers (R4-R9)
    registers = box.get("additionalRegisters", {})
    required_regs = {
        REG_HOUSE_PK, REG_PLAYER_PK, REG_COMMITMENT,
        REG_PLAYER_CHOICE, REG_TIMEOUT_HEIGHT, REG_PLAYER_SECRET,
    }
    if not required_regs.issubset(set(registers.keys())):
        return None

    try:
        regs = decode_registers(registers)
    except (ValueError, KeyError) as e:
        logger.warning("box_register_decode_failed", box_id=box.get("boxId"), error=str(e))
        return None

    return PendingBet(
        box_id=box["boxId"],
        transaction_id=box["transactionId"],
        value=int(box["value"]),
        house_pk_bytes=regs["house_pk_bytes"],
        player_pk_bytes=regs["player_pk_bytes"],
        commitment_hash=regs["commitment_hash"],
        player_choice=regs["player_choice"],
        timeout_height=regs["timeout_height"],
        player_secret=regs["player_secret"],
        creation_height=int(box.get("creationHeight", 0)),
    )


# ─── Payout Calculation ───────────────────────────────────────────────────

def calculate_payout(
    bet_amount: int,
    outcome: BetOutcome,
    house_edge_bps: int = 300,
) -> int:
    """
    Calculate payout amount matching on-chain contract.

    coinflip_v2.es:
        winPayout = betAmount * 97 / 50   (1.94x, 3% house edge)
        losePayout = betAmount             (house takes all)

    Args:
        bet_amount: Bet amount in nanoERG
        outcome: WIN or LOSE
        house_edge_bps: House edge in basis points (300 = 3%)

    Returns:
        Payout in nanoERG
    """
    if outcome == BetOutcome.WIN:
        # winPayout = betAmount * 97 / 50 (1.94x)
        return bet_amount * 97 // 50
    else:
        # House wins: takes full bet
        return bet_amount


# ─── Transaction Building ─────────────────────────────────────────────────

def build_reveal_transaction(
    bet: PendingBet,
    outcome: BetOutcome,
    payout_amount: int,
    house_address: str,
    current_height: int,
    fee_nanoerg: int = 1_000_000,
) -> Optional[dict]:
    """
    Build the reveal transaction JSON for the Ergo node /transactions endpoint.

    Spending path (coinflip_v2.es canReveal):
      houseProp && commitmentOk && (
        if (playerWins):
          OUTPUTS(0).propositionBytes == playerProp.propBytes &&
          OUTPUTS(0).value >= winPayout
        else:
          OUTPUTS(0).propositionBytes == houseProp.propBytes &&
          OUTPUTS(0).value >= betAmount
      )

    We build the unsigned transaction and let the node sign with the house wallet.

    Args:
        bet: The pending bet to settle
        outcome: Win/lose determination
        payout_amount: Amount for OUTPUTS(0)
        house_address: House P2PK address (for loss payouts)
        current_height: Current block height

    Returns:
        Transaction dict suitable for node submission, or None on error.
    """
    if outcome == BetOutcome.WIN:
        # Player wins: OUTPUTS(0) pays player
        # We use the player PK bytes to reconstruct their address.
        # The node wallet will sign with house key.
        outputs = [
            {
                "value": payout_amount,
                "ergoTree": f"0008cd{bet.player_pk_bytes.hex()}",
                "registers": {},
                "assets": [],
            }
        ]
    else:
        # House wins: OUTPUTS(0) pays house
        outputs = [
            {
                "value": payout_amount,
                "address": house_address,
                "registers": {},
                "assets": [],
            }
        ]

    # Ensure total outputs don't exceed input value minus fee
    # If player wins, payout > bet, so house must fund the difference
    # We use the house wallet as the sign/prove mechanism
    tx = {
        "inputs": [
            {
                "boxId": bet.box_id,
                "spendingProof": {
                    "proofBytes": "",
                    "extension": {},
                },
            }
        ],
        "dataInputs": [],
        "outputs": outputs,
    }

    return tx


# ─── Backend Reporting ────────────────────────────────────────────────────

async def report_settlement(
    backend_url: str,
    result: SettlementResult,
    client: httpx.AsyncClient,
) -> bool:
    """
    Post settlement result to the backend API for bet history.

    The backend stores this in its bet history so the frontend can show
    resolved bets.

    Args:
        backend_url: Base URL of the backend API
        result: Settlement result from the bet processor
        client: HTTP client

    Returns:
        True if reported successfully, False otherwise
    """
    if not backend_url:
        logger.debug("backend_report_skipped", reason="no_backend_url")
        return False

    try:
        payload = {
            "boxId": result.box_id,
            "txId": result.tx_id or "",
            "outcome": result.outcome.value,
            "rngResult": result.rng_result,
            "playerChoice": result.player_choice,
            "playerAddress": result.player_address,
            "betAmount": result.bet_amount_nanoerg,
            "payout": result.payout_nanoerg,
        }

        response = await client.post(
            f"{backend_url}/settle",
            json=payload,
            timeout=10.0,
        )
        response.raise_for_status()
        logger.info(
            "backend_report_success",
            box_id=result.box_id,
            outcome=result.outcome.value,
        )
        return True

    except httpx.HTTPError as e:
        logger.warning(
            "backend_report_failed",
            box_id=result.box_id,
            error=str(e),
        )
        return False


# ─── Player Address Derivation ────────────────────────────────────────────

def pk_bytes_to_address(pk_bytes: bytes, network_prefix: str = "3") -> str:
    """
    Derive an Ergo P2PK address from compressed public key bytes.

    This is a simplified derivation — in production, use the full
    Sigma protocol address encoding. For the PoC, we reconstruct
    the ErgoTree prefix + PK bytes into the P2PK address.

    Args:
        pk_bytes: 33-byte compressed public key
        network_prefix: '3' for testnet, '9' for mainnet

    Returns:
        Encoded P2PK address
    """
    import base58

    # P2PK ErgoTree: 0008cd{33-byte-pk-hex}
    ergo_tree_hex = f"0008cd{pk_bytes.hex()}"
    ergo_tree_bytes = bytes.fromhex(ergo_tree_hex)

    # Prepend version byte (0x00 for testnet, 0x10 for mainnet)
    version = 0x00 if network_prefix == "3" else 0x10
    payload = bytes([version]) + ergo_tree_bytes

    # Base58 encode
    address = base58.b58encode_check(payload).decode("ascii")
    return address
