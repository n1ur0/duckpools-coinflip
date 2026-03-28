# DuckPools LP Staking Contract Design

**Document version:** 1.0
**Author:** LP Contract Developer Jr
**Issue:** Build LP token stake/unstake ErgoTree contract with yield distribution logic
**Last updated:** 2026-03-27

---

## 1. Overview

A staking mechanism for LP token holders where they can lock their LP tokens to earn additional yield. This incentivizes long-term liquidity provision and reduces withdrawal frequency.

**Key Concepts:**
- **Staking:** Lock LP tokens in a staking contract to earn rewards
- **Yield:** Rewards distributed to stakers (could be ERG, protocol tokens, or reward tokens)
- **Unstaking:** Withdraw staked LP tokens + accumulated rewards

## 2. Architecture

### Single-Contract Staking Pool Design

```
┌──────────────────────────┐
│  StakingPool Box         │
│  ─────────────────────   │
│  ERG: rewards reserve    │
│  Tokens:                 │
│    0: Staking NFT (1)    │
│    1: LP Token (staked)  │
│  R4: LP Token ID         │
│  R5: Reward Token ID     │
│  R6: Reward per share    │
│  R7: Last update height  │
└──────────────────────────┘
      │
      ├── Stake: User sends LP tokens → gets staked
      ├── Unstake: User burns staking position → gets LP tokens + rewards
      └── Distribute: House deposits rewards
```

## 3. Smart Contract: StakingPool

### Registers

| Register | Type        | Content                                    |
|----------|-------------|--------------------------------------------|
| R4       | Coll[Byte]  | LP Token ID (32 bytes)                     |
| R5       | Coll[Byte]  | Reward Token ID (32 bytes, or empty for ERG)|
| R6       | Long        | Accumulated reward per LP share (scaled)   |
| R7       | Int         | Last update height                         |

### Tokens

| Index | Token       | Description                               |
|-------|-------------|-------------------------------------------|
| 0     | Staking NFT | Singleton NFT identifying staking pool     |
| 1     | LP Token    | Staked LP tokens (total staked amount)    |

### Spending Paths

#### 1. Stake (any LP holder)

```
Conditions:
- Staking NFT preserved in output
- LP token amount increases (more tokens staked)
- Output preserves R4, R5, R7 (config unchanged)
- R6 updated: reward per share recalculated
```

#### 2. Unstake (LP holder, after optional lock period)

```
Conditions:
- Staking NFT preserved in output
- LP token amount decreases (tokens unstaked)
- LP holder receives their LP tokens back
- LP holder receives proportional reward share
- R6 updated: reward per share recalculated
```

#### 3. Reward Distribution (house only)

```
Conditions:
- Staking NFT preserved in output
- LP token supply unchanged
- Rewards ERG (or reward tokens) added to pool
- R6 updated: reward per share increases
- R7 updated: last update height set to current height
- proveDlog(house signature)
```

### ErgoScript Contract

```ergoscript
{
  // StakingPool Singleton Contract
  //
  // Tokens(0) = Staking NFT (singleton, 1 unit)
  // Tokens(1) = LP Token (staked amount)
  //
  // R4: Coll[Byte] - LP Token ID (32 bytes)
  // R5: Coll[Byte] - Reward Token ID (32 bytes, or empty = ERG)
  // R6: Long       - Accumulated reward per share (scaled by 1e12)
  // R7: Int        - Last update height

  val stakingNFT = SELF.tokens(0)._1
  val lpTokenId = SELF.R4[Coll[Byte]].get
  val selfStakedAmount = SELF.tokens(1)._2
  val rewardTokenId = SELF.R5[Coll[Byte]].get
  val selfRewardPerShare = SELF.R6[Long].get
  val lastUpdateHeight = SELF.R7[Int].get

  // Find the output that continues this contract
  val poolOut = OUTPUTS.find { (b: Box) =>
    b.tokens.size >= 2 &&
    b.tokens(0)._1 == stakingNFT &&
    b.propositionBytes == SELF.propositionBytes
  }.get

  val outStakedAmount = poolOut.tokens(1)._2
  val outRewardPerShare = poolOut.R6[Long].get
  val stakedDelta = outStakedAmount - selfStakedAmount

  // --- Path 1: Stake (more LP tokens locked) ---
  val isStake = stakedDelta > 0L &&
    poolOut.R4[Coll[Byte]].get == SELF.R4[Coll[Byte]].get &&
    poolOut.R5[Coll[Byte]].get == SELF.R5[Coll[Byte]].get &&
    poolOut.R7[Int].get == lastUpdateHeight  // height unchanged on stake

  // --- Path 2: Unstake (LP tokens released + rewards) ---
  // User gets their LP tokens back + proportional rewards
  val isUnstake = stakedDelta < 0L &&
    poolOut.R4[Coll[Byte]].get == SELF.R4[Coll[Byte]].get &&
    poolOut.R5[Coll[Byte]].get == SELF.R5[Coll[Byte]].get &&
    outStakedAmount >= 0L

  // --- Path 3: Distribute Rewards (house only) ---
  // Rewards added, reward per share increases, height updated
  val isDistribute = stakedDelta == 0L &&
    poolOut.value > SELF.value &&              // ERG increased (if ERG rewards)
    poolOut.R4[Coll[Byte]].get == SELF.R4[Coll[Byte]].get &&
    poolOut.R5[Coll[Byte]].get == SELF.R5[Coll[Byte]].get &&
    poolOut.R7[Int].get >= lastUpdateHeight  // height can increase
    // proveDlog(housePk)  // Add house signature here

  isStake || isUnstake || isDistribute
}
```

## 4. User Position Management

### Staking Position Box

Each staker has their own position box tracking their stake:

```
┌──────────────────────────┐
│  StakingPosition        │
│  ─────────────────────   │
│  Tokens:                 │
│    0: LP Token (staked)  │
│  R4: Holder ErgoTree     │
│  R5: Reward debt         │
│  R6: Creation height     │
└──────────────────────────┘
```

**Reward Calculation:**
```
userReward = (newRewardPerShare - oldRewardPerShare) * stakedAmount
rewardDebt = oldRewardPerShare * stakedAmount
accumulatedReward = currentRewardDebt - oldRewardDebt
```

## 5. Price and Yield Calculations

### Reward Per Share (off-chain)

```
totalRewards = pool.rewardsERG + pool.rewardsTokens
rewardPerShare = totalRewards / totalStakedLP * SCALING_FACTOR (1e12)
```

### APY Calculation

```
dailyRewardsPerLP = rewardPerShare / SCALING_FACTOR * blocksPerDay / currentBlockHeight
apy = dailyRewardsPerLP * 365 / lpPricePerShare
```

## 6. Transaction Flows

### Stake Flow

```
User → Backend: POST /stake { lpAmount, address }
Backend:
  1. Query StakingPool state (reward per share)
  2. Calculate: rewardDebt = rewardPerShare * lpAmount
  3. Build tx: [userInput(LP tokens), stakingPool] →
     [poolOut(more LP, updated R6), positionBox(LP, rewardDebt)]
  4. Submit
User → Position box created (track staked amount + reward debt)
```

### Unstake Flow

```
User → Backend: POST /unstake { positionBoxId }
Backend:
  1. Query position and pool state
  2. Calculate: pendingReward = (currentRewardPerShare - rewardDebt) * stakedAmount
  3. Build tx: [positionBox, stakingPool] →
     [poolOut(less LP, updated R6), userOut(LP + rewards)]
  4. Submit
User → Gets LP tokens + rewards
```

### Reward Distribution Flow

```
Bot/House → Scheduled task
Backend:
  1. Calculate rewards from house edge/fees
  2. Build tx: [stakingPool] → [poolOut(more rewards, updated R6, R7)]
  3. Submit
All stakers → Reward per share increases
```

## 7. Backend API

### New Endpoints

| Method | Path                  | Description                    |
|--------|-----------------------|--------------------------------|
| GET    | `/stake/pool`         | Staking pool state (TVL, APY)   |
| GET    | `/stake/balance/{addr}`| Staked balance for address    |
| GET    | `/stake/rewards/{addr}`| Pending rewards for address   |
| GET    | `/stake/apy`          | Current staking APY            |
| POST   | `/stake`              | Build stake transaction        |
| POST   | `/unstake`            | Build unstake transaction      |
| POST   | `/claim`              | Claim rewards (without unstake)|

## 8. Yield Distribution Strategy

### Option 1: ERG Rewards (Simple)

Rewards are ERG taken from a portion of house edge profits.
- **Pros:** Simple, no additional token needed
- **Cons:** dilutes pool value, complexity in separating from LP pool

### Option 2: Protocol Token Rewards (Standard)

Mint/burn a separate reward token (e.g., DUCKS) for staking rewards.
- **Pros:** Clear separation, tokenomics potential
- **Cons:** Requires token deployment

### Option 3: Compounding LP Rewards (Advanced)

Rewards are minted as additional LP tokens, compounding stakers' share of the LP pool.
- **Pros:** Aligns staker incentives with pool growth, auto-compounding
- **Cons:** Complex, dilutes non-staked LP holders

**Recommendation:** Start with Option 2 (Protocol Token Rewards) for clean separation and future tokenomics flexibility.

## 9. Security Considerations

1. **No reentrancy:** eUTXO model prevents this naturally
2. **Math overflow protection:** Use 128-bit or scaled integers
3. **Minimum stake amount:** Prevent dust spam
4. **Unstaking cooldown:** Optional, prevents reward farming abuse
5. **Reward debt tracking:** Ensures users only earn rewards after staking
6. **House-only reward distribution:** Only house can add rewards

## 10. Future Enhancements

1. **Vesting schedules:** Rewards unlock over time (incentivize long-term staking)
2. **Tiered rewards:** Higher APY for longer lock periods
3. **Multi-token rewards:** Support multiple reward tokens
4. **Yield boosting:** Boost rewards based on other protocol activities
5. **Governance voting:** Staked LP tokens = voting power
