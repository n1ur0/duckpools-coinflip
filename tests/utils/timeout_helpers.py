"""
Helper functions for timeout and refund testing (MAT-53)
"""

import httpx
import asyncio
import hashlib
from typing import Tuple, Optional

# Configuration
TEST_NODE_URL = "http://localhost:9052"
TEST_API_KEY = "hello"
HOUSE_ADDRESS = "3WyrB3D5AMpyEc88UJ7FpdsBMXAZKwzQzkKeDbAQVfXytDPgxF26"
NANO_ERG_PER_ERG = 1e9


async def get_current_height() -> int:
    """Get current blockchain height"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{TEST_NODE_URL}/info",
            headers={"api_key": TEST_API_KEY},
            timeout=10.0
        )
        response.raise_for_status()
        data = response.json()
        return data["fullHeight"]


async def get_player_balance(address: str) -> int:
    """Get player balance in nanoERG"""
    # For testnet, we can use explorer or node API
    async with httpx.AsyncClient() as client:
        # Try explorer first
        response = await client.get(
            f"https://api-testnet.ergoplatform.com/api/v1/addresses/{address}/balance",
            timeout=10.0
        )
        if response.status_code == 200:
            data = response.json()
            return int(data["nanoErgs"])

        # Fallback to node (if wallet has address)
        response = await client.get(
            f"{TEST_NODE_URL}/wallet/balances",
            headers={"api_key": TEST_API_KEY},
            timeout=10.0
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("balance", 0)

        return 0


async def get_box_by_id(box_id: str) -> Optional[dict]:
    """Get box details by ID"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{TEST_NODE_URL}/blockchain/box/byId/{box_id}",
            headers={"api_key": TEST_API_KEY},
            timeout=10.0
        )
        if response.status_code == 200:
            return response.json()
        return None


async def wait_for_blocks(num_blocks: int, check_interval: int = 5):
    """Wait for specified number of blocks to be mined"""
    start_height = await get_current_height()
    target_height = start_height + num_blocks

    print(f"Waiting for {num_blocks} blocks (from {start_height} to {target_height})...")

    while True:
        current_height = await get_current_height()
        if current_height >= target_height:
            print(f"Reached height {current_height}")
            return
        await asyncio.sleep(check_interval)


async def place_bet(
    player_address: str,
    bet_amount: int,
    bet_choice: int,
    commitment: Optional[str] = None,
    timeout_delta: int = 100
) -> Tuple[str, str]:
    """
    Place a bet with timeout.

    Returns: (tx_id, box_id)
    """
    from off_chain_bot.client_consts import COINFLIP_NFT_ID

    if commitment is None:
        # Generate default commitment
        secret = "test_secret_timeout"
        commitment = generate_commit(secret, bet_choice)

    # Build bet transaction
    bet_tx = await build_bet_transaction(
        player_address=player_address,
        bet_amount=bet_amount,
        bet_choice=bet_choice,
        commitment=commitment,
        timeout_delta=timeout_delta
    )

    # Submit transaction
    tx_id = await submit_transaction(bet_tx)

    # Get the bet box ID from transaction outputs
    bet_box_id = await find_bet_box_from_tx(tx_id, player_address)

    return tx_id, bet_box_id


async def build_bet_transaction(
    player_address: str,
    bet_amount: int,
    bet_choice: int,
    commitment: str,
    timeout_delta: int
) -> dict:
    """Build a bet transaction with timeout"""
    # This should use the actual PendingBet contract with timeout support
    # For now, return a placeholder - will be implemented when MAT-28 is complete

    # TODO: Implement proper transaction building with FleetSDK
    return {
        "requests": [
            {
                "address": "3WtestPendingBetAddress",  # PendingBet contract address
                "value": bet_amount,
                "assets": [],
                "registers": {
                    "R4": {"value": "ergo_tree_bytes", "type": "Coll[Byte]"},  # Player's ErgoTree
                    "R5": {"value": commitment, "type": "Coll[Byte]"},  # Commitment hash
                    "R6": {"value": bet_choice, "type": "Int"},  # Bet choice
                    "R9": {"value": f"height_{timeout_delta}", "type": "Int"}  # Timeout
                }
            }
        ]
    }


async def build_refund_transaction(
    bet_box_id: str,
    refund_address: str
) -> dict:
    """
    Build a refund transaction for an expired bet.

    The PendingBet contract should allow refunding after timeout
    by spending the box and sending funds back to player.
    """
    # Get the bet box
    bet_box = await get_box_by_id(bet_box_id)
    if not bet_box:
        raise ValueError(f"Bet box {bet_box_id} not found")

    # Verify timeout has passed
    current_height = await get_current_height()
    timeout_height = bet_box["additionalRegisters"]["R9"]["value"]
    if current_height < timeout_height:
        raise ValueError(f"Timeout not reached: current={current_height}, timeout={timeout_height}")

    # TODO: Implement proper transaction building
    # The contract should verify that:
    # 1. Current height >= timeout register
    # 2. Refund address matches original player (R4)

    return {
        "inputs": [bet_box_id],
        "outputs": [
            {
                "address": refund_address,
                "value": bet_box["value"],
                "assets": bet_box.get("assets", [])
            }
        ]
    }


async def build_reveal_transaction(
    bet_box_id: str,
    secret: str,
    bet_choice: int
) -> dict:
    """Build a reveal transaction (normal bet flow)"""
    from tests.utils.crypto import sha256

    bet_box = await get_box_by_id(bet_box_id)
    if not bet_box:
        raise ValueError(f"Bet box {bet_box_id} not found")

    # Reconstruct commitment to verify
    secret_bytes = secret.encode('utf-8')[:8].ljust(8, b'\x00')
    choice_byte = bytes([bet_choice])
    commitment = sha256(secret_bytes + choice_byte)

    # TODO: Implement proper transaction building
    return {
        "inputs": [bet_box_id],
        "outputs": [
            {
                "address": HOUSE_ADDRESS,
                "value": bet_box["value"],
                "assets": bet_box.get("assets", []),
                "registers": {
                    "R4": {"value": "revealed_secret", "type": "Coll[Byte]"}
                }
            }
        ]
    }


async def submit_transaction(tx: dict) -> str:
    """Submit transaction to node"""
    async with httpx.AsyncClient() as client:
        # Unlock wallet first
        await client.post(
            f"{TEST_NODE_URL}/wallet/unlock",
            headers={"api_key": TEST_API_KEY},
            json={"pass": "1231231230"},
            timeout=10.0
        )

        response = await client.post(
            f"{TEST_NODE_URL}/wallet/transaction/send",
            headers={"api_key": TEST_API_KEY},
            json=tx,
            timeout=30.0
        )

        if response.status_code != 200:
            error = response.text
            raise Exception(f"Transaction failed: {error}")

        result = response.json()
        return result.get("txId", "")


async def find_bet_box_from_tx(tx_id: str, player_address: str) -> str:
    """Find the PendingBet box ID from a transaction"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{TEST_NODE_URL}/blockchain/transaction/byId/{tx_id}",
            headers={"api_key": TEST_API_KEY},
            timeout=10.0
        )
        if response.status_code != 200:
            return ""

        tx_data = response.json()
        # Find output box with PendingBet ErgoTree
        # For now, return first non-change output
        outputs = tx_data.get("outputs", [])
        for output in outputs:
            if output.get("address") != player_address:
                return output.get("boxId", "")

        return ""


def generate_commit(secret: str, choice: int) -> str:
    """Generate commitment hash for bet"""
    from tests.utils.crypto import sha256

    secret_bytes = secret.encode('utf-8')[:8].ljust(8, b'\x00')
    choice_byte = bytes([choice])
    commit_hash = sha256(secret_bytes + choice_byte)
    return commit_hash.hex()


def verify_commit(commit_hex: str, secret: str, choice: int) -> bool:
    """Verify commitment matches"""
    from tests.utils.crypto import sha256

    secret_bytes = secret.encode('utf-8')[:8].ljust(8, b'\x00')
    choice_byte = bytes([choice])
    computed_hash = sha256(secret_bytes + choice_byte).hex()

    return commit_hex.lower() == computed_hash.lower()
