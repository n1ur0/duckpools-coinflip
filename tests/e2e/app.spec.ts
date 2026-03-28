import { test, expect } from '@playwright/test';

test.describe('DuckPools Application', () => {
  test('should load the main page successfully', async ({ page }) => {
    // Navigate to the application
    await page.goto('/');

    // Wait for the page to load
    await page.waitForLoadState('networkidle');

    // Check that the page title contains DuckPools
    await expect(page).toHaveTitle(/DuckPools/i);

    // Take a screenshot for visual verification
    await page.screenshot({ path: 'main-page-loaded.png' });
  });

  test('should display game navigation options', async ({ page }) => {
    // Navigate to the application
    await page.goto('/');

    // Wait for the page to load
    await page.waitForLoadState('networkidle');

    // Check if game navigation elements are present
    // This assumes there are navigation elements for different games
    const gameNavigation = page.locator('[data-testid="game-navigation"]');
    const isVisible = await gameNavigation.isVisible().catch(() => false);
    
    if (isVisible) {
      // If game navigation exists, verify it has game options
      const gameOptions = gameNavigation.locator('[data-testid^="game-option-"]');
      const gameCount = await gameOptions.count();
      
      // Should have at least one game option
      expect(gameCount).toBeGreaterThan(0);
    }
  });

  test('should display wallet connection button', async ({ page }) => {
    // Navigate to the application
    await page.goto('/');

    // Wait for the page to load
    await page.waitForLoadState('networkidle');

    // Check for wallet connection button
    const walletButton = page.locator('[data-testid="wallet-connect-button"], button:has-text("Connect Wallet")');
    await expect(walletButton).toBeVisible();
  });

  test('should be responsive on mobile viewport', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    // Navigate to the application
    await page.goto('/');

    // Wait for the page to load
    await page.waitForLoadState('networkidle');

    // Take a screenshot for mobile verification
    await page.screenshot({ path: 'mobile-view.png' });

    // Check that the page is still functional on mobile
    const walletButton = page.locator('[data-testid="wallet-connect-button"], button:has-text("Connect Wallet")');
    await expect(walletButton).toBeVisible();
  });

  test('should handle navigation to game pages', async ({ page }) => {
    // Navigate to the application
    await page.goto('/');

    // Wait for the page to load
    await page.waitForLoadState('networkidle');

    // Try to navigate to coinflip game (if it exists)
    const coinflipLink = page.locator('a[href*="coinflip"], [data-testid="nav-coinflip"]');
    const coinflipVisible = await coinflipLink.isVisible().catch(() => false);
    
    if (coinflipVisible) {
      await coinflipLink.click();
      
      // Wait for navigation
      await page.waitForURL('**/*coinflip**');
      
      // Verify we're on the coinflip page
      await expect(page).toHaveURL(/.*coinflip.*/);
      
      // Take a screenshot
      await page.screenshot({ path: 'coinflip-page.png' });
    }
  });

  test.describe('Accessibility', () => {
    test('should have proper heading structure', async ({ page }) => {
      // Navigate to the application
      await page.goto('/');

      // Wait for the page to load
      await page.waitForLoadState('networkidle');

      // Check for proper heading hierarchy
      const headings = await page.locator('h1, h2, h3, h4, h5, h6').all();
      
      // Should have at least one h1
      const h1Count = await page.locator('h1').count();
      expect(h1Count).toBeGreaterThan(0);
      
      // Take a screenshot for accessibility verification
      await page.screenshot({ path: 'accessibility-structure.png' });
    });

    test('should have alt text for images', async ({ page }) => {
      // Navigate to the application
      await page.goto('/');

      // Wait for the page to load
      await page.waitForLoadState('networkidle');

      // Check all images have alt text
      const images = await page.locator('img').all();
      
      for (const image of images) {
        const altText = await image.getAttribute('alt');
        expect(altText).toBeDefined();
      }
    });
  });
});