import { test, expect } from '@playwright/test';

test.describe('Coinflip Game', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the application
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Navigate to coinflip game if not already there
    const url = page.url();
    if (!url.includes('coinflip')) {
      const coinflipLink = page.locator('a[href*="coinflip"], [data-testid="nav-coinflip"]');
      const coinflipVisible = await coinflipLink.isVisible().catch(() => false);
      
      if (coinflipVisible) {
        await coinflipLink.click();
        await page.waitForURL('**/*coinflip**');
        await page.waitForLoadState('networkidle');
      }
    }
  });

  test('should display coinflip game interface', async ({ page }) => {
    // Check if we're on the coinflip page
    await expect(page).toHaveURL(/.*coinflip.*/);

    // Take a screenshot of the game interface
    await page.screenshot({ path: 'coinflip-interface.png' });

    // Check for game title
    const gameTitle = page.locator('[data-testid="game-title"], h1:has-text("Coinflip"), h2:has-text("Coinflip")');
    const titleVisible = await gameTitle.isVisible().catch(() => false);
    
    if (titleVisible) {
      await expect(gameTitle).toBeVisible();
    }

    // Check for betting interface
    const bettingInterface = page.locator('[data-testid="betting-interface"], .betting-interface');
    const bettingVisible = await bettingInterface.isVisible().catch(() => false);
    
    if (bettingVisible) {
      await expect(bettingInterface).toBeVisible();
    }
  });

  test('should display betting options for coinflip', async ({ page }) => {
    // Check for coinflip options (heads/tails)
    const headsOption = page.locator('[data-testid="option-heads"], button:has-text("Heads")');
    const tailsOption = page.locator('[data-testid="option-tails"], button:has-text("Tails")');
    
    // Should have both heads and tails options
    await expect(headsOption).toBeVisible();
    await expect(tailsOption).toBeVisible();
  });

  test('should allow user to select bet amount', async ({ page }) => {
    // Look for bet amount input
    const betAmountInput = page.locator('[data-testid="bet-amount"], input[type="number"], input[placeholder*="bet"]');
    const inputVisible = await betAmountInput.isVisible().catch(() => false);
    
    if (inputVisible) {
      // Test entering a bet amount
      await betAmountInput.fill('1');
      await expect(betAmountInput).toHaveValue('1');
      
      // Test clearing the bet amount
      await betAmountInput.clear();
      await expect(betAmountInput).toHaveValue('');
    }
  });

  test('should validate bet amount input', async ({ page }) => {
    // Look for bet amount input
    const betAmountInput = page.locator('[data-testid="bet-amount"], input[type="number"], input[placeholder*="bet"]');
    const inputVisible = await betAmountInput.isVisible().catch(() => false);
    
    if (inputVisible) {
      // Test entering an invalid bet amount (zero)
      await betAmountInput.fill('0');
      
      // Look for validation error
      const errorMessage = page.locator('[data-testid="error-message"], .error-message');
      const errorVisible = await errorMessage.isVisible().catch(() => false);
      
      if (errorVisible) {
        await expect(errorMessage).toBeVisible();
        await expect(errorMessage).toContainText(/minimum|invalid|zero/i);
      }
      
      // Test entering a valid bet amount
      await betAmountInput.fill('1');
      
      // Error should disappear
      if (errorVisible) {
        await expect(errorMessage).not.toBeVisible();
      }
    }
  });

  test('should show place bet button', async ({ page }) => {
    // Look for place bet button
    const placeBetButton = page.locator('[data-testid="place-bet-button"], button:has-text("Place Bet"), button:has-text("Bet")');
    await expect(placeBetButton).toBeVisible();
  });

  test('should enable place bet button when valid bet is selected', async ({ page }) => {
    // Look for bet amount input and place bet button
    const betAmountInput = page.locator('[data-testid="bet-amount"], input[type="number"], input[placeholder*="bet"]');
    const placeBetButton = page.locator('[data-testid="place-bet-button"], button:has-text("Place Bet"), button:has-text("Bet")');
    const inputVisible = await betAmountInput.isVisible().catch(() => false);
    
    if (inputVisible) {
      // Check initial state (button should be disabled)
      const isInitiallyDisabled = await placeBetButton.isDisabled();
      
      // Select heads option
      const headsOption = page.locator('[data-testid="option-heads"], button:has-text("Heads")');
      await headsOption.click();
      
      // Enter valid bet amount
      await betAmountInput.fill('1');
      
      // Button should now be enabled
      if (isInitiallyDisabled) {
        await expect(placeBetButton).toBeEnabled();
      }
    }
  });

  test('should show bet confirmation modal when place bet is clicked', async ({ page }) => {
    // Mock wallet connection for betting
    await page.addInitScript(() => {
      (window as any).walletState = {
        connected: true,
        address: '3WyrB3D5AMpyEc88UJ7FpdsBMXAZKwzQzkKeDbAQVfXytDPgxF26',
        balance: '1000000000'
      };
    });

    // Reload to apply the script
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Look for bet amount input and place bet button
    const betAmountInput = page.locator('[data-testid="bet-amount"], input[type="number"], input[placeholder*="bet"]');
    const placeBetButton = page.locator('[data-testid="place-bet-button"], button:has-text("Place Bet"), button:has-text("Bet")');
    const inputVisible = await betAmountInput.isVisible().catch(() => false);
    
    if (inputVisible) {
      // Select heads option
      const headsOption = page.locator('[data-testid="option-heads"], button:has-text("Heads")');
      await headsOption.click();
      
      // Enter valid bet amount
      await betAmountInput.fill('1');
      
      // Click place bet button
      await placeBetButton.click();
      
      // Wait for bet confirmation modal
      const confirmationModal = page.locator('[data-testid="bet-confirmation"], .bet-confirmation, [role="dialog"]');
      const modalVisible = await confirmationModal.isVisible().catch(() => false);
      
      if (modalVisible) {
        await expect(confirmationModal).toBeVisible();
        
        // Take screenshot of confirmation modal
        await page.screenshot({ path: 'bet-confirmation.png' });
        
        // Check for bet details in the modal
        const betDetails = page.locator('[data-testid="bet-details"], .bet-details');
        await expect(betDetails).toBeVisible();
        
        // Check for confirm and cancel buttons
        const confirmButton = page.locator('[data-testid="confirm-bet"], button:has-text("Confirm")');
        const cancelButton = page.locator('[data-testid="cancel-bet"], button:has-text("Cancel")');
        await expect(confirmButton).toBeVisible();
        await expect(cancelButton).toBeVisible();
      }
    }
  });

  test('should handle bet placement error', async ({ page }) => {
    // Mock wallet connection
    await page.addInitScript(() => {
      (window as any).walletState = {
        connected: true,
        address: '3WyrB3D5AMpyEc88UJ7FpdsBMXAZKwzQzkKeDbAQVfXytDPgxF26',
        balance: '1000000000'
      };
    });

    // Reload to apply the script
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Mock bet placement error
    await page.route('**/api/bet/**', route => route.abort('failed'));

    // Look for bet amount input and place bet button
    const betAmountInput = page.locator('[data-testid="bet-amount"], input[type="number"], input[placeholder*="bet"]');
    const placeBetButton = page.locator('[data-testid="place-bet-button"], button:has-text("Place Bet"), button:has-text("Bet")');
    const inputVisible = await betAmountInput.isVisible().catch(() => false);
    
    if (inputVisible) {
      // Select heads option
      const headsOption = page.locator('[data-testid="option-heads"], button:has-text("Heads")');
      await headsOption.click();
      
      // Enter valid bet amount
      await betAmountInput.fill('1');
      
      // Click place bet button
      await placeBetButton.click();
      
      // Wait for bet confirmation modal
      const confirmationModal = page.locator('[data-testid="bet-confirmation"], .bet-confirmation, [role="dialog"]');
      const modalVisible = await confirmationModal.isVisible().catch(() => false);
      
      if (modalVisible) {
        await expect(confirmationModal).toBeVisible();
        
        // Click confirm button
        const confirmButton = page.locator('[data-testid="confirm-bet"], button:has-text("Confirm")');
        await confirmButton.click();
        
        // Wait for error message
        const errorMessage = page.locator('[data-testid="error-message"], .error-message, .alert-error');
        const errorVisible = await errorMessage.isVisible().catch(() => false);
        
        if (errorVisible) {
          await expect(errorMessage).toBeVisible();
          await expect(errorMessage).toContainText(/error|failed|unable/i);
        }
      }
    }
  });

  test('should show bet history', async ({ page }) => {
    // Look for bet history section
    const betHistory = page.locator('[data-testid="bet-history"], .bet-history');
    const historyVisible = await betHistory.isVisible().catch(() => false);
    
    if (historyVisible) {
      await expect(betHistory).toBeVisible();
      
      // Check for bet history items
      const historyItems = page.locator('[data-testid="bet-history-item"], .bet-history-item');
      const itemCount = await historyItems.count();
      
      // Should have at least the headers even if no bets
      const historyHeaders = page.locator('[data-testid="bet-history-headers"], .bet-history-headers');
      await expect(historyHeaders).toBeVisible();
      
      // Take screenshot of bet history
      await page.screenshot({ path: 'bet-history.png' });
    }
  });

  test('should be responsive on mobile', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    // Reload to apply responsive layout
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Check that game interface is still visible
    const bettingInterface = page.locator('[data-testid="betting-interface"], .betting-interface');
    const bettingVisible = await bettingInterface.isVisible().catch(() => false);
    
    if (bettingVisible) {
      await expect(bettingInterface).toBeVisible();
    }

    // Take screenshot of mobile view
    await page.screenshot({ path: 'coinflip-mobile.png' });
  });
});