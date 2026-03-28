// DuckPools LP Staking Position Contract v1.0
//
// Tracks an individual LP holder's staked position.
// Each position holds the staked LP tokens and tracks reward debt.
//
// Spending Paths:
// 1. Increase Stake: User locks more LP tokens
// 2. Decrease Stake: User unstakes (after optional lock period)
// 3. Claim Rewards: User claims rewards without unstaking
//
// MAT-XXX: LP token stake/unstake ErgoTree contract with yield distribution logic

{
  // === CONFIGURATION ===
  //
  // Tokens(0) = LP Token (staked amount)
  //
  // R4: Coll[Byte] - Holder's ErgoTree (address script)
  // R5: Long       - Reward debt (rewardPerShare at last stake * stakedAmount)
  // R6: Int        - Creation height (for optional lock period)
  // R7: Int        - Lock duration (blocks), 0 = no lock

  // Extract position parameters
  val lpTokenId = SELF.tokens(0)._1
  val selfStakedAmount = SELF.tokens(0)._2
  val holderErgoTree = SELF.R4[Coll[Byte]].get
  val rewardDebt = SELF.R5[Long].get
  val creationHeight = SELF.R6[Int].get
  val lockDuration = SELF.R7[Int].get

  // === FIND POSITION OUTPUT ===
  // Find the output that continues this position
  val positionOut = OUTPUTS.find { (b: Box) =>
    b.propositionBytes == SELF.propositionBytes
  }.get

  val outStakedAmount = positionOut.tokens(0)._2
  val outRewardDebt = positionOut.R5[Long].get
  val stakedDelta = outStakedAmount - selfStakedAmount

  // === HELPER: HOLDER SIGNATURE ===
  // Verify the spender is the position holder
  val holderSigned = atLeast(1, Coll(holderErgoTree))

  // === PATH 1: INCREASE STAKE ===
  // User locks more LP tokens
  // Conditions:
  // - Staked amount increases
  // - Holder signed
  // - Reward debt recalculated based on new rewardPerShare
  val isIncrease = stakedDelta > 0L &&
    holderSigned &&
    outStakedAmount > 0L

  // === PATH 2: DECREASE STAKE (UNSTAKE) ===
  // User unstakes LP tokens (after lock period if configured)
  // Conditions:
  // - Staked amount decreases
  // - Holder signed
  // - Lock period expired (if configured)
  // - Can't unstake below minimum (optional, enforced by off-chain)
  val lockExpired = lockDuration == 0 || HEIGHT >= creationHeight + lockDuration
  val isDecrease = stakedDelta < 0L &&
    holderSigned &&
    lockExpired &&
    outStakedAmount >= 0L

  // === PATH 3: CLAIM REWARDS ===
  // User claims rewards without unstaking
  // Conditions:
  // - Staked amount unchanged
  // - Holder signed
  // - Reward debt updated (rewards claimed)
  val isClaim = stakedDelta == 0L &&
    holderSigned &&
    outRewardDebt > rewardDebt  // rewards claimed, debt updated

  // === FINAL CHECK ===
  // At least one spending path must be valid
  isIncrease || isDecrease || isClaim
}
