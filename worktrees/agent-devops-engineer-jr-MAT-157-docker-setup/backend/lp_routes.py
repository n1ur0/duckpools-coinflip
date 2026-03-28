"""
DuckPools - LP Pool API Routes

FastAPI endpoints for liquidity pool operations:
- Pool state queries (TVL, APY, price)
- Deposit/withdraw transaction building
- Withdrawal request management

MAT-15: Tokenized bankroll and liquidity pool
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator

from validators import validate_ergo_address, ValidationError
from pool_manager import (
    PoolConfig,
    PoolStateManager,
    PoolState,
    calculate_apy,
    calculate_withdraw_erg,
    PRECISION_FACTOR,
)

router = APIRouter(prefix="/lp", tags=["liquidity-pool"])


# ─── Request/Response Models ─────────────────────────────────────────

class DepositRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Deposit amount in nanoERG")
    address: str = Field(..., min_length=1, description="LP's ERG address")

    @field_validator("address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        try:
            return validate_ergo_address(v)
        except ValidationError as e:
            raise ValueError(str(e))


class WithdrawRequestCreate(BaseModel):
    lp_amount: int = Field(..., gt=0, description="LP tokens to withdraw")
    address: str = Field(..., min_length=1, description="LP's ERG address")

    @field_validator("address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        try:
            return validate_ergo_address(v)
        except ValidationError as e:
            raise ValueError(str(e))


class WithdrawExecuteRequest(BaseModel):
    box_id: str = Field(..., min_length=1, description="WithdrawRequest box ID")


class WithdrawCancelRequest(BaseModel):
    box_id: str = Field(..., min_length=1, description="WithdrawRequest box ID")


class PoolStateResponse(BaseModel):
    bankroll: str = Field(..., description="Bankroll in nanoERG")
    bankroll_erg: str = Field(..., description="Bankroll in ERG")
    total_supply: str = Field(..., description="LP token total supply")
    total_value: str = Field(..., description="Total value (bankroll + pending)")
    total_value_erg: str = Field(..., description="Total value in ERG")
    price_per_share: str = Field(..., description="Price per LP share (with precision)")
    price_per_share_erg: str = Field(..., description="Price per LP share in ERG")
    house_edge_bps: int = Field(..., description="House edge in basis points")
    cooldown_blocks: int = Field(..., description="Withdrawal cooldown in blocks")
    cooldown_hours: float = Field(..., description="Withdrawal cooldown in hours")
    pending_bets: int = Field(..., description="Number of pending bets")


class EstimateResponse(BaseModel):
    shares: str = Field(..., description="LP shares (mint or burn)")
    erg_amount: str = Field(..., description="ERG amount (deposit or withdraw)")
    price_per_share: str = Field(..., description="Current price per share")
    new_total_value: str = Field(..., description="New pool total value")


class APYResponse(BaseModel):
    apy_percent: float = Field(..., description="Annualized percentage yield")
    house_edge_bps: int
    avg_bet_size_erg: str = Field(..., description="Average bet size used for calc")
    bets_per_block: float = Field(..., description="Bets per block used for calc")
    estimated_daily_profit_erg: str
    estimated_monthly_profit_erg: str
    estimated_yearly_profit_erg: str


class TxResponse(BaseModel):
    tx_id: Optional[str] = Field(None, description="Transaction ID if submitted")
    tx_json: dict = Field(..., description="Built transaction for signing")
    message: str


class LPBalanceResponse(BaseModel):
    address: str
    lp_balance: str = Field(..., description="LP token balance")
    erg_value: str = Field(..., description="Equivalent ERG value")
    share_percent: float = Field(..., description="Percentage of pool owned")


# ─── Helper ──────────────────────────────────────────────────────────

def get_pool_manager(request: Request) -> PoolStateManager:
    """Get pool manager from app state."""
    return request.app.state.pool_manager


def nano_to_erg(nano: int) -> str:
    """Convert nanoERG to ERG string."""
    return f"{nano / 1e9:.9f}".rstrip('0').rstrip('.')


# ─── Pool Query Endpoints ───────────────────────────────────────────

@router.get("/pool", response_model=PoolStateResponse)
async def get_pool_state(request: Request):
    """Get current pool state, TVL, and LP token price."""
    mgr = get_pool_manager(request)
    state = await mgr.get_pool_state()
    price_erg = state.price_per_share / PRECISION_FACTOR

    return PoolStateResponse(
        bankroll=str(state.bankroll),
        bankroll_erg=nano_to_erg(state.bankroll),
        total_supply=str(state.total_supply),
        total_value=str(state.total_value),
        total_value_erg=nano_to_erg(state.total_value),
        price_per_share=str(state.price_per_share),
        price_per_share_erg=nano_to_erg(int(price_erg)),
        house_edge_bps=state.house_edge_bps,
        cooldown_blocks=state.cooldown_blocks,
        cooldown_hours=round(state.cooldown_blocks * 2 / 60, 1),  # ~2 min blocks
        pending_bets=state.pending_bets,
    )


@router.get("/price")
async def get_lp_price(request: Request):
    """Get current LP token price."""
    mgr = get_pool_manager(request)
    state = await mgr.get_pool_state()
    price_erg = state.price_per_share / PRECISION_FACTOR

    return {
        "price_per_share": str(state.price_per_share),
        "price_per_share_erg": nano_to_erg(int(price_erg)),
        "total_supply": str(state.total_supply),
        "total_value": str(state.total_value),
        "total_value_erg": nano_to_erg(state.total_value),
    }


@router.get("/balance/{address:path}", response_model=LPBalanceResponse)
async def get_lp_balance(address: str, request: Request):
    """Get LP token balance for an address."""
    import httpx

    # BE-9: Validate address to prevent SSRF via node API
    try:
        address = validate_ergo_address(address)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    mgr = get_pool_manager(request)
    state = await mgr.get_pool_state()

    if not state.lp_token_id:
        raise HTTPException(404, "LP token ID not available")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{mgr.node_url}/blockchain/box/unspent/byTokenId/{state.lp_token_id}",
            headers=mgr._headers(),
        )
        resp.raise_for_status()
        boxes = resp.json()

    total_balance = 0
    for box in boxes:
        for asset in box.get("assets", []):
            if asset.get("tokenId") == state.lp_token_id:
                total_balance += int(asset.get("amount", 0))

    erg_value = (
        calculate_withdraw_erg(total_balance, state.total_value, state.total_supply)
        if state.total_supply > 0 else total_balance
    )
    share_pct = (total_balance * 10000 / state.total_supply) if state.total_supply > 0 else 0

    return LPBalanceResponse(
        address=address,
        lp_balance=str(total_balance),
        erg_value=nano_to_erg(erg_value),
        share_percent=round(share_pct / 100, 4),
    )


@router.get("/apy", response_model=APYResponse)
async def get_pool_apy(
    request: Request,
    avg_bet_size: Optional[str] = Query(None, description="Average bet size in ERG"),
    bets_per_block: Optional[float] = Query(None, description="Average bets per block", ge=0, le=1000),
):
    """Calculate pool APY based on metrics."""
    mgr = get_pool_manager(request)
    state = await mgr.get_pool_state()

    # Validate avg_bet_size if provided
    if avg_bet_size is not None:
        try:
            bet_size_erg = float(avg_bet_size)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="avg_bet_size must be a numeric value in ERG")
        if bet_size_erg <= 0:
            raise HTTPException(status_code=400, detail="avg_bet_size must be positive")
        if bet_size_erg > 1_000_000:
            raise HTTPException(status_code=400, detail="avg_bet_size unreasonably large (max 1,000,000 ERG)")
    else:
        bet_size_erg = 1.0

    bet_size_nano = int(bet_size_erg * 1e9)
    bpb = bets_per_block if bets_per_block is not None else 0.5

    apy_info = calculate_apy(
        house_edge_bps=state.house_edge_bps,
        avg_bet_size=bet_size_nano,
        bets_per_block=bpb,
        bankroll=state.bankroll,
    )

    return APYResponse(
        apy_percent=apy_info.apy_percent,
        house_edge_bps=apy_info.house_edge_bps,
        avg_bet_size_erg=nano_to_erg(apy_info.avg_bet_size),
        bets_per_block=apy_info.bets_per_block,
        estimated_daily_profit_erg=nano_to_erg(apy_info.estimated_daily_profit),
        estimated_monthly_profit_erg=nano_to_erg(apy_info.estimated_monthly_profit),
        estimated_yearly_profit_erg=nano_to_erg(apy_info.estimated_yearly_profit),
    )


# ─── Estimate Endpoints ─────────────────────────────────────────────

@router.get("/estimate/deposit", response_model=EstimateResponse)
async def estimate_deposit(
    amount: int = Query(..., gt=0, description="Deposit amount in nanoERG"),
    request: Request = None,
):
    """Estimate LP shares for a deposit."""
    mgr = get_pool_manager(request)
    state = await mgr.get_pool_state()

    from pool_manager import calculate_deposit_shares
    shares = calculate_deposit_shares(amount, state.total_value, state.total_supply)
    new_value = state.total_value + amount

    return EstimateResponse(
        shares=str(shares),
        erg_amount=str(amount),
        price_per_share=str(state.price_per_share),
        new_total_value=str(new_value),
    )


@router.get("/estimate/withdraw", response_model=EstimateResponse)
async def estimate_withdraw(
    shares: int = Query(..., gt=0, description="LP shares to withdraw"),
    request: Request = None,
):
    """Estimate ERG for burning LP shares."""
    mgr = get_pool_manager(request)
    state = await mgr.get_pool_state()

    erg = calculate_withdraw_erg(shares, state.total_value, state.total_supply)

    # Cap at available bankroll minus minimum
    max_withdraw = max(0, state.bankroll - mgr.config.min_pool_value)
    erg = min(erg, max_withdraw)

    new_value = state.total_value - erg

    return EstimateResponse(
        shares=str(shares),
        erg_amount=str(erg),
        price_per_share=str(state.price_per_share),
        new_total_value=str(new_value),
    )


# ─── Transaction Endpoints ──────────────────────────────────────────

@router.post("/deposit", response_model=TxResponse)
async def build_deposit_tx(body: DepositRequest, request: Request):
    """
    Build (and optionally submit) a deposit transaction.

    The user deposits ERG and receives LP tokens proportional to their share.
    First deposit: 1 ERG = 1 LP token.
    Subsequent: shares = deposit * totalSupply / totalValue
    """
    import httpx
    from pool_manager import calculate_deposit_shares

    mgr = get_pool_manager(request)
    state = await mgr.get_pool_state()

    # Validate minimum deposit
    if body.amount < mgr.config.min_deposit:
        raise HTTPException(
            400,
            f"Minimum deposit is {nano_to_erg(mgr.config.min_deposit)} ERG",
        )

    # Calculate shares
    shares = calculate_deposit_shares(body.amount, state.total_value, state.total_supply)

    if shares == 0:
        raise HTTPException(400, "Deposit too small to mint any shares")

    # Build transaction using node wallet
    tx = {
        "requests": [
            {
                "address": body.address,
                "value": str(body.amount),
                "assets": [
                    {
                        "tokenId": state.lp_token_id,
                        "amount": str(shares),
                    }
                ] if state.lp_token_id else [],
            }
        ],
        "fee": str(1_000_000),  # 0.001 ERG
    }

    return TxResponse(
        tx_id=None,
        tx_json=tx,
        message=f"Deposit {nano_to_erg(body.amount)} ERG for {shares} LP shares",
    )


@router.post("/request-withdraw", response_model=TxResponse)
async def request_withdrawal(body: WithdrawRequestCreate, request: Request):
    """
    Create a withdrawal request.

    LP tokens are locked in a WithdrawRequest box. After the cooldown period,
    the withdrawal can be executed to receive ERG.
    """
    import httpx
    from pool_manager import serialize_coll_byte, serialize_int, serialize_long

    mgr = get_pool_manager(request)
    state = await mgr.get_pool_state()

    if body.lp_amount > state.total_supply:
        raise HTTPException(400, "Withdrawal amount exceeds pool supply")

    if not state.lp_token_id:
        raise HTTPException(400, "LP token not deployed yet")

    # Calculate ERG to receive
    erg_amount = calculate_withdraw_erg(body.lp_amount, state.total_value, state.total_supply)
    max_withdraw = max(0, state.bankroll - mgr.config.min_pool_value)
    erg_amount = min(erg_amount, max_withdraw)

    # Get current height
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{mgr.node_url}/info", headers=mgr._headers())
        current_height = resp.json().get("fullHeight", 0)

        # Get address ErgoTree
        resp2 = await client.get(
            f"{mgr.node_url}/script/addressToBytes/{body.address}",
            headers=mgr._headers(),
        )
        resp2.raise_for_status()
        address_bytes = resp2.json().get("bytes", "")

    ergo_tree_bytes = bytes.fromhex(address_bytes) if address_bytes else b''

    if not mgr.config.withdraw_request_tree_hex:
        raise HTTPException(400, "Withdraw request contract not configured")

    # Build WithdrawRequest box registers
    registers = {
        "R4": serialize_coll_byte(ergo_tree_bytes),        # Holder's ErgoTree
        "R5": serialize_long(erg_amount),                    # Requested ERG
        "R6": serialize_int(current_height),                 # Creation height
        "R7": serialize_int(state.cooldown_blocks),          # Cooldown delta
    }

    tx = {
        "requests": [
            {
                "ergoTree": mgr.config.withdraw_request_tree_hex,
                "value": str(max(1_000_000, erg_amount // 10)),  # Small ERG for box rent
                "assets": [
                    {
                        "tokenId": state.lp_token_id,
                        "amount": str(body.lp_amount),
                    }
                ],
                "additionalRegisters": registers,
            }
        ],
        "fee": str(1_000_000),
    }

    return TxResponse(
        tx_id=None,
        tx_json=tx,
        message=f"Withdrawal requested: {body.lp_amount} LP shares for {nano_to_erg(erg_amount)} ERG (cooldown: {state.cooldown_blocks} blocks)",
    )


@router.post("/execute-withdraw", response_model=TxResponse)
async def execute_withdrawal(body: WithdrawExecuteRequest, request: Request):
    """
    Execute a matured withdrawal request.

    Burns LP tokens from the WithdrawRequest box and sends ERG to the holder.
    Must be called after the cooldown period has passed.
    """
    import httpx

    mgr = get_pool_manager(request)
    state = await mgr.get_pool_state()

    # Verify the withdraw request box exists and is mature
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{mgr.node_url}/blockchain/box/byId/{body.box_id}",
            headers=mgr._headers(),
        )
        resp.raise_for_status()
        request_box = resp.json()

    registers = request_box.get("additionalRegisters", {})
    request_height_str = registers.get("R6", {}).get("serializedValue", "")
    cooldown_str = registers.get("R7", {}).get("serializedValue", "")

    request_height = mgr._extract_int_from_serialized(request_height_str)
    cooldown = mgr._extract_int_from_serialized(cooldown_str)

    # Get current height
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{mgr.node_url}/info", headers=mgr._headers())
        current_height = resp.json().get("fullHeight", 0)

    if current_height < request_height + cooldown:
        remaining = request_height + cooldown - current_height
        raise HTTPException(
            400,
            f"Withdrawal not yet mature. {remaining} blocks remaining.",
        )

    # Build execution transaction: spend the request box, output ERG to holder
    holder_tree_hex = registers.get("R4", {}).get("serializedValue", "")

    # Calculate ERG to send (from pool bankroll minus min pool value)
    # The actual ERG comes from the bankroll box, not the request box
    requested_erg = 0
    requested_erg_str = registers.get("R5", {}).get("serializedValue", "")
    if requested_erg_str:
        # R5 uses serialize_long (0x04 prefix) — handled by shared method (SEC-A6)
        requested_erg = mgr._extract_int_from_serialized(requested_erg_str)

    # Actual erg is capped by available bankroll
    max_withdraw = max(0, state.bankroll - mgr.config.min_pool_value)
    actual_erg = min(requested_erg, max_withdraw)

    tx = {
        "rawInputBoxes": [body.box_id],
        "requests": [
            {
                "value": str(actual_erg),
                "ergoTree": holder_tree_hex,
            }
        ],
        "fee": str(1_000_000),
    }

    return TxResponse(
        tx_id=None,
        tx_json=tx,
        message=f"Withdrawal execution: {nano_to_erg(actual_erg)} ERG to holder",
    )


@router.post("/cancel-withdraw", response_model=TxResponse)
async def cancel_withdrawal(body: WithdrawCancelRequest, request: Request):
    """
    Cancel a pending withdrawal request.

    Returns LP tokens to the holder (no ERG from pool).
    """
    import httpx

    mgr = get_pool_manager(request)

    # Verify the withdraw request box exists
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{mgr.node_url}/blockchain/box/byId/{body.box_id}",
            headers=mgr._headers(),
        )
        resp.raise_for_status()
        request_box = resp.json()

    # Extract holder address from R4
    registers = request_box.get("additionalRegisters", {})
    holder_tree_hex = registers.get("R4", {}).get("serializedValue", "")

    # Get LP token amount from box assets
    lp_amount = 0
    lp_token_id = ""
    for asset in request_box.get("assets", []):
        lp_amount = int(asset.get("amount", 0))
        lp_token_id = asset.get("tokenId", "")
        break

    tx = {
        "rawInputBoxes": [body.box_id],
        "requests": [
            {
                "ergoTree": holder_tree_hex,
                "value": str(1_000_000),  # Minimum box value
                "assets": [
                    {
                        "tokenId": lp_token_id,
                        "amount": str(lp_amount),
                    }
                ],
            }
        ],
        "fee": str(1_000_000),
    }

    return TxResponse(
        tx_id=None,
        tx_json=tx,
        message="Withdrawal cancellation: LP tokens returned to holder",
    )
