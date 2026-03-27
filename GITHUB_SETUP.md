# GitHub Repository Setup Guide

This document outlines the process for setting up the DuckPools Coinflip GitHub repository and establishing best practices for ongoing development.

## Overview

The DuckPools Coinflip project is a decentralized gambling protocol on the Ergo blockchain. This guide covers repository initialization, branch management, CI/CD configuration, and contribution workflows.

## Prerequisites

- GitHub account with appropriate permissions
- Git installed locally
- Access to project environment variables and secrets
- Familiarity with Ergo blockchain development

## Repository Initialization

### 1. Create GitHub Repository

```bash
# Step 1: Create empty repository on GitHub
# - Go to https://github.com/organizations/YOUR_ORG/new
# - Repository name: duckpools-coinflip
# - Description: Decentralized coinflip betting protocol on Ergo blockchain
# - Visibility: Public (open source) or Private (during development)
# - Initialize with: README, .gitignore (Python/Node), License (MIT)
# - DO NOT add a .gitignore manually (use the existing one)
```

### 2. Initialize Local Git Repository

```bash
cd /Users/n1ur0/Documents/git/duckpools-coinflip

# Initialize git
git init

# Add all files
git add .

# Initial commit
git commit -m "Initial commit: DuckPools Coinflip MVP

- Frontend: React 18 + TypeScript + Vite
- Backend: FastAPI with 24 endpoints
- Smart contracts: PendingBet, GameState, LP pool
- Off-chain bot for bet resolution
- Docker support
- Comprehensive documentation"
```

### 3. Connect Local to Remote

```bash
# Add remote (replace with actual repo URL)
git remote add origin https://github.com/YOUR_ORG/duckpools-coinflip.git

# Push to main branch
git branch -M main
git push -u origin main
```

## Branch Protection Rules

### Main Branch Protection

Settings → Branches → Add rule: `main`

**Required settings:**

- [x] Require a pull request before merging
- [x] Require approvals: 1
- [x] Dismiss stale PR approvals when new commits are pushed
- [x] Require review from CODEOWNERS
- [x] Require branches to be up to date before merging
- [x] Require status checks to pass before merging
  - [ ] lint-frontend
  - [ ] lint-backend
  - [ ] test-backend
  - [ ] test-frontend
- [ ] Do not allow bypassing the above settings
- [x] Require linear history
- [ ] Restrict who can push to matching branches (optional for main)

### Development Branch Protection

Settings → Branches → Add rule: `dev`

**Required settings:**

- [x] Require a pull request before merging
- [ ] Require approvals: 1 (optional)
- [x] Require status checks to pass before merging
  - [ ] lint-backend
  - [ ] test-backend
- [x] Require linear history

## Branch Strategy

### Standard Branches

```
main        # Production-ready, tagged releases only
dev         # Integration branch for feature development
feature/*   # Feature branches (e.g., feature/lp-pool, feature/oracle-integration)
fix/*       # Bugfix branches (e.g., fix/rng-calculation, fix/nautilus-signing)
hotfix/*    # Emergency production fixes (bypass dev)
release/*   # Release preparation (e.g., release/v1.0.0)
```

### Workflow

1. **Feature Development:**
   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b feature/your-feature-name
   # ... work on feature ...
   git push origin feature/your-feature-name
   # Create PR to dev
   ```

2. **Release Process:**
   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b release/v1.0.0
   # ... update version, CHANGELOG.md ...
   git push origin release/v1.0.0
   # Create PR to main (with approval + checks)
   # Merge to main
   git checkout main
   git pull origin main
   git tag -a v1.0.0 -m "Release v1.0.0: Coinflip MVP"
   git push origin v1.0.0
   # Merge main back to dev
   git checkout dev
   git merge main
   git push origin dev
   ```

3. **Hotfix Process:**
   ```bash
   git checkout main
   git pull origin main
   git checkout -b hotfix/critical-fix
   # ... fix the bug ...
   git push origin hotfix/critical-fix
   # Create PR to main (fast-track approval)
   # Merge to main, tag release
   # Merge main back to dev
   ```

## GitHub Actions CI/CD

### Workflow Files Location

```
.github/
├── workflows/
│   ├── lint-frontend.yml
│   ├── lint-backend.yml
│   ├── test-backend.yml
│   ├── test-frontend.yml
│   ├── deploy-mainnet.yml
│   └── deploy-testnet.yml
└── dependabot.yml
```

### Example: Backend Lint Workflow

```yaml
# .github/workflows/lint-backend.yml
name: Lint Backend

on:
  push:
    branches: [main, dev, feature/*, fix/*]
  pull_request:
    branches: [main, dev]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install flake8 mypy black

      - name: Run flake8
        run: |
          cd backend
          flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
          flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

      - name: Run mypy
        run: |
          cd backend
          mypy --ignore-missing-imports .

      - name: Run black check
        run: |
          cd backend
          black --check .
```

### Example: Frontend Lint Workflow

```yaml
# .github/workflows/lint-frontend.yml
name: Lint Frontend

on:
  push:
    branches: [main, dev, feature/*, fix/*]
  pull_request:
    branches: [main, dev]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: |
          cd frontend
          npm ci

      - name: Run ESLint
        run: |
          cd frontend
          npm run lint

      - name: TypeScript check
        run: |
          cd frontend
          npx tsc --noEmit
```

### Example: Backend Test Workflow

```yaml
# .github/workflows/test-backend.yml
name: Test Backend

on:
  push:
    branches: [main, dev]
  pull_request:
    branches: [main, dev]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      ergo-node:
        image: ergoplatform/ergo:latest
        ports:
          - 9052:9052
        env:
          - ergo.network=testnet

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt

      - name: Run tests
        run: |
          cd backend
          python -m pytest tests/ -v --cov=. --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./backend/coverage.xml
```

### Dependabot Configuration

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/backend"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10
    groups:
      dependencies:
        patterns:
          - "*"

  - package-ecosystem: "npm"
    directory: "/frontend"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10
    groups:
      dependencies:
        patterns:
          - "*"
```

## Repository Secrets

### Required Secrets (Settings → Secrets and variables → Actions)

| Secret Name | Description | Example |
|------------|-------------|---------|
| `NODE_URL` | Ergo node REST API URL | `https://ergo-node.example.com` |
| `TESTNET_NODE_URL` | Testnet node URL | `https://testnet.ergoplatform.com` |
| `HOUSE_ADDRESS` | House wallet address | `3Wy...` |
| `COINFLIP_NFT_ID` | Coinflip NFT token ID | `b0a...` |
| `API_KEY` | Node API key | `hello` |
| `EXPLORER_API_KEY` | Ergo explorer API key (optional) | `xxx` |

### Environment-Specific Secrets

For deployments, use environment-specific secrets:
- `PROD_*` for mainnet
- `STAGING_*` for testnet
- `DEV_*` for development

## Issues and Project Management

### Issue Labels

Settings → Labels → Create custom labels:

| Label | Color | Description |
|-------|-------|-------------|
| `bug` | #ef4444 | Software bug |
| `enhancement` | #a855f7 | Feature request |
| `documentation` | #06b6d4 | Documentation update |
| `good first issue` | #7c3aed | Easy starter issue |
| `help wanted` | #f59e0b | Community contributions welcome |
| `priority: critical` | #dc2626 | Urgent fix needed |
| `priority: high` | #ea580c | High priority |
| `priority: medium` | #eab308 | Medium priority |
| `priority: low` | #84cc16 | Low priority |
| `security` | #b91c1c | Security vulnerability |
| `phase-1-mvp` | #3b82f6 | MVP phase task |
| `phase-2-growth` | #8b5cf6 | Growth phase task |
| `phase-3-protocol` | #ec4899 | Protocol phase task |
| `type-engineering` | #f59e0b | Engineering task |
| `type-design` | #a855f7 | Design task |
| `type-operations` | #10b981 | Operations task |
| `type-marketing` | #06b6d4 | Marketing task |
| `type-security` | #ef4444 | Security task |

### Issue Templates

Create `.github/ISSUE_TEMPLATE/` directory:

**bug_report.md:**
```markdown
---
name: Bug report
about: Create a report to help us improve
title: '[BUG] '
labels: bug
---

## Describe the bug
A clear and concise description of what the bug is.

## Steps to reproduce
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

## Expected behavior
A clear and concise description of what you expected to happen.

## Screenshots
If applicable, add screenshots to help explain your problem.

## Environment
- OS: [e.g. macOS 14.5]
- Node version: [e.g. v20.11.0]
- Browser: [e.g. Chrome 123]
- Wallet: [e.g. Nautilus 2.4.0]

## Additional context
Add any other context about the problem here.
```

**feature_request.md:**
```markdown
---
name: Feature request
about: Suggest an idea for this project
title: '[FEAT] '
labels: enhancement
---

## Is your feature request related to a problem?
A clear and concise description of what the problem is.

## Describe the solution you'd like
A clear and concise description of what you want to happen.

## Describe alternatives you've considered
A clear and concise description of any alternative solutions or features you've considered.

## Additional context
Add any other context or screenshots about the feature request here.
```

### Pull Request Templates

Create `.github/PULL_REQUEST_TEMPLATE.md`:

```markdown
## Description
Brief description of changes made in this PR.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Related Issues
Fixes #(issue number)
Closes #(issue number)
Relates to #(issue number)

## How Has This Been Tested?
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing on testnet
- [ ] Manual testing with Nautilus wallet

## Checklist
- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review of my code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have updated the documentation accordingly
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally
- [ ] Any dependent changes have been merged and published
```

## CODEOWNERS

Create `.github/CODEOWNERS`:

```
# Default: All files not covered below
* @ducks

# Backend
backend/ @backend-team
backend/services/ @backend-team
backend/models/ @backend-team

# Frontend
frontend/ @frontend-team
frontend/src/ @frontend-team

# Smart Contracts
smart-contracts/ @contracts-team

# Documentation
docs/ @documentation-team
*.md @documentation-team

# Security vulnerabilities
SECURITY.md @security-team
```

## Security Policy

Create `SECURITY.md`:

```markdown
# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| v1.0.x  | ✅ |
| < v1.0  | ❌ |

## Reporting a Vulnerability

If you discover a security vulnerability, please **DO NOT** open a public issue.

Instead, send an email to: security@duckpools.io

Include:
- Description of the vulnerability
- Steps to reproduce
- Impact assessment
- Proposed fix (if available)

Response time: Within 48 hours

## Bug Bounty Program

We offer rewards for responsible disclosure of security vulnerabilities:

| Severity | Reward |
|----------|--------|
| Critical | Up to $5,000 |
| High     | Up to $2,000 |
| Medium   | Up to $500 |
| Low      | Up to $100 |

## Security Best Practices

1. **Never commit secrets** to the repository
2. Use environment variables for all sensitive data
3. Enable branch protection on main
4. Require code review for all changes
5. Regular dependency updates via Dependabot
6. Audit smart contracts before deployment
7. Monitor on-chain activity for anomalies
```

## Release Management

### Semantic Versioning

- **MAJOR**: Incompatible API changes, protocol-breaking changes
- **MINOR**: Backwards-compatible functionality additions
- **PATCH**: Backwards-compatible bug fixes

### Changelog

Maintain `CHANGELOG.md`:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- LP pool withdrawal cooldown mechanism
- Player statistics dashboard

### Changed
- Improved RNG verification on reveal

### Fixed
- Fixed Nautilus wallet signing for large bet amounts

## [1.0.0] - 2026-03-27

### Added
- Initial MVP release
- Coinflip smart contracts
- Nautilus wallet integration
- Off-chain bet resolution bot
- Backend API with 24 endpoints
- React frontend

### Changed
- Migrated from manual to automated bet resolution
```

## Next Steps After Setup

1. **Invite team members** to the repository
2. **Set up GitHub Pages** for documentation site (optional)
3. **Configure status badges** in README.md
4. **Set up GitHub Discussions** for community Q&A
5. **Enable GitHub Actions** for CI/CD
6. **Create first feature branch** from dev
7. **Set up automated release notes** via semantic-release (optional)

## Maintenance Tasks

### Weekly
- Review and merge Dependabot PRs
- Check for stale issues
- Review open PRs

### Monthly
- Review and update documentation
- Audit security vulnerabilities
- Check CI/CD pipeline health
- Review branch protection rules

### Quarterly
- Review and update dependencies
- Conduct security audit of smart contracts
- Review team permissions
- Update contribution guidelines

## Resources

- [GitHub Documentation](https://docs.github.com/)
- [Ergo Documentation](https://ergoplatform.org/en/)
- [Contributing Guide](CONTRIBUTING.md)
- [Architecture Docs](ARCHITECTURE.md)

## Support

For issues or questions about repository setup, contact:
- GitHub Administrator: [Admin Name] - admin@duckpools.io
- DevOps Team: devops@duckpools.io
