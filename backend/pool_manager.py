"""
DuckPools - Liquidity Pool Module

Backend services for managing the LP token pool:
- Pool state tracking
- Deposit/withdraw transaction building
- APY calculation
- Withdrawal request management

MAT-15: Tokenized bankroll and liquidity pool
"""

import time
from dataclasses import dataclass, field
from typing import Optional

# ─── Constants ───────────────────────────────────────────────────────

MIN_DEPOSIT_NANOERG = 100_000_000        # 0.1 ERG
COOLDOWN_BLOCKS = 60                      # ~2 hours at 2min/block
HOUSE_EDGE_BPS = 300                      # 3% in basis points
MIN_POOL_VALUE_NANOERG = 1_000_000_000    # 1 ERG anti-drain floor
LP_TOKEN_DECIMALS = 9                     # nanoERG-level precision
PRECISION_FACTOR = 1_000_000_000

BLOCKS_PER_YEAR = 262_800  # ~2 min block time * 60 * 24 * 365


# ─── Data Classes ────────────────────────────────────────────────────

@dataclass
class PoolConfig:
    """Pool configuration parameters"""
    min_deposit: int = MIN_DEPOSIT_NANOERG
    cooldown_blocks: int = COOLDOWN_BLOCKS
    house_edge_bps: int = HOUSE_EDGE_BPS
    min_pool_value: int = MIN_POOL_VALUE_NANOERG
    lp_token_decimals: int = LP_TOKEN_DECIMALS
    precision: int = PRECISION_FACTOR
    pool_nft_id: Optional[str] = None
    lp_token_id: Optional[str] = None
    bankroll_tree_hex: Optional[str] = None
    withdraw_request_tree_hex: Optional[str] = None


@dataclass
class PoolState:
    """Current pool state computed from on-chain data"""
    bankroll: int = 0              # nanoERG in bankroll box
    total_supply: int = 0          # LP token total supply
    pending_bets: int = 0          # count of pending bets
    pending_bets_value: int = 0    # nanoERG locked in pending bets
    total_value: int = 0           # bankroll + pending_bets_value
    price_per_share: int = 0       # with PRECISION_FACTOR
    house_edge_bps: int = HOUSE_EDGE_BPS
    cooldown_blocks: int = COOLDOWN_BLOCKS
    pool_nft_id: str = ""
    lp_token_id: str = ""
    last_updated: float = 0.0


@dataclass
class WithdrawalRequest:
    """Pending withdrawal request"""
    box_id: str
    holder_address: str
    lp_amount: int
    requested_erg: int
    request_height: int
    cooldown_delta: int
    tx_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    @property
    def executable_height(self) -> int:
        return self.request_height + self.cooldown_delta


@dataclass
class DepositEstimate:
    """Result of estimating a deposit"""
    deposit_amount: int
    shares_to_mint: int
    price_per_share: int
    new_total_value: int
    new_total_supply: int


@dataclass
class WithdrawEstimate:
    """Result of estimating a withdrawal"""
    shares_to_burn: int
    erg_to_receive: int
    price_per_share: int
    new_total_value: int
    new_total_supply: int


@dataclass
class APYInfo:
    """APY calculation result"""
    apy_percent: float
    house_edge_bps: int
    avg_bet_size: int
    bets_per_block: float
    bankroll: int
    estimated_daily_profit: int
    estimated_monthly_profit: int
    estimated_yearly_profit: int


# ─── Pool Math ───────────────────────────────────────────────────────

def calculate_price_per_share(
    total_value: int,
    total_supply: int,
    precision: int = PRECISION_FACTOR
) -> int:
    """
    Calculate pool token price with precision.

    price = totalValue * PRECISION / totalSupply

    Returns precision (1:1) if no supply (first deposit).
    """
    if total_supply == 0 or total_value == 0:
        return precision  # 1:1 for first deposit
    return (total_value * precision) // total_supply


def calculate_deposit_shares(
    deposit_amount: int,
    total_value: int,
    total_supply: int
) -> int:
    """
    Calculate LP shares to mint for a deposit.

    newShares = depositAmount * totalSupply / totalValue

    For first deposit: 1:1 ratio.
    """
    if total_supply == 0 or total_value == 0:
        return deposit_amount  # First deposit: 1:1
    return (deposit_amount * total_supply) // total_value


def calculate_withdraw_erg(
    burn_amount: int,
    total_value: int,
    total_supply: int
) -> int:
    """
    Calculate ERG to return for burning LP shares.

    withdrawERG = burnAmount * totalValue / totalSupply
    """
    if total_supply == 0:
        return 0
    return (burn_amount * total_value) // total_supply


def calculate_shares_to_burn_for_erg(
    desired_erg: int,
    total_value: int,
    total_supply: int
) -> int:
    """
    Calculate how many LP shares to burn to get a desired ERG amount.

    burnShares = desiredERG * totalSupply / totalValue

    This is the inverse of calculate_withdraw_erg.
    """
    if total_value == 0 or total_supply == 0:
        return 0
    return (desired_erg * total_supply) // total_value


def calculate_apy(
    house_edge_bps: int,
    avg_bet_size: int,
    bets_per_block: float,
    bankroll: int,
    blocks_per_year: int = BLOCKS_PER_YEAR
) -> APYInfo:
    """
    Calculate annualized percentage yield for LPs.

    APY = (profitPerBlock / bankroll) * blocksPerYear * 100

    profitPerBlock = avgBetSize * houseEdgeBps/10000 * betsPerBlock
    """
    if bankroll == 0:
        return APYInfo(
            apy_percent=0.0,
            house_edge_bps=house_edge_bps,
            avg_bet_size=avg_bet_size,
            bets_per_block=bets_per_block,
            bankroll=bankroll,
            estimated_daily_profit=0,
            estimated_monthly_profit=0,
            estimated_yearly_profit=0,
        )

    profit_per_block = (avg_bet_size * house_edge_bps * int(bets_per_block * 1000)) // (10000 * 1000)
    blocks_per_day = 720  # 2 min blocks
    blocks_per_month = 21_600  # ~30 days

    daily_profit = profit_per_block * blocks_per_day
    monthly_profit = profit_per_block * blocks_per_month
    yearly_profit = profit_per_block * blocks_per_year

    apy = (yearly_profit * 10000) // bankroll / 100  # percentage with 2 decimals

    return APYInfo(
        apy_percent=apy,
        house_edge_bps=house_edge_bps,
        avg_bet_size=avg_bet_size,
        bets_per_block=bets_per_block,
        bankroll=bankroll,
        estimated_daily_profit=daily_profit,
        estimated_monthly_profit=monthly_profit,
        estimated_yearly_profit=yearly_profit,
    )


# ─── Sigma Serialization (LP registers) ─────────────────────────────

def encode_vlq(value: int) -> str:
    """Encode integer using Variable-Length Quantity."""
    if value == 0:
        return "00"

    result = []
    remaining = value
    while remaining > 0:
        byte = remaining & 0x7F
        remaining >>= 7
        if remaining > 0:
            byte |= 0x80
        result.append(byte)

    return ''.join(f'{b:02x}' for b in result)


def zigzag_encode_i32(value: int) -> int:
    """ZigZag encode a 32-bit signed integer."""
    return ((value << 1) ^ (value >> 31)) & 0xFFFFFFFF


def zigzag_encode_i64(value: int) -> int:
    """ZigZag encode a 64-bit signed integer."""
    return ((value << 1) ^ (value >> 63)) & 0xFFFFFFFFFFFFFFFF


def serialize_int(value: int) -> str:
    """Serialize IntConstant: 02 + VLQ(zigzag_i32)."""
    zigzag = zigzag_encode_i32(value)
    return f"02{encode_vlq(zigzag)}"


def serialize_long(value: int) -> str:
    """Serialize LongConstant: 04 + VLQ(zigzag_i64)."""
    zigzag = zigzag_encode_i64(value)
    return f"04{encode_vlq(zigzag)}"


def serialize_coll_byte(data: bytes) -> str:
    """Serialize Coll[Byte]: 0e 01 VLQ(len) hex."""
    return f"0e01{encode_vlq(len(data))}{data.hex()}"


# ─── Pool State Manager ─────────────────────────────────────────────

class PoolStateManager:
    """
    Manages pool state by reading from the Ergo node.
    Caches state and provides computed metrics.
    """

    def __init__(self, node_url: str, api_key: str, config: PoolConfig):
        self.node_url = node_url
        self.api_key = api_key
        self.config = config
        self._cached_state: Optional[PoolState] = None
        self._cache_time: float = 0
        self._cache_ttl: float = 10.0  # 10 seconds

    def _headers(self) -> dict:
        return {"api_key": self.api_key}

    async def get_pool_state(self, force_refresh: bool = False) -> PoolState:
        """Get current pool state from on-chain data."""
        import httpx

        now = time.time()
        if (
            not force_refresh
            and self._cached_state
            and (now - self._cache_time) < self._cache_ttl
        ):
            return self._cached_state

        if not self.config.pool_nft_id:
            raise ValueError("Pool NFT ID not configured")

        async with httpx.AsyncClient(timeout=30) as client:
            # Query bankroll box by Pool NFT
            resp = await client.get(
                f"{self.node_url}/blockchain/box/unspent/byTokenId/{self.config.pool_nft_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            pool_boxes = resp.json()

            if not pool_boxes:
                raise ValueError("Bankroll pool box not found on-chain")

            pool_box = pool_boxes[0]
            bankroll = int(pool_box.get("value", 0))

            # Extract LP token supply from pool box assets
            total_supply = 0
            lp_token_id = self.config.lp_token_id or ""
            for asset in pool_box.get("assets", []):
                if lp_token_id and asset.get("tokenId") == lp_token_id:
                    total_supply = int(asset.get("amount", 0))
                elif not lp_token_id and len(pool_box.get("assets", [])) > 1:
                    # Second token in pool box is the LP token (first is Pool NFT)
                    total_supply = int(asset.get("amount", 0))
                    lp_token_id = asset.get("tokenId", "")

            # Extract pool parameters from registers
            house_edge_bps = self.config.house_edge_bps
            cooldown_blocks = self.config.cooldown_blocks

            registers = pool_box.get("additionalRegisters", {})
            if "R7" in registers:
                house_edge_bps = self._extract_int_from_serialized(
                    registers["R7"].get("serializedValue", "")
                )
            if "R6" in registers:
                cooldown_blocks = self._extract_int_from_serialized(
                    registers["R6"].get("serializedValue", "")
                )

            # TODO: Query PendingBet boxes for pending_bets_value
            # For now, pending bets value requires the coinflip NFT ID
            pending_bets = 0
            pending_bets_value = 0

            total_value = bankroll + pending_bets_value

            state = PoolState(
                bankroll=bankroll,
                total_supply=total_supply,
                pending_bets=pending_bets,
                pending_bets_value=pending_bets_value,
                total_value=total_value,
                price_per_share=calculate_price_per_share(total_value, total_supply),
                house_edge_bps=house_edge_bps,
                cooldown_blocks=cooldown_blocks,
                pool_nft_id=self.config.pool_nft_id,
                lp_token_id=lp_token_id,
                last_updated=now,
            )

            self._cached_state = state
            self._cache_time = now
            return state

    def estimate_deposit(self, amount: int) -> DepositEstimate:
        """Estimate shares for a deposit (uses cached state)."""
        if not self._cached_state:
            raise ValueError("Pool state not loaded; call get_pool_state first")

        state = self._cached_state
        shares = calculate_deposit_shares(amount, state.total_value, state.total_supply)
        new_total_value = state.total_value + amount
        new_total_supply = state.total_supply + shares

        return DepositEstimate(
            deposit_amount=amount,
            shares_to_mint=shares,
            price_per_share=state.price_per_share,
            new_total_value=new_total_value,
            new_total_supply=new_total_supply,
        )

    def estimate_withdraw(self, shares: int) -> WithdrawEstimate:
        """Estimate ERG for burning shares (uses cached state)."""
        if not self._cached_state:
            raise ValueError("Pool state not loaded; call get_pool_state first")

        state = self._cached_state
        erg = calculate_withdraw_erg(shares, state.total_value, state.total_supply)

        # Cap withdrawal to keep minimum pool value
        max_withdraw = max(0, state.bankroll - self.config.min_pool_value)
        if erg > max_withdraw:
            erg = max_withdraw

        new_total_value = state.total_value - erg
        new_total_supply = state.total_supply - shares

        return WithdrawEstimate(
            shares_to_burn=shares,
            erg_to_receive=erg,
            price_per_share=state.price_per_share,
            new_total_value=new_total_value,
            new_total_supply=new_total_supply,
        )

    def estimate_withdraw_for_erg(self, desired_erg: int) -> WithdrawEstimate:
        """Estimate shares to burn for a desired ERG amount."""
        if not self._cached_state:
            raise ValueError("Pool state not loaded; call get_pool_state first")

        state = self._cached_state
        shares = calculate_shares_to_burn_for_erg(desired_erg, state.total_value, state.total_supply)

        actual_erg = calculate_withdraw_erg(shares, state.total_value, state.total_supply)
        max_withdraw = max(0, state.bankroll - self.config.min_pool_value)
        if actual_erg > max_withdraw:
            actual_erg = max_withdraw
            shares = calculate_shares_to_burn_for_erg(actual_erg, state.total_value, state.total_supply)

        return WithdrawEstimate(
            shares_to_burn=shares,
            erg_to_receive=actual_erg,
            price_per_share=state.price_per_share,
            new_total_value=state.total_value - actual_erg,
            new_total_supply=state.total_supply - shares,
        )

    def _extract_int_from_serialized(self, hex_str: str) -> int:
        """Extract an Int value from a serialized SValue hex string."""
        if not hex_str or len(hex_str) < 4:
            return 0

        buf = bytes.fromhex(hex_str)
        if buf[0] != 0x02:
            return 0

        # Decode VLQ
        value = 0
        shift = 0
        for i in range(1, len(buf)):
            byte = buf[i]
            value |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                break
            shift += 7

        # ZigZag decode
        return (value >> 1) ^ -(value & 1)
