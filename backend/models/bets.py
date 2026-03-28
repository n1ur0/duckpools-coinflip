"""Pydantic models and ORM schema for bet history API endpoints.

This module defines the request/response models for the bet history API,
including pagination, filtering, and statistics aggregation, along with the
ORM model for storing bet data in the database.
"""

from datetime import datetime
from typing import List, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field, validator
from decimal import Decimal

from sqlalchemy import String, Numeric, DateTime, Integer, Index, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db import Base


class GameType(str, Enum):
    """Supported game types for bet history."""
    COINFLIP = "coinflip"
    DICE = "dice"
    PLINKO = "plinko"


class BetResult(str, Enum):
    """Possible bet outcomes."""
    WIN = "win"
    LOSE = "lose"


class BetFilterParams(BaseModel):
    """Query parameters for filtering bet history."""
    game_type: Optional[GameType] = Field(None, description="Filter by game type")
    result: Optional[BetResult] = Field(None, description="Filter by bet result (win/lose)")
    start_date: Optional[datetime] = Field(None, description="Start date for filtering (UTC)")
    end_date: Optional[datetime] = Field(None, description="End date for filtering (UTC)")

    @validator('end_date')
    def validate_end_date(cls, v, values):
        """Ensure end_date is after start_date if both are provided."""
        if v and 'start_date' in values and values['start_date']:
            if v <= values['start_date']:
                raise ValueError("end_date must be after start_date")
        return v


class BetResponse(BaseModel):
    """Individual bet response model."""
    id: str = Field(..., description="Unique bet identifier")
    game_type: GameType = Field(..., description="Type of game")
    player_address: str = Field(..., description="Player's Ergo address")
    amount: Decimal = Field(..., description="Bet amount in ERG")
    result: BetResult = Field(..., description="Bet result (win/lose)")
    payout: Decimal = Field(..., description="Payout amount (0 for losses)")
    timestamp: datetime = Field(..., description="Bet timestamp (UTC)")

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v)
        }


class BetListResponse(BaseModel):
    """Paginated bet history response."""
    bets: List[BetResponse] = Field(..., description="List of bets")
    total_count: int = Field(..., description="Total number of bets matching filters")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, le=100, description="Number of bets per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v)
        }


class BetStats(BaseModel):
    """Basic bet statistics."""
    total_bets: int = Field(..., ge=0, description="Total number of bets")
    total_wagered: Decimal = Field(..., ge=0, description="Total amount wagered")
    total_won: Decimal = Field(..., ge=0, description="Total amount won")
    win_rate: float = Field(..., ge=0, le=1, description="Win rate (0.0 to 1.0)")
    house_profit: Decimal = Field(..., description="House profit/loss")

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v)
        }


class BetStatsByGame(BaseModel):
    """Bet statistics grouped by game type."""
    game_type: GameType = Field(..., description="Game type")
    stats: BetStats = Field(..., description="Statistics for this game type")

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v)
        }


class Bet(Base):
    """ORM model for storing bet history in the database.
    
    This table tracks all bets placed on the platform, including game type,
    player address, amount, result, and payout information.
    """
    __tablename__ = "bets"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    game_type: Mapped[GameType] = mapped_column(SQLEnum(GameType), nullable=False, index=True)
    player_address: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    result: Mapped[BetResult] = mapped_column(SQLEnum(BetResult), nullable=False, index=True)
    payout: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    
    # Optional metadata
    client_seed: Mapped[str] = mapped_column(String(64), nullable=True)
    server_seed: Mapped[str] = mapped_column(String(64), nullable=True)
    nonce: Mapped[int] = mapped_column(Integer, nullable=True)
    
    # Game-specific data (stored as JSON string)
    game_data: Mapped[str] = mapped_column(Text, nullable=True)
    
    __table_args__ = (
        Index("idx_player_timestamp", "player_address", "timestamp"),
        Index("idx_game_result", "game_type", "result"),
        Index("idx_timestamp_desc", "timestamp"),
    )


class BetStatsResponse(BaseModel):
    """Bet statistics response."""
    overall: BetStats = Field(..., description="Overall statistics")
    by_game_type: Optional[List[BetStatsByGame]] = Field(None, description="Statistics by game type (if requested)")

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v)
        }