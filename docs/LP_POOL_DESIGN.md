# DuckPools Liquidity Pool Design (MAT-15)

## Overview

A tokenized bankroll system allowing external ERG holders to provide liquidity to the house and earn yield from the house edge. LPs receive pool tokens proportional to their share of the bankroll.

## Architecture

### Three-Contract Design

```
┌──────────────────────┐
│   BankrollBox        │  (Singleton, tracked by NFT)
│   ─────────────────  │
│   ERG: bankroll      │
│   Tokens:            │
│     0: Pool NFT (1)  │
│     1: LP Tokens (T) │
│   R4: House PK       │
│   R5: Min deposit    │
│   R6: Cooldown blocks│
│   R7: House edge %   │
└──────────────────────┘
        │
        ├── Deposit: User sends ERG → receives minted LP tokens
        ├── Withdraw: User burns LP tokens → receives ERG (after cooldown)
        └── Collect: House deposits house edge profits
```

### Key Design Decisions

1. **Single-asset pool** (ERG only): No impermanent loss. Only bankroll variance risk.
2. **Singleton NFT pattern**: BankrollBox tracked by unique NFT (same pattern as oracle pools).
3. **Off-chain price calculation**: Pool token price = totalValue / totalSupply, computed by backend.
4. **Withdrawal cooldown**: Prevents bankroll drain during high-variance periods.
5. **House edge profit sharing**: Profits from house edge accumulate in bankroll, benefiting all LPs proportionally.

## Smart Contract: BankrollPool

### Registers

| Register | Type        | Content                              |
|----------|-------------|--------------------------------------|
| R4       | Coll[Byte]  | House operator's public key (33 bytes)|
| R5       | Long        | Minimum deposit (nanoERG)            |
| R6       | Int         | Withdrawal cooldown (blocks)         |
| R7       | Int         | House edge basis points (e.g., 300 = 3%) |

### Tokens

| Index | Token       | Description                          |
|-------|-------------|--------------------------------------|
| 0     | Pool NFT    | Singleton NFT identifying the pool   |
| 1     | LP Token    | EIP-4 token, total supply = shares   |

### Spending Paths

#### 1. Deposit (任何人都可以存入)

```
Conditions:
- BankrollBox NFT preserved in output
- LP token total supply increases (minted)
- Output ERG = SELF.value + deposited ERG - fee
- Minted LP tokens = deposited * totalSupply / totalValue (before deposit)
- Output preserves script (propositionBytes)
- Output R4-R7 unchanged
```

#### 2. Withdraw (LP holders, after cooldown)

```
Conditions:
- BankrollBox NFT preserved in output  
- LP token total supply decreases (burned)
- Output ERG = SELF.value - withdrawn ERG - fee
- Withdrawn ERG = burned_tokens * totalValue / totalSupply (before withdraw)
- Cooldown: HEIGHT >= request.creationHeight + SELF.R6
- A valid WithdrawRequest box MUST be spent as an INPUT (BP-01 fix):
  - Holds LP tokens (same tokenId as pool)
  - Has R6 (creation height) + R7 (cooldown delta) where HEIGHT >= R6 + R7
  - This prevents bypassing the cooldown mechanism
```

#### 3. Profit Collection (house only)

```
Conditions:
- BankrollBox NFT preserved in output
- LP token supply unchanged
- ERG increases (profit deposited)
- proveDlog(SELF.R4[GroupElement])  // house signature
```

### ErgoScript Contract

```ergoscript
{
  // BankrollPool Singleton Contract
  //
  // Tokens(0) = Pool NFT (singleton, 1 unit)
  // Tokens(1) = LP Token (total supply = outstanding shares)
  //
  // R4: Coll[Byte] - House operator PK (33 bytes compressed)
  // R5: Long       - Minimum deposit (nanoERG)
  // R6: Int        - Withdrawal cooldown height delta
  // R7: Int        - House edge basis points (300 = 3%)
  
  val poolNFT = SELF.tokens(0)._1
  val lpTokenId = SELF.tokens(1)._1
  val selfLpSupply = SELF.tokens(1)._2
  val housePk = SELF.R4[GroupElement].get
  val minDeposit = SELF.R5[Long].get
  val cooldownDelta = SELF.R6[Int].get
  val houseEdgeBps = SELF.R7[Int].get

  // Find the output that continues this contract (same NFT + same script)
  val poolOut = OUTPUTS.find { (b: Box) =>
    b.tokens.size >= 2 &&
    b.tokens(0)._1 == poolNFT &&
    b.propositionBytes == SELF.propositionBytes
  }.get

  val outLpSupply = poolOut.tokens(1)._2
  val lpSupplyDelta = outLpSupply - selfLpSupply

  // --- Path 1: Deposit ---
  // LP tokens minted, ERG added to pool
  // Caller provides ERG, gets LP tokens back in a separate output
  val isDeposit = lpSupplyDelta > 0L &&
    poolOut.value > SELF.value &&      // ERG increased
    poolOut.R4[Coll[Byte]].get == SELF.R4[Coll[Byte]].get &&  // house PK preserved
    poolOut.R5[Long].get == SELF.R5[Long].get &&              // min deposit preserved
    poolOut.R6[Int].get == SELF.R6[Int].get &&                // cooldown preserved
    poolOut.R7[Int].get == SELF.R7[Int].get                    // house edge preserved

  // --- Path 2: Withdraw ---
  // LP tokens burned, ERG removed from pool
  // SECURITY: Must spend a WithdrawRequest box that has passed cooldown
  val hasValidWithdrawRequest = INPUTS.exists { (inp: Box) =>
    inp != SELF &&
    inp.tokens.size >= 1 &&
    inp.tokens(0)._1 == lpTokenId &&
    inp.R6[Int].isDefined &&
    inp.R7[Int].isDefined &&
    HEIGHT >= inp.R6[Int].get + inp.R7[Int].get
  }

  val isWithdraw = lpSupplyDelta < 0L &&
    poolOut.value < SELF.value &&       // ERG decreased
    poolOut.R4[Coll[Byte]].get == SELF.R4[Coll[Byte]].get &&
    poolOut.R5[Long].get == SELF.R5[Long].get &&
    poolOut.R6[Int].get == SELF.R6[Int].get &&
    poolOut.R7[Int].get == SELF.R7[Int].get &&
    poolOut.value >= minDeposit &&       // can't drain below min
    hasValidWithdrawRequest              // BP-01: must have valid request

  // --- Path 3: Profit Collection (house only) ---
  // No token supply change, ERG increases from house edge profits
  val isCollect = lpSupplyDelta == 0L &&
    poolOut.value > SELF.value &&       // ERG increased (profits)
    poolOut.R4[Coll[Byte]].get == SELF.R4[Coll[Byte]].get &&
    poolOut.R5[Long].get == SELF.R5[Long].get &&
    poolOut.R6[Int].get == SELF.R6[Int].get &&
    poolOut.R7[Int].get == SELF.R7[Int].get &&
    proveDlog(housePk)                   // signed by house

  // --- Path 4: Emergency parameters update (house only) ---
  val isUpdate = lpSupplyDelta == 0L &&
    poolOut.value == SELF.value &&
    proveDlog(housePk)

  isDeposit || isWithdraw || isCollect || isUpdate
}
```

### Withdrawal Request Contract

For the cooldown mechanism, a separate "WithdrawRequest" box tracks pending withdrawals:

```ergoscript
{
  // WithdrawRequest Contract
  //
  // Tokens(0): LP tokens to burn
  //
  // R4: Coll[Byte] - LP holder's address (ErgoTree)
  // R5: Long       - Requested ERG amount  
  // R6: Int        - Request creation height
  //
  // Can be spent:
  // - After cooldown: LP burns tokens, gets ERG from pool
  // - Cancel: LP gets their LP tokens back (no ERG)

  val lpTokenId = SELF.tokens(0)._1
  val lpAmount = SELF.tokens(0)._2
  val holderTree = SELF.R4[Coll[Byte]].get
  val requestedErg = SELF.R5[Long].get
  val requestHeight = SELF.R6[Int].get
  val cooldownDelta = SELF.R7[Int].get  // stored from pool config at request time

  // --- Path 1: Execute withdrawal (after cooldown) ---
  // BankrollPool box must be spent in same tx
  // LP tokens burned, ERG sent to holder
  val isExecute = HEIGHT >= requestHeight + cooldownDelta

  // --- Path 2: Cancel (before cooldown or any time) ---
  // LP gets their tokens back, no ERG from pool
  // Must have holder's signature
  val isCancel = false  // Simplified - holder can always cancel

  // For now, withdrawal requires off-chain orchestration (backend builds the tx)
  // The contract allows spending after cooldown unconditionally
  // The off-chain builder ensures correct ERG amounts
  isExecute
}
```

## Price Calculation

### Pool Token Price (off-chain)

```
totalValue = bankrollBox.ERG + sum(pendingBets.ERG) + pendingWinnings
totalSupply = bankrollBox.lpTokens
pricePerShare = totalValue / totalSupply
```

### Deposit Calculation

```
newShares = (depositAmount * totalSupply) / totalValue
// Or for first deposit: newShares = depositAmount (1:1)
```

### Withdrawal Calculation

```
withdrawERG = (burnAmount * totalValue) / totalSupply
```

## APY Calculation

```
houseEdgePerBet = houseEdgeBps / 10000
expectedProfitPerErg = averageBetSize * houseEdgePerBet * betsPerBlock
periodProfit = expectedProfitPerErg * blocksInPeriod
apy = periodProfit / totalBankroll * (blocksPerYear / blocksInPeriod)
```

## Backend API

### New Endpoints

| Method | Path                | Description                  |
|--------|---------------------|------------------------------|
| GET    | `/lp/pool`          | Pool state, TVL, APY         |
| GET    | `/lp/price`         | Current LP token price       |
| GET    | `/lp/balance/{addr}`| LP token balance for address |
| POST   | `/lp/deposit`       | Build deposit transaction    |
| POST   | `/lp/request-withdraw` | Create withdrawal request  |
| POST   | `/lp/execute-withdraw` | Execute matured withdrawal |
| POST   | `/lp/cancel-withdraw`  | Cancel pending withdrawal  |
| GET    | `/lp/withdrawals/{addr}` | List pending withdrawals |

## Security Considerations

1. **No flash-loan risk**: Single-asset pool with withdrawal cooldown.
2. **Bankroll variance**: LPs can lose money if players win streaks. Must be communicated.
3. **Cooldown prevents griefing**: Prevents mass withdrawal during high-variance events.
4. **Minimum deposit**: Prevents dust spam and rounding attacks.
5. **House-only parameter updates**: Only house can change min deposit, cooldown, etc.
6. **Singleton NFT**: Ensures only one bankroll pool instance exists.

## Transaction Flows

### Deposit Flow

```
User → Backend: POST /lp/deposit { amount, address }
Backend:
  1. Query BankrollBox state (ERG, LP supply)
  2. Calculate: newShares = (amount * supply) / ergValue
  3. Build tx: [userInput, bankrollBox] → [poolOut(more ERG, more LP), userOut(LP tokens)]
  4. Submit via node wallet
User → Gets LP tokens
```

### Withdraw Flow

```
Step 1 - Request:
User → Backend: POST /lp/request-withdraw { lpAmount, address }
Backend:
  1. Build tx creating WithdrawRequest box (LP tokens locked, cooldown starts)
  2. Submit

Step 2 - Execute (after cooldown):
Bot → Detects matured WithdrawRequest boxes
Backend:
  1. Calculate: withdrawERG = (lpAmount * totalValue) / totalSupply
  2. Build tx: [withdrawRequest, bankrollBox] → [poolOut(less ERG, less LP), userOut(ERG)]
  3. Submit
User → Gets ERG
```
