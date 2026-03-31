"""
DuckPools Off-Chain Bot - Transaction Builder

Builds reveal transactions for PendingBet boxes.

The reveal transaction spends the PendingBet box and creates an output
paying the winner (player or house) according to the coinflip_v2.es contract.

Contract spending paths (coinflip_v2.es):
  1. REVEAL (house):
     - houseProp && commitmentOk
     - If playerWins: OUTPUTS(0) to player with value >= winPayout (1.94x)
     - If houseWins:  OUTPUTS(0) to house with value >= betAmount

  2. REFUND (player, after timeout):
     - HEIGHT >= timeoutHeight && playerProp
     - OUTPUTS(0) to player with value >= refundAmount (0.98x)

This bot handles the REVEAL path only. The refund path is player-initiated.

Transaction structure:
  Inputs:
    - PendingBet box (must satisfy coinflip_v2.es guard)
    - House UTXO (for change + fee)
  Outputs:
    - Winner payment box
    - House change box (remainder after fee + payout)

The actual transaction signing is done by the Ergo node wallet via
/transactions/send (offline signing not needed for node-managed wallets).

MAT-419: Implement off-chain bot reveal logic
"""

from typing import Optional

from logger import get_logger
from ergo_box_decoder import PendingBetBox

logger = get_logger(__name__)

# House edge: 3% (win multiplier = 1.94x = 97/50)
WIN_MULTIPLIER_NUM = 97
WIN_MULTIPLIER_DEN = 50

# Refund fee: 2% (multiplier = 0.98x = 49/50)
REFUND_MULTIPLIER_NUM = 49
REFUND_MULTIPLIER_DEN = 50

# Minimum ERG box value (Ergo protocol requirement)
MIN_BOX_VALUE = 1_000_000  # 0.001 ERG


def compute_win_payout(bet_amount_nanoerg: int) -> int:
    """
    Compute win payout: betAmount * 97 / 50 (1.94x).

    Matches coinflip_v2.es line 71:
      val winPayout = betAmount * 97L / 50L
    """
    return bet_amount_nanoerg * WIN_MULTIPLIER_NUM // WIN_MULTIPLIER_DEN


def compute_refund_amount(bet_amount_nanoerg: int) -> int:
    """
    Compute refund amount: betAmount - betAmount / 50 (0.98x).

    Matches coinflip_v2.es line 73:
      val refundAmount = betAmount - betAmount / 50L
    """
    return bet_amount_nanoerg - bet_amount_nanoerg // REFUND_MULTIPLIER_DEN


def build_reveal_request(
    bet_box: PendingBetBox,
    player_wins: bool,
    player_address: str,
    house_address: str,
) -> Optional[dict]:
    """
    Build a reveal transaction request for the Ergo node wallet.

    Uses the node's /wallet/payment/send endpoint which handles
    input selection and signing automatically.

    For a more production-ready approach, use /wallet/transaction/send
    with explicit inputs and data inputs.

    Args:
        bet_box: The decoded PendingBet box
        player_wins: Whether the player won the flip
        player_address: Ergo address to pay on player win
        house_address: Ergo address for house funds

    Returns:
        Transaction request dict for the node API, or None on error
    """
    if player_wins:
        payout = compute_win_payout(bet_box.value)
        recipient = player_address
        logger.info(
            "building_player_payout",
            box_id=bet_box.box_id[:16] + "...",
            payout_nanoerg=payout,
            payout_erg=payout / 1e9,
            recipient=recipient[:16] + "...",
        )
    else:
        # House wins — bet amount goes to house
        payout = bet_box.value
        recipient = house_address
        logger.info(
            "building_house_payout",
            box_id=bet_box.box_id[:16] + "...",
            payout_nanoerg=payout,
            payout_erg=payout / 1e9,
            recipient=recipient[:16] + "...",
        )

    if payout < MIN_BOX_VALUE:
        logger.error(
            "payout_below_minimum",
            payout=payout,
            minimum=MIN_BOX_VALUE,
        )
        return None

    # Build the transaction request for /wallet/payment/send
    # The node wallet will:
    # 1. Select house UTXOs as additional inputs (for fee)
    # 2. Sign with house key
    # 3. Broadcast
    request = {
        "requests": [
            {
                "address": recipient,
                "value": str(payout),
                "assets": [],
            }
        ],
        "fee": str(1_000_000),  # 0.001 ERG default fee
        "inputsRaw": [bet_box.box_id],
    }

    logger.info(
        "reveal_tx_built",
        box_id=bet_box.box_id[:16] + "...",
        player_wins=player_wins,
        payout=payout / 1e9,
    )

    return request


def build_reveal_transaction(
    bet_box: PendingBetBox,
    player_wins: bool,
    player_pk_bytes: bytes,
    house_pk_bytes: bytes,
    parent_block_id: bytes,
    current_height: int,
    house_change_address: str,
) -> Optional[dict]:
    """
    Build a full reveal transaction for /wallet/transaction/send.

    This is the more explicit version that specifies all inputs, data inputs,
    and outputs for maximum control over the transaction.

    Transaction structure:
      Inputs:
        0: PendingBet box (will be spent by house signature)
        1+: House wallet UTXOs (for change + fees)
      Data Inputs:
        (none needed for coinflip_v2)
      Outputs:
        0: Winner payout box (player if win, house if lose)
        1: House change box

    Args:
        bet_box: Decoded PendingBet box
        player_wins: Whether player won
        player_pk_bytes: Player's public key bytes (R5)
        house_pk_bytes: House's public key bytes (R4)
        parent_block_id: Block hash for RNG entropy
        current_height: Current block height
        house_change_address: House address for change output

    Returns:
        Transaction request dict, or None on error
    """
    if player_wins:
        payout_amount = compute_win_payout(bet_box.value)
        recipient_prop_bytes = _pk_to_prop_bytes(player_pk_bytes)
    else:
        payout_amount = bet_box.value
        recipient_prop_bytes = _pk_to_prop_bytes(house_pk_bytes)

    if payout_amount < MIN_BOX_VALUE:
        logger.error("payout_below_minimum", payout=payout_amount)
        return None

    # Build the transaction using Ergo node's transaction API
    # The node wallet will add signing inputs and handle fees
    tx_request = {
        "inputs": [
            {
                "boxId": bet_box.box_id,
                "spendingProof": {
                    "proofBytes": "",
                    "extension": {},
                },
            }
        ],
        "dataInputs": [],
        "outputs": [
            {
                "value": str(payout_amount),
                "ergoTree": recipient_prop_bytes,
                "assets": [],
                "creationHeight": current_height,
                "additionalRegisters": {},
            }
        ],
        "fee": str(1_000_000),
        "timestamp": None,
    }

    logger.info(
        "reveal_transaction_built",
        box_id=bet_box.box_id[:16] + "...",
        player_wins=player_wins,
        payout_erg=payout_amount / 1e9,
        height=current_height,
    )

    return tx_request


def _pk_to_prop_bytes(pk_bytes: bytes) -> str:
    """
    Convert compressed public key bytes to SigmaProp proposition bytes.

    The proposition bytes for proveDlog(pk) are the serialized SigmaProp:
    0x08 || pk_bytes (where 0x08 is the proveDlog group element tag).

    Args:
        pk_bytes: 33-byte compressed public key

    Returns:
        Hex-encoded proposition bytes
    """
    return "08" + pk_bytes.hex()
