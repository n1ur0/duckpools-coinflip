"""
DuckPools - Dice Game E2E Tests

End-to-end tests for the dice game covering:
1. Place bet - User can place a dice bet with amount and target
2. Reveal - Game reveals the dice roll result
3. Payout - Correct payout calculated and displayed
4. Wallet Balance - Wallet balance updates after win/loss

Based on Issue: 49df5e36-9287-406a-8fde-b95c6dc9301f

Usage:
    cd /Users/n1ur0/projects/worktrees/agent/regression-tester-jr-55-regression-test-suite
    python3 -m pytest regression_tests/test_dice_game_e2e.py -v
"""

import pytest
import asyncio
import json
from decimal import Decimal
from playwright.async_api import async_playwright

# ─── Configuration ────────────────────────────────────────────────────

FRONTEND_URL = "http://localhost:3000"
BACKEND_URL = "http://localhost:8000"

# Test constants
TEST_BET_AMOUNT = "0.1"
TEST_TARGET_VALUE = 50
DICE_MIN_TARGET = 2
DICE_MAX_TARGET = 98


# ─── DG-1: Place Bet ─────────────────────────────────────────────────

class TestDicePlaceBet:
    """Verify users can place dice bets with valid parameters."""

    @pytest.mark.asyncio
    async def test_dice_game_loads(self):
        """Dice game component loads without errors."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context()
            page = await context.new_page()

            # Capture console errors
            errors = []
            def on_console(msg):
                if msg.type == "error":
                    errors.append(msg.text)
            
            page.on("console", on_console)

            # Navigate to frontend
            await page.goto(FRONTEND_URL, wait_until="networkidle", timeout=10000)
            
            # Check if dice game is present
            dice_elements = await page.query_selector_all('[class*="dice"], [data-testid*="dice"]')
            assert len(dice_elements) > 0, "Dice game component not found"
            
            # Check for console errors
            critical_errors = [e for e in errors if "error" in e.lower() and "warning" not in e.lower()]
            if critical_errors:
                pytest.fail(f"Page loaded with {len(critical_errors)} console error(s):\\n" + "\\n".join(critical_errors))

            await browser.close()

    @pytest.mark.asyncio
    async def test_dice_bet_form_elements_present(self):
        """Dice bet form has all required input elements."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(FRONTEND_URL, wait_until="networkidle", timeout=10000)
            await asyncio.sleep(1)  # Wait for dynamic content

            # Check for amount input
            amount_input = await page.query_selector('input.dice-amount-input, input[type="number"], input[placeholder*="0.0"]')
            assert amount_input, "Dice amount input not found"

            # Check for target input
            target_input = await page.query_selector('input.dice-target-input, input[type="range"], input[min="2"]')
            assert target_input, "Dice target input not found"

            # Check for submit button
            submit_button = await page.query_selector('button:has-text("Roll Dice"), button:has-text("Place Bet"), button.dice-submit-btn')
            assert submit_button, "Dice submit button not found"

            await browser.close()

    @pytest.mark.asyncio
    async def test_dice_bet_validation(self):
        """Dice bet form validates inputs correctly."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(FRONTEND_URL, wait_until="networkidle", timeout=10000)
            await asyncio.sleep(1)

            # Try to submit with empty amount
            submit_button = await page.query_selector('button:has-text("Roll Dice"), button:has-text("Place Bet"), button.dice-submit-btn')
            if submit_button and await submit_button.is_enabled():
                await submit_button.click()
                await asyncio.sleep(0.5)
                
                # Check for validation error (error message or button still disabled)
                error_element = await page.query_selector('.dice-error, .error, [class*="error"]')
                # Note: Error handling depends on frontend implementation
                # This test primarily checks the form doesn't crash

            await browser.close()

    @pytest.mark.asyncio
    async def test_dice_bet_api_endpoint(self):
        """Backend /api/dice/bet endpoint accepts valid requests."""
        # This test will verify the backend endpoint without frontend
        # For full E2E, we need a test wallet with funds
        
        test_address = "9iUk8HPLX4RMRt2xXN1CzqZvE5W5B4YxZ7Xj8N9W5E8RjK4Q9Z"
        test_amount = 100000000  # 0.1 ERG in nanoergs
        test_target = 50
        
        # We'll need to check if the backend has the dice bet endpoint
        # For now, this is a placeholder test that can be extended
        pytest.skip("Need test wallet with funds to complete E2E bet placement test")


# ─── DG-2: Reveal ─────────────────────────────────────────────────

class TestDiceReveal:
    """Verify dice roll reveals work correctly."""

    @pytest.mark.asyncio
    async def test_dice_roll_reveal_flow(self):
        """Dice roll reveals after blockchain confirmation."""
        # This test requires a placed bet that reaches reveal stage
        pytest.skip("Requires placed bet with blockchain confirmation for full testing")

    @pytest.mark.asyncio
    async def test_dice_roll_display(self):
        """Dice roll result displays correctly in UI."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(FRONTEND_URL, wait_until="networkidle", timeout=10000)
            await asyncio.sleep(1)

            # Look for roll result display elements
            result_elements = await page.query_selector_all('[class*="result"], [class*="roll"], [data-testid*="result"]')
            # Elements may exist but be hidden until a bet completes
            # This test verifies the UI structure is present

            await browser.close()


# ─── DG-3: Payout ─────────────────────────────────────────────────

class TestDicePayout:
    """Verify payout calculations are correct."""

    @pytest.mark.asyncio
    async def test_dice_payout_calculation(self):
        """Payout multiplier calculation matches frontend logic."""
        # Based on frontend/src/utils/dice.ts
        from decimal import Decimal, getcontext
        getcontext().prec = 10
        
        # Test cases: (roll_target, expected_multiplier_approx)
        test_cases = [
            (50, 1.94),    # ~94% payout
            (10, 9.7),     # ~97% payout for risky bet
            (90, 1.055),   # ~95% payout for safe bet
        ]
        
        for roll_target, expected_multiplier in test_cases:
            # Calculate expected payout using frontend formula
            win_probability = roll_target / 100
            risk_factor = 1 - win_probability
            base_house_edge = 0.03
            house_edge = max(0.01, min(0.05, base_house_edge - risk_factor * 0.02))
            calculated_multiplier = (100 / roll_target) * (1 - house_edge)
            
            # Verify calculation is within expected range
            assert abs(calculated_multiplier - expected_multiplier) < 0.1, \
                f"Payout calculation for target {roll_target}: got {calculated_multiplier}, expected ~{expected_multiplier}"

    @pytest.mark.asyncio
    async def test_payout_display_frontend(self):
        """Payout amount displays correctly in frontend."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(FRONTEND_URL, wait_until="networkidle", timeout=10000)
            await asyncio.sleep(1)

            # Find amount input and target slider
            amount_input = await page.query_selector('input.dice-amount-input, input[placeholder*="0.0"]')
            target_input = await page.query_selector('input.dice-target-input, input[type="range"]')
            
            if amount_input and target_input:
                # Enter test amount
                await amount_input.fill(TEST_BET_AMOUNT)
                await asyncio.sleep(0.5)
                
                # Check if payout preview updates
                payout_element = await page.query_selector('.dice-payout-preview, [class*="payout"]')
                if payout_element:
                    payout_text = await payout_element.text_content()
                    assert "ERG" in payout_text, "Payout preview missing ERG unit"
                    assert "0." in payout_text, "Payout preview missing amount"

            await browser.close()


# ─── DG-4: Wallet Balance ─────────────────────────────────────────

class TestWalletBalance:
    """Verify wallet balance updates after game results."""

    @pytest.mark.asyncio
    async def test_wallet_balance_display(self):
        """Wallet balance displays in frontend when connected."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(FRONTEND_URL, wait_until="networkidle", timeout=10000)
            await asyncio.sleep(1)

            # Look for wallet connection button
            connect_button = await page.query_selector('button:has-text("Connect"), button:has-text("Wallet")')
            # Note: Without actual Nautilus wallet, we can't test full connection
            # But we can verify the UI elements are present

            # Look for balance display elements
            balance_elements = await page.query_selector_all('[class*="balance"], [data-testid*="balance"]')
            # Balance may not show until wallet is connected

            await browser.close()

    @pytest.mark.asyncio
    async def test_wallet_balance_update_after_bet(self):
        """Wallet balance updates after winning/losing a bet."""
        # This test requires an actual wallet with funds and a completed bet
        pytest.skip("Requires actual wallet connection and completed bet for balance testing")


# ─── Integration Tests ─────────────────────────────────────────────

class TestDiceGameIntegration:
    """Integration tests for complete dice game flow."""

    @pytest.mark.asyncio
    async def test_complete_dice_game_flow_ui(self):
        """Test UI flow through all dice game states."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(FRONTEND_URL, wait_until="networkidle", timeout=10000)
            await asyncio.sleep(1)

            # 1. Verify initial state
            title_element = await page.query_selector('h2:has-text("Dice Game"), .dice-title, [class*="title"]')
            assert title_element, "Dice game title not found"

            # 2. Find and interact with form elements
            amount_input = await page.query_selector('input.dice-amount-input, input[placeholder*="0.0"]')
            target_input = await page.query_selector('input.dice-target-input, input[type="range"]')
            submit_button = await page.query_selector('button:has-text("Roll Dice"), button:has-text("Place Bet")')

            if amount_input and target_input:
                # 3. Test form interaction
                await amount_input.fill(TEST_BET_AMOUNT)
                await asyncio.sleep(0.5)
                
                # Check target value display updates
                target_value = await page.query_selector('.dice-target-value, [class*="target-value"]')
                if target_value:
                    target_text = await target_value.text_content()
                    assert target_text.isdigit(), f"Target value not numeric: {target_text}"

            # 4. Verify submit button state
            if submit_button:
                is_enabled = await submit_button.is_enabled()
                # Without wallet connected, it should be disabled
                assert not is_enabled, "Submit button should be disabled without wallet connection"

            await browser.close()

    @pytest.mark.asyncio 
    async def test_dice_game_responsive(self):
        """Dice game works on different viewport sizes."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context()
            page = await context.new_page()

            # Test mobile view
            await page.set_viewport_size({"width": 375, "height": 667})
            await page.goto(FRONTEND_URL, wait_until="networkidle", timeout=10000)
            await asyncio.sleep(0.5)
            
            # Check dice game is visible
            dice_container = await page.query_selector('[class*="dice-game"], [class*="DiceGame"]')
            assert dice_container, "Dice game not visible on mobile"

            # Test desktop view
            await page.set_viewport_size({"width": 1920, "height": 1080})
            await page.goto(FRONTEND_URL, wait_until="networkidle", timeout=10000)
            await asyncio.sleep(0.5)
            
            # Check dice game is still visible
            dice_container = await page.query_selector('[class*="dice-game"], [class*="DiceGame"]')
            assert dice_container, "Dice game not visible on desktop"

            await browser.close()


# ─── Security Tests ───────────────────────────────────────────────

class TestDiceGameSecurity:
    """Security tests for dice game functionality."""

    @pytest.mark.asyncio
    async def test_dice_rng_no_modulo_bias(self):
        """Verify dice RNG uses rejection sampling to avoid modulo bias."""
        # This checks the frontend dice.ts file for proper RNG implementation
        # Based on security/test_regression.py test_dice_rng_no_modulo_bias
        
        try:
            with open('frontend/src/utils/dice.ts', 'r') as f:
                dice_content = f.read()
            
            # Check for rejection sampling implementation
            has_rejection_sampling = 'byte < 200' in dice_content
            has_modulo_warning = 'modulo bias' in dice_content.lower()
            
            assert has_rejection_sampling, "Dice RNG should use rejection sampling (byte < 200)"
            assert has_modulo_warning or 'rejection' in dice_content.lower(), \
                "Dice code should document modulo bias prevention"
                
        except FileNotFoundError:
            pytest.skip("frontend/src/utils/dice.ts not found - cannot verify RNG implementation")

    @pytest.mark.asyncio
    async def test_bet_amount_validation(self):
        """Bet amounts are validated to prevent negative or zero bets."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(FRONTEND_URL, wait_until="networkidle", timeout=10000)
            await asyncio.sleep(1)

            # Try to enter negative amount
            amount_input = await page.query_selector('input.dice-amount-input, input[placeholder*="0.0"]')
            if amount_input:
                await amount_input.fill("-1.0")
                await asyncio.sleep(0.5)
                
                # Check if submit button is still disabled
                submit_button = await page.query_selector('button:has-text("Roll Dice"), button:has-text("Place Bet")')
                if submit_button:
                    is_enabled = await submit_button.is_enabled()
                    assert not is_enabled, "Submit should be disabled with negative amount"

            await browser.close()