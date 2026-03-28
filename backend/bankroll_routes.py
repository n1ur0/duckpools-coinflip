"""
DuckPools - Bankroll Management API Routes

FastAPI endpoints for managing the house bankroll:
- Deposit funds into the bankroll
- Withdraw funds from the bankroll
- Get bankroll status and balance

All monetary calculations use decimal.Decimal for precision.

MAT-15: Tokenized bankroll and liquidity pool
"""

from typing import Optional
from decimal import Decimal, getcontext, ROUND_DOWN

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from pool_manager import PoolStateManager

# Set decimal context for monetary calculations
getcontext().prec = 50  # Sufficient precision for nanoERG operations
getcontext().rounding = ROUND_DOWN  # Consistent rounding for financial calc

router = APIRouter(prefix="/api/bankroll", tags=["bankroll"])


# ─── Request/Response Models ─────────────────────────────────────────────

class BankrollDepositRequest(BaseModel):
    """Request model for bankroll deposit."""
    amount: Decimal = Field(..., gt=0, description="Deposit amount in ERG (decimal)")
    description: Optional[str] = Field(None, description="Optional deposit description")


class BankrollWithdrawRequest(BaseModel):
    """Request model for bankroll withdrawal."""
    amount: Decimal = Field(..., gt=0, description="Withdrawal amount in ERG (decimal)")
    description: Optional[str] = Field(None, description="Optional withdrawal description")


class BankrollStatusResponse(BaseModel):
    """Response model for bankroll status."""
    bankroll_nanoerg: int = Field(..., description="Bankroll amount in nanoERG")
    bankroll_erg: str = Field(..., description="Bankroll amount in ERG (decimal)")
    min_bankroll_erg: str = Field(..., description="Minimum required bankroll in ERG")
    available_for_withdrawal_erg: str = Field(..., description="Amount available for withdrawal in ERG")
    last_updated: float = Field(..., description="Timestamp of last update")


class BankrollTransactionResponse(BaseModel):
    """Response model for bankroll transactions."""
    transaction_id: Optional[str] = Field(None, description="Transaction ID if submitted")
    transaction_json: dict = Field(..., description="Built transaction for signing")
    message: str = Field(..., description="Human-readable message about the transaction")


# ─── Helper Functions ───────────────────────────────────────────────────

def get_pool_manager(request: Request) -> PoolStateManager:
    """Get pool manager from app state."""
    return request.app.state.pool_manager


def erg_to_nanoerg(erg_amount: Decimal) -> int:
    """Convert ERG to nanoERG using decimal arithmetic."""
    nanoerg_amount = erg_amount * Decimal(1_000_000_000)
    return int(nanoerg_amount.to_integral_value(rounding=ROUND_DOWN))


def nanoerg_to_erg(nanoerg_amount: int) -> str:
    """Convert nanoERG to ERG string with proper decimal formatting."""
    erg_amount = Decimal(nanoerg_amount) / Decimal(1_000_000_000)
    return str(erg_amount)


# ─── Bankroll Endpoints ──────────────────────────────────────────────────

@router.get("/status", response_model=BankrollStatusResponse)
async def get_bankroll_status(request: Request):
    """Get current bankroll status and balance."""
    mgr = get_pool_manager(request)
    state = await mgr.get_pool_state()
    
    # Calculate available amount for withdrawal (bankroll - minimum pool value)
    available_for_withdrawal = max(0, state.bankroll - mgr.config.min_pool_value)
    
    return BankrollStatusResponse(
        bankroll_nanoerg=state.bankroll,
        bankroll_erg=nanoerg_to_erg(state.bankroll),
        min_bankroll_erg=nanoerg_to_erg(mgr.config.min_pool_value),
        available_for_withdrawal_erg=nanoerg_to_erg(available_for_withdrawal),
        last_updated=state.last_updated,
    )


@router.post("/deposit", response_model=BankrollTransactionResponse)
async def create_bankroll_deposit(body: BankrollDepositRequest, request: Request):
    """
    Create a bankroll deposit transaction.
    
    This endpoint builds a transaction to deposit funds into the house bankroll.
    The transaction must be signed and submitted by the house operator.
    """
    import httpx
    
    mgr = get_pool_manager(request)
    state = await mgr.get_pool_state()
    
    # Convert ERG to nanoERG for calculations
    deposit_nanoerg = erg_to_nanoerg(body.amount)
    
    # Validate minimum deposit
    if deposit_nanoerg < mgr.config.min_deposit:
        raise HTTPException(
            400,
            f"Minimum deposit is {nanoerg_to_erg(mgr.config.min_deposit)} ERG",
        )
    
    # Get current blockchain info for transaction building
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{mgr.node_url}/info", headers=mgr._headers())
        resp.raise_for_status()
        info = resp.json()
    
    # Build deposit transaction
    # This is a simplified version - in production, you'd need to properly construct
    # the transaction to update the bankroll box
    tx = {
        "requests": [
            {
                "address": info.get("walletAddress", ""),  # House operator address
                "value": str(deposit_nanoerg),
                "registers": {
                    "R4": {
                        "serializedValue": f"0e01{len(body.description or 'Bankroll deposit'):02x}{(body.description or 'Bankroll deposit').encode().hex()}"
                        if body.description else ""
                    }
                }
            }
        ],
        "fee": str(1_000_000),  # 0.001 ERG fee
        "dataInputs": [],  # Would include bankroll box reference in production
    }
    
    return BankrollTransactionResponse(
        transaction_id=None,
        transaction_json=tx,
        message=f"Bankroll deposit: {body.amount} ERG to house bankroll",
    )


@router.post("/withdraw", response_model=BankrollTransactionResponse)
async def create_bankroll_withdrawal(body: BankrollWithdrawRequest, request: Request):
    """
    Create a bankroll withdrawal transaction.
    
    This endpoint builds a transaction to withdraw funds from the house bankroll.
    The transaction must be signed and submitted by the house operator.
    
    Withdrawals cannot reduce the bankroll below the minimum required amount.
    """
    import httpx
    
    mgr = get_pool_manager(request)
    state = await mgr.get_pool_state()
    
    # Convert ERG to nanoERG for calculations
    withdraw_nanoerg = erg_to_nanoerg(body.amount)
    
    # Check if withdrawal would violate minimum bankroll requirement
    available_for_withdrawal = max(0, state.bankroll - mgr.config.min_pool_value)
    
    if withdraw_nanoerg > available_for_withdrawal:
        raise HTTPException(
            400,
            f"Withdrawal amount exceeds available bankroll. Maximum withdrawal is {nanoerg_to_erg(available_for_withdrawal)} ERG",
        )
    
    # Get current blockchain info for transaction building
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{mgr.node_url}/info", headers=mgr._headers())
        resp.raise_for_status()
        info = resp.json()
    
    # Build withdrawal transaction
    # This is a simplified version - in production, you'd need to properly construct
    # the transaction to update the bankroll box
    tx = {
        "requests": [
            {
                "address": info.get("walletAddress", ""),  # House operator address
                "value": str(withdraw_nanoerg),
                "registers": {
                    "R4": {
                        "serializedValue": f"0e01{len(body.description or 'Bankroll withdrawal'):02x}{(body.description or 'Bankroll withdrawal').encode().hex()}"
                        if body.description else ""
                    }
                }
            }
        ],
        "fee": str(1_000_000),  # 0.001 ERG fee
        "dataInputs": [],  # Would include bankroll box reference in production
    }
    
    return BankrollTransactionResponse(
        transaction_id=None,
        transaction_json=tx,
        message=f"Bankroll withdrawal: {body.amount} ERG from house bankroll",
    )


@router.get("/estimate/withdraw")
async def estimate_max_withdrawal(request: Request):
    """Estimate maximum amount that can be withdrawn from bankroll."""
    mgr = get_pool_manager(request)
    state = await mgr.get_pool_state()
    
    # Calculate available amount for withdrawal
    available_for_withdrawal = max(0, state.bankroll - mgr.config.min_pool_value)
    
    return {
        "max_withdrawal_nanoerg": available_for_withdrawal,
        "max_withdrawal_erg": nanoerg_to_erg(available_for_withdrawal),
        "min_bankroll_erg": nanoerg_to_erg(mgr.config.min_pool_value),
        "current_bankroll_erg": nanoerg_to_erg(state.bankroll),
    }