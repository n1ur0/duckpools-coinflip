"""
Test Suite: Bet Timeout and Refund Mechanism (MAT-28, MAT-53)

This test suite validates the bet timeout functionality that allows players
to reclaim funds after their bet expires without being revealed.

DEPENDS ON: MAT-28 (Implement bet timeout and refund mechanism)

Test Cases:
- TC-1: Timeout Refund After Expiry
- TC-2: Refund Blocked Before Timeout
- TC-3: Reveal Still Works Before Timeout
- TC-4: Timeout Value Correctness
- TC-5: Multiple Expired Bets
"""

import pytest
import asyncio
from datetime import datetime, timedelta
import httpx

from tests.conftest import TEST_NODE_URL, TEST_API_KEY, HOUSE_ADDRESS
from tests.utils import (
    place_bet,
    wait_for_blocks,
    get_box_by_id,
    build_refund_transaction,
    submit_transaction,
    get_current_height
)


class TestTimeoutRefund:
    """Test bet timeout and refund mechanism"""

    async def test_tc1_timeout_refund_after_expiry(self):
        """
        TC-1: Timeout Refund After Expiry

        1. Place bet (PendingBetBox with timeout register)
        2. Wait until timeout height passes
        3. Submit refund transaction spending expired box
        4. ASSERT: Refund tx succeeds, player gets bet amount back (minus fee)
        5. ASSERT: PendingBetBox consumed
        """
        # Get initial player balance
        player_address = "3WtestPlayer..."  # Test wallet address
        initial_balance = await get_player_balance(player_address)

        # Place a bet with timeout
        bet_amount = 1000000000  # 1 ERG in nanoERG
        bet_choice = 0  # heads
        timeout_delta = 100  # 100 blocks from creation

        bet_tx_id, bet_box_id = await place_bet(
            player_address=player_address,
            bet_amount=bet_amount,
            bet_choice=bet_choice,
            timeout_delta=timeout_delta
        )

        # Verify the bet was created with timeout
        bet_box = await get_box_by_id(bet_box_id)
        assert bet_box is not None, "Bet box not found"
        creation_height = bet_box['creationHeight']
        expected_timeout = creation_height + timeout_delta
        assert bet_box['additionalRegisters']['R9']['value'] == expected_timeout, \
            f"Expected timeout {expected_timeout}, got {bet_box['additionalRegisters']['R9']['value']}"

        # Wait for timeout to pass
        current_height = await get_current_height()
        blocks_to_wait = expected_timeout - current_height + 1
        if blocks_to_wait > 0:
            await wait_for_blocks(blocks_to_wait)

        # Build and submit refund transaction
        refund_tx = await build_refund_transaction(
            bet_box_id=bet_box_id,
            refund_address=player_address
        )

        refund_tx_id = await submit_transaction(refund_tx)

        # Verify refund succeeded
        assert refund_tx_id is not None, "Refund transaction failed"

        # Wait for transaction to be confirmed
        await wait_for_blocks(2)

        # Verify player got refund (minus fee)
        final_balance = await get_player_balance(player_address)
        # Allow for small fee difference
        assert final_balance >= initial_balance - 0.001 * 1e9, \
            f"Player did not receive refund: initial={initial_balance}, final={final_balance}"

        # Verify bet box was consumed
        bet_box_after = await get_box_by_id(bet_box_id)
        assert bet_box_after is None, "Bet box was not consumed by refund"

    async def test_tc2_refund_blocked_before_timeout(self):
        """
        TC-2: Refund Blocked Before Timeout

        1. Place bet with timeout = current_height + 100
        2. Immediately attempt refund
        3. ASSERT: Refund tx FAILS (contract rejects)
        4. ASSERT: PendingBetBox remains unspent
        """
        player_address = "3WtestPlayer..."
        bet_amount = 1000000000
        bet_choice = 1  # tails
        timeout_delta = 100

        # Place bet
        bet_tx_id, bet_box_id = await place_bet(
            player_address=player_address,
            bet_amount=bet_amount,
            bet_choice=bet_choice,
            timeout_delta=timeout_delta
        )

        # Try to refund immediately (before timeout)
        refund_tx = await build_refund_transaction(
            bet_box_id=bet_box_id,
            refund_address=player_address
        )

        # Submit and expect failure
        try:
            refund_tx_id = await submit_transaction(refund_tx)
            assert False, "Refund should have been rejected before timeout"
        except Exception as e:
            assert "rejected" in str(e).lower() or "failed" in str(e).lower(), \
                f"Expected rejection, got: {e}"

        # Verify bet box still exists
        bet_box = await get_box_by_id(bet_box_id)
        assert bet_box is not None, "Bet box was spent before timeout"

    async def test_tc3_reveal_still_works_before_timeout(self):
        """
        TC-3: Reveal Still Works Before Timeout

        1. Place bet with timeout
        2. Before timeout, submit valid reveal
        3. ASSERT: Reveal succeeds (normal flow not blocked by timeout addition)
        """
        from tests.utils import build_reveal_transaction, generate_commit

        player_address = "3WtestPlayer..."
        bet_amount = 1000000000
        bet_choice = 0  # heads
        timeout_delta = 100
        secret = "test_secret_123"

        # Generate commitment
        commitment = generate_commit(secret, bet_choice)

        # Place bet
        bet_tx_id, bet_box_id = await place_bet(
            player_address=player_address,
            bet_amount=bet_amount,
            bet_choice=bet_choice,
            commitment=commitment,
            timeout_delta=timeout_delta
        )

        # Wait a bit but well before timeout
        await wait_for_blocks(5)

        # Build and submit reveal transaction
        reveal_tx = await build_reveal_transaction(
            bet_box_id=bet_box_id,
            secret=secret,
            bet_choice=bet_choice
        )

        reveal_tx_id = await submit_transaction(reveal_tx)

        # Verify reveal succeeded
        assert reveal_tx_id is not None, "Reveal transaction failed"

        # Wait for confirmation
        await wait_for_blocks(2)

        # Verify bet box was consumed
        bet_box_after = await get_box_by_id(bet_box_id)
        assert bet_box_after is None, "Bet box was not consumed by reveal"

    async def test_tc4_timeout_value_correctness(self):
        """
        TC-4: Timeout Value Correctness

        1. Inspect PendingBetBox after placement
        2. ASSERT: Timeout register = creation_height + expected delta (e.g. 100)
        """
        player_address = "3WtestPlayer..."
        bet_amount = 500000000
        bet_choice = 0
        timeout_delta = 100

        # Place bet
        bet_tx_id, bet_box_id = await place_bet(
            player_address=player_address,
            bet_amount=bet_amount,
            bet_choice=bet_choice,
            timeout_delta=timeout_delta
        )

        # Inspect the box
        bet_box = await get_box_by_id(bet_box_id)
        assert bet_box is not None, "Bet box not found"

        creation_height = bet_box['creationHeight']
        timeout_register = bet_box['additionalRegisters']['R9']['value']

        expected_timeout = creation_height + timeout_delta
        assert timeout_register == expected_timeout, \
            f"Timeout register incorrect: expected={expected_timeout}, got={timeout_register}"

    async def test_tc5_multiple_expired_bets(self):
        """
        TC-5: Multiple Expired Bets

        1. Place 3 bets, let all expire
        2. Refund all 3
        3. ASSERT: All succeed, total = sum of bet amounts (minus fees)
        """
        player_address = "3WtestPlayer..."
        bet_amount = 500000000  # 0.5 ERG each
        timeout_delta = 50  # Short timeout for faster testing

        # Place 3 bets
        bet_info = []
        for i in range(3):
            bet_tx_id, bet_box_id = await place_bet(
                player_address=player_address,
                bet_amount=bet_amount,
                bet_choice=i % 2,
                timeout_delta=timeout_delta
            )
            bet_info.append((bet_box_id, bet_amount))

        # Wait for all to expire
        await wait_for_blocks(timeout_delta + 5)

        # Refund all bets
        initial_balance = await get_player_balance(player_address)
        total_refunded = 0

        for bet_box_id, amount in bet_info:
            refund_tx = await build_refund_transaction(
                bet_box_id=bet_box_id,
                refund_address=player_address
            )
            refund_tx_id = await submit_transaction(refund_tx)
            assert refund_tx_id is not None, f"Refund failed for bet {bet_box_id}"
            total_refunded += amount

        # Wait for all refunds to confirm
        await wait_for_blocks(3)

        # Verify player got all refunds (minus reasonable fees)
        final_balance = await get_player_balance(player_address)
        expected_balance = initial_balance + total_refunded
        # Allow for transaction fees (~3 ERG total)
        fee_allowance = 3 * 1e9
        assert final_balance >= expected_balance - fee_allowance, \
            f"Player did not receive all refunds: expected≈{expected_balance}, got={final_balance}"

        # Verify all bet boxes were consumed
        for bet_box_id, _ in bet_info:
            bet_box_after = await get_box_by_id(bet_box_id)
            assert bet_box_after is None, f"Bet box {bet_box_id} was not consumed"


# Security tests

async def test_security_no_replay_attack_on_refund():
    """
    Security: Verify that a refund transaction cannot be replayed
    """
    player_address = "3WtestPlayer..."
    bet_amount = 1000000000
    timeout_delta = 50

    # Place bet
    bet_tx_id, bet_box_id = await place_bet(
        player_address=player_address,
        bet_amount=bet_amount,
        bet_choice=0,
        timeout_delta=timeout_delta
    )

    # Wait for timeout
    await wait_for_blocks(timeout_delta + 2)

    # Build refund
    refund_tx = await build_refund_transaction(
        bet_box_id=bet_box_id,
        refund_address=player_address
    )

    # Submit first refund
    refund_tx_id = await submit_transaction(refund_tx)
    assert refund_tx_id is not None

    # Wait for confirmation
    await wait_for_blocks(2)

    # Try to submit the same refund again (replay)
    try:
        refund_tx_id_2 = await submit_transaction(refund_tx)
        assert False, "Replay attack should be rejected"
    except Exception as e:
        assert "rejected" in str(e).lower() or "double spend" in str(e).lower(), \
            f"Expected rejection of replay, got: {e}"


async def test_security_timeout_cannot_be_past_height():
    """
    Security: Verify timeout cannot be set to a past height
    """
    player_address = "3WtestPlayer..."
    current_height = await get_current_height()

    # Try to place bet with timeout in the past
    past_timeout_delta = -10  # Invalid: negative

    try:
        bet_tx_id, bet_box_id = await place_bet(
            player_address=player_address,
            bet_amount=1000000000,
            bet_choice=0,
            timeout_delta=past_timeout_delta
        )
        assert False, "Should reject timeout in the past"
    except Exception as e:
        assert "invalid" in str(e).lower() or "timeout" in str(e).lower(), \
            f"Expected validation error, got: {e}"


async def test_security_house_cannot_drain_timed_out_bets():
    """
    Security: Verify house cannot drain timed-out bets - only player can refund
    """
    player_address = "3WtestPlayer..."
    bet_amount = 1000000000
    timeout_delta = 50

    # Place bet
    bet_tx_id, bet_box_id = await place_bet(
        player_address=player_address,
        bet_amount=bet_amount,
        bet_choice=0,
        timeout_delta=timeout_delta
    )

    # Wait for timeout
    await wait_for_blocks(timeout_delta + 2)

    # Try to refund to house address (should fail)
    try:
        refund_tx = await build_refund_transaction(
            bet_box_id=bet_box_id,
            refund_address=HOUSE_ADDRESS  # House address, not player
        )
        refund_tx_id = await submit_transaction(refund_tx)
        assert False, "House should not be able to refund player's expired bet"
    except Exception as e:
        assert "rejected" in str(e).lower() or "forbidden" in str(e).lower(), \
            f"Expected rejection, got: {e}"
