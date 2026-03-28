# DuckPools CoinFlip - Architecture and Security Design

## Overview
DuckPools CoinFlip is a proof-of-concept decentralized gambling application built on the Ergo blockchain using the commit-reveal pattern.

## Commit-Reveal Pattern

### How It Works
1. **Commit Phase**: Player creates a bet by locking ERG in a contract box
   - Player generates a secret (8 bytes, random)
   - Player commits to a choice (heads=0, tails=1)
   - Commitment hash = blake2b256(secret || choice)
   - Box registers:
     - R4: House public key (SigmaProp)
     - R5: Player address (Coll[Byte])
     - R6: Commitment hash (Coll[Byte])
     - R7: Player choice (Int)
     - R8: Player secret (Int)
     - R9: Bet ID (Coll[Byte])
     - R10: Timeout height (Int)

2. **Reveal Phase**: House reveals the outcome
   - House fetches current block hash from node
   - RNG outcome = (block_hash_bytes[0] % 2)
   - House proves fairness by using on-chain block hash
   - Contract verifies: blake2b256(secret || choice) == R6[CommitmentHash]
   - House spends commit box, pays player if they win

3. **Refund Phase**: Player timeout protection
   - If currentHeight > R10[TimeoutHeight], player can spend commit box
   - Player receives bet amount minus 2% fee
   - House reclaims game NFT

## Security Considerations (Production vs. PoC)

### Design Trade-Offs for PoC

**1. Player Secret Visible On-Chain (MAT-348)**
- **Issue**: Player secret is stored in R8 register, visible to anyone
- **Impact**: House can peek at player's choice before reveal
- **Trust Assumption**: House is honest about not peeking at R8
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
- Not peek at player's choice in R8 register
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

## Smart Contract: coinflip_v1.es

### Guard Clauses
- **IsHouse**: INPUTS(0).propositionBytes == R4[HousePubKey]
- **IsPlayer**: INPUTS(0).propositionBytes == R5[PlayerAddress]
- **NFTPreserved**: Game NFT token preserved in spend
- **IsValidReveal**: blake2b256(R8[Secret] || R7[Choice]) == R6[CommitmentHash]
- **IsTimedOut**: currentHeight > R10[TimeoutHeight]
- **RefundValueOk**: OUTPUTS(0).value >= (INPUTS(0).value - (INPUTS(0).value * 2/100))

### Spend Paths
1. **House Reveal**: canReveal (isHouse && nftPreserved && isValidReveal)
2. **Player Refund**: canRefund (isTimedOut && isPlayer && refundValueOk && nftToHouse)

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
SHA-256(commitment || secret || block_hash) → first byte % 2 = outcome (0=heads, 1=tails)

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

### Unit Tests
- backend/tests/test_game_routes.py (incomplete)
- backend/tests/test_rng_module.py (statistical tests)

### E2E Tests
- tests/e2e/coinflip.spec.ts (Frontend coinflip flow)
- tests/e2e/regression.spec.ts (Bug regression tests)

### Coverage Gaps
- No backend API tests for coinflip endpoints (MAT-331)
- No integration tests for full game flow
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
