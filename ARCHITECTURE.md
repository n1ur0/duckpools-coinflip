# DuckPools CoinFlip - Architecture and Security Design

## Overview
DuckPools CoinFlip is a proof-of-concept decentralized gambling application built on the Ergo blockchain using the commit-reveal pattern.

## Commit-Reveal Pattern

### How It Works
1. **Commit Phase**: Player creates a bet by locking ERG in a contract box
   - Player generates a secret (8 bytes, random)
   - Player commits to a choice (heads=0, tails=1)
   - Commitment hash = blake2b256(secret || choice)
   - Box registers (coinflip_v2.es — compiled and deployed):
     - R4: House public key (Coll[Byte], 33-byte compressed PK)
     - R5: Player public key (Coll[Byte], 33-byte compressed PK)
     - R6: Commitment hash (Coll[Byte], blake2b256(secret || choice))
     - R7: Player choice (Int, 0=heads, 1=tails)
     - R8: Timeout height (Int, block height for refund)
     - R9: Player secret (Coll[Byte], 32 random bytes)
     - Note: betId tracked off-chain only. No R10 (Ergo supports R4-R9).

2. **Reveal Phase**: House reveals the outcome
   - House fetches current block hash from node
   - RNG outcome = (block_hash_bytes[0] % 2)
   - House proves fairness by using on-chain block hash
   - Contract verifies: blake2b256(secret || choice) == R6[CommitmentHash]
   - House spends commit box, pays player if they win

3. **Refund Phase**: Player timeout protection
   - If HEIGHT >= R8[TimeoutHeight], player can spend commit box
   - Player receives bet amount minus 2% fee
   - Note: v2_final uses PK-based auth, no NFTs

## Security Considerations (Production vs. PoC)

### Design Trade-Offs for PoC

**1. Player Secret Visible On-Chain (MAT-348)**
- **Issue**: Player secret is stored in R9 register, visible to anyone
- **Impact**: House can peek at player's choice before reveal
- **Trust Assumption**: House is honest about not peeking at R9
- **Production Solution**: Use ZK-proof or commitment scheme where secret is not stored in box

**2. No Payout Amount Enforcement (MAT-336)**
- **Issue**: Contract doesn't verify payout amount during reveal
- **Impact**: Malicious house could underpay player (pay 0 ERG)
- **Trust Assumption**: House is honest and follows payout rules
- **Production Solution**: Add contract guard: OUTPUTS(0).value >= bet_amount * 0.97

**3. Block Hash Selection (MAT-336)**
- **Issue**: House chooses which block height/hash to use for RNG
- **Impact**: House could grind blocks for favorable outcome
- **Trust Assumption**: House uses current block hash without manipulation
- **Production Solution**: Add house commitment (pre-commit to block height) or use oracle

**4. Only House Can Reveal (MAT-336)**
- **Issue**: Player cannot self-reveal if house goes offline
- **Impact**: Player must wait for timeout to claim refund
- **Trust Assumption**: House is always available to reveal
- **Production Solution**: Add player-initiated reveal path with on-chain RNG

### Trust Model for PoC
The DuckPools CoinFlip PoC trusts the house operator to:
- Not peek at player's choice in R9 register
- Pay correct amounts (bet + winnings) during reveal
- Use fair block hash without manipulation
- Be available to reveal bets within timeout window

### Production Security Requirements
For a production system, the following would be needed:
- Zero-knowledge proofs for secret verification
- On-chain payout amount enforcement
- Pre-committed block height or oracle RNG
- Player self-reveal capability
- House commitment to block height before reveal
- Economic stakes for house (security deposit slashed on misbehavior)

## Smart Contract: coinflip_v2_final.es (canonical, deployed)

### Register Layout (R4-R9 only; R10 not supported in ErgoScript Lithos 6.0.3)
| Register | Type | Content |
|----------|------|---------|
| R4 | Coll[Byte] | House compressed public key (33 bytes) |
| R5 | Coll[Byte] | Player compressed public key (33 bytes) |
| R6 | Coll[Byte] | Commitment hash: blake2b256(secret \|\| choice_byte) (32 bytes) |
| R7 | Int | Player choice: 0=heads, 1=tails |
| R8 | Int | Timeout height for refund (~100 blocks from bet) |
| R9 | Coll[Byte] | Player secret (8 random bytes) |

### Derived Values
- `rngBlockHeight = timeoutHeight - 30` (REVEAL_WINDOW constant in contract)
- Reveal window: house can reveal between rngBlockHeight and timeoutHeight

### Guard Clauses
- **Reveal path (house)**: houseProp && commitmentOk && (HEIGHT in reveal window) && correct payout output
- **Refund path (player)**: HEIGHT >= timeoutHeight && playerProp && refund >= 98% of bet
- **Commitment verification**: blake2b256(R9[Secret] ++ Coll(choiceByte)) == R6[CommitmentHash]
- **RNG**: blake2b256(prevBlockHash ++ R9[Secret])[0] % 2

### Spend Paths
1. **House Reveal**: Verifies commitment, checks reveal window, determines outcome via block-hash RNG, pays winner
2. **Player Refund**: After timeout height, player reclaims 98% of bet (2% spam-prevention fee)

### Economics
- House edge: 3% (player gets 1.94x on win instead of 2x)
- Refund fee: 2% (player gets 0.98x on timeout refund)
- Timeout: 100 blocks (~200 minutes on Ergo)
- Reveal window: 30 blocks (~60 minutes, derived as timeoutHeight - 30)

### Legacy Contracts
- `coinflip_v1.es`: NFT-based auth, LEGACY, do NOT deploy. Has compilation issues.
- `coinflip_v2.es`: Early PK-based version, no reveal window. Superseded by v2_final.
- `coinflip_v3.es`: Added R10 (rngBlockHeight) but R10 not supported on Lithos 6.0.3.
- `coinflip_commit_reveal.es`: Duplicate of v2 with different comments.

## Backend Architecture

### Components
- **FastAPI Server**: REST API for game operations
- **Game Routes**: `/place-bet`, `/history/{address}`, `/player/stats/{address}`, `/player/comp/{address}`, `/leaderboard`
- **Off-Chain Bot**: Polls for reveal transactions, updates bet history
- **Oracle**: ERG/USD price feed for liquidity calculations

### Data Flow
```
Player -> Frontend (React) -> Backend API -> Ergo Node
                                   ↓
                            PostgreSQL (off-chain state)
                                   ↓
                          Coin History / Player Stats
```

### Bet Resolution Pipeline
1. Player places bet via `/place-bet` endpoint
2. Bet stored in `_bets` list with status "pending"
3. House off-chain bot monitors blockchain for reveal transactions
4. When reveal tx mined, bot updates bet status to "won" or "lost"
5. Player can fetch updated history via `/history/{address}`

### Current Issue: Bet History Not Updating (MAT-167)
- Symptom: All bets show status="pending" with empty playerAddress
- Root Cause: Off-chain bot not running or not updating bet history
- Fix Required: Verify bot is running and properly updating `_bets` list

## Frontend Architecture

### Tech Stack
- React 18 + TypeScript
- Vite build tool
- Tailwind CSS
- Zustand state management
- @nautilus-js/wallet for EIP-12 integration

### Key Components
- **CoinFlipGame.tsx**: Main game UI
- **BetForm**: Input form for bet amount and choice
- **SimpleBetForm**: Backend wallet mode (no extension required)
- **WalletContext**: Exposes wallet connection and signing

### Wallet Integration
- Nautilus wallet via EIP-12 standard
- `connect()`: Prompt user to connect wallet
- `get_balance()`: Get wallet ERG/token balances
- `sign_tx()`: Sign transaction for commit/reveal/refund
- `submit_tx()`: Broadcast signed transaction to network

### Current Issues
- **MAT-361**: No signTransaction calls from game component
- **MAT-362**: SDK imports not wired into game
- **MAT-103**: Nautilus wallet connection not working from UI

## Security Headers (MAT-196, MAT-326, MAT-337)

### Implemented Headers
- X-Content-Type-Options: nosniff
- X-Frame-Options: SAMEORIGIN
- X-XSS-Protection: 1; mode=block
- Referrer-Policy: strict-origin-when-cross-origin
- Permissions-Policy: geolocation=(), camera=(), microphone=()
- Content-Security-Policy: restrictive (allows unsafe-inline for dev)

### Current Issue (MAT-326)
Security headers not applied to 500 error responses, potentially leaking system information.

### Production Hardening (MAT-337)
- Remove `unsafe-eval` from CSP
- Use nonces instead of `unsafe-inline`
- Remove debug header `X-Security-Middleware`
- Update `connect-src` to include WebSocket and API origins

## RNG Fairness

### Algorithm
blake2b256(prevBlockHash ++ playerSecret)[0] % 2 = outcome (0=heads, 1=tails)

### Statistical Properties (MAT-220)
- Uniform distribution: Expected 50% heads, 50% tails
- Independence: No autocorrelation between consecutive outcomes
- Entropy: Maximum 1 bit per flip

### Current Issue (MAT-349)
Simulation code has redacted `secret_bytes`, making statistical tests invalid.

## Known Bugs

### MAT-167: Bet History Shows All Pending
- 29 bets all show status="pending" with empty playerAddress
- Off-chain bot resolution pipeline not running
- History endpoint returns incomplete data

### MAT-194: Max Bet Exceeds Pool Liquidity
- MAX_BET_NANOERG = 100,000 ERG but pool has only 5.7 ERG
- Dynamic cap needed: max_bet = pool_liquidity * 0.10 (10% safety factor)
- Risk: Player could drain pool 17,000x over if they win

### MAT-350: No Bet Deduplication
- Same betId can be submitted multiple times
- No uniqueness check in `/place-bet` endpoint
- Allows replay attack: inflate stats, game leaderboard

## Testing

### Smart Contract Tests (102 tests, ALL PASSING)
- `smart-contracts/tests/test_coinflip_v2_final.py` — 48 tests: commitment verification, RNG, payout math, reveal/refund paths, reveal window (7 tests), end-to-end flows, edge cases
- `smart-contracts/tests/test_contract_logic.py` — 54 tests: v2 and v3 contract logic, reveal window, NFT preservation notes, edge cases
- Run: `python3 -m pytest smart-contracts/tests/ -v`

### RNG Fairness Verification
- `smart-contracts/rng_fairness_verify.py` — Standalone module: commitment verification, flip computation, statistical fairness (chi-squared, runs test, serial correlation)
- Run: `python3 smart-contracts/rng_fairness_verify.py`
- All statistical tests PASS (uniformity, independence, no autocorrelation)

### E2E Tests
- tests/e2e/coinflip.spec.ts (Frontend coinflip flow)
- tests/e2e/regression.spec.ts (Bug regression tests)

### Coverage Gaps
- No backend API tests for coinflip endpoints (MAT-331)
- No on-chain integration tests (require running Ergo node + sigma-rust)
- No performance tests under load

## Deployment

### Environment Variables
- `NODE_URL`: Ergo node endpoint (http://127.0.0.1:9052 for local dev)
- `VITE_NODE_URL`: Node URL for frontend (http://localhost:9052 for local)
- `NODE_API_KEY`: API key for node (default: "hello")
- `BOT_API_KEY`: API key for bot endpoints

### Docker vs Local
- Local dev: http://127.0.0.1:9052 (node), :8000 (backend), :3000 (frontend)
- Docker: http://host.docker.internal:9052 (node), :8000 (backend), :3000 (frontend)

## Conclusion

DuckPools CoinFlip is a **proof-of-concept**, not a production system. The trust model assumes a honest house operator. For production deployment, the security gaps documented above must be addressed with proper cryptographic guarantees and on-chain enforcement mechanisms.

This playbook documents what was learned:
- ErgoScript smart contract development
- Commit-reveal pattern implementation
- EIP-12 wallet integration
- Off-chain bot architecture for resolution
- Security trade-offs in blockchain game design
