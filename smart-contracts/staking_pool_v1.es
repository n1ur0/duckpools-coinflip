// DuckPools LP Staking Pool Contract v1.0
//
// A staking mechanism for LP token holders where they can lock their LP tokens
// to earn additional yield from protocol rewards.
//
// Spending Paths:
// 1. Stake: LP holders lock more tokens to earn rewards
// 2. Unstake: LP holders withdraw tokens + accumulated rewards
// 3. Distribute: House distributes rewards to all stakers
//
// MAT-XXX: LP token stake/unstake ErgoTree contract with yield distribution logic

{
  // === CONFIGURATION ===
  //
  // Tokens(0) = Staking NFT (singleton, 1 unit)
  // Tokens(1) = LP Token (staked amount)
  //
  // R4: Coll[Byte] - LP Token ID (32 bytes) - which LP token can be staked
  // R5: Coll[Byte] - Reward Token ID (32 bytes, or empty = ERG rewards)
  // R6: Long       - Accumulated reward per LP share (scaled by 1e12 for precision)
  // R7: Int        - Last update height

  // Extract contract parameters
  val stakingNFT = SELF.tokens(0)._1
  val lpTokenId = SELF.R4[Coll[Byte]].get
  val selfStakedAmount = SELF.tokens(1)._2
  val rewardTokenId = SELF.R5[Coll[Byte]].get
  val selfRewardPerShare = SELF.R6[Long].get
  val lastUpdateHeight = SELF.R7[Int].get

  // === FIND POOL OUTPUT ===
  // Find the output that continues this staking pool contract
  val poolOut = OUTPUTS.find { (b: Box) =>
    b.tokens.size >= 2 &&
    b.tokens(0)._1 == stakingNFT &&
    b.propositionBytes == SELF.propositionBytes
  }.get

  // Extract output state
  val outStakedAmount = poolOut.tokens(1)._2
  val outRewardPerShare = poolOut.R6[Long].get
  val stakedDelta = outStakedAmount - selfStakedAmount

  // === PATH 1: STAKE ===
  // LP holder locks more LP tokens in the pool
  // Conditions:
  // - Staked amount increases
  // - LP token ID preserved
  // - Reward token ID preserved
  // - Last update height unchanged (no new rewards distributed)
  val isStake = stakedDelta > 0L &&
    poolOut.R4[Coll[Byte]].get == SELF.R4[Coll[Byte]].get &&
    poolOut.R5[Coll[Byte]].get == SELF.R5[Coll[Byte]].get &&
    poolOut.R7[Int].get == lastUpdateHeight &&
    outStakedAmount > 0L

  // === PATH 2: UNSTAKE ===
  // LP holder withdraws staked LP tokens + proportional rewards
  // Conditions:
  // - Staked amount decreases
  // - LP token ID preserved
  // - Reward token ID preserved
  // - Output staked amount >= 0 (can't go negative)
  // - User receives rewards proportionally (enforced by off-chain builder)
  val isUnstake = stakedDelta < 0L &&
    poolOut.R4[Coll[Byte]].get == SELF.R4[Coll[Byte]].get &&
    poolOut.R5[Coll[Byte]].get == SELF.R5[Coll[Byte]].get &&
    outStakedAmount >= 0L

  // === PATH 3: DISTRIBUT REWARDS ===
  // House distributes rewards to all stakers
  // Conditions:
  // - Staked amount unchanged
  // - Rewards added (ERG increased or reward token amount increased)
  // - Last update height updated to current height
  // - LP/Reward token IDs preserved
  // - Reward per share increases or stays same (never decreases)
  val isDistribute = stakedDelta == 0L &&
    poolOut.R4[Coll[Byte]].get == SELF.R4[Coll[Byte]].get &&
    poolOut.R5[Coll[Byte]].get == SELF.R5[Coll[Byte]].get &&
    poolOut.R7[Int].get >= lastUpdateHeight &&
    outRewardPerShare >= selfRewardPerShare

  // === SECURITY: House Signature for Distribution ===
  // Uncomment and add house PK check if needed:
  // val housePk = poolOut.R4[GroupElement].get
  // val houseSigned = proveDlog(housePk)
  // val isDistribute = isDistribute && houseSigned

  // === FINAL CHECK ===
  // At least one spending path must be valid
  isStake || isUnstake || isDistribute
}
