/**
 * DuckPools SDK - Bankroll Pool Contracts
 * ErgoScript source and helpers for the LP token liquidity pool
 *
 * MAT-15: Tokenized bankroll and liquidity pool
 */

/**
 * BankrollPool Contract (ErgoScript)
 *
 * Singleton contract that holds the house bankroll and tracks LP token supply.
 * Spending paths: deposit, withdraw, collect (house profits), update params.
 *
 * Tokens:
 *   (0) = Pool NFT (singleton, 1 unit) - identifies this pool instance
 *   (1) = LP Token (EIP-4) - total supply = outstanding shares
 *
 * Registers:
 *   R4: Coll[Byte] - House operator's public key (33 bytes compressed)
 *   R5: Long       - Minimum deposit in nanoERG
 *   R6: Int        - Withdrawal cooldown height delta
 *   R7: Int        - House edge basis points (300 = 3.00%)
 */
export const BANKROLL_POOL_SCRIPT = `{
  // --- BankrollPool Singleton Contract ---
  // Holds the house bankroll, tracks LP token supply.
  // Spending paths: deposit | withdraw | collect | update
  //
  // Tokens(0) = Pool NFT  (singleton, 1 unit)
  // Tokens(1) = LP Token  (EIP-4, total supply = shares)
  //
  // R4 = Coll[Byte]  House operator PK (33-byte compressed)
  // R5 = Long        Minimum deposit (nanoERG)
  // R6 = Int         Withdrawal cooldown (block delta)
  // R7 = Int         House edge basis points (e.g. 300 = 3%)

  val poolNFT      = SELF.tokens(0)._1
  val lpTokenId    = SELF.tokens(1)._1
  val selfLpSupply = SELF.tokens(1)._2
  val housePk      = SELF.R4[GroupElement].get
  val minDeposit   = SELF.R5[Long].get
  val cooldownDelta= SELF.R6[Int].get
  val houseEdgeBps = SELF.R7[Int].get

  // Find the output box that continues this pool (same NFT + same script)
  val poolOut = OUTPUTS.find { (b: Box) =>
    b.tokens.size >= 2 &&
    b.tokens(0)._1 == poolNFT &&
    b.propositionBytes == SELF.propositionBytes
  }.get

  val outLpSupply   = poolOut.tokens(1)._2
  val lpSupplyDelta = outLpSupply - selfLpSupply

  // --- Path 1: Deposit ---
  // LP tokens are minted (supply increases), ERG is added to pool.
  // The caller's ERG becomes part of the bankroll.
  // Minted amount is calculated off-chain: newShares = deposit * supply / value
  val isDeposit = lpSupplyDelta > 0L &&
    poolOut.value > SELF.value &&
    poolOut.R4[Coll[Byte]].get == SELF.R4[Coll[Byte]].get &&
    poolOut.R5[Long].get == SELF.R5[Long].get &&
    poolOut.R6[Int].get == SELF.R6[Int].get &&
    poolOut.R7[Int].get == SELF.R7[Int].get

  // --- Path 2: Withdraw ---
  // LP tokens are burned (supply decreases), ERG is removed from pool.
  // Requires a WithdrawRequest box in the same transaction that has passed
  // its cooldown period.
  // Burn amount and ERG withdrawal calculated off-chain.
  val isWithdraw = lpSupplyDelta < 0L &&
    poolOut.value < SELF.value &&
    poolOut.R4[Coll[Byte]].get == SELF.R4[Coll[Byte]].get &&
    poolOut.R5[Long].get == SELF.R5[Long].get &&
    poolOut.R6[Int].get == SELF.R6[Int].get &&
    poolOut.R7[Int].get == SELF.R7[Int].get &&
    poolOut.value >= minDeposit

  // --- Path 3: Profit Collection (house only) ---
  // No LP token supply change. ERG increases from house edge profits.
  // Requires house operator signature.
  val isCollect = lpSupplyDelta == 0L &&
    poolOut.value > SELF.value &&
    poolOut.R4[Coll[Byte]].get == SELF.R4[Coll[Byte]].get &&
    poolOut.R5[Long].get == SELF.R5[Long].get &&
    poolOut.R6[Int].get == SELF.R6[Int].get &&
    poolOut.R7[Int].get == SELF.R7[Int].get &&
    proveDlog(housePk)

  // --- Path 4: Parameter Update (house only) ---
  // No ERG or supply changes. House can adjust minDeposit/cooldown/edge.
  val isUpdate = lpSupplyDelta == 0L &&
    poolOut.value == SELF.value &&
    proveDlog(housePk)

  isDeposit || isWithdraw || isCollect || isUpdate
}`;

/**
 * WithdrawRequest Contract (ErgoScript)
 *
 * Tracks a pending withdrawal request with a cooldown timer.
 * LP tokens are locked in this box until the cooldown expires.
 *
 * Tokens:
 *   (0) = LP Token (amount to burn on withdrawal)
 *
 * Registers:
 *   R4: Coll[Byte] - LP holder's address ErgoTree (who receives ERG)
 *   R5: Long       - Requested ERG withdrawal amount
 *   R6: Int        - Creation height (for cooldown calculation)
 *   R7: Int        - Cooldown delta (copied from pool at request time)
 */
export const WITHDRAW_REQUEST_SCRIPT = `{
  // --- WithdrawRequest Contract ---
  // Holds LP tokens pending withdrawal. After cooldown, can be spent
  // to execute the withdrawal (burn LP tokens, receive ERG from pool).
  //
  // Tokens(0) = LP Token (amount to be burned)
  //
  // R4 = Coll[Byte]  Holder's ErgoTree (receives ERG on execution)
  // R5 = Long        Requested ERG amount
  // R6 = Int         Creation height
  // R7 = Int         Cooldown delta (blocks until executable)

  val lpTokenId    = SELF.tokens(0)._1
  val lpAmount      = SELF.tokens(0)._2
  val holderTree    = SELF.R4[Coll[Byte]].get
  val requestedErg  = SELF.R5[Long].get
  val requestHeight = SELF.R6[Int].get
  val cooldownDelta = SELF.R7[Int].get

  // --- Path 1: Execute Withdrawal (after cooldown) ---
  // After cooldown expires, the request box can be spent.
  // The spending transaction must:
  //   - Burn the LP tokens in this box
  //   - Send ERG to the holder's address (R4)
  //   - Spend the BankrollPool box to reduce its ERG and LP supply
  // Contract allows spending after cooldown; off-chain builder enforces
  // correct ERG amounts.
  val isExecute = HEIGHT >= requestHeight + cooldownDelta

  // --- Path 2: Cancel Withdrawal (anytime) ---
  // Holder can cancel and get their LP tokens back.
  // Output must send LP tokens back to holder's address.
  val cancelOut = OUTPUTS.find { (b: Box) =>
    b.tokens.size >= 1 &&
    b.tokens(0)._1 == lpTokenId &&
    b.tokens(0)._2 >= lpAmount
  }.get

  val isCancel = cancelOut.propositionBytes == holderTree

  isExecute || isCancel
}`;

/**
 * Pool configuration constants
 */
export const POOL_CONFIG = {
  /** Minimum deposit in nanoERG (0.1 ERG) */
  MIN_DEPOSIT: 100_000_000n,
  /** Withdrawal cooldown in blocks (~2 hours at 2min/block) */
  COOLDOWN_BLOCKS: 60,
  /** House edge in basis points (300 = 3%) */
  HOUSE_EDGE_BPS: 300,
  /** Minimum pool value (anti-drain) in nanoERG */
  MIN_POOL_VALUE: 1_000_000_000n, // 1 ERG
  /** LP token decimals */
  LP_TOKEN_DECIMALS: 9,
  /** Precision factor for share calculations */
  PRECISION: 1_000_000_000n,
} as const;

/**
 * LP token name and description for EIP-4
 */
export const LP_TOKEN_INFO = {
  name: 'DuckPools LP',
  description: 'DuckPools Coinflip Liquidity Provider Token',
  decimals: POOL_CONFIG.LP_TOKEN_DECIMALS,
  numUnits: 0, // Unlimited supply
} as const;

/**
 * Pool state computed from on-chain data
 */
export interface PoolState {
  /** Total ERG in the bankroll box (nanoERG) */
  bankroll: bigint;
  /** Total LP token supply */
  totalSupply: bigint;
  /** Number of pending bets */
  pendingBets: number;
  /** Total ERG locked in pending bets (nanoERG) */
  pendingBetsValue: bigint;
  /** Total value (bankroll + pending bets) */
  totalValue: bigint;
  /** Price per LP share (nanoERG, with PRECISION factor) */
  pricePerShare: bigint;
  /** House edge in basis points */
  houseEdgeBps: number;
  /** Cooldown in blocks */
  cooldownBlocks: number;
  /** Pool NFT token ID */
  poolNftId: string;
  /** LP token ID */
  lpTokenId: string;
}

/**
 * Withdrawal request data (from on-chain box)
 */
export interface WithdrawalRequest {
  boxId: string;
  /** LP holder's address */
  holderAddress: string;
  /** LP tokens being withdrawn */
  lpAmount: bigint;
  /** Requested ERG amount */
  requestedErg: bigint;
  /** Block height when request was created */
  requestHeight: number;
  /** Cooldown delta (blocks) */
  cooldownDelta: number;
  /** Block height when withdrawal becomes executable */
  executableHeight: number;
  /** Whether the cooldown has passed */
  isMature: boolean;
}

/**
 * Calculate pool token price
 * pricePerShare = totalValue * PRECISION / totalSupply
 */
export function calculatePricePerShare(
  totalValue: bigint,
  totalSupply: bigint,
  precision: bigint = POOL_CONFIG.PRECISION
): bigint {
  if (totalSupply === 0n) return precision; // 1:1 for first deposit
  return (totalValue * precision) / totalSupply;
}

/**
 * Calculate LP shares to mint for a deposit
 * newShares = depositAmount * totalSupply / totalValue
 */
export function calculateDepositShares(
  depositAmount: bigint,
  totalValue: bigint,
  totalSupply: bigint
): bigint {
  if (totalSupply === 0n || totalValue === 0n) {
    // First deposit: 1:1 ratio
    return depositAmount;
  }
  return (depositAmount * totalSupply) / totalValue;
}

/**
 * Calculate ERG to return for a withdrawal
 * withdrawErg = burnAmount * totalValue / totalSupply
 */
export function calculateWithdrawErg(
  burnAmount: bigint,
  totalValue: bigint,
  totalSupply: bigint
): bigint {
  if (totalSupply === 0n) return 0n;
  return (burnAmount * totalValue) / totalSupply;
}

/**
 * Calculate APY based on historical house edge profits
 *
 * APY = (profitPerBlock / bankroll) * blocksPerYear * 100
 *
 * @param houseEdgeBps House edge in basis points (300 = 3%)
 * @param avgBetSize Average bet size in nanoERG
 * @param betsPerBlock Average number of bets per block
 * @param bankroll Current bankroll in nanoERG
 * @param blocksPerYear Ergo blocks per year (~262800)
 */
export function calculateAPY(
  houseEdgeBps: number,
  avgBetSize: bigint,
  betsPerBlock: number,
  bankroll: bigint,
  blocksPerYear: number = 262_800
): number {
  if (bankroll === 0n) return 0;
  const profitPerBlock = avgBetSize * BigInt(houseEdgeBps) * BigInt(betsPerBlock) / 10000n;
  const annualProfit = profitPerBlock * BigInt(blocksPerYear);
  const apy = Number((annualProfit * 10000n) / bankroll) / 10000;
  return apy;
}
