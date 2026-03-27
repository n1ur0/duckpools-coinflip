# Contributing Guide

Thank you for your interest in contributing to DuckPools Coinflip! This guide covers our development workflow, code style standards, and testing requirements.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Workflow](#development-workflow)
3. [Code Style](#code-style)
4. [Testing](#testing)
5. [Pull Request Process](#pull-request-process)
6. [Issue Reporting](#issue-reporting)

---

## Getting Started

### Prerequisites

Ensure you have the following installed:
- Java 11+ (for Ergo node)
- Python 3.12+ (for backend)
- Node.js 18+ (for frontend)
- Git

### Initial Setup

```bash
# Fork and clone your fork
git clone https://github.com/YOUR_USERNAME/duckpools-coinflip.git
cd duckpools-coinflip

# Add upstream remote
git remote add upstream https://github.com/ergoplatform/duckpools-coinflip.git

# Install dependencies
cd backend && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
cd ../frontend && npm install
```

### Running Tests

```bash
# Backend tests
cd backend
source venv/bin/activate
pytest -v

# Frontend type checking
cd frontend
npm run typecheck
```

---

## Development Workflow

We follow a **feature branch** workflow:

```
main (protected)
  ↑
  develop
  ↑
  feature/my-cool-feature
```

### Creating a Branch

```bash
# Ensure main is up to date
git checkout main
git fetch upstream
git rebase upstream/main

# Create feature branch from main
git checkout -b feature/my-cool-feature
```

### Making Changes

1. Write code following style guidelines
2. Add/update tests
3. Commit with clear messages
4. Push to your fork

```bash
git add .
git commit -m "feat: add support for multiple bet amounts"
git push origin feature/my-cool-feature
```

### Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples**:

```
feat(bet): add support for multiple bet amounts

Users can now select from predefined bet amounts (0.1, 0.5, 1.0 ERG).
The BetForm component now uses a dropdown instead of raw input.

Closes #123
```

```
fix(backend): correct RNG calculation for outcome

The RNG was using int(hash[-1]) % 2 instead of hash[0] % 2.
This caused incorrect outcomes. Fixed to use first byte as specified.

Fixes #145
```

---

## Code Style

### Python (Backend)

Follow **PEP 8** guidelines with these additions:

#### Type Hints

All functions should have type hints:

```python
from typing import Optional, List

def place_bet(
    amount: int,
    choice: int,
    secret: Optional[int] = None
) -> dict:
    """
    Place a bet on the blockchain.
    
    Args:
        amount: Bet amount in nanoERG
        choice: Bet choice (0=heads, 1=tails)
        secret: Player's random secret (32-bit)
    
    Returns:
        Dictionary with transaction ID and bet details
    """
    pass
```

#### Docstrings

Use **Google-style** docstrings:

```python
def calculate_payout(bet_amount: int, won: bool) -> int:
    """Calculate payout for a bet.
    
    Args:
        bet_amount: Original bet amount in nanoERG
        won: Whether the player won
        
    Returns:
        Payout amount in nanoERG
        
    Raises:
        ValueError: If bet_amount is negative
    """
    if bet_amount < 0:
        raise ValueError("Bet amount must be positive")
    return int(bet_amount * 1.94) if won else 0
```

#### Imports

Order: stdlib, third-party, local

```python
import hashlib
from datetime import datetime
from typing import Optional

import httpx
from fastapi import FastAPI

from .services.blockchain import get_node_height
from .types import BetRequest
```

### TypeScript (Frontend)

Follow these TypeScript best practices:

#### Type Definitions

Always define types for your data:

```typescript
interface Bet {
  id: string;
  amount: number;
  choice: 0 | 1;
  playerAddress: string;
  status: 'pending' | 'revealed' | 'settled';
  outcome?: 0 | 1;
}

type BetStatus = 'pending' | 'revealed' | 'settled';
```

#### React Components

Use functional components with hooks:

```typescript
interface BetFormProps {
  onBetPlaced: (bet: Bet) => void;
  minBet: number;
  maxBet: number;
}

export const BetForm: React.FC<BetFormProps> = ({ onBetPlaced, minBet, maxBet }) => {
  const [amount, setAmount] = useState<number>(minBet);
  const [choice, setChoice] = useState<0 | 1>(0);
  
  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    // ...
  };
  
  return (
    <form onSubmit={handleSubmit}>
      {/* Form content */}
    </form>
  );
};
```

#### Async/Await

Always use async/await with error handling:

```typescript
const placeBet = async (amount: number, choice: 0 | 1) => {
  try {
    const txId = await backend.placeBet(amount, choice);
    toast.success('Bet placed successfully!');
    return txId;
  } catch (error) {
    console.error('Failed to place bet:', error);
    toast.error('Failed to place bet');
    throw error;
  }
};
```

### Common Style Rules

**Python**:
- Maximum line length: 100 characters
- Use f-strings for formatting: `f"Hello, {name}"`
- No mutable default arguments: `def func(x: list = None)` (use `None` and default to `[]`)

**TypeScript**:
- Maximum line length: 120 characters
- Use template literals: `` `Hello, ${name}` ``
- Use `const` by default, `let` only if reassignment needed
- Use `===` instead of `==`

---

## Testing

### Backend Tests (Python)

Use **pytest** for backend testing.

#### Running Tests

```bash
cd backend
source venv/bin/activate

# Run all tests
pytest -v

# Run specific test file
pytest tests/test_smart_contract.py -v

# Run specific test function
pytest tests/test_smart_contract.py::test_bet_validation -v

# Run with coverage
pytest --cov=. --cov-report=html
```

#### Writing Tests

```python
import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

def test_place_bet_success():
    """Test placing a bet successfully."""
    response = client.post("/place-bet", json={
        "amount": 1000000000,  # 1 ERG
        "choice": 0
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "txId" in data
    assert data["betAmount"] == 1000000000

@pytest.mark.asyncio
async def test_rng_outcome():
    """Test RNG outcome calculation."""
    from services.rng_module import calculate_outcome
    
    # Given block hash and secret
    block_hash = "abcd1234"
    secret = 42
    
    outcome = await calculate_outcome(block_hash, secret)
    
    # Should return 0 or 1
    assert outcome in [0, 1]
```

### Frontend Tests (TypeScript)

Use **Vitest** for frontend testing.

#### Running Tests

```bash
cd frontend

# Run all tests
npm test

# Run specific test file
npm test BetForm

# Run with coverage
npm test -- --coverage
```

#### Writing Tests

```typescript
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import BetForm from '@/components/BetForm';

describe('BetForm', () => {
  it('should render bet input fields', () => {
    render(<BetForm onBetPlaced={vi.fn()} minBet={0.1} maxBet={10} />);
    
    expect(screen.getByLabelText(/bet amount/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/choice/i)).toBeInTheDocument();
  });

  it('should call onBetPlaced when form is submitted', async () => {
    const onBetPlaced = vi.fn();
    render(<BetForm onBetPlaced={onBetPlaced} minBet={0.1} maxBet={10} />);
    
    const amountInput = screen.getByLabelText(/bet amount/i);
    const submitButton = screen.getByRole('button', { name: /place bet/i });
    
    fireEvent.change(amountInput, { target: { value: '1' } });
    fireEvent.click(submitButton);
    
    await waitFor(() => {
      expect(onBetPlaced).toHaveBeenCalledWith(
        expect.objectContaining({
          amount: 1000000000,
          choice: 0
        })
      );
    });
  });
});
```

### Integration Tests

Integration tests verify end-to-end flows:

```python
# tests/integration/test_full_bet_flow.py
import pytest

def test_full_bet_flow(node_client, backend_api):
    """Test placing and settling a bet end-to-end."""
    # 1. Place bet via API
    bet_response = backend_api.place_bet(amount=1000000000, choice=0)
    assert bet_response["status"] == "pending"
    
    # 2. Find PendingBet box on blockchain
    boxes = node_client.get_unspent_boxes_by_token_id(COINFLIP_NFT_ID)
    pending_box = [b for b in boxes if b["ergoTree"] == PENDING_BET_TREE][0]
    
    # 3. Reveal bet
    reveal_response = backend_api.reveal_bet(
        bet_id=bet_response["betId"],
        secret=12345
    )
    assert reveal_response["status"] == "revealed"
    
    # 4. Check settlement
    # ... verify payout was sent correctly
```

### Test Coverage Goals

- **Backend**: Minimum 80% coverage
- **Frontend**: Minimum 70% coverage
- Critical paths (bet placement, RNG calculation, settlement): 95%+ coverage

---

## Pull Request Process

### Before Submitting

1. **Run tests**: Ensure all tests pass locally
2. **Update documentation**: If your change affects user-facing features
3. **Check style**: Run linters (`flake8` for Python, `eslint` for TypeScript)
4. **Rebase**: Ensure your branch is up to date with `main`

### Creating a Pull Request

1. Push your branch to GitHub
2. Open a PR from your fork to the upstream `main` branch
3. Fill out the PR template

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] All tests pass
- [ ] New tests added
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-reviewed code
- [ ] Added/updated documentation
- [ ] No merge conflicts

## Related Issues
Closes #123
Related to #456
```

### Review Process

1. **Automated checks**: CI runs tests and linters
2. **Code review**: Maintainer reviews your PR
3. **Changes requested**: Address feedback and update PR
4. **Approval**: PR approved and ready to merge
5. **Merge**: Maintainer merges to `main`

### Merge Requirements

- At least one approval from maintainer
- All CI checks passing
- No merge conflicts

---

## Issue Reporting

### Bug Reports

When reporting a bug, include:

1. **Description**: Clear explanation of the issue
2. **Steps to reproduce**: How to trigger the bug
3. **Expected behavior**: What should happen
4. **Actual behavior**: What actually happens
5. **Environment**: Node version, Python version, OS
6. **Logs**: Relevant error logs

**Template**:

```markdown
**Describe the bug**
Bet placed but not showing in history

**To Reproduce**
1. Connect wallet
2. Place bet of 1 ERG
3. Check GameHistory
4. Bet is not listed

**Expected behavior**
Bet should appear in history immediately

**Actual behavior**
History is empty

**Environment**
- Node: v6.0.3
- Python: 3.12.0
- OS: macOS 14.2

**Logs**
```
ERROR: Bet ID not found in database
```
```

### Feature Requests

For new features, include:

1. **Description**: What you want to add
2. **Use case**: Why it's needed
3. **Proposed solution**: How it could work
4. **Alternatives**: Other approaches considered

**Template**:

```markdown
**Is your feature request related to a problem?**
I want to place multiple bets at once for better UX

**Describe the solution you'd like**
Add "Quick Bet" feature to place 3 bets with preset amounts

**Describe alternatives you've considered**
- Manual placement (too slow)
- Betting queue (too complex)

**Additional context**
Would reduce transaction time by 60%
```

---

## Development Tips

### Debugging

**Backend**:
```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug("Debug message: %s", variable)
```

**Frontend**:
```typescript
console.log('Debug:', data);
console.error('Error:', error);
```

### Common Pitfalls

1. **Forgot to rebase**: Always `git rebase upstream/main` before pushing
2. **Missing type hints**: All Python functions need type hints
3. **Silent errors**: Always wrap async code in try/except
4. **Register encoding**: Use proper Sigma-state type tags, not raw hex
5. **Address validation**: `3W` addresses ARE valid on testnet

### Useful Commands

```bash
# Show changed files
git status

# Show recent commits
git log --oneline -10

# Show diff
git diff HEAD~1

# Cherry-pick commit
git cherry-pick <commit-hash>

# Stash changes
git stash save "WIP"
```

---

## Community

- **GitHub Issues**: Report bugs and request features
- **Discussions**: Ask questions and share ideas
- **Ergo Discord**: Chat with other developers

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

## Thank You!

We appreciate your contributions to DuckPools Coinflip! 🚀
