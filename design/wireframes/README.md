# DuckPools Interaction Design Wireframes

## Overview

This directory contains interaction flow wireframes for the DuckPools provably-fair gambling protocol on Ergo.

## Wireframes

| Flow | Description |
|------|-------------|
| [Bet Placement Flow](./bet-placement-flow.md) | User flow for placing bets on Coin Flip and future games |
| [Game History Flow](./game-history-flow.md) | User flow for viewing and interacting with bet history |
| [Account Pages Flow](./account-pages-flow.md) | User flow for account management, stats, and LP pool interaction |

## Design Principles

1. **Clarity Over Cleverness** - Every interaction should be immediately understandable
2. **Trust Through Transparency** - Show transaction details, odds, and fairness proofs prominently
3. **Progressive Disclosure** - Start simple, reveal complexity only when needed
4. **Responsive Feedback** - Every action should have immediate visual feedback
5. **Error Prevention** - Guide users away from mistakes before they happen

## User Personas

### The Quick Flipper
- Goal: Fast betting, minimal friction
- Needs: Quick bet amounts, instant confirmation, minimal clicks
- Flow: Connect → Select Amount → Pick Side → Flip → Done

### The Stat Tracker
- Goal: Analyze performance, optimize strategy
- Needs: Detailed history, statistics export, filtering options
- Flow: Bet → Monitor Stats → Analyze Trends → Adjust Strategy

### The Liquidity Provider
- Goal: Earn passive income from bankroll
- Needs: APY visibility, deposit/withdraw controls, risk info
- Flow: Review APY → Deposit → Monitor Returns → Withdraw

## Visual Hierarchy

```
Primary Actions (Large, Prominent)
├── Connect Wallet
├── Place Bet / Flip
└── Deposit / Withdraw

Secondary Actions (Medium, Accessible)
├── Quick Bet Amounts
├── View History
└── Refresh Stats

Tertiary Actions (Small, Hover-Revealed)
├── Explorer Links
├── Detailed Views
└── Settings
```

## Color System

| Purpose | Color | Usage |
|---------|-------|-------|
| Primary Action | Emerald | Place bet, deposit |
| Success | Green | Win confirmation |
| Warning | Amber | Pending, cooldown |
| Error | Red | Loss, errors |
| Info | Blue | Neutral info |
| Neutral | Gray | Disabled, secondary |

## Component Patterns

### Number Displays
- Large primary values (e.g., bet amounts, payouts)
- Compact secondary values (e.g., timestamps, hashes)
- Color-coded for positive/negative values

### Buttons
- Primary: Full-width or prominent, high contrast
- Secondary: Outline or subtle background
- Tertiary: Text or icon only
- Disabled: Grayed out with clear opacity

### Loading States
- Spinner + text (e.g., "Processing transaction...")
- Skeleton loaders for lists/tables
- Progress bars for multi-step actions

### Feedback
- Toast notifications for quick updates
- Modal dialogs for confirmations
- Inline validation for forms
- Success/empty states for lists

## File Format

All wireframes use:
- ASCII art for quick visual reference
- Mermaid diagrams for flow visualization
- Markdown for detailed descriptions
- Component references for implementation

## Next Steps

1. Review each flow wireframe
2. Provide feedback on interaction patterns
3. UI Developer Jr implements based on approved flows
4. Component Developer Jr builds reusable components
5. QA tests against interaction specifications

---

**Issue**: Design interaction flow wireframes for bet placement, game history, and account pages  
**Agent**: Interaction Designer Jr  
**Status**: In Progress
