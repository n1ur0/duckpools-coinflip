# DuckPools RNG Threat Model

> **Version:** 1.0
> **Date:** 2026-03-28
> **Author:** Senior Ergo Specialist (Protocol Core)
> **Status:** Draft for Review
> **Issue:** RNG-SEC-1 (#38)
> **Classification:** Security — Protocol Design

---

## 1. Scope

This document provides a standalone threat model for the DuckPools commit-reveal RNG scheme as implemented in `backend/rng_module.py` and enforced by the on-chain `PendingBet` contract.

Cross-references:
- `smart-contracts/SECURITY_AUDIT_PREPARATION.md` — full audit prep with contract-level findings
- `docs/ARCHITECTURE.md` — system architecture and RNG formula
- `sdk/src/crypto/index.ts` — SDK-side RNG implementation

---

## 2. RNG Protocol Specification

### 2.1 Commit Phase

```
Player generates:
  secret:  8 random bytes (crypto.getRandomValues / os.urandom)
  choice:  0 (heads) or 1 (tails)

Player computes:
  commitment = SHA256(secret_bytes || choice_byte)

Player submits on-chain:
  R5 = commitment (32 bytes)
  R6 = choice (Int)
  R7 = secret (Int, 8-byte big-endian)
```

### 2.2 Reveal Phase

```
Bot reads PendingBetBox, verifies:
  SHA256(R7 || R6) == R5

Bot computes outcome:
  rng_data  = blockHash.encode('utf-8') || secret_bytes
  rng_hash  = SHA256(rng_data)
  outcome   = rng_hash[0] % 2

Player wins if outcome == choice.
Payout (win):  bet_amount * 1.94  (3% house edge)
Payout (lose): 0 (bet absorbed by pool)
```

### 2.3 Entropy Budget

| Source | Bits | Distribution | Source of Randomness |
|--------|------|-------------|---------------------|
| Player secret | 64 | Uniform (CSPRNG) | Client-side crypto.getRandomValues |
| Block hash | 256 | Uniform (PoW) | Autolykos v2 proof-of-work |
| Combined (SHA256 output) | 256 | Uniform | Hash of both sources |
| Extracted outcome (first byte % 2) | 1 | Exactly 50/50 | Single bit from hash |

**Note:** Only 1 bit of the 256-bit hash is used for coinflip. This is sufficient for a binary outcome. Dice (0-99) and plinko (multi-zone) use rejection sampling from more hash bytes (see `dice_rng()`).

---

## 3. Threat Actors

| Actor | Capability | Motivation | Access Level |
|-------|-----------|------------|-------------|
| Player | Chooses secret, submits bets | Win money | On-chain transactions |
| House operator (bot) | Constructs reveal/refund txs, signs collect | Earn house edge | Private key, bot access |
| Ergo miner | Selects tx ordering, block nonce, extra data | Block rewards, potential manipulation | Hash power |
| Ergo network | Chain reorgs, consensus rules | Protocol integrity | Social/economic consensus |
| Off-chain bot operator | Constructs reveal/refund txs | Operational reliability | Server access |
| Backend API operator | Serves pool state, bet history | Availability | API keys |
| External attacker | Arbitrary on-chain transactions | Steal funds, exploit | None initially |
| 51% attacker | Reorgs chain, censors transactions | Targeted manipulation | >50% hash power |

---

## 4. Threat Analysis

### T1: Miner Manipulates Block Hash for Favorable Outcome

**Severity:** CRITICAL (theoretical) | **Likelihood:** VERY LOW | **Risk:** ACCEPTABLE

**Description:** A miner could try to find a block hash where `SHA256(blockHash || secret)[0] % 2` produces a desired outcome.

**Analysis:**
- Autolykos v2 requires the block hash to satisfy the difficulty target (current ~10^15)
- Finding a valid block is already finding a needle in a 2^256 haystack
- Additionally constraining the first byte of a SHA256 derivative would require finding a valid block that ALSO satisfies `hash[0] ∈ {even, odd}` — but since valid blocks are already uniformly distributed across the hash space, this doesn't add meaningful work
- **However:** a 51% attacker can mine multiple blocks and discard those with unfavorable outcomes (grinding attack)

**Concrete grinding scenario:**
1. 51% attacker observes PendingBetBox in mempool
2. Reads R7 (secret) — it's stored in plaintext
3. Mines blocks until finding one where `SHA256(blockHash || secret)[0] % 2` favors the house
4. Publishes only the favorable block

**Why this is limited:**
- On Ergo, each block takes ~2 minutes. Mining N blocks to find a favorable one costs N × (block reward + fees)
- For coinflip (50/50), expected blocks to grind = 2. Cost = 2 blocks of mining
- At Ergo's current block reward (~67.5 ERG), grinding cost = ~135 ERG per manipulated bet
- If the bet is smaller than ~135 ERG, grinding is unprofitable
- For large bets, this IS a concern

**Mitigation:** 
- Wait 2-3 confirmations before revealing (reduces reorg probability but doesn't prevent 51% grinding)
- **Recommended for mainnet:** Switch to a multi-party commit-reveal or VRF where the house also commits entropy BEFORE the player's reveal
- **Acceptable for testnet/launch:** Document the grinding threshold and set a max bet amount below the grinding cost

**Status:** ACCEPTED RISK (testnet) | REQUIRES MITIGATION (mainnet)

---

### T2: Player Front-Runs Commit Transaction

**Severity:** LOW | **Likelihood:** VERY LOW | **Risk:** NEGLIGIBLE

**Description:** A player sees a commit in the mempool and tries to extract the choice to front-run.

**Analysis:**
- Commitment = SHA256(secret || choice). SHA256 is preimage-resistant.
- Even knowing the commitment hash, the attacker cannot determine choice (1 bit) without inverting SHA256
- Front-running the commit itself is pointless — the attacker would need to submit their own bet, which is just... placing a bet

**Status:** NOT EXPLOITABLE

---

### T3: House Refuses to Reveal (Liveness Attack)

**Severity:** MEDIUM | **Likelihood:** MEDIUM | **Risk:** MITIGATED

**Description:** The house bot goes offline or deliberately refuses to reveal, trapping player funds.

**Analysis:**
- The PendingBet contract has a timeout refund path (R9 = timeout height)
- After timeout, the player can reclaim their bet via the refund spending path
- The eUTXO model guarantees the box exists until spent

**Concrete values:**
- Current timeout: configurable via contract parameter
- Recommendation: 30 blocks (~60 minutes) — long enough for bot to reveal, short enough to not trap funds

**Status:** MITIGATED by timeout refund

---

### T4: Griefing via Many Small Bets

**Severity:** MEDIUM | **Likelihood:** HIGH | **Risk:** MITIGATED

**Description:** Attacker creates many PendingBetBoxes to waste house liquidity or bot processing time.

**Analysis:**
- Each bet requires real ERG from the attacker (not dust)
- Minimum bet amount (e.g., 0.01 ERG) provides economic disincentive
- Each bet costs transaction fees (~0.001 ERG per input/output)
- If house doesn't reveal, attacker gets refund after timeout — attacker only loses fees
- House liquidity is temporarily locked but not lost

**Mitigation:**
- Minimum bet amount enforced by backend
- Rate limiting on commit submissions
- Bot should prioritize larger bets for reveal

**Status:** MITIGATED by economic cost

---

### T5: Block Reorg During Reveal

**Severity:** HIGH | **Likelihood:** LOW | **Risk:** MITIGATED

**Description:** A chain reorg changes the block hash used for RNG after the reveal transaction is submitted.

**Analysis:**
- The reveal transaction references a specific block ID (via context variables or data inputs)
- If that block gets reorged out, the reveal tx becomes invalid
- The bot must reconstruct the reveal tx with the new block hash
- The outcome changes, but fairness is preserved — neither party chose the block hash

**Ergo-specific context:**
- Ergo has ~2 minute block times
- Shallow reorgs (1-2 blocks) are possible but rare
- Deep reorgs (>4 blocks) are extremely unlikely without 51% attack

**Mitigation:**
- Bot should wait for 2-3 confirmations before constructing reveal tx
- If reveal tx fails due to reorg, reconstruct with current block
- Total delay: ~6 minutes (acceptable for gambling UX)

**Status:** MITIGATED by confirmation depth

---

### T6: Pre-Image Attack on SHA256

**Severity:** CRITICAL | **Likelihood:** THEORETICAL | **Risk:** ACCEPTABLE

**Description:** An attacker finds a pre-image for SHA256, allowing them to forge commitments or predict outcomes.

**Analysis:**
- SHA256 preimage resistance: 2^256 operations (best known attack)
- No practical attacks on SHA256 preimage resistance exist
- Grover's algorithm (quantum) reduces to 2^128 — still infeasible
- NIST SP 800-107 Rev. 1 confirms SHA256 security through 2030+

**Status:** NOT A PRACTICAL CONCERN

---

### T7: Collision Attack on SHA256 (Commitment Forging)

**Severity:** HIGH | **Likelihood:** VERY LOW | **Risk:** ACCEPTABLE

**Description:** An attacker finds two (secret, choice) pairs with the same commitment, then reveals the unfavorable one.

**Analysis:**
- SHA256 collision resistance: 2^128 operations (birthday attack)
- The attacker needs: SHA256(s1 || c1) == SHA256(s2 || c2) where c1 != c2
- 2^128 work is computationally infeasible
- Note: The commitment binds both secret AND choice (9 bytes total), making multi-collision attacks even harder

**Status:** NOT A PRACTICAL CONCERN

---

### T8: Secret Stored in Plaintext (Information Leak)

**Severity:** LOW | **Likelihood:** CERTAIN | **Risk:** ACCEPTED

**Description:** R7 (the player's secret) is stored in plaintext on-chain during the commit phase.

**Analysis:**
- Anyone can read R7 from the PendingBetBox
- Knowing the secret does NOT allow outcome prediction — the outcome depends on the FUTURE block hash
- The secret is only useful for computing the outcome AFTER the reveal block is mined
- At that point, the bot has already computed the outcome

**Sub-threat:** If the secret is known before reveal, and a colluding miner exists (see T1), the grinding attack becomes easier. The miner already has the secret and just needs to grind the block hash.

**Mitigation:** The combined T1 + T8 attack is the main concern. See T1 mitigation.

**Status:** ACCEPTED — information leak is by design, not a vulnerability. Fairness depends on block hash unpredictability, not secret secrecy.

---

### T9: Timing Attack on Block Hash Selection

**Severity:** MEDIUM | **Likelihood:** LOW | **Risk:** MITIGATED

**Description:** The bot has a window between block publication and reveal transaction submission where it could choose NOT to reveal (if outcome favors player).

**Analysis:**
- The bot sees the outcome as soon as the block is mined
- If the bot withholds the reveal for losing bets, players must wait for timeout
- This is a liveness attack, not a fairness attack — the outcome is still fair
- Players get refunded after timeout

**Mitigation:**
- Bot uptime monitoring and SLA
- Public bet queue visibility (players can see if reveals are being processed)
- If bot consistently withholds losing reveals, it's detectable and reputation-damaging

**Status:** MITIGATED by timeout refund + operational monitoring

---

### T10: Replay of Old Commitments

**Severity:** LOW | **Likelihood:** VERY LOW | **Risk:** NOT EXPLOITABLE

**Description:** An attacker replays a previously-used commitment.

**Analysis:**
- The PendingBet NFT is consumed (spent) during reveal or refund
- The eUTXO model ensures each box can only be spent once
- After spending, the box no longer exists
- Creating a new box with the same commitment requires a new transaction and new NFT (impossible — NFT is singleton)

**Status:** NOT EXPLOITABLE — eUTXO prevents replay

---

### T11: Miner Censorship (Withholding Reveal Transactions)

**Severity:** MEDIUM | **Likelihood:** LOW | **Risk:** MITIGATED

**Description:** A miner censors reveal transactions, forcing players into timeout refunds.

**Analysis:**
- If a miner withholds reveals for bets the house would lose, the house avoids paying out
- Players eventually get refunds via timeout path
- This is equivalent to T9 but from a miner instead of the bot
- Ergo's decentralized mining makes sustained censorship unlikely

**Status:** MITIGATED by timeout refund + decentralized mining

---

### T12: Multiple Bets Same Block (Correlation)

**Severity:** LOW | **Likelihood:** HIGH | **Risk:** NEGLIGIBLE

**Description:** Multiple bets revealed in the same block use the same block hash, creating correlated outcomes.

**Analysis:**
- If N bets use the same block hash but different secrets, the outcomes are:
  - `SHA256(blockHash || secret_1)[0] % 2`
  - `SHA256(blockHash || secret_2)[0] % 2`
  - etc.
- SHA256 behaves as a random oracle — different secrets produce independent outputs
- The probability that all N outcomes are the same is 2^(1-N)
- For N=10: P(all heads) = 0.1% — unusual but not suspicious
- This is EXPECTED BEHAVIOR, not a vulnerability

**Status:** NOT A VULNERABILITY — independence is guaranteed by SHA256

---

## 5. Risk Matrix

| ID | Threat | Severity | Likelihood | Risk Level | Mitigation Status |
|----|--------|----------|------------|------------|-------------------|
| T1 | Miner block hash grinding | CRITICAL | VERY LOW | MEDIUM | Accepted (testnet), needs VRF (mainnet) |
| T2 | Player front-runs commit | LOW | VERY LOW | NEGLIGIBLE | Not exploitable |
| T3 | House refuses to reveal | MEDIUM | MEDIUM | MEDIUM | Mitigated (timeout refund) |
| T4 | Griefing (many small bets) | MEDIUM | HIGH | MEDIUM | Mitigated (min bet, fees) |
| T5 | Block reorg during reveal | HIGH | LOW | MEDIUM | Mitigated (confirmation depth) |
| T6 | SHA256 preimage attack | CRITICAL | THEORETICAL | NEGLIGIBLE | Not a practical concern |
| T7 | SHA256 collision (commit forging) | HIGH | VERY LOW | NEGLIGIBLE | Not a practical concern |
| T8 | Secret in plaintext on-chain | LOW | CERTAIN | LOW | Accepted by design |
| T9 | Bot withholds losing reveals | MEDIUM | LOW | LOW | Mitigated (timeout + monitoring) |
| T10 | Replay old commitments | LOW | VERY LOW | NEGLIGIBLE | Not exploitable (eUTXO) |
| T11 | Miner censorship of reveals | MEDIUM | LOW | LOW | Mitigated (timeout + decentralization) |
| T12 | Correlated outcomes same block | LOW | HIGH | NEGLIGIBLE | Not a vulnerability (SHA256 independence) |

---

## 6. Comparison with Industry RNG Approaches

### 6.1 Chainlink VRF (Verifiable Random Function)

| Property | DuckPools (commit-reveal) | Chainlink VRF |
|----------|--------------------------|---------------|
| Randomness source | Block hash + player secret | VRF proof from oracle |
| Verifiability | Anyone can recompute | On-chain VRF verification |
| Miner manipulation | Possible with 51% (T1) | Resistant (VRF is unpredictable) |
| Latency | 2-3 block confirmations | 1-2 block confirmations |
| Cost | No oracle fee | VRF request fee (~$0.10-0.50) |
| Complexity | Simple (SHA256) | Complex (VRF smart contract) |
| Ergo availability | Native | NOT AVAILABLE on Ergo |
| Trust model | Trustless (no oracle) | Trust in Chainlink node operators |

**Verdict:** Chainlink VRF is stronger against miner manipulation but is NOT available on Ergo. Porting it would require a custom VRF implementation, which is itself a significant security undertaking.

### 6.2 drand (Distributed Randomness Beacon)

| Property | DuckPools (commit-reveal) | drand |
|----------|--------------------------|-------|
| Randomness source | Block hash + player secret | Threshold BLS signature from distributed nodes |
| Verifiability | Anyone can recompute | On-chain threshold signature verification |
| Miner manipulation | Possible with 51% | Resistant (independent of blockchain) |
| Latency | 2-3 blocks | Round-dependent (~30s for drand v2) |
| Cost | No oracle fee | Free (public beacon) |
| Ergo availability | Native | Requires oracle/relay integration |
| Trust model | Trustless | Trust in drand committee |

**Verdict:** drand provides stronger fairness guarantees and is free. Integration would require:
1. An oracle that reads the latest drand round and submits it on-chain
2. Smart contract verification of the drand threshold signature
3. This adds an oracle dependency, contradicting DuckPools' trustless design goal

### 6.3 Multi-Party Commit-Reveal (Recommended Mainnet Upgrade)

| Property | DuckPools (current) | Multi-Party C/R |
|----------|---------------------|-----------------|
| Commit phase | Player only | Player + House |
| Reveal phase | Bot reveals with block hash | Both reveal, combine secrets |
| Miner manipulation | Possible (T1) | Resistant — outcome depends on TWO secrets |
| Complexity | Low | Medium |
| Latency | 2-3 blocks | 3-4 blocks (two reveal phases) |
| Trust model | Trustless | Trustless |

**Protocol sketch:**
```
Phase 1: Player commits SHA256(player_secret || choice)
Phase 2: House commits SHA256(house_secret)
Phase 3: Player reveals (player_secret, choice)
Phase 4: House reveals (house_secret)
Phase 5: Outcome = SHA256(blockHash || player_secret || house_secret)[0] % 2
```

**Why this defeats T1:** Even with 51% hash power, the miner doesn't know `house_secret` at the time of mining. Grinding requires knowledge of ALL entropy inputs. The house secret is committed in Phase 2 but not revealed until Phase 4, AFTER the block is finalized.

**Verdict:** This is the RECOMMENDED upgrade path for mainnet. It preserves the trustless model, adds minimal complexity, and eliminates the primary fairness concern (T1).

### 6.4 Commit-Reveal with VDF (Verifiable Delay Function)

| Property | DuckPools (current) | C/R + VDF |
|----------|---------------------|-----------|
| Miner manipulation | Possible (T1) | Further reduced |
| Complexity | Low | High |
| Latency | 2-3 blocks | 2-3 blocks + VDF evaluation time |
| Ergo availability | Native | Requires off-chain VDF computation |

**Verdict:** VDFs add unnecessary complexity for our use case. Multi-party C/R (6.3) is simpler and achieves the same goal.

---

## 7. Recommendations

### 7.1 For Testnet/Launch (Immediate)

1. **Set max bet amount** below mining grinding cost (~100 ERG safety margin)
2. **Set timeout to 30 blocks** (~60 min) for player refund
3. **Bot should wait 2-3 confirmations** before constructing reveal tx
4. **Monitor bot uptime** — alert on missed reveals

### 7.2 For Mainnet (Before Public Launch)

1. **Implement multi-party commit-reveal** (Section 6.3) — house commits entropy BEFORE player reveal
2. **Increase secret size to 32 bytes** for post-quantum readiness (currently 8 bytes — sufficient for binding but larger is future-proof)
3. **Add on-chain outcome verification** — the PendingBet contract should verify `SHA256(blockHash || playerSecret || houseSecret)[0] % 2` instead of relying on off-chain computation
4. **Consider max bet enforcement on-chain** — prevent bets exceeding grinding threshold

### 7.3 Long-Term (Post-Launch)

1. **Monitor Ergo hash rate distribution** — if a single miner approaches 30%+, grinding becomes more feasible
2. **Evaluate drand integration** — if a trustless drand relay becomes available on Ergo
3. **Statistical monitoring** — implement chi-square tests on actual bet outcomes to detect manipulation (tools exist in `rng_module.py`)

---

## 8. Open Questions for Discussion

1. **Multi-party C/R UX impact:** Adding a house commit phase means the player must wait for the house to commit before revealing. How does this affect the betting UX? Can the house pre-commit for a batch of bets?

2. **Block hash source:** Currently using the block where the reveal tx is included. Should we use a specific future block height instead (e.g., "reveal uses block at height H+10")? This would make grinding even harder but increase latency.

3. **Secret size increase:** Moving from 8 to 32 bytes changes the R7 register encoding (Int → Coll[Byte] or Long). This requires a contract update. Is this worth it for the marginal security improvement?

4. **Outcome extraction for dice/plinko:** The current `dice_rng()` uses rejection sampling from hash bytes. Should we use a different extraction method (e.g., HMAC-DRBG) for multi-outcome games?

---

## Appendix A: Formal Security Properties

### P1: Binding (Commitment)
SHA256 is collision-resistant. Given commitment C = SHA256(s || c), finding (s', c') != (s, c) with SHA256(s' || c') = C requires ~2^128 work. **BOUND: 128-bit security.**

### P2: Hiding (Secrecy)
SHA256 is preimage-resistant. Given C = SHA256(s || c), finding any (s, c) requires ~2^256 work. Learning just c (1 bit) is as hard as full preimage. **BOUND: 256-bit security.**

### P3: Unpredictability (RNG Fairness)
Outcome = SHA256(H || s)[0] % 2, where H = block hash. At time of commitment, H is unknown. At time of reveal, H is determined by PoW. An attacker who can influence H is bounded by PoW difficulty. **BOUND: min(256, difficulty) bits of unpredictability.**

### P4: Uniqueness (No Double-Spend)
eUTXO model: each box can be spent exactly once. PendingBet NFT is consumed on spend. **BOUND: Guaranteed by consensus.**

### P5: Fairness (Equal Probability)
SHA256 output is uniformly distributed over {0, ..., 2^256-1}. First byte is uniform over {0, ..., 255}. `byte % 2` is exactly 50/50. **BOUND: Exact fairness (not probabilistic).**

---

## Appendix B: Attack Cost Analysis

### T1 Grinding Cost (Miner Attack)

```
Assumptions:
  Ergo block reward: 67.5 ERG
  Ergo block time: ~120 seconds
  Hash rate to grind one favorable block (coinflip): ~2x normal mining
  Grinding cost per attack: 2 × 67.5 ERG = 135 ERG

Grinding profitability:
  profit = bet_amount × 0.97 - 135 ERG
  profit > 0 when bet_amount > 139 ERG

Recommendation: Max bet = 100 ERG (37% safety margin below grinding threshold)
```

### T3 Liveness Attack Cost (House Withholding)

```
Player cost: 
  - Bet locked for timeout period (30 blocks × 120s = 60 minutes)
  - Opportunity cost of capital
  
House cost:
  - Forfeits reputation
  - Player gets refund (no fund loss to house)
  - If player would have won, house saves payout
  
House incentive to withhold:
  - Only if bet would result in player win AND bet > bot's operational cost
  - Detectable via public blockchain analysis
```
