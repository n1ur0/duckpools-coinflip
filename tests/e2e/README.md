# DuckPools E2E Testing Suite

This directory contains End-to-End (E2E) tests for the DuckPools application using Playwright. These tests verify that the entire application works correctly from a user's perspective, including the frontend, backend integration, and critical user flows.

## What's Tested

### Application Tests (`app.spec.ts`)
- **Main Page Load**: Verifies that the application loads successfully and displays correctly
- **Game Navigation**: Tests navigation between different game sections
- **Wallet Connection Button**: Ensures the wallet connection button is present and functional
- **Mobile Responsiveness**: Verifies the application works correctly on mobile devices
- **Accessibility**: Checks for proper heading structure and image alt text

### Wallet Functionality Tests (`wallet.spec.ts`)
- **Wallet Connection Modal**: Tests the appearance and functionality of the wallet connection modal
- **Wallet Options**: Verifies that available wallet options (like Nautilus) are displayed
- **Modal Interactions**: Tests opening and closing the wallet modal
- **Error Handling**: Ensures wallet connection errors are handled gracefully
- **Connected State**: Tests the UI state when a wallet is successfully connected
- **Disconnection**: Verifies that users can disconnect their wallets correctly

### Coinflip Game Tests (`coinflip.spec.ts`)
- **Game Interface**: Verifies that the coinflip game interface displays correctly
- **Betting Options**: Tests that heads/tails options are available and selectable
- **Bet Amount Input**: Validates bet amount input functionality and validation
- **Place Bet Button**: Tests the place bet button state and functionality
- **Bet Confirmation**: Verifies the bet confirmation modal displays correctly
- **Error Handling**: Tests error scenarios during bet placement
- **Bet History**: Checks that bet history is displayed correctly
- **Mobile Responsiveness**: Ensures the game works correctly on mobile devices

## Prerequisites

1. **Node.js**: Version 18 or higher
2. **Playwright**: Install browsers and dependencies

## Installation

1. Navigate to the E2E tests directory:
   ```bash
   cd tests/e2e
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Install Playwright browsers:
   ```bash
   npm run install:browsers
   ```

## Running Tests

### Run All Tests
```bash
npm test
```

### Run Tests in Headed Mode (Visible Browser)
```bash
npm run test:headed
```

### Run Tests in Debug Mode
```bash
npm run test:debug
```

### Run Tests with UI Mode
```bash
npm run test:ui
```

### Run Tests in CI Mode
```bash
npm run test:ci
```

### View Test Reports
```bash
npm run report:show
```

## Test Configuration

The Playwright configuration (`playwright.config.ts`) includes:

- **Multiple Browsers**: Tests run on Chromium, Firefox, and WebKit
- **Mobile Viewports**: Tests include mobile responsiveness checks
- **Auto-wait**: Playwright automatically waits for elements to be ready
- **Screenshots**: Screenshots are taken on test failures
- **Videos**: Videos are recorded for failed tests
- **Trace**: Traces are captured for debugging failed tests
- **Web Server**: Automatically starts the frontend development server

## Writing New Tests

### Test Structure

1. **Use `test.describe()` to group related tests**
2. **Use `test.beforeEach()` for common setup**
3. **Use descriptive test names**
4. **Include assertions that verify the expected behavior**

### Best Practices

1. **Use data-testid attributes** for reliable element selection
2. **Wait for elements to be visible** before interacting with them
3. **Include both positive and negative test cases**
4. **Test error scenarios** as well as happy paths
5. **Include accessibility checks** where appropriate
6. **Test on multiple viewports** including mobile

### Example Test Structure

```typescript
import { test, expect } from '@playwright/test';

test.describe('Feature Name', () => {
  test.beforeEach(async ({ page }) => {
    // Common setup code
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('should do something', async ({ page }) => {
    // Test steps
    const element = page.locator('[data-testid="element"]');
    await expect(element).toBeVisible();
    
    // Interact with the element
    await element.click();
    
    // Verify the result
    const result = page.locator('[data-testid="result"]');
    await expect(result).toBeVisible();
  });
});
```

## Debugging Tests

1. **Use the debug mode**: `npm run test:debug`
2. **Use the UI mode**: `npm run test:ui`
3. **Check the HTML report**: `npm run report:show`
4. **Look at screenshots and videos** for failed tests
5. **Use Playwright Trace Viewer** for detailed debugging

## Continuous Integration

These E2E tests are designed to run in CI/CD pipelines:

- Use `npm run test:ci` for CI execution
- Reports are generated and can be archived
- Tests run on multiple browsers to ensure cross-browser compatibility

## Contributing

When adding new E2E tests:

1. **Follow the existing test structure**
2. **Include comprehensive test coverage**
3. **Test both success and failure scenarios**
4. **Add appropriate test data and mocking**
5. **Update this README** if adding new test files or major functionality

## Troubleshooting

### Common Issues

1. **Timeout Errors**: Increase timeouts in `playwright.config.ts` or use `page.waitForTimeout()`
2. **Element Not Found**: Use Playwright's locator methods and wait for elements
3. **Network Issues**: Mock network requests using `page.route()`
4. **Authentication Issues**: Use `page.addInitScript()` to mock authentication state

### Getting Help

- [Playwright Documentation](https://playwright.dev/)
- [Playwright API Reference](https://playwright.dev/docs/api/class-playwright)
- [DuckPools Documentation](../../README.md)