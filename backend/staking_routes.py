"""
DuckPools - LP Staking API Routes

FastAPI endpoints for LP token staking operations:
- Stake LP tokens to earn rewards
- Unstake and claim rewards
- Query staking state and pending rewards

MAT-XXX: LP token stake/unstake ErgoTree contract with yield distribution logic
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/stake", tags=["lp-staking"])


# ─── Request/Response Models ─────────────────────────────────────────

class StakeRequest(BaseModel):
    amount: int = Field(..., gt=0, description="LP token amount to stake")
    address: str = Field(..., min_length=1, description="Staker's ERG address")


class UnstakeRequest(BaseModel):
    position_box_id: str = Field(..., min_length=1, description="StakingPosition box ID")
    amount: Optional[int] = Field(None, gt=0, description="LP amount to unstake (default: all)")


class ClaimRequest(BaseModel):
    position_box_id: str = Field(..., min_length=1, description="StakingPosition box ID")


class StakingPoolStateResponse(BaseModel):
    lp_token_id: str
    reward_token_id: Optional[str]
    total_staked: str
    total_rewards: str
    reward_per_share: str
    last_update_height: int
    apy_percent: Optional[float]


class StakerBalanceResponse(BaseModel):
    address: str
    staked_amount: str
    pending_rewards: str
    reward_token_id: Optional[str]


class TxResponse(BaseModel):
    tx_id: Optional[str] = None
    tx_json: dict
    message: str


# ─── Pool Query Endpoints ───────────────────────────────────────────

@router.get("/pool", response_model=StakingPoolStateResponse)
async def get_staking_pool(request: Request):
    """
    Get current staking pool state, TVL, and APY.
    """
    # TODO: Implement pool state retrieval from blockchain
    # For now, return placeholder data
    return StakingPoolStateResponse(
        lp_token_id="placeholder_lp_token_id",
        reward_token_id=None,  # None = ERG rewards
        total_staked="0",
        total_rewards="0",
        reward_per_share="0",
        last_update_height=0,
        apy_percent=0.0,
    )


@router.get("/balance/{address:path}", response_model=StakerBalanceResponse)
async def get_staker_balance(address: str, request: Request):
    """
    Get staked balance and pending rewards for an address.
    """
    # TODO: Implement staker balance retrieval
    # Query all StakingPosition boxes for this address
    # Sum staked amounts and calculate pending rewards
    return StakerBalanceResponse(
        address=address,
        staked_amount="0",
        pending_rewards="0",
        reward_token_id=None,
    )


@router.get("/rewards/{address:path}")
async def get_pending_rewards(address: str, request: Request):
    """
    Get pending rewards for an address.
    """
    # TODO: Calculate pending rewards based on:
    # - stakedAmount
    # - currentRewardPerShare
    # - rewardDebt from position box
    return {
        "address": address,
        "pending_rewards": "0",
        "reward_token_id": None,
    }


@router.get("/apy")
async def get_staking_apy(
    request: Request,
    reward_rate: Optional[float] = Query(None, description="Rewards per block (ERG)"),
):
    """
    Calculate current staking APY.
    """
    # TODO: Implement APY calculation
    # APY = (rewardsPerBlock * blocksPerYear) / totalStakedValue
    return {
        "apy_percent": 0.0,
        "reward_per_block": reward_rate or 0.0,
        "total_staked": "0",
    }


# ─── Transaction Endpoints ──────────────────────────────────────────

@router.post("/stake", response_model=TxResponse)
async def build_stake_tx(body: StakeRequest, request: Request):
    """
    Build a staking transaction.

    User sends LP tokens to a StakingPosition box and the StakingPool updates.
    Reward debt is calculated to prevent reward gaming.
    """
    import httpx

    # TODO: Implement stake transaction building
    # 1. Query StakingPool state (current rewardPerShare)
    # 2. Calculate rewardDebt = rewardPerShare * body.amount
    # 3. Build tx:
    #    - Inputs: user LP tokens + StakingPool
    #    - Outputs:
    #      * StakingPool (more LP tokens, updated rewardPerShare)
    #      * StakingPosition (LP tokens + rewardDebt)
    # 4. Return unsigned tx for user signing

    # Placeholder response
    return TxResponse(
        tx_id=None,
        tx_json={
            "requests": [
                {
                    "address": body.address,
                    "value": "1000000",  # min box value
                    "assets": [
                        {
                            "tokenId": "placeholder_lp_token_id",
                            "amount": str(body.amount),
                        }
                    ],
                }
            ],
            "fee": "1000000",
        },
        message=f"Stake {body.amount} LP tokens",
    )


@router.post("/unstake", response_model=TxResponse)
async def build_unstake_tx(body: UnstakeRequest, request: Request):
    """
    Build an unstake transaction.

    User unstakes LP tokens and claims accumulated rewards.
    Rewards = (currentRewardPerShare - rewardDebt) * stakedAmount
    """
    import httpx

    # TODO: Implement unstake transaction building
    # 1. Query StakingPosition and StakingPool states
    # 2. Calculate pending rewards
    # 3. Build tx:
    #    - Inputs: StakingPosition + StakingPool
    #    - Outputs:
    #      * StakingPool (fewer LP tokens, updated rewardPerShare)
    #      * User output (LP tokens + rewards)
    # 4. Return unsigned tx for user signing

    # Placeholder response
    return TxResponse(
        tx_id=None,
        tx_json={
            "rawInputBoxes": [body.position_box_id],
            "requests": [
                {
                    "address": "placeholder",
                    "value": "1000000",
                }
            ],
            "fee": "1000000",
        },
        message=f"Unstake from position {body.position_box_id}",
    )


@router.post("/claim", response_model=TxResponse)
async def build_claim_tx(body: ClaimRequest, request: Request):
    """
    Build a rewards claim transaction.

    User claims rewards without unstaking LP tokens.
    """
    import httpx

    # TODO: Implement claim transaction building
    # 1. Query StakingPosition and StakingPool states
    # 2. Calculate pending rewards
    # 3. Build tx:
    #    - Inputs: StakingPosition
    #    - Outputs:
    #      * StakingPosition (same LP tokens, updated rewardDebt)
    #      * User output (rewards only)
    # 4. Return unsigned tx for user signing

    # Placeholder response
    return TxResponse(
        tx_id=None,
        tx_json={
            "rawInputBoxes": [body.position_box_id],
            "requests": [
                {
                    "address": "placeholder",
                    "value": "1000000",
                }
            ],
            "fee": "1000000",
        },
        message=f"Claim rewards from position {body.position_box_id}",
    )
