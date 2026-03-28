"""Database models for bankroll management system.

This module defines the ORM models for tracking house bankroll state,
transactions, alerts, and auto-reload events.
"""

from sqlalchemy import String, Numeric, BigInteger, DateTime, Boolean, Integer, Index, Text, Enum as SQLEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime
from decimal import Decimal
from enum import Enum
import uuid


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class TransactionType(str, Enum):
    """Types of bankroll transactions."""
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    BET_PLACED = "bet_placed"
    BET_WON = "bet_won"
    BET_LOST = "bet_lost"
    HOUSE_EDGE = "house_edge"
    AUTO_RELOAD = "auto_reload"
    LP_DEPOSIT = "lp_deposit"
    LP_WITHDRAWAL = "lp_withdrawal"
    ADJUSTMENT = "adjustment"


class AlertType(str, Enum):
    """Types of bankroll alerts."""
    LOW_BALANCE = "low_balance"
    NEGATIVE_BALANCE = "negative_balance"
    UNUSUAL_LOSS = "unusual_loss"
    AUTO_RELOAD_TRIGGERED = "auto_reload_triggered"
    RELOAD_FAILED = "reload_failed"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class BankrollState(Base):
    """Current state of the house bankroll.
    
    This table stores a single row representing the current bankroll state.
    It is updated on every transaction to maintain accurate real-time data.
    """
    __tablename__ = "bankroll_state"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    current_balance: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False, default=Decimal("0"))
    total_tv: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False, default=Decimal("0"))  # Total Value
    house_liquidity: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False, default=Decimal("0"))
    lp_pool_balance: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False, default=Decimal("0"))
    max_payout_capacity: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False, default=Decimal("0"))
    house_edge_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("3.00"))
    
    # Risk metrics
    risk_of_ruin: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=True)  # e.g., 0.0001 = 0.01%
    kelly_fraction: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=True)  # Optimal bet fraction
    
    # Auto-reload settings
    auto_reload_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    min_balance_threshold: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False, default=Decimal("100"))
    reload_amount: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False, default=Decimal("1000"))
    reload_cooldown_minutes: Mapped[int] = mapped_column(Integer, default=60)
    last_reload_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Alert thresholds
    low_balance_threshold: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False, default=Decimal("50"))
    unusual_loss_threshold: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False, default=Decimal("10"))
    unusual_loss_window_minutes: Mapped[int] = mapped_column(Integer, default=5)
    
    # Timestamps
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class BankrollTransaction(Base):
    """Historical record of all bankroll transactions.
    
    This table maintains an immutable audit trail of all bankroll movements
    including bets, deposits, withdrawals, and automatic reloads.
    """
    __tablename__ = "bankroll_transactions"
    
    id: Mapped[uuid.UUID] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tx_type: Mapped[TransactionType] = mapped_column(SQLEnum(TransactionType), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)  # Positive for incoming, negative for outgoing
    balance_before: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    
    # Reference fields
    tx_hash: Mapped[str] = mapped_column(String(64), nullable=True, index=True)  # On-chain transaction hash
    bet_id: Mapped[str] = mapped_column(String(64), nullable=True, index=True)  # Game bet identifier
    game_type: Mapped[str] = mapped_column(String(50), nullable=True)  # coinflip, dice, plinko
    
    # LP-specific fields
    lp_address: Mapped[str] = mapped_column(String(100), nullable=True)  # LP provider address
    lp_share_amount: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=True)  # Number of LP shares
    
    # Metadata
    description: Mapped[str] = mapped_column(Text, nullable=True)
    metadata: Mapped[dict] = mapped_column(Text, nullable=True)  # JSON string for additional data
    
    # Timestamps
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index("idx_tx_type_created", "tx_type", "created_at"),
        Index("idx_bet_id_game", "bet_id", "game_type"),
    )


class BankrollAlert(Base):
    """Historical record of bankroll alerts.
    
    This table tracks all alerts generated by the bankroll monitoring system,
    including low balance warnings, unusual activity detection, and auto-reload events.
    """
    __tablename__ = "bankroll_alerts"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    alert_type: Mapped[AlertType] = mapped_column(SQLEnum(AlertType), nullable=False, index=True)
    severity: Mapped[AlertSeverity] = mapped_column(SQLEnum(AlertSeverity), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Alert-specific data
    balance_at_alert: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=True)
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=True)
    window_start: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)
    window_end: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)
    loss_amount: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=True)
    
    # Resolution
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[str] = mapped_column(String(100), nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_notes: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index("idx_alert_severity_created", "severity", "created_at"),
        Index("idx_alert_type_resolved", "alert_type", "resolved"),
    )


class AutoReloadEvent(Base):
    """Historical record of automatic bankroll reload events.
    
    This table tracks all automatic reload events including the trigger condition,
    reload amount, and success/failure status.
    """
    __tablename__ = "auto_reload_events"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    reload_amount: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    balance_before_reload: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    balance_after_reload: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    
    # Trigger information
    trigger_reason: Mapped[str] = mapped_column(String(200), nullable=False)
    balance_at_trigger: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    
    # Transaction details
    tx_hash: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    from_address: Mapped[str] = mapped_column(String(100), nullable=True)
    to_address: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Error details (if failed)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    error_code: Mapped[str] = mapped_column(String(50), nullable=True)
    
    # Timestamps
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index("idx_reload_success_created", "success", "created_at"),
        Index("idx_reload_trigger_created", "trigger_reason", "created_at"),
    )


class RiskProjection(Base):
    """Variance projection for bankroll risk analysis.
    
    This table stores calculated risk projections based on historical data,
    including variance, standard deviation, and percentile estimates.
    """
    __tablename__ = "risk_projections"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    current_balance: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    house_edge: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    
    # Risk metrics
    expected_value: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    variance: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    standard_deviation: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    
    # Percentile projections (1, 5, 25, 50, 75, 95, 99)
    p1_balance: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    p5_balance: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    p25_balance: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    p50_balance: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    p75_balance: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    p95_balance: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    p99_balance: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    
    # Kelly criterion
    kelly_fraction: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    kelly_optimal_bet: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    
    # Risk of ruin
    risk_of_ruin: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    bankroll_multiple: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)  # Bankroll / standard deviation
    
    # Calculation metadata
    num_bets_sampled: Mapped[int] = mapped_column(Integer, nullable=False)
    time_window_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Timestamps
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index("idx_projection_created", "created_at"),
    )
