# DuckPools — Agent Guide

> Quick reference for all Matsuzaka agents working on DuckPools.

## Hierarchy

| Tier | Model | Role | Job |
|------|-------|------|-----|
| CEO | glm-5-turbo | Direction | Priorities, policy, intervention |
| EM (PM) | glm-5-turbo | Management | Assign work, wake agents, track velocity |
| Senior | glm-5-turbo | Review | Code review, architecture, merge PRs |
| Junior (Jr) | glm-4.7 | Implement | Build features, write tests, open PRs |

**Juniors** have "Jr" in their name. Everyone else is a senior.

## Git Workflow

### Branch Naming
```
agent/{YourName}/ISSUE-ID-short-description
```
Example: `agent/UI-Developer-Jr/42-add-dice-game-component`

### Worktree Setup
```bash
cd ~/projects/DuckPools
git fetch origin
git worktree add ../worktrees/agent/YourName/ISSUE-ID-desc -b agent/YourName/ISSUE-ID-desc origin/main
cd ../worktrees/agent/YourName/ISSUE-ID-desc
```

### Daily Flow
1. Create worktree for your assigned issue
2. Implement, test, commit (conventional commits)
3. Push: `git push -u origin agent/YourName/ISSUE-ID-desc`
4. Open PR: `~/bin/gh pr create --title "ISSUE-ID: Short title" --body "## Summary\n\nCloses #ISSUE-ID\n\n## Testing\n\n..."`
5. Tag reviewer: `~/bin/gh pr edit PR_NUMBER --add-reviewer SENIOR_GH_HANDLE`
6. Post PR URL as comment on the issue
7. After merge: `git worktree remove ../worktrees/agent/YourName/ISSUE-ID-desc`

### Commit Convention
```
feat: add dice game component
fix: correct RNG seed calculation
test: add unit tests for bankroll module
docs: update API endpoint documentation
refactor: extract shared button component
chore: update dependencies
```

## Project Structure
```
DuckPools/
├── backend/       # FastAPI (Python 3.12)
│   ├── app/api/   # Route handlers
│   ├── app/models/# SQLAlchemy/Pydantic
│   ├── app/services/# Business logic
│   └── tests/
├── frontend/      # React 18 + TypeScript + Vite
│   ├── src/components/games/   # Game UIs
│   ├── src/hooks/              # useWallet, useGame, useBet
│   ├── src/pages/
│   └── tests/
├── protocol/      # ErgoTree smart contracts
│   ├── contracts/ # .es files
│   ├── sdk/       # TypeScript SDK
│   └── tests/
├── security/      # Audits, pen tests, regression
├── devops/        # Docker, CI, monitoring
└── docs/          # Architecture docs, runbooks
```

## Coding Conventions

### Backend (Python)
- Ruff: `ruff check . && ruff format .`
- All monetary values: `decimal.Decimal`, never `float`
- All functions typed, Pydantic for API schemas
- Async throughout, no blocking I/O
- Tests: `pytest`, files named `tests/test_<module>.py`

### Frontend (TypeScript)
- ESLint + Prettier: `npm run lint && npm run format`
- Functional components, typed interfaces
- Zustand stores (no prop drilling beyond 2 levels)
- Tailwind utilities, no inline styles
- Tests: Vitest

### Protocol (ErgoTree)
- One contract per `.es` file in `protocol/contracts/`
- Every guard clause commented (WHY, not WHAT)
- Matching test in `protocol/tests/`

## Domain Knowledge

### Commit-Reveal RNG
1. Player commits `hash(outcome || salt)` on-chain
2. Wait N blocks (configurable delay)
3. Player reveals `outcome || salt`
4. Contract verifies hash, calculates payout atomically

### Bankroll Model
- ERG deposited → LP tokens received (tokenized LP)
- House edge configurable per game (~3% default)
- LP holders get proportional profit share
- Withdrawal: burn LP tokens, receive proportional ERG

### Data Flow
```
Player → Frontend (React) → Backend API (FastAPI) → Ergo Node
                                ↓
                          PostgreSQL (off-chain state)
                                ↓
                          Oracle Pool (ERG/USD price)
```

## Issue Labels

| Label | Meaning |
|-------|---------|
| `priority:high` | Must do this sprint |
| `priority:medium` | Should do this sprint |
| `priority:low` | Nice to have |
| `domain:protocol` | ErgoTree contracts |
| `domain:backend` | FastAPI server |
| `domain:frontend` | React SPA |
| `domain:security` | Audits, pen testing |
| `domain:devops` | CI/CD, Docker, infra |
| `status:blocked` | Waiting on dependency |
| `status:needs-review` | PR open, awaiting review |

## Rules

1. **No direct main commits.** Every change via PR with code review.
2. **One issue = one branch = one worktree = one PR.**
3. **Juniors implement, seniors review.** Don't merge your own PR.
4. **Test before PR.** CI must pass.
5. **If stuck, tell your EM.** Don't waste cycles spinning.
6. **Clean up your worktree** after PR merge.
7. **Use conventional commits** for all commit messages.
8. **Tag your senior reviewer** when opening a PR.
