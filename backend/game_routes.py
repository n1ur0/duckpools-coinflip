"""
DuckPools - Game Routes

Frontend-facing endpoints for the coinflip game PoC.
These routes match the API contract expected by the React frontend.

MAT-309: Rebuild backend API to match frontend contract.
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field, field_validator

from validators import validate_ergo_address, ValidationError as ErgoValidationError

router = APIRouter(tags=["game"])

# ─── Compiled Contract Constants ──────────────────────────────────
# coinflip_v2.es compiled 2026-03-28 against node v6.0.3 (Lithos testnet)
# Values MUST match smart-contracts/coinflip_deployed.json
COINFLIP_P2S_ADDRESS = "3yNMkSZ6b36YGBJJNhpavxxCFg4f2ceH5JF81hXJgzWoWozuFJSjoW8Q5JXow6fsTVNrqz48h8a9ajYSTKfwaxG16GbHzxrDcsarkBkbR6NYdGeoCZ9KgNcNMYPLV9RPkLFwBPLHxDxyTmBfqn5L75zqftETuAadKr8FHEYZrVPZ6kn6gdiZbzMwghxRy2g4wpTdby4jnxhA42UH7JJzMibgMNBW4yvzw8EaguPLVja6xsxx43yihw5DEzMGzL7HKWYUs6uVugK1C8Feh3KUX9kpea5xpLXX5oZCV47W6cnTrJfJD3"
COINFLIP_ERGO_TREE = "19d8010c04000200020104000404040005c20105640400040004000564d805d601cdeee4c6a7040ed602e4c6a7090ed603e4c6a70704d604cdeee4c6a7050ed605c1a7eb02ea02ea027201d193cbb3720283010295937203730073017302e4c6a7060ed195939e7eb2cbb3db6902db6503fe72027303000473047203d801d606b2a5730500ed93c27206d0720492c172069d9c720573067307d801d606b2a5730800ed93c27206d0720192c172067205ea02ea02ea02d192a3e4c6a708047204d193c2b2a5730900d07204d192c1b2a5730a009972059d7205730b"

# Register layout (must match coinflip_v2.es and frontend coinflipService.ts)
# R4: housePubKey (Coll[Byte])     — 33-byte compressed public key
# R5: playerPubKey (Coll[Byte])    — 33-byte compressed public key
# R6: commitmentHash (Coll[Byte])  — blake2b256(secret || choice_byte)
# R7: playerChoice (Int)           — 0=heads, 1=tails
# R8: timeoutHeight (Int)          — block height for refund
# R9: playerSecret (Coll[Byte])    — player's random secret bytes


# ─── Response Models (match frontend types/Game.ts) ────────────────


class GameChoice(BaseModel):
    gameType: str = "coinflip"
    side: Optional[str] = None
    rollTarget: Optional[int] = None
    rows: Optional[int] = None


class GameOutcome(BaseModel):
    gameType: str = "coinflip"
    result: Optional[str] = None
    rngValue: Optional[int] = None
    slot: Optional[int] = None
    multiplier: Optional[float] = None


class BetRecord(BaseModel):
    betId: str
    txId: str
    boxId: str = ""
    playerAddress: str
    gameType: str = "coinflip"
    choice: GameChoice = Field(default_factory=GameChoice)
    betAmount: str
    outcome: str = "pending"
    actualOutcome: Optional[GameOutcome] = None
    payout: str = "0"
    payoutMultiplier: float = 0.97
    timestamp: str
    blockHeight: int = 0
    resolvedAtHeight: Optional[int] = None


class PlaceBetRequest(BaseModel):
    address: str
    amount: str
    choice: int  # 0 = Heads, 1 = Tails
    commitment: str
    betId: str
    secret: str = ""  # Player's random secret (hex). Required for on-chain bets.
    onchain: bool = False  # If true, create PendingBetBox on-chain via node

    @field_validator("address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        try:
            return validate_ergo_address(v)
        except ErgoValidationError as e:
            raise ValueError(str(e))

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: str) -> str:
        try:
            amount = int(v)
        except (ValueError, TypeError):
            raise ValueError("amount must be a valid integer string (nanoERG)")
        if amount <= 0:
            raise ValueError("amount must be positive (nanoERG)")
        if amount < 1_000_000:
            raise ValueError("minimum bet is 0.001 ERG (1,000,000 nanoERG)")
        if amount > 100_000_000_000:
            raise ValueError("maximum bet is 100 ERG (100,000,000,000 nanoERG)")
        return v

    @field_validator("choice")
    @classmethod
    def validate_choice(cls, v: int) -> int:
        if v not in (0, 1):
            raise ValueError("choice must be 0 (Heads) or 1 (Tails)")
        return v

    @field_validator("commitment")
    @classmethod
    def validate_commitment(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("commitment is required")
        v = v.strip().lower()
        if len(v) != 64:
            raise ValueError("commitment must be a 64-character hex string (blake2b256)")
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("commitment must be valid hex")
        return v

    @field_validator("betId")
    @classmethod
    def validate_bet_id(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("betId is required")
        return v.strip()


class PlaceBetResponse(BaseModel):
    success: bool = True
    txId: str = ""
    betId: str = ""
    message: str = ""


class PlayerStats(BaseModel):
    address: str
    totalBets: int = 0
    wins: int = 0
    losses: int = 0
    pending: int = 0
    winRate: float = 0.0
    totalWagered: str = "0"
    totalWon: str = "0"
    totalLost: str = "0"
    netPnL: str = "0"
    biggestWin: str = "0"
    currentStreak: int = 0
    longestWinStreak: int = 0
    longestLossStreak: int = 0
    compPoints: int = 0
    compTier: str = "Bronze"


class LeaderboardEntry(BaseModel):
    rank: int
    address: str
    totalBets: int = 0
    netPnL: str = "0"
    winRate: float = 0.0
    compPoints: int = 0
    compTier: str = "Bronze"


class LeaderboardResponse(BaseModel):
    players: List[LeaderboardEntry]
    totalPlayers: int = 0
    sortBy: str = "netPnL"


class CompPointsResponse(BaseModel):
    address: str
    points: int = 0
    tier: str = "Bronze"
    tierProgress: float = 0.0
    nextTier: str = "Silver"
    pointsToNextTier: int = 100
    totalEarned: int = 0
    benefits: List[str] = []


# ─── In-memory game store (PoC — no database) ──────────────────────

_bets: List[dict] = []
_pool_stats = {
    "liquidity": "50000000000000",  # 50,000 ERG in nanoERG
    "totalBets": 0,
    "playerWins": 0,
    "houseWins": 0,
    "totalFees": "0",
}


# ─── Routes ───────────────────────────────────────────────────────

@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard():
    """Leaderboard for Leaderboard.tsx."""
    return LeaderboardResponse(
        players=[],
        totalPlayers=0,
        sortBy="netPnL",
    )


@router.get("/history/{address}", response_model=List[BetRecord])
async def get_history(address: str):
    """Bet history for GameHistory.tsx."""
    return [BetRecord(**b) for b in _bets if b["playerAddress"] == address]


@router.get("/player/stats/{address}", response_model=PlayerStats)
async def get_player_stats(address: str):
    """Player stats for StatsDashboard.tsx."""
    player_bets = [b for b in _bets if b["playerAddress"] == address]
    wins = sum(1 for b in player_bets if b["outcome"] == "win")
    losses = sum(1 for b in player_bets if b["outcome"] == "loss")
    pending = sum(1 for b in player_bets if b["outcome"] == "pending")
    total = len(player_bets)
    win_rate = (wins / total * 100) if total > 0 else 0.0

    total_wagered = sum(int(b["betAmount"]) for b in player_bets)
    total_won = sum(int(b["payout"]) for b in player_bets if b["outcome"] == "win")
    total_lost = sum(int(b["betAmount"]) for b in player_bets if b["outcome"] == "loss")
    net_pnl = total_won - total_lost
    biggest_win = max((int(b["payout"]) for b in player_bets if b["outcome"] == "win"), default=0)

    # Streaks
    current_streak = 0
    longest_win = 0
    longest_loss = 0
    streak = 0
    streak_type = None
    for b in reversed(player_bets):
        if b["outcome"] in ("win", "loss"):
            if streak_type is None:
                streak_type = b["outcome"]
                streak = 1
            elif b["outcome"] == streak_type:
                streak += 1
            else:
                break
    current_streak = streak if streak_type == "win" else -streak

    # Full streak analysis
    ws = ls = 0
    cur = 0
    cur_type = None
    for b in player_bets:
        if b["outcome"] in ("win", "loss"):
            if cur_type == b["outcome"]:
                cur += 1
            else:
                if cur_type == "win":
                    ws = max(ws, cur)
                elif cur_type == "loss":
                    ls = max(ls, cur)
                cur_type = b["outcome"]
                cur = 1
    if cur_type == "win":
        ws = max(ws, cur)
    elif cur_type == "loss":
        ls = max(ls, cur)

    # Comp points: 1 point per 0.01 ERG wagered
    comp_points = total_wagered // 10000000  # 0.01 ERG = 10M nanoERG
    comp_tier = "Bronze"
    if comp_points >= 10000:
        comp_tier = "Diamond"
    elif comp_points >= 1000:
        comp_tier = "Gold"
    elif comp_points >= 100:
        comp_tier = "Silver"

    return PlayerStats(
        address=address,
        totalBets=total,
        wins=wins,
        losses=losses,
        pending=pending,
        winRate=win_rate,
        totalWagered=str(total_wagered),
        totalWon=str(total_won),
        totalLost=str(total_lost),
        netPnL=str(net_pnl),
        biggestWin=str(biggest_win),
        currentStreak=current_streak,
        longestWinStreak=longest_win,
        longestLossStreak=longest_loss,
        compPoints=comp_points,
        compTier=comp_tier,
    )


@router.get("/player/comp/{address}", response_model=CompPointsResponse)
async def get_player_comp(address: str):
    """Comp points for CompPoints.tsx."""
    player_bets = [b for b in _bets if b["playerAddress"] == address]
    total_wagered = sum(int(b["betAmount"]) for b in player_bets)
    comp_points = total_wagered // 10000000

    tier_thresholds = {"Bronze": 0, "Silver": 100, "Gold": 1000, "Diamond": 10000}
    tier_order = ["Bronze", "Silver", "Gold", "Diamond"]

    current_tier = "Bronze"
    for tier, threshold in tier_thresholds.items():
        if comp_points >= threshold:
            current_tier = tier

    tier_idx = tier_order.index(current_tier)
    is_max = tier_idx >= len(tier_order) - 1

    if is_max:
        next_tier = ""
        points_to_next = 0
        progress = 1.0
    else:
        next_tier = tier_order[tier_idx + 1]
        next_threshold = tier_thresholds[next_tier]
        current_threshold = tier_thresholds[current_tier]
        points_to_next = next_threshold - comp_points
        progress = (comp_points - current_threshold) / max(next_threshold - current_threshold, 1)

    benefits_map = {
        "Bronze": ["Basic access"],
        "Silver": ["Reduced house edge", "Priority support"],
        "Gold": ["Further reduced edge", "Exclusive tournaments", "Dedicated support"],
        "Diamond": ["Best house edge", "VIP tournaments", "Personal manager", "Early access"],
    }

    return CompPointsResponse(
        address=address,
        points=comp_points,
        tier=current_tier,
        tierProgress=round(progress, 4),
        nextTier=next_tier,
        pointsToNextTier=points_to_next,
        totalEarned=comp_points,
        benefits=benefits_map.get(current_tier, []),
    )


@router.get("/contract-info")
async def contract_info():
    """Return compiled coinflip contract address and register layout.
    Frontend needs this to build transactions targeting the contract."""
    return {
        "p2sAddress": COINFLIP_P2S_ADDRESS,
        "ergoTree": COINFLIP_ERGO_TREE,
        "registers": {
            "R4": "housePubKey (Coll[Byte])",
            "R5": "playerPubKey (Coll[Byte])",
            "R6": "commitmentHash (Coll[Byte])",
            "R7": "playerChoice (Int)",
            "R8": "timeoutHeight (Int)",
            "R9": "playerSecret (Coll[Byte])",
        },
    }


@router.post("/place-bet", response_model=PlaceBetResponse)
async def place_bet(req: PlaceBetRequest):
    """Place a coinflip bet from BetForm.tsx / CoinFlipGame.tsx.

    When onchain=True and secret is provided, creates a PendingBetBox on-chain
    via the Ergo node /wallet/payment/send endpoint. Otherwise, records the bet
    in-memory (PoC mode).
    """
    now = datetime.now(timezone.utc).isoformat()

    side = "heads" if req.choice == 0 else "tails"

    # ─── On-chain mode (MAT-410) ─────────────────────────────────
    if req.onchain and req.secret:
        try:
            from ergo_tx_builder import (
                place_bet_onchain,
                get_house_wallet_pubkey,
                decode_ergo_address_to_pubkey,
                verify_commitment,
            )

            # Verify commitment matches secret + choice
            if not verify_commitment(req.secret, req.choice, req.commitment):
                return PlaceBetResponse(
                    success=False,
                    txId="",
                    betId=req.betId,
                    message="Commitment verification failed: blake2b256(secret || choice) != commitment",
                )

            # Get public keys from addresses
            house_pubkey = await get_house_wallet_pubkey()
            player_pubkey = decode_ergo_address_to_pubkey(req.address)

            # Submit to ergo node
            result = await place_bet_onchain(
                bet_amount=int(req.amount),
                house_pubkey_hex=house_pubkey,
                player_pubkey_hex=player_pubkey,
                commitment_hex=req.commitment,
                choice=req.choice,
                secret_hex=req.secret,
            )

            if result["success"]:
                # Record in-memory bet with txId
                bet = {
                    "betId": req.betId,
                    "txId": result["txId"],
                    "boxId": "",
                    "playerAddress": req.address,
                    "gameType": "coinflip",
                    "choice": {"gameType": "coinflip", "side": side},
                    "betAmount": req.amount,
                    "outcome": "pending",
                    "actualOutcome": None,
                    "payout": "0",
                    "payoutMultiplier": 0.97,
                    "timestamp": now,
                    "blockHeight": 0,
                    "resolvedAtHeight": None,
                }
                _bets.append(bet)
                _pool_stats["totalBets"] += 1
                fee = int(req.amount) * 3 // 100
                _pool_stats["totalFees"] = str(int(_pool_stats["totalFees"]) + fee)

                # Track tx for off-chain bot (MAT-416)
                _track_tx_for_bot(result["txId"])

                return PlaceBetResponse(
                    success=True,
                    txId=result["txId"],
                    betId=req.betId,
                    message=result["message"],
                )
            else:
                return PlaceBetResponse(
                    success=False,
                    txId="",
                    betId=req.betId,
                    message=f"On-chain bet failed: {result['message']}",
                )

        except Exception as e:
            return PlaceBetResponse(
                success=False,
                txId="",
                betId=req.betId,
                message=f"Error creating on-chain bet: {str(e)}",
            )

    # ─── In-memory mode (PoC) ────────────────────────────────────
    bet = {
        "betId": req.betId,
        "txId": "",  # Will be filled when tx is actually broadcast
        "boxId": "",
        "playerAddress": req.address,
        "gameType": "coinflip",
        "choice": {"gameType": "coinflip", "side": side},
        "betAmount": req.amount,
        "outcome": "pending",
        "actualOutcome": None,
        "payout": "0",
        "payoutMultiplier": 0.97,
        "timestamp": now,
        "blockHeight": 0,
        "resolvedAtHeight": None,
    }
    _bets.append(bet)

    # Update pool stats
    _pool_stats["totalBets"] += 1

    # Calculate fee
    fee = int(req.amount) * 3 // 100  # 3% house edge
    _pool_stats["totalFees"] = str(int(_pool_stats["totalFees"]) + fee)

    return PlaceBetResponse(
        success=True,
        txId="",  # In PoC, no actual tx broadcast
        betId=req.betId,
        message="Bet placed. Waiting for on-chain confirmation.",
    )


# ─── Bot-facing endpoints (MAT-416) ────────────────────────────────

_pending_tx_tracker: List[str] = []  # Track bet tx IDs for the bot


def _track_tx_for_bot(tx_id: str):
    """
    Internal helper: register a bet tx ID for the off-chain bot.

    Writes to both the in-memory list and the shared pending_txs.json file.
    Called automatically when on-chain bets are placed.
    """
    if tx_id not in _pending_tx_tracker:
        _pending_tx_tracker.append(tx_id)
    # Persist to file for the separate bot process
    try:
        import json as _json
        from pathlib import Path as _Path
        bot_dir = _Path(__file__).parent.parent / "off-chain-bot"
        bot_dir.mkdir(exist_ok=True)
        tx_file = bot_dir / "pending_txs.json"
        existing = []
        if tx_file.exists():
            existing = _json.loads(tx_file.read_text()).get("tx_ids", [])
        if tx_id not in existing:
            existing.append(tx_id)
            tx_file.write_text(_json.dumps({"tx_ids": existing}))
    except Exception:
        pass


@router.post("/bot/track-tx")
async def track_bet_tx(tx_id: str):
    """
    Register a bet transaction ID for the off-chain bot to process.

    The bot polls this endpoint (or reads from a shared file) to find
    PendingBet boxes that need revealing. This bridges the gap between
    the frontend placing a bet and the bot discovering it.

    MAT-416: Fix 'bet transaction submitted but no after effect'
    """
    _track_tx_for_bot(tx_id)
    return {"success": True, "tracked_txs": len(_pending_tx_tracker)}


@router.get("/bot/pending-txs")
async def get_pending_txs():
    """Return list of tracked pending bet transaction IDs."""
    return {"tx_ids": _pending_tx_tracker}


@router.post("/bot/untrack-tx")
async def untrack_bet_tx(tx_id: str):
    """Remove a processed bet tx ID from tracking."""
    if tx_id in _pending_tx_tracker:
        _pending_tx_tracker.remove(tx_id)
    # Also remove from file
    try:
        import json as _json
        from pathlib import Path as _Path
        tx_file = _Path(__file__).parent.parent / "off-chain-bot" / "pending_txs.json"
        if tx_file.exists():
            data = _json.loads(tx_file.read_text())
            txs = data.get("tx_ids", [])
            if tx_id in txs:
                txs.remove(tx_id)
                tx_file.write_text(_json.dumps({"tx_ids": txs}))
    except Exception:
        pass
    return {"success": True, "tracked_txs": len(_pending_tx_tracker)}


# ─── Bot bet resolution endpoint (MAT-419) ─────────────────────────

class ResolveBetRequest(BaseModel):
    """Payload from the off-chain bot when a bet is resolved on-chain."""
    boxId: str = ""
    txId: str = ""               # Reveal tx ID
    playerWins: Optional[bool] = None
    payoutAmount: str = "0"
    playerAddress: str = ""
    betAmount: str = "0"
    blockHeight: int = 0
    revealTxId: str = ""


class ResolveBetResponse(BaseModel):
    success: bool
    message: str = ""
    betUpdated: bool = False


@router.post("/bot/resolve-bet", response_model=ResolveBetResponse)
async def resolve_bet(request: Request, body: ResolveBetRequest):
    """
    Receive bet resolution from the off-chain bot and update bet history.

    When the bot successfully reveals a coinflip on-chain, it calls this
    endpoint so the backend can:
    1. Update the in-memory bet record (pending -> win/loss)
    2. Fire WebSocket events (bet_revealed + bet_settled) to the frontend
    3. Untrack the bet tx ID

    MAT-419: Fix bet history not updating after on-chain resolution.
    """
    import logging
    _log = logging.getLogger("duckpools.game.resolve")

    player_address = body.playerAddress.strip().lower() if body.playerAddress else ""
    bet_tx_id = body.txId.strip() if body.txId else ""  # Original place-bet tx ID
    box_id = body.boxId.strip() if body.boxId else ""

    # ── 1. Find the matching pending bet ───────────────────────────
    # Priority: match by txId > boxId > playerAddress+pending
    matched_bet = None
    matched_idx = None

    # Strategy 1: Match by txId (most reliable — one-to-one mapping)
    if bet_tx_id:
        for i, bet in enumerate(_bets):
            if bet.get("txId", "") == bet_tx_id and bet.get("outcome") == "pending":
                matched_bet = bet
                matched_idx = i
                _log.info("resolve_bet: matched by txId", tx_id=bet_tx_id[:16])
                break

    # Strategy 2: Match by boxId
    if matched_bet is None and box_id:
        for i, bet in enumerate(_bets):
            if bet.get("boxId", "") == box_id and bet.get("outcome") == "pending":
                matched_bet = bet
                matched_idx = i
                _log.info("resolve_bet: matched by boxId", box_id=box_id[:16])
                break

    # Strategy 3: Match by playerAddress + pending status
    if matched_bet is None and player_address:
        for i, bet in enumerate(_bets):
            if bet.get("playerAddress", "").lower() == player_address and bet.get("outcome") == "pending":
                matched_bet = bet
                matched_idx = i
                _log.info("resolve_bet: matched by playerAddress", player=player_address[:16])
                break

    # Strategy 4: Last resort — any pending bet
    if matched_bet is None:
        for i, bet in enumerate(_bets):
            if bet.get("outcome") == "pending":
                matched_bet = bet
                matched_idx = i
                _log.warning(
                    "resolve_bet: fallback to first pending bet",
                    bet_id=bet.get("betId", "")[:16],
                )
                break

    # ── 2. Update the bet record ───────────────────────────────────
    bet_updated = False
    if matched_bet is not None:
        outcome = "win" if body.playerWins else "loss"
        rng_result = "heads" if matched_bet.get("choice", {}).get("side") == "heads" else "tails"

        _bets[matched_idx]["outcome"] = outcome
        _bets[matched_idx]["resolvedAtHeight"] = body.blockHeight
        _bets[matched_idx]["payout"] = body.payoutAmount if body.playerWins else "0"
        _bets[matched_idx]["boxId"] = body.boxId
        _bets[matched_idx]["actualOutcome"] = {
            "gameType": "coinflip",
            "result": rng_result,
            "multiplier": 1.94 if body.playerWins else 0.0,
        }

        # Update pool stats
        if body.playerWins:
            _pool_stats["playerWins"] += 1
        else:
            _pool_stats["houseWins"] += 1

        bet_updated = True
        _log.info(
            "bet_resolved",
            bet_id=matched_bet.get("betId", "")[:16],
            outcome=outcome,
            player=player_address[:16],
        )
    else:
        _log.warning(
            "resolve_bet: no matching pending bet found",
            player=player_address[:16] if player_address else "unknown",
            box_id=body.boxId[:16] if body.boxId else "unknown",
        )

    # ── 3. Fire WebSocket events ───────────────────────────────────
    ws_manager = getattr(request.app.state, "ws_manager", None)
    if ws_manager and player_address:
        try:
            from game_events import (
                make_bet_revealed_event,
                make_bet_settled_event,
                broadcast_bet_event,
            )

            rng_result = "heads" if (matched_bet or {}).get("choice", {}).get("side") == "heads" else "tails"

            # bet_revealed event
            revealed_event = make_bet_revealed_event(
                bet_id=(matched_bet or {}).get("betId", body.boxId),
                player_address=player_address,
                rng_result=rng_result,
            )
            sent1 = await broadcast_bet_event(ws_manager, revealed_event, player_address)

            # bet_settled event
            outcome = "win" if body.playerWins else "loss"
            settled_event = make_bet_settled_event(
                bet_id=(matched_bet or {}).get("betId", body.boxId),
                player_address=player_address,
                outcome=outcome,
                payout_nanoerg=int(body.payoutAmount) if body.payoutAmount else 0,
                player_choice=rng_result,
                rng_result=rng_result,
            )
            sent2 = await broadcast_bet_event(ws_manager, settled_event, player_address)

            _log.info(
                "ws_events_sent",
                revealed_to=sent1,
                settled_to=sent2,
                player=player_address[:16],
            )
        except Exception as e:
            _log.error("ws_broadcast_failed", error=str(e))

    # ── 4. Untrack resolved tx IDs ────────────────────────────────
    # The revealTxId is the new reveal transaction — untrack it
    if body.revealTxId:
        if body.revealTxId in _pending_tx_tracker:
            _pending_tx_tracker.remove(body.revealTxId)
    # The txId is the original bet placement tx — also untrack it
    if bet_tx_id and bet_tx_id in _pending_tx_tracker:
        _pending_tx_tracker.remove(bet_tx_id)
        # Also clean up the shared file
        try:
            import json as _json
            from pathlib import Path as _Path
            tx_file = _Path(__file__).parent.parent / "off-chain-bot" / "pending_txs.json"
            if tx_file.exists():
                data = _json.loads(tx_file.read_text())
                txs = data.get("tx_ids", [])
                if bet_tx_id in txs:
                    txs.remove(bet_tx_id)
                    tx_file.write_text(_json.dumps({"tx_ids": txs}))
        except Exception:
            pass

    return ResolveBetResponse(
        success=True,
        message=f"Bet resolved: {'win' if body.playerWins else 'loss'}",
        betUpdated=bet_updated,
    )
