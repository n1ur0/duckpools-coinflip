# DuckPools Bankroll Operations Guide

## Overview

The bankroll management system provides real-time monitoring, risk assessment,
P&L tracking, and automatic reload capabilities for the house bankroll.

## Architecture

```
api_server.py (lifespan)
├── BankrollMonitorService (services/bankroll_monitor.py)
│   ├── Wallet balance polling (Ergo node /wallet/balances)
│   ├── Snapshot history (5-min intervals)
│   └── P&L record tracking
├── BankrollAutoReload (services/bankroll_autoreload.py)
│   ├── Balance threshold monitoring
│   └── Auto-topup from reserve wallet
├── bankroll_risk.py
│   ├── Kelly Criterion calculations
│   ├── Risk-of-Ruin (Brownian motion approximation)
│   └── Variance projection (CLT)
└── BankrollManager (services/bankroll_manager.py)
    └── Unified facade for all above
```

## API Endpoints

### Real-time Status
| Endpoint | Description |
|----------|-------------|
| `GET /api/bankroll/status` | Current balance, exposure, capacity, max bet |
| `GET /api/bankroll/dashboard` | **Primary monitoring endpoint** - all metrics in one call |
| `GET /api/bankroll/metrics` | P&L, utilization, house edge stats |

### History
| Endpoint | Description |
|----------|-------------|
| `GET /api/bankroll/history?limit=50&offset=0` | Balance snapshots (paginated) |
| `GET /api/bankroll/pnl?from_ts=...&to_ts=...&limit=100` | Per-round P&L records |

### Risk Assessment
| Endpoint | Description |
|----------|-------------|
| `GET /api/bankroll/risk?bankroll_nanoerg=...&max_bet_nanoerg=...` | Full risk metrics |
| `GET /api/bankroll/projection?n_rounds=1000&avg_bet_nanoerg=...` | Variance projection |

### Auto-Reload
| Endpoint | Description |
|----------|-------------|
| `GET /api/bankroll/autoreload/config` | Current auto-reload settings |
| `POST /api/bankroll/autoreload/config` | Update settings |
| `GET /api/bankroll/autoreload/history` | Reload event history |

## Dashboard Alerts

The `/api/bankroll/dashboard` endpoint returns an `alerts` array with operational warnings:

| Code | Severity | Trigger |
|------|----------|---------|
| `HIGH_EXPOSURE` | Critical | Exposure > 80% of bankroll |
| `LOW_BANKROLL` | Critical | Balance < 10 ERG |
| `INSUFFICIENT_BANKROLL` | Critical | Safety ratio < 1.0x |
| `MODERATE_BANKROLL` | Warning | Balance < 100 ERG |
| `LOW_SAFETY_RATIO` | Warning | Safety ratio < 3.0x |
| `LOW_REALIZED_EDGE` | Warning | Realized edge < 50% of expected (after 50+ rounds) |

## Risk Model Parameters

The risk model is calibrated for DuckPools coinflip:

- **House win probability**: 50% (true coinflip)
- **Payout multiplier**: 1.94x (on player win)
- **House edge**: 3% (300 basis points)
- **Kelly fraction**: ~3.19% (very close to house edge, expected for near-even games)
- **Recommended operating bankroll**: 1/4 Kelly = use 0.8% of bankroll per max bet

### Key Metrics Interpretation

| Metric | Good Range | Danger Zone |
|--------|-----------|-------------|
| Safety Ratio | > 3.0x | < 1.0x |
| Risk of Ruin | < 1% | > 5% |
| Utilization | < 30% | > 80% |
| Realized Edge | 250-350 bps | < 150 bps |

## Auto-Reload Configuration

Configure via environment variables or the POST endpoint:

```bash
# Environment variables
AUTO_RELOAD_ENABLED=true
BANKROLL_MIN_ERG=10        # Trigger reload below this
BANKROLL_TARGET_ERG=100    # Target after reload
AUTO_RELOAD_CHECK_INTERVAL_SEC=60
RESERVE_WALLET_ADDRESS=3W...  # Wallet to fund reloads
```

Without `RESERVE_WALLET_ADDRESS`, reload runs in **dry-run mode** (logs only, no transactions).

## P&L Tracking

P&L is recorded automatically when bets are resolved. To manually record:

```python
# From the bet resolution flow
monitor.record_pnl(
    bet_id="abc123...",
    player_address="3W...",
    bet_amount_nanoerg=1_000_000_000,  # 1 ERG
    outcome="loss",  # player lost
    house_payout_nanoerg=0,  # nothing paid out
    block_height=252500,
)
```

## Operational Procedures

### Pre-Launch Checklist
1. Set `RESERVE_WALLET_ADDRESS` to a funded wallet
2. Verify `/api/bankroll/dashboard` returns data
3. Confirm auto-reload dry-run triggers (set `BANKROLL_MIN_ERG` above current balance temporarily)
4. Check risk metrics: safety ratio should be > 3x

### Daily Monitoring
```bash
# Check dashboard
curl -s http://localhost:8000/api/bankroll/dashboard | jq '.alerts'

# Check P&L for last 24h
curl -s "http://localhost:8000/api/bankroll/pnl?from_ts=$(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%SZ)" | jq '.house_edge_actual_bps'
```

### Incident Response
1. If `INSUFFICIENT_BANKROLL` alert fires: immediately fund the house wallet
2. If `LOW_REALIZED_EDGE` alert fires: investigate potential RNG or payout bugs
3. If `HIGH_EXPOSURE` alert fires: temporarily reduce `MAX_BET_NANOERG`

## Variance Math

For coinflip with 3% edge:

- **Bets for statistical reliability** (~1045): After this many rounds, the house edge becomes statistically distinguishable from variance
- **Minimum bankroll for 1% RoR** (per 1 ERG max bet): ~72 ERG
- **Minimum bankroll for 0.1% RoR** (per 1 ERG max bet): ~108 ERG
- **1-sigma daily range** (100 rounds at 1 ERG avg): -9.7 ERG to +10.0 ERG
- **3-sigma worst case** (100 rounds at 1 ERG avg): -28.1 ERG loss
