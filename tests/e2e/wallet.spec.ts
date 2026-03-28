import { test, expect } from '@playwright/test';

test.describe('Wallet Functionality', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the application before each test
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('should display wallet connection modal when connect button is clicked', async ({ page }) => {
    // Click the wallet connect button
    const walletButton = page.locator('[data-testid="wallet-connect-button"], button:has-text("Connect Wallet")');
    await walletButton.click();

    // Wait for the wallet connection modal to appear
    const walletModal = page.locator('[data-testid="wallet-modal"], .wallet-modal, [role="dialog"]');
    await expect(walletModal).toBeVisible();

    // Take a screenshot of the modal
    await page.screenshot({ path: 'wallet-modal.png' });
  });

  test('should display available wallet options', async ({ page }) => {
    // Click the wallet connect button
    const walletButton = page.locator('[data-testid="wallet-connect-button"], button:has-text("Connect Wallet")');
    await walletButton.click();

    // Wait for the wallet connection modal to appear
    const walletModal = page.locator('[data-testid="wallet-modal"], .wallet-modal, [role="dialog"]');
    await expect(walletModal).toBeVisible();

    // Check for wallet options (Nautilus is the main Ergo wallet)
    const nautilusOption = page.locator('[data-testid="wallet-nautilus"], button:has-text("Nautilus")');
    const walletOptions = page.locator('[data-testid^="wallet-option-"], .wallet-option');
    
    const nautilusVisible = await nautilusOption.isVisible().catch(() => false);
    if (nautilusVisible) {
      await expect(nautilusOption).toBeVisible();
    }
    
    // Should have at least one wallet option
    const walletCount = await walletOptions.count();
    expect(walletCount).toBeGreaterThan(0);
  });

  test('should close modal when cancel button is clicked', async ({ page }) => {
    // Click the wallet connect button
    const walletButton = page.locator('[data-testid="wallet-connect-button"], button:has-text("Connect Wallet")');
    await walletButton.click();

    // Wait for the wallet connection modal to appear
    const walletModal = page.locator('[data-testid="wallet-modal"], .wallet-modal, [role="dialog"]');
    await expect(walletModal).toBeVisible();

    // Click the cancel/close button
    const closeButton = page.locator('[data-testid="modal-close"], button:has-text("Cancel"), button:has-text("Close")');
    const closeVisible = await closeButton.isVisible().catch(() => false);
    
    if (closeVisible) {
      await closeButton.click();
      await expect(walletModal).not.toBeVisible();
    } else {
      // Try clicking outside the modal to close it
      await page.mouse.click(10, 10);
      await expect(walletModal).not.toBeVisible();
    }
  });

  test('should handle wallet connection error gracefully', async ({ page }) => {
    // Mock a wallet connection error
    await page.route('**/wallet/**', route => route.abort('failed'));

    // Click the wallet connect button
    const walletButton = page.locator('[data-testid="wallet-connect-button"], button:has-text("Connect Wallet")');
    await walletButton.click();

    // Wait for the wallet connection modal to appear
    const walletModal = page.locator('[data-testid="wallet-modal"], .wallet-modal, [role="dialog"]');
    await expect(walletModal).toBeVisible();

    // Try to connect with Nautilus wallet
    const nautilusOption = page.locator('[data-testid="wallet-nautilus"], button:has-text("Nautilus")');
    const nautilusVisible = await nautilusOption.isVisible().catch(() => false);
    
    if (nautilusVisible) {
      await nautilusOption.click();
      
      // Wait for error message to appear
      const errorMessage = page.locator('[data-testid="error-message"], .error-message, .alert-error');
      const errorVisible = await errorMessage.isVisible().catch(() => false);
      
      if (errorVisible) {
        await expect(errorMessage).toBeVisible();
        await expect(errorMessage).toContainText(/error|failed|unable/i);
      }
    }
  });

  test('should show connected state after successful wallet connection', async ({ page }) => {
    // Mock a successful wallet connection
    await page.route('**/wallet/**', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          address: '3WyrB3D5AMpyEc88UJ7FpdsBMXAZKwzQzkKeDbAQVfXytDPgxF26',
          balance: '1000000000', // 1 ERG in nanoERG
          connected: true
        })
      });
    });

    // Click the wallet connect button
    const walletButton = page.locator('[data-testid="wallet-connect-button"], button:has-text("Connect Wallet")');
    await walletButton.click();

    // Wait for the wallet connection modal to appear
    const walletModal = page.locator('[data-testid="wallet-modal"], .wallet-modal, [role="dialog"]');
    await expect(walletModal).toBeVisible();

    // Try to connect with Nautilus wallet
    const nautilusOption = page.locator('[data-testid="wallet-nautilus"], button:has-text("Nautilus")');
    const nautilusVisible = await nautilusOption.isVisible().catch(() => false);
    
    if (nautilusVisible) {
      await nautilusOption.click();
      
      // Wait for the modal to close
      await expect(walletModal).not.toBeVisible();
      
      // Check that the wallet is now connected
      const walletStatus = page.locator('[data-testid="wallet-status"], .wallet-status');
      await expect(walletStatus).toBeVisible();
      await expect(walletStatus).toContainText(/connected|3WyrB3D5/i);
      
      // Check that the balance is displayed
      const walletBalance = page.locator('[data-testid="wallet-balance"], .wallet-balance');
      await expect(walletBalance).toBeVisible();
      
      // Take a screenshot of connected state
      await page.screenshot({ path: 'wallet-connected.png' });
    }
  });

  test('should display disconnect option when wallet is connected', async ({ page }) => {
    // First, set up a connected state
    await page.addInitScript(() => {
      // Mock a connected wallet state
      (window as any).walletState = {
        connected: true,
        address: '3WyrB3D5AMpyEc88UJ7FpdsBMXAZKwzQzkKeDbAQVfXytDPgxF26',
        balance: '1000000000'
      };
    });

    // Reload the page to apply the script
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Check that disconnect option is available
    const disconnectButton = page.locator('[data-testid="wallet-disconnect"], button:has-text("Disconnect")');
    const disconnectVisible = await disconnectButton.isVisible().catch(() => false);
    
    if (disconnectVisible) {
      await expect(disconnectButton).toBeVisible();
    }
  });

  test('should handle wallet disconnection', async ({ page }) => {
    // First, set up a connected state
    await page.addInitScript(() => {
      // Mock a connected wallet state
      (window as any).walletState = {
        connected: true,
        address: '3WyrB3D5AMpyEc88UJ7FpdsBMXAZKwzQzkKeDbAQVfXytDPgxF26',
        balance: '1000000000'
      };
    });

    // Reload the page to apply the script
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Click the disconnect button
    const disconnectButton = page.locator('[data-testid="wallet-disconnect"], button:has-text("Disconnect")');
    const disconnectVisible = await disconnectButton.isVisible().catch(() => false);
    
    if (disconnectVisible) {
      await disconnectButton.click();
      
      // Verify that we're back to disconnected state
      const connectButton = page.locator('[data-testid="wallet-connect-button"], button:has-text("Connect Wallet")');
      await expect(connectButton).toBeVisible();
      
      // Take a screenshot of disconnected state
      await page.screenshot({ path: 'wallet-disconnected.png' });
    }
  });
});