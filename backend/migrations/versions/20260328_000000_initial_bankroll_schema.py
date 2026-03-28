"""Initial bankroll management schema.

This migration creates all tables required for the bankroll management system:
- bankroll_state: Current bankroll state and settings
- bankroll_transactions: Historical transaction records
- bankroll_alerts: Alert history
- auto_reload_events: Auto-reload history
- risk_projections: Risk analysis projections

Revision ID: 001
Revises: 
Create Date: 2026-03-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create bankroll_state table
    op.create_table(
        'bankroll_state',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('current_balance', sa.Numeric(precision=36, scale=18), nullable=False, server_default='0'),
        sa.Column('total_tv', sa.Numeric(precision=36, scale=18), nullable=False, server_default='0'),
        sa.Column('house_liquidity', sa.Numeric(precision=36, scale=18), nullable=False, server_default='0'),
        sa.Column('lp_pool_balance', sa.Numeric(precision=36, scale=18), nullable=False, server_default='0'),
        sa.Column('max_payout_capacity', sa.Numeric(precision=36, scale=18), nullable=False, server_default='0'),
        sa.Column('house_edge_percentage', sa.Numeric(precision=5, scale=2), nullable=False, server_default='3.00'),
        sa.Column('risk_of_ruin', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('kelly_fraction', sa.Numeric(precision=8, scale=6), nullable=True),
        sa.Column('auto_reload_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('min_balance_threshold', sa.Numeric(precision=36, scale=18), nullable=False, server_default='100'),
        sa.Column('reload_amount', sa.Numeric(precision=36, scale=18), nullable=False, server_default='1000'),
        sa.Column('reload_cooldown_minutes', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('last_reload_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('low_balance_threshold', sa.Numeric(precision=36, scale=18), nullable=False, server_default='50'),
        sa.Column('unusual_loss_threshold', sa.Numeric(precision=36, scale=18), nullable=False, server_default='10'),
        sa.Column('unusual_loss_window_minutes', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.utcnow()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.utcnow()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create bankroll_transactions table
    op.create_table(
        'bankroll_transactions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('tx_type', sa.Enum('deposit', 'withdrawal', 'bet_placed', 'bet_won', 'bet_lost', 
                                      'house_edge', 'auto_reload', 'lp_deposit', 'lp_withdrawal', 'adjustment', 
                                      name='transactiontype'), nullable=False),
        sa.Column('amount', sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column('balance_before', sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column('balance_after', sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column('tx_hash', sa.String(64), nullable=True),
        sa.Column('bet_id', sa.String(64), nullable=True),
        sa.Column('game_type', sa.String(50), nullable=True),
        sa.Column('lp_address', sa.String(100), nullable=True),
        sa.Column('lp_share_amount', sa.Numeric(precision=36, scale=18), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('metadata', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.utcnow()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_bankroll_transactions_tx_type', 'bankroll_transactions', ['tx_type'])
    op.create_index('idx_bankroll_transactions_created_at', 'bankroll_transactions', ['created_at'])
    op.create_index('idx_bankroll_transactions_tx_hash', 'bankroll_transactions', ['tx_hash'])
    op.create_index('idx_bankroll_transactions_bet_id', 'bankroll_transactions', ['bet_id'])
    op.create_index('idx_tx_type_created', 'bankroll_transactions', ['tx_type', 'created_at'])
    op.create_index('idx_bet_id_game', 'bankroll_transactions', ['bet_id', 'game_type'])
    
    # Create bankroll_alerts table
    op.create_table(
        'bankroll_alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alert_type', sa.Enum('low_balance', 'negative_balance', 'unusual_loss', 
                                        'auto_reload_triggered', 'reload_failed', 
                                        name='alerttype'), nullable=False),
        sa.Column('severity', sa.Enum('info', 'warning', 'error', 'critical', name='alertseverity'), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('balance_at_alert', sa.Numeric(precision=36, scale=18), nullable=True),
        sa.Column('threshold_value', sa.Numeric(precision=36, scale=18), nullable=True),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('window_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('loss_amount', sa.Numeric(precision=36, scale=18), nullable=True),
        sa.Column('acknowledged', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_by', sa.String(100), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.utcnow()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_bankroll_alerts_alert_type', 'bankroll_alerts', ['alert_type'])
    op.create_index('idx_bankroll_alerts_severity', 'bankroll_alerts', ['severity'])
    op.create_index('idx_bankroll_alerts_created_at', 'bankroll_alerts', ['created_at'])
    op.create_index('idx_alert_severity_created', 'bankroll_alerts', ['severity', 'created_at'])
    op.create_index('idx_alert_type_resolved', 'bankroll_alerts', ['alert_type', 'resolved'])
    
    # Create auto_reload_events table
    op.create_table(
        'auto_reload_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('reload_amount', sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column('balance_before_reload', sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column('balance_after_reload', sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column('trigger_reason', sa.String(200), nullable=False),
        sa.Column('balance_at_trigger', sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column('threshold_value', sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column('tx_hash', sa.String(64), nullable=True),
        sa.Column('from_address', sa.String(100), nullable=True),
        sa.Column('to_address', sa.String(100), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.utcnow()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_auto_reload_events_success', 'auto_reload_events', ['success'])
    op.create_index('idx_auto_reload_events_created_at', 'auto_reload_events', ['created_at'])
    op.create_index('idx_auto_reload_events_tx_hash', 'auto_reload_events', ['tx_hash'])
    op.create_index('idx_reload_success_created', 'auto_reload_events', ['success', 'created_at'])
    op.create_index('idx_reload_trigger_created', 'auto_reload_events', ['trigger_reason', 'created_at'])
    
    # Create risk_projections table
    op.create_table(
        'risk_projections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('current_balance', sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column('house_edge', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('expected_value', sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column('variance', sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column('standard_deviation', sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column('p1_balance', sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column('p5_balance', sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column('p25_balance', sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column('p50_balance', sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column('p75_balance', sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column('p95_balance', sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column('p99_balance', sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column('kelly_fraction', sa.Numeric(precision=8, scale=6), nullable=False),
        sa.Column('kelly_optimal_bet', sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column('risk_of_ruin', sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column('bankroll_multiple', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('num_bets_sampled', sa.Integer(), nullable=False),
        sa.Column('time_window_hours', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.utcnow()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_risk_projections_created_at', 'risk_projections', ['created_at'])
    op.create_index('idx_projection_created', 'risk_projections', ['created_at'])
    
    # Insert initial bankroll state
    op.execute("""
        INSERT INTO bankroll_state (
            id, current_balance, total_tv, house_liquidity, lp_pool_balance,
            max_payout_capacity, house_edge_percentage, auto_reload_enabled,
            min_balance_threshold, reload_amount, reload_cooldown_minutes,
            low_balance_threshold, unusual_loss_threshold, unusual_loss_window_minutes
        ) VALUES (
            1, 0, 0, 0, 0,
            0, 3.00, true,
            100, 1000, 60,
            50, 10, 5
        )
    """)


def downgrade() -> None:
    op.drop_table('risk_projections')
    op.drop_index('idx_projection_created', table_name='risk_projections')
    op.drop_index('idx_risk_projections_created_at', table_name='risk_projections')
    
    op.drop_table('auto_reload_events')
    op.drop_index('idx_reload_trigger_created', table_name='auto_reload_events')
    op.drop_index('idx_reload_success_created', table_name='auto_reload_events')
    op.drop_index('idx_auto_reload_events_tx_hash', table_name='auto_reload_events')
    op.drop_index('idx_auto_reload_events_created_at', table_name='auto_reload_events')
    op.drop_index('idx_auto_reload_events_success', table_name='auto_reload_events')
    
    op.drop_table('bankroll_alerts')
    op.drop_index('idx_alert_type_resolved', table_name='bankroll_alerts')
    op.drop_index('idx_alert_severity_created', table_name='bankroll_alerts')
    op.drop_index('idx_bankroll_alerts_created_at', table_name='bankroll_alerts')
    op.drop_index('idx_bankroll_alerts_severity', table_name='bankroll_alerts')
    op.drop_index('idx_bankroll_alerts_alert_type', table_name='bankroll_alerts')
    
    op.drop_table('bankroll_transactions')
    op.drop_index('idx_bet_id_game', table_name='bankroll_transactions')
    op.drop_index('idx_tx_type_created', table_name='bankroll_transactions')
    op.drop_index('idx_bankroll_transactions_bet_id', table_name='bankroll_transactions')
    op.drop_index('idx_bankroll_transactions_tx_hash', table_name='bankroll_transactions')
    op.drop_index('idx_bankroll_transactions_created_at', table_name='bankroll_transactions')
    op.drop_index('idx_bankroll_transactions_tx_type', table_name='bankroll_transactions')
    
    op.drop_table('bankroll_state')
