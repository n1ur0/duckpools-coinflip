# QA Preparation: MAT-172 - Design Token Audit

**Agent:** QA Agent (ID: 780f04f8-c43c-496e-a126-6a95acb76aae)
**Date:** 2026-03-27
**Issue:** [UX/UI] Audit design token adoption across all frontend components

---

## Overview
Design tokens (tokens.css) and UI component library were built in MAT-146/147/149, but many components still use hardcoded colors, fonts, spacing, border-radius, and shadows that should use design tokens.

---

## Design Tokens Available (from tokens.css)

### Backgrounds
- `--bg-primary: #080b14`
- `--bg-secondary: #0f1423`
- `--bg-tertiary: #161d30`
- `--bg-card: rgba(255, 255, 255, 0.03)`
- `--bg-card-hover: rgba(255, 255, 255, 0.06)`
- `--bg-elevated: rgba(255, 255, 255, 0.08)`
- `--bg-overlay: rgba(0, 0, 0, 0.6)`
- `--bg-input: rgba(255, 255, 255, 0.05)`

### Text Colors
- `--text-primary: #f0f0f0`
- `--text-secondary: #8892b0`
- `--text-tertiary: #5a6380`
- `--text-muted: #3d4560`
- `--text-inverse: #080b14`
- `--text-link: #f0b429`

### Accent Colors
- `--accent-gold: #f0b429`
- `--accent-gold-light: #ffd700`
- `--accent-gold-dark: #c4922a`
- `--accent-gold-subtle: rgba(240, 180, 41, 0.15)`
- `--accent-green: #00ff88`
- `--accent-green-light: #33ffaa`
- `--accent-green-dark: #00cc6a`
- `--accent-green-subtle: rgba(0, 255, 136, 0.15)`
- `--accent-red: #ef4444`
- `--accent-red-light: #f87171`
- `--accent-red-dark: #dc2626`
- `--accent-red-subtle: rgba(239, 68, 68, 0.15)`
- `--accent-blue: #3b82f6`
- `--accent-purple: #8b5cf6`

### Borders
- `--border-default: rgba(255, 255, 255, 0.08)`
- `--border-subtle: rgba(255, 255, 255, 0.04)`
- `--border-strong: rgba(255, 255, 255, 0.15)`
- `--border-focus: rgba(240, 180, 41, 0.5)`
- `--border-color: rgba(255, 255, 255, 0.08)`

### Typography
- `--font-heading: "Space Grotesk", sans-serif`
- `--font-body: "Inter", sans-serif`
- `--font-mono: "JetBrains Mono", monospace`
- `--text-xs: clamp(0.7rem, 0.65rem + 0.25vw, 0.75rem)`
- `--text-sm: clamp(0.8rem, 0.75rem + 0.25vw, 0.875rem)`
- `--text-base: clamp(0.9rem, 0.85rem + 0.25vw, 1rem)`
- `--text-lg: clamp(1.05rem, 1rem + 0.25vw, 1.125rem)`
- `--text-xl: clamp(1.15rem, 1.05rem + 0.5vw, 1.25rem)`
- `--text-2xl: clamp(1.35rem, 1.2rem + 0.75vw, 1.5rem)`
- `--text-3xl: clamp(1.7rem, 1.4rem + 1.5vw, 1.875rem)`
- `--text-4xl: clamp(2rem, 1.5rem + 2.5vw, 2.25rem)`
- `--font-normal: 400`
- `--font-medium: 500`
- `--font-semibold: 600`
- `--font-bold: 700`
- `--leading-tight: 1.25`
- `--leading-normal: 1.5`
- `--leading-relaxed: 1.625`
- `--leading-loose: 2`

### Spacing
- `--space-1: 0.25rem` through `--space-32: 8rem`

### Border Radius
- `--radius-sm: 0.375rem`
- `--radius-md: 0.5rem`
- `--radius-lg: 0.75rem`
- `--radius-xl: 1rem`
- `--radius-2xl: 1.5rem`
- `--radius-full: 9999px`

### Shadows
- `--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3)`
- `--shadow-md: 0 4px 6px rgba(0, 0, 0, 0.3)`
- `--shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.3)`
- `--shadow-xl: 0 20px 25px rgba(0, 0, 0, 0.4)`
- `--shadow-glow-gold: 0 0 20px rgba(240, 180, 41, 0.3)`
- `--shadow-glow-green: 0 0 20px rgba(0, 255, 136, 0.3)`

### Transitions
- `--transition-fast: 150ms ease`
- `--transition-normal: 250ms ease`
- `--transition-slow: 400ms ease`

---

## Files to Audit (24 CSS files found)

### Priority Files (from issue description)
1. `BetForm.css` - game UI
2. `DiceForm.css` - game UI
3. `WalletConnector.css` - user-facing critical component
4. `PoolUI.css` - financial component
5. `PoolManager.css` - financial component
6. `GameHistory.css` - data display
7. `Leaderboard.css` - data display
8. `StatsDashboard.css` - data display
9. `CompPoints.css` - rewards UI
10. `App.css` - global styles

### Additional Files Found
- `OnboardingWizard.css`
- `GameNav.css`
- `GameCard.css`
- `Skeleton.css`
- `ErrorBoundary.css`
- `ErrorWithRetry.css`
- `TestWallet.css`
- `animations/animations.css`
- `ui/` folder components:
  - `Button.css`
  - `Card.css`
  - `Input.css`
  - `Modal.css`
  - `Badge.css`
  - `Toggle.css`
  - `EmptyState.css`

---

## Issues Found in Sample Files

### BetForm.css - Observations
**Good:**
- Uses `var(--bg-card, ...)` with fallbacks
- Uses `var(--border-color, ...)` with fallbacks
- Uses `var(--font-heading, ...)` with fallbacks
- Uses `var(--text-primary, ...)` with fallbacks
- Uses `var(--accent-gold, ...)` with fallbacks

**Needs Improvement (hardcoded values):**
- Line 6: `border-radius: 16px;` → should be `var(--radius-xl, 1rem)`
- Line 7: `padding: 24px;` → should be `var(--space-6, 1.5rem)`
- Line 15: `font-size: 1.5rem;` → should be `var(--text-2xl, ...)`
- Line 16: `font-weight: 700;` → should be `var(--font-bold, 700)`
- Line 19: `margin-bottom: 20px;` → should use spacing token
- Line 25: `margin-bottom: 20px;` → should use spacing token
- Line 30: `font-size: 0.85rem;` → should be `var(--text-sm, ...)`
- Line 33: `font-weight: 500;` → should be `var(--font-medium, 500)`
- Line 38: `gap: 8px;` → should be `var(--space-2, 0.5rem)`
- Line 44: `background: rgba(255, 255, 255, 0.04);` → should use `--bg-input`
- Line 46: `border-radius: 10px;` → should be `var(--radius-lg, 0.75rem)`
- Line 47: `padding: 12px 16px;` → should use spacing tokens
- Line 50: `font-size: 1.1rem;` → should be `var(--text-lg, ...)`
- Line 52: `transition: border-color 0.2s, box-shadow 0.2s;` → should be `var(--transition-fast, ...)`
- Line 57: `box-shadow: 0 0 0 2px rgba(240, 180, 41, 0.15);` → should use `--accent-gold-subtle`
- Line 61: `color: rgba(255, 255, 255, 0.2);` → should use `--text-muted`
- Line 74: `gap: 8px;` → should use spacing token
- Line 81: `border-radius: 8px;` → should use `var(--radius-md, 0.5rem)`
- Line 82: `padding: 6px 14px;` → should use spacing tokens
- Line 87: `transition: all 0.2s;` → should be `var(--transition-fast, ...)`

**Tails button specific (lines 162-186):**
- Line 162: `color: #63b3ed;` → hardcoded blue (should use token)
- Line 164: `border-color: rgba(99, 179, 237, 0.2);` → hardcoded
- Line 169: `border-color: #63b3ed;` → hardcoded
- Line 184: `border-color: #63b3ed;` → hardcoded

### DiceForm.css - Observations
**Similar patterns to BetForm.css:**
- Uses design tokens with fallbacks for most colors
- Has many hardcoded values for spacing, border-radius, font-size, font-weight

**Additional observations:**
- Line 118: `font-size: 1.8rem;` → should be `var(--text-3xl, ...)`
- Line 121: `line-height: 1;` → should be `var(--leading-tight, 1.25)`
- Line 127: `gap: 10px;` → should use spacing token
- Line 144: `height: 8px;` → hardcoded
- Line 145: `border-radius: 4px;` → hardcoded
- Line 146: `background: rgba(255, 255, 255, 0.08);` → should use token
- Line 154-155: `width: 22px; height: 22px;` → hardcoded
- Line 156: `border-radius: 50%;` → should be `var(--radius-full, ...)`
- Line 159: `border: 3px solid #080b14;` → hardcoded
- Line 160: `box-shadow: 0 0 10px rgba(240, 180, 41, 0.4);` → hardcoded shadow
- Line 161: `transition: transform 0.15s, box-shadow 0.15s;` → hardcoded transition
- Line 202: `border-radius: 6px;` → hardcoded
- Line 204: `background: rgba(255, 255, 255, 0.03);` → hardcoded
- Line 208: `font-size: 0.8rem;` → should use text token
- Line 209: `font-weight: 600;` → should be `var(--font-semibold, 600)`
- Line 210: `transition: all 0.2s;` → should be `var(--transition-fast, ...)`
- Line 232: `gap: 12px;` → should use spacing token
- Line 233: `padding: 16px;` → should use spacing token
- Line 234: `border-radius: 12px;` → should be `var(--radius-xl, 1rem)`
- Line 236: `transition: all 0.3s;` → should be `var(--transition-normal, ...)`

**Risk level backgrounds (lines 239-261):**
All use hardcoded RGBA values that should use token variants.

---

## Test Plan for MAT-172

### Phase 1: Visual Regression Testing (Before Fixes)
1. Take baseline screenshots of all component pages
2. Document current visual state
3. Identify inconsistent styling across components

### Phase 2: Token Replacement Verification
After fixes are applied, verify:
1. **Color consistency**: All colors use design tokens with appropriate fallbacks
2. **Typography consistency**: All fonts, sizes, weights use design tokens
3. **Spacing consistency**: All padding, margins, gaps use design tokens
4. **Border-radius consistency**: All border-radius values use design tokens
5. **Shadow consistency**: All box-shadow values use design tokens
6. **Transition consistency**: All transitions use design tokens

### Phase 3: Cross-Component Consistency Testing
1. Test BetForm and DiceForm side-by-side to ensure consistent styling
2. Verify all game forms use same design tokens
3. Test WalletConnector across different pages
4. Verify PoolUI and PoolManager have consistent financial styling

### Phase 4: Browser Testing
1. Test in Chrome, Firefox, Safari
2. Test responsive breakpoints (mobile, tablet, desktop)
3. Test dark mode is maintained
4. Test fallback values work (for older browsers that don't support CSS variables)

### Phase 5: Accessibility Testing
1. Verify contrast ratios remain WCAG AA compliant after token changes
2. Test with screen readers
3. Verify keyboard navigation works
4. Test with browser zoom levels

### Phase 6: Edge Cases
1. Test with JavaScript disabled (should still load with CSS variables)
2. Test with custom user CSS
3. Test with different system font preferences
4. Test with different color profiles (sRGB, P3)

---

## Test Cases to Write

### TC1: BetForm Token Adoption
**Objective**: Verify BetForm.css uses design tokens for all styling
**Steps**:
1. Open BetForm component
2. Inspect all styled elements
3. Verify colors use `var(--accent-*, --text-*, --bg-*)` tokens
4. Verify fonts use `var(--font-*)` tokens
5. Verify spacing uses `var(--space-*)` tokens
6. Verify border-radius uses `var(--radius-*)` tokens
7. Verify shadows use `var(--shadow-*)` tokens
8. Verify transitions use `var(--transition-*)` tokens
**Expected Result**: All styling uses design tokens with appropriate fallbacks

### TC2: DiceForm Token Adoption
**Objective**: Verify DiceForm.css uses design tokens for all styling
**Steps**: Same as TC1, for DiceForm
**Expected Result**: All styling uses design tokens with appropriate fallbacks

### TC3: WalletConnector Token Adoption
**Objective**: Verify WalletConnector.css uses design tokens for all styling
**Steps**: Same as TC1, for WalletConnector
**Expected Result**: All styling uses design tokens with appropriate fallbacks

### TC4: Cross-Browser Fallback Testing
**Objective**: Verify fallback values work in browsers without CSS variable support
**Steps**:
1. Load page in browser without CSS variable support
2. Verify all elements render with fallback values
3. Verify visual consistency across components
**Expected Result**: All elements render correctly with fallback values

### TC5: Visual Consistency Across Game Forms
**Objective**: Verify BetForm and DiceForm have consistent styling
**Steps**:
1. Open BetForm and DiceForm side-by-side
2. Compare button styles
3. Compare input field styles
4. Compare error message styles
5. Compare typography
**Expected Result**: Consistent styling across both game forms

---

## Missing Tokens to Document

Based on review, potential missing tokens:
1. **Blue accent**: DiceForm uses `#63b3ed` for tails button - should we add `--accent-blue` variant?
2. **Custom color values**: Various RGBA opacity levels not in tokens
3. **Specific heights**: Some height values (8px, 22px, 28px) not covered by spacing tokens

---

## Next Steps

1. Wait for MAT-172 to be assigned or for fixes to be made
2. Run full audit on all 24 CSS files
3. Execute test plan above
4. Document any missing tokens found
5. Verify all fixes pass visual regression tests
6. Provide detailed QA report

---

## Tools Needed

- Browser dev tools (Chrome DevTools, Firefox Inspector)
- Visual regression testing tool (BackstopJS, Percy, or Chromatic)
- Accessibility testing tool (axe DevTools, WAVE)
- Cross-browser testing (BrowserStack, Sauce Labs, or local browsers)
- Screenshot comparison tool

---

**Status**: Ready for testing. Waiting for MAT-172 assignment or fixes to be completed.
