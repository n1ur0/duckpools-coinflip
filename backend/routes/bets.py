"""
Bet history API routes for DuckPools.

This module provides REST API endpoints for retrieving player bet history,
including pagination, filtering, and statistics aggregation.
"""

from typing import List, Optional, Union
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import selectinload

from backend.app.db import get_db
from backend.models.bets import (
    Bet, BetResponse, BetListResponse, BetStats, BetStatsResponse,
    BetStatsByGame, BetFilterParams, GameType, BetResult
)

router = APIRouter(prefix="/api/bets", tags=["bets"])


@router.get("/", response_model=BetListResponse, summary="Get paginated bet history")
async def get_bet_history(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    game_type: Optional[GameType] = Query(None, description="Filter by game type"),
    result: Optional[BetResult] = Query(None, description="Filter by bet result"),
    start_date: Optional[datetime] = Query(None, description="Start date (ISO 8601 format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO 8601 format)"),
    player_address: Optional[str] = Query(None, description="Filter by player address"),
    db: AsyncSession = Depends(get_db)
):
    """Get paginated bet history with optional filtering.
    
    Returns a paginated list of bets sorted by timestamp (newest first).
    Supports filtering by game type, result, date range, and player address.
    
    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)
        game_type: Filter by game type (coinflip, dice, plinko)
        result: Filter by result (win, lose)
        start_date: Start of date range (UTC)
        end_date: End of date range (UTC)
        player_address: Filter by specific player address
        db: Database session
        
    Returns:
        BetListResponse: Paginated bet history
        
    Raises:
        HTTPException: If date range is invalid
    """
    # Validate date range
    if start_date and end_date and start_date >= end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be before end_date"
        )
    
    # Build base query
    query = select(Bet)
    
    # Apply filters
    conditions = []
    
    if game_type:
        conditions.append(Bet.game_type == game_type)
    
    if result:
        conditions.append(Bet.result == result)
    
    if start_date:
        conditions.append(Bet.timestamp >= start_date)
    
    if end_date:
        conditions.append(Bet.timestamp <= end_date)
    
    if player_address:
        conditions.append(Bet.player_address == player_address)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # Get total count
    count_query = select(func.count(Bet.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))
    
    total_count = await db.scalar(count_query)
    
    # Apply pagination and ordering
    query = query.order_by(desc(Bet.timestamp))
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    # Execute query
    result = await db.execute(query)
    bets = result.scalars().all()
    
    # Convert to response model
    bet_responses = [
        BetResponse(
            id=bet.id,
            game_type=bet.game_type,
            player_address=bet.player_address,
            amount=bet.amount,
            result=bet.result,
            payout=bet.payout,
            timestamp=bet.timestamp
        )
        for bet in bets
    ]
    
    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size if total_count else 0
    
    return BetListResponse(
        bets=bet_responses,
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/stats", response_model=BetStatsResponse, summary="Get bet statistics")
async def get_bet_stats(
    group_by: Optional[str] = Query(
        None, 
        regex="^(game_type|none)$", 
        description="Group statistics by game type"
    ),
    start_date: Optional[datetime] = Query(None, description="Start date (ISO 8601 format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO 8601 format)"),
    player_address: Optional[str] = Query(None, description="Filter by player address"),
    db: AsyncSession = Depends(get_db)
):
    """Get aggregated bet statistics.
    
    Returns overall bet statistics including total bets, amounts wagered/won,
    and win rate. Can optionally group statistics by game type.
    
    Args:
        group_by: Group by "game_type" or "none" (default)
        start_date: Start of date range (UTC)
        end_date: End of date range (UTC)
        player_address: Filter by specific player address
        db: Database session
        
    Returns:
        BetStatsResponse: Aggregated statistics
        
    Raises:
        HTTPException: If date range is invalid
    """
    # Validate date range
    if start_date and end_date and start_date >= end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be before end_date"
        )
    
    # Build base query conditions
    conditions = []
    
    if start_date:
        conditions.append(Bet.timestamp >= start_date)
    
    if end_date:
        conditions.append(Bet.timestamp <= end_date)
    
    if player_address:
        conditions.append(Bet.player_address == player_address)
    
    # Get overall statistics
    overall_query = select(
        func.count(Bet.id).label('total_bets'),
        func.sum(Bet.amount).label('total_wagered'),
        func.sum(Bet.payout).label('total_won'),
        func.sum(
            func.case(
                (Bet.result == BetResult.WIN, 1),
                else_=0
            )
        ).label('win_count')
    )
    
    if conditions:
        overall_query = overall_query.where(and_(*conditions))
    
    overall_result = await db.execute(overall_query)
    overall_stats = overall_result.fetchone()
    
    if not overall_stats or overall_stats.total_bets == 0:
        # No bets found
        overall = BetStats(
            total_bets=0,
            total_wagered=Decimal('0'),
            total_won=Decimal('0'),
            win_rate=0.0,
            house_profit=Decimal('0')
        )
        
        if group_by == 'game_type':
            by_game_type = []
        else:
            by_game_type = None
            
        return BetStatsResponse(
            overall=overall,
            by_game_type=by_game_type
        )
    
    # Calculate overall statistics
    total_bets = int(overall_stats.total_bets)
    total_wagered = overall_stats.total_wagered or Decimal('0')
    total_won = overall_stats.total_won or Decimal('0')
    win_count = int(overall_stats.win_count or 0)
    win_rate = win_count / total_bets if total_bets > 0 else 0.0
    house_profit = total_wagered - total_won
    
    overall = BetStats(
        total_bets=total_bets,
        total_wagered=total_wagered,
        total_won=total_won,
        win_rate=win_rate,
        house_profit=house_profit
    )
    
    # Get statistics by game type if requested
    by_game_type = None
    if group_by == 'game_type':
        group_query = select(
            Bet.game_type,
            func.count(Bet.id).label('total_bets'),
            func.sum(Bet.amount).label('total_wagered'),
            func.sum(Bet.payout).label('total_won'),
            func.sum(
                func.case(
                    (Bet.result == BetResult.WIN, 1),
                    else_=0
                )
            ).label('win_count')
        )
        
        if conditions:
            group_query = group_query.where(and_(*conditions))
            
        group_query = group_query.group_by(Bet.game_type)
        
        group_result = await db.execute(group_query)
        group_stats = group_result.fetchall()
        
        by_game_type = []
        for row in group_stats:
            if row.total_bets > 0:
                game_total_bets = int(row.total_bets)
                game_total_wagered = row.total_wagered or Decimal('0')
                game_total_won = row.total_won or Decimal('0')
                game_win_count = int(row.win_count or 0)
                game_win_rate = game_win_count / game_total_bets if game_total_bets > 0 else 0.0
                game_house_profit = game_total_wagered - game_total_won
                
                game_stats = BetStats(
                    total_bets=game_total_bets,
                    total_wagered=game_total_wagered,
                    total_won=game_total_won,
                    win_rate=game_win_rate,
                    house_profit=game_house_profit
                )
                
                by_game_type.append(
                    BetStatsByGame(
                        game_type=row.game_type,
                        stats=game_stats
                    )
                )
    
    return BetStatsResponse(
        overall=overall,
        by_game_type=by_game_type
    )