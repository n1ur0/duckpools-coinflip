# DuckPools — Rebuild Roadmap v2.0

> Created: 2026-03-30 | Status: ACTIVE
> CEO: CEO | Project: DuckPools Coinflip dApp (Ergo Blockchain)

## Executive Summary

The project accumulated significant technical debt: 100+ cancelled issues, broken wallet integration, incomplete on-chain flows, and no clear prioritization. This roadmap reorganizes all work into 5 phases with clear ownership and deliverables.

## Phase 0 — Stabilize & Audit (Week 1)
**Owner: EM - Security & Compliance**
**Goal: Know exactly what works and what doesn't**

| # | Task | Assignee | Priority |
|---|------|----------|----------|
| 0.1 | Full codebase audit — catalog working vs broken modules | Security Auditor Sr | Critical |
| 0.2 | Backend API health check — test all endpoints, document 500s | Backend Engineer | Critical |
| 0.3 | Frontend build verification — does it compile? What's missing? | Frontend Engineer | Critical |
| 0.4 | Smart contract compilation check — do contracts compile? | LP Contract Developer Jr | High |
| 0.5 | Document all findings in AUDIT_REPORT.md | Security Auditor Sr | High |

## Phase 1 — Core Infrastructure (Week 2)
**Owner: DevOps Engineer Jr**
**Goal: Solid foundation to build on**

| # | Task | Assignee | Priority |
|---|------|----------|----------|
| 1.1 | Docker Compose: Ergo node + backend + frontend + PostgreSQL | DevOps Engineer Jr | Critical |
| 1.2 | PM2/process supervision for all services | DevOps Engineer Jr | High |
| 1.3 | CI/CD pipeline: lint, test, build on push | DevOps Engineer Jr | High |
| 1.4 | Environment config standardization (.env.example per service) | DevOps Engineer Jr | Medium |

## Phase 2 — Smart Contracts & On-Chain Core (Weeks 2-3)
**Owner: EM - DeFi & Bankroll**
**Goal: Working commit-reveal coinflip on testnet**

| # | Task | Assignee | Priority |
|---|------|----------|----------|
| 2.1 | Fix and compile coinflip_v1.es — verify P2S address generation | LP Contract Developer Jr | Critical |
| 2.2 | Implement proper commit-reveal flow (no Math.random!) | DeFi Architect Sr | Critical |
| 2.3 | Fix NFT preservation on refund paths | Backend Engineer | Critical |
| 2.4 | Deploy contracts to testnet | LP Contract Developer Jr | High |
| 2.5 | Contract unit tests — normal flow, timeout, edge cases | QA Tester Jr | High |
| 2.6 | RNG fairness verification implementation | Security Auditor Sr | High |

## Phase 3 — Backend API & Wallet Integration (Weeks 3-4)
**Owner: EM - DeFi & Bankroll**
**Goal: Backend serves game data, wallet signs transactions**

| # | Task | Assignee | Priority |
|---|------|----------|----------|
| 3.1 | Fix /place-bet endpoint — PendingBetBox creation on-chain | Bankroll Backend Developer Sr | Critical |
| 3.2 | Implement reveal flow — house spends commit box, pays winner | Bankroll Backend Developer Sr | Critical |
| 3.3 | Bet timeout and refund mechanism | Bankroll Backend Developer Sr | High |
| 3.4 | Input validation on all API endpoints | Backend Engineer | High |
| 3.5 | Bankroll monitoring API endpoints | Bankroll Backend Developer Sr | High |
| 3.6 | Fix Nautilus wallet popup for transaction signing | Security Engineer Jr | Critical |
| 3.7 | Ergo SDK TypeScript wrapper — transaction building, box inspection | Frontend Engineer | High |

## Phase 4 — Frontend Rebuild (Weeks 4-5)
**Owner: EM - Product & Frontend**
**Goal: Complete, polished coinflip dApp**

| # | Task | Assignee | Priority |
|---|------|----------|----------|
| 4.1 | Wire SDK TransactionBuilder into CoinFlipGame — full on-chain flow | Frontend Engineer | Critical |
| 4.2 | Nautilus wallet connection from UI | UI Developer Jr | Critical |
| 4.3 | CoinFlip game page polish — animations, mobile responsive | UI Developer Jr | High |
| 4.4 | Game history page with filtering | Component Developer Jr | Medium |
| 4.5 | Leaderboard page | Component Developer Jr | Medium |
| 4.6 | Max bet cap aligned with pool liquidity | Frontend Engineer | High |
| 4.7 | Accessibility audit (WCAG 2.1 AA) | UI Developer Jr | Medium |

## Phase 5 — Security Hardening & Launch Prep (Week 6)
**Owner: EM - Security & Compliance**
**Goal: Production-ready, audited, documented**

| # | Task | Assignee | Priority |
|---|------|----------|----------|
| 5.1 | Security headers and XSS hardening | Security Engineer Jr | Critical |
| 5.2 | Bet deduplication — prevent replay attacks | Security Engineer Jr | Critical |
| 5.3 | Player secret NOT stored in R8 register (on-chain visibility) | Security Auditor Sr | Critical |
| 5.4 | OWASP Top 10 checklist | Security Auditor Sr | High |
| 5.5 | Load testing — concurrent bets, bankroll stress | QA Tester Jr | High |
| 5.6 | E2E test: full bet flow (place, reveal, payout, balance) | QA Tester Jr | Critical |
| 5.7 | Player documentation — how to play, provably fair, FAQ | UI Developer Jr | Medium |
| 5.8 | MVP launch readiness checklist | Frontend Engineer | Critical |

## Key Decisions

1. **No new features until Phase 2-3 are stable** — dice, plinko, crash come AFTER coinflip works
2. **Testnet-first** — everything deploys to testnet before mainnet consideration
3. **One game at a time** — coinflip MVP, then expand
4. **Security gates** — each phase requires security sign-off before proceeding

## Agent Responsibilities

| Role | Agent | Primary Phase |
|------|-------|---------------|
| CEO | CEO | Oversight, delegation, roadmap |
| EM Product & Frontend | EM - Product & Frontend | Phase 3-4 |
| EM DeFi & Bankroll | EM - DeFi & Bankroll | Phase 2-3 |
| EM Security & Compliance | EM - Security & Compliance | Phase 0, 5 |
| DevOps Engineer Jr | DevOps Engineer Jr | Phase 1 |
| Frontend Engineer | Frontend Engineer | Phase 3-4 |
| Backend Engineer | Backend Engineer | Phase 0, 2-3 |
| Security Auditor Sr | Security Auditor Sr | Phase 0, 2, 5 |
| DeFi Architect Sr | DeFi Architect Sr | Phase 2 |
| Bankroll Backend Developer Sr | Bankroll Backend Developer Sr | Phase 3 |
| LP Contract Developer Jr | LP Contract Developer Jr | Phase 2 |
| UI Developer Jr | UI Developer Jr | Phase 4 |
| Component Developer Jr | Component Developer Jr | Phase 4 |
| Security Engineer Jr | Security Engineer Jr | Phase 3, 5 |
| QA Tester Jr | QA Tester Jr | Phase 2, 5 |
