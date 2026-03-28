# Contributing to DuckPools

## Issue Labels

| Label | Color | Purpose |
|---|---|---|
| `priority:high` | 🔴 red | Must do this sprint |
| `priority:medium` | 🟠 orange | Should do this sprint |
| `priority:low` | 🟢 green | Nice to have |
| `domain:protocol` | 🔵 blue | ErgoTree contracts |
| `domain:backend` | 🟣 purple | FastAPI server |
| `domain:frontend` | 🩵 light blue | React SPA |
| `domain:security` | 💗 pink | Audits, pen testing |
| `domain:devops` | ⚪ gray | CI/CD, Docker, infra |
| `status:blocked` | ⚫ black | Waiting on dependency |
| `status:needs-review` | 🟡 yellow | PR open, awaiting review |

## Cross-Team Dependencies

When an issue depends on work from another team:
1. Add a `depends: #ISSUE_ID` comment to the issue body
2. Label with `status:blocked`
3. EMs check blocked issues daily and escalate to CEO if blocked > 48h

Common cross-team deps:
- Frontend games ← Protocol contracts (Wallet Integration Jr needs contract addresses)
- Bankroll module ← Protocol LP contracts
- All games ← Backend game engine API
- All frontend ← Wallet Integration Jr (EIP-12 hooks)
