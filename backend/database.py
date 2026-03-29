"""
DuckPools - Database Module

Database implementation for replacing the in-memory store (PoC) with a proper PostgreSQL database.
"""

import asyncpg
from typing import List, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timezone
from decimal import Decimal

# Database connection configuration
DB_CONFIG = {
    "user": "duckpools",
    "password": "duckpools_password",
    "database": "duckpools",
    "host": "localhost",
    "port": 5432
}

# Database connection pool
pool = None

async def init_db():
    """Initialize the database connection pool."""
    global pool
    pool = await asyncpg.create_pool(**DB_CONFIG)
    print("Database connection pool initialized")

async def close_db():
    """Close the database connection pool."""
    if pool:
        await pool.close()
        print("Database connection pool closed")

# Database models
class BetRecord(BaseModel):
    betId: str
    txId: str
    boxId: str = ""
    playerAddress: str
    gameType: str = "coinflip"
    choice: Dict[str, Any] = {"gameType": "coinflip", "side": None}
    betAmount: str
    outcome: str = "pending"
    actualOutcome: Dict[str, Any] = None
    payout: str = "0"
    payoutMultiplier: float = 0.97
    timestamp: str
    blockHeight: int = 0
    resolvedAtHeight: int = None

class PoolStats(BaseModel):
    liquidity: str = "50000000000000"  # 50,000 ERG in nanoERG
    totalBets: int = 0
    playerWins: int = 0
    houseWins: int = 0
    totalFees: str = "0"

# Database operations
async def create_bet_table():
    """Create the bets table if it doesn't exist."""
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bets (
                betId VARCHAR(255) PRIMARY KEY,
                txId VARCHAR(255),
                boxId VARCHAR(255),
                playerAddress VARCHAR(255) NOT NULL,
                gameType VARCHAR(50) NOT NULL,
                choice JSONB NOT NULL,
                betAmount VARCHAR(255) NOT NULL,
                outcome VARCHAR(50) NOT NULL DEFAULT 'pending',
                actualOutcome JSONB,
                payout VARCHAR(255) NOT NULL DEFAULT '0',
                payoutMultiplier FLOAT NOT NULL DEFAULT 0.97,
                timestamp TIMESTAMP NOT NULL,
                blockHeight INTEGER NOT NULL DEFAULT 0,
                resolvedAtHeight INTEGER
            )
        """)

async def create_pool_stats_table():
    """Create the pool stats table if it doesn't exist."""
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS pool_stats (
                id SERIAL PRIMARY KEY,
                liquidity VARCHAR(255) NOT NULL,
                totalBets INTEGER NOT NULL DEFAULT 0,
                playerWins INTEGER NOT NULL DEFAULT 0,
                houseWins INTEGER NOT NULL DEFAULT 0,
                totalFees VARCHAR(255) NOT NULL DEFAULT '0'
            )
        """)

async def insert_or_update_pool_stats(stats: PoolStats):
    """Insert or update pool statistics."""
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO pool_stats (liquidity, totalBets, playerWins, houseWins, totalFees)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (id) DO UPDATE SET
                liquidity = EXCLUDED.liquidity,
                totalBets = EXCLUDED.totalBets,
                playerWins = EXCLUDED.playerWins,
                houseWins = EXCLUDED.houseWins,
                totalFees = EXCLUDED.totalFees
        """, stats.liquidity, stats.totalBets, stats.playerWins, stats.houseWins, stats.totalFees)

async def get_pool_stats() -> PoolStats:
    """Get current pool statistics."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM pool_stats ORDER BY id DESC LIMIT 1")
        if row:
            return PoolStats(
                liquidity=row['liquidity'],
                totalBets=row['totalBets'],
                playerWins=row['playerWins'],
                houseWins=row['houseWins'],
                totalFees=row['totalFees']
            )
        # Return default stats if no row exists
        return PoolStats()

async def insert_bet(bet: BetRecord):
    """Insert a new bet into the database."""
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO bets (betId, txId, boxId, playerAddress, gameType, choice, betAmount, outcome, actualOutcome, payout, payoutMultiplier, timestamp, blockHeight, resolvedAtHeight)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        """, bet.betId, bet.txId, bet.boxId, bet.playerAddress, bet.gameType, bet.choice, bet.betAmount, bet.outcome, bet.actualOutcome, bet.payout, bet.payoutMultiplier, bet.timestamp, bet.blockHeight, bet.resolvedAtHeight)

async def get_bets_by_address(address: str) -> List[BetRecord]:
    """Get all bets for a specific player address."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM bets WHERE playerAddress = $1", address)
        return [BetRecord(**row) for row in rows]

async def update_bet_outcome(betId: str, outcome: str, actualOutcome: Dict[str, Any], payout: str, resolvedAtHeight: int):
    """Update the outcome of a bet."""
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE bets 
            SET outcome = $1, actualOutcome = $2, payout = $3, resolvedAtHeight = $4
            WHERE betId = $5
        """, outcome, actualOutcome, payout, resolvedAtHeight, betId)

async def get_all_bets() -> List[BetRecord]:
    """Get all bets (for testing and admin purposes)."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM bets")
        return [BetRecord(**row) for row in rows]

async def get_bet_count() -> int:
    """Get total number of bets."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT COUNT(*) FROM bets")
        return row['count']

async def get_player_win_rate(address: str) -> float:
    """Calculate win rate for a specific player."""
    async with pool.acquire() as conn:
        result = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN outcome = 'win' THEN 1 ELSE 0 END) as wins
            FROM bets 
            WHERE playerAddress = $1 AND outcome IN ('win', 'loss')
        """, address)
        
        total = result['total'] or 0
        wins = result['wins'] or 0
        
        return (wins / total * 100) if total > 0 else 0.0

async def get_player_stats(address: str) -> Dict[str, Any]:
    """Get comprehensive player statistics."""
    async with pool.acquire() as conn:
        # Get basic stats
        basic_stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN outcome = 'win' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 'loss' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN outcome = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN outcome = 'win' THEN payout::numeric ELSE 0 END) as total_won,
                SUM(CASE WHEN outcome = 'loss' THEN betAmount::numeric ELSE 0 END) as total_lost
            FROM bets 
            WHERE playerAddress = $1
        """, address)
        
        total = basic_stats['total'] or 0
        wins = basic_stats['wins'] or 0
        losses = basic_stats['losses'] or 0
        pending = basic_stats['pending'] or 0
        total_won = basic_stats['total_won'] or 0
        total_lost = basic_stats['total_lost'] or 0
        
        # Calculate win rate
        win_rate = (wins / total * 100) if total > 0 else 0.0
        
        # Calculate net PnL
        net_pnl = total_won - total_lost
        
        # Calculate biggest win
        biggest_win = await conn.fetchval("""
            SELECT MAX(payout::numeric) 
            FROM bets 
            WHERE playerAddress = $1 AND outcome = 'win'
        """, address) or 0
        
        # Calculate streaks (simplified - in production this would be more complex)
        current_streak = 0
        longest_win = 0
        longest_loss = 0
        
        # Get recent bets to calculate current streak
        recent_bets = await conn.fetch("""
            SELECT outcome 
            FROM bets 
            WHERE playerAddress = $1 AND outcome IN ('win', 'loss')
            ORDER BY timestamp DESC 
            LIMIT 10
        """, address)
        
        if recent_bets:
            streak = 0
            streak_type = None
            for bet in recent_bets:
                outcome = bet['outcome']
                if streak_type is None:
                    streak_type = outcome
                    streak = 1
                elif outcome == streak_type:
                    streak += 1
                else:
                    break
            current_streak = streak if streak_type == "win" else -streak
        
        # Calculate comp points (1 point per 0.01 ERG wagered)
        comp_points = int(total_lost / 10000000)  # 0.01 ERG = 10M nanoERG
        
        # Determine comp tier
        if comp_points >= 10000:
            comp_tier = "Diamond"
        elif comp_points >= 1000:
            comp_tier = "Gold"
        elif comp_points >= 100:
            comp_tier = "Silver"
        else:
            comp_tier = "Bronze"
        
        return {
            "address": address,
            "totalBets": total,
            "wins": wins,
            "losses": losses,
            "pending": pending,
            "winRate": win_rate,
            "totalWagered": str(int(total_won + total_lost)),
            "totalWon": str(int(total_won)),
            "totalLost": str(int(total_lost)),
            "netPnL": str(int(net_pnl)),
            "biggestWin": str(int(biggest_win)),
            "currentStreak": current_streak,
            "longestWinStreak": longest_win,
            "longestLossStreak": longest_loss,
            "compPoints": comp_points,
            "compTier": comp_tier
        }

async def get_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    """Get leaderboard of top players."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                playerAddress,
                COUNT(*) as totalBets,
                SUM(CASE WHEN outcome = 'win' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 'loss' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN outcome = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN outcome = 'win' THEN payout::numeric ELSE 0 END) as total_won,
                SUM(CASE WHEN outcome = 'loss' THEN betAmount::numeric ELSE 0 END) as total_lost
            FROM bets 
            WHERE outcome IN ('win', 'loss')
            GROUP BY playerAddress
            ORDER BY (total_won - total_lost) DESC
            LIMIT $1
        """, limit)
        
        leaderboard = []
        for i, row in enumerate(rows, 1):
            total_won = row['total_won'] or 0
            total_lost = row['total_lost'] or 0
            net_pnl = total_won - total_lost
            
            leaderboard.append({
                "rank": i,
                "address": row['playerAddress'],
                "totalBets": row['totalBets'],
                "wins": row['wins'],
                "losses": row['losses'],
                "pending": row['pending'],
                "winRate": (row['wins'] / row['totalBets'] * 100) if row['totalBets'] > 0 else 0.0,
                "totalWagered": str(int(total_won + total_lost)),
                "totalWon": str(int(total_won)),
                "totalLost": str(int(total_lost)),
                "netPnL": str(int(net_pnl)),
                "biggestWin": "0",
                "currentStreak": 0,
                "longestWinStreak": 0,
                "longestLossStreak": 0,
                "compPoints": 0,
                "compTier": "Bronze"
            })
        
        return leaderboard

async def get_total_players() -> int:
    """Get total number of unique players."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT COUNT(DISTINCT playerAddress) FROM bets")
        return row['count'] or 0

async def migrate_from_in_memory(bets: List[Dict[str, Any]]):
    """Migrate data from in-memory store to database."""
    async with pool.acquire() as conn:
        for bet in bets:
            await conn.execute("""
                INSERT INTO bets (betId, txId, boxId, playerAddress, gameType, choice, betAmount, outcome, actualOutcome, payout, payoutMultiplier, timestamp, blockHeight, resolvedAtHeight)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                ON CONFLICT (betId) DO NOTHING
            """, bet['betId'], bet['txId'], bet['boxId'], bet['playerAddress'], bet['gameType'], bet['choice'], bet['betAmount'], bet['outcome'], bet['actualOutcome'], bet['payout'], bet['payoutMultiplier'], bet['timestamp'], bet['blockHeight'], bet['resolvedAtHeight'])