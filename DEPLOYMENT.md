# Deployment Guide

This document covers deployment strategies and procedures for the DuckPools Coinflip protocol.

## Table of Contents

1. [Environment Overview](#environment-overview)
2. [Deployment Environments](#deployment-environments)
3. [Prerequisites](#prerequisites)
4. [Local Development Deployment](#local-development-deployment)
5. [Testnet Deployment](#testnet-deployment)
6. [Mainnet Deployment](#mainnet-deployment)
7. [Monitoring and Observability](#monitoring-and-observability)
8. [Rollback Procedures](#rollback-procedures)
9. [Troubleshooting](#troubleshooting)

---

## Environment Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Infrastructure                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │   Frontend   │    │   Backend    │    │ Ergo Node    │ │
│  │  (React/Vite)│───▶│  (FastAPI)   │───▶│  (REST API)  │ │
│  │  Port: 3000  │    │  Port: 8000  │    │  Port: 9052  │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│         │                                      │            │
│         │         ┌──────────────┐             │            │
│         └────────▶│   PM2        │             │            │
│                  │  Process Mgr  │             │            │
│                  └──────────────┘             │            │
│                                               │            │
│  ┌──────────────┐                             │            │
│  │   Off-chain  │─────────────────────────────┘            │
│  │      Bot     │                                          │
│  └──────────────┘                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Deployment Environments

### Development (dev)

- **Purpose**: Local development and testing
- **URL**: http://localhost:3000
- **Ergo Network**: Testnet (local node)
- **Database**: In-memory / local SQLite
- **Wallet**: Nautilus testnet wallet

### Staging (testnet)

- **Purpose**: Pre-production testing
- **URL**: https://testnet.duckpools.io
- **Ergo Network**: Public Testnet
- **Database**: PostgreSQL (staging instance)
- **Wallet**: Production house wallet (testnet)

### Production (mainnet)

- **Purpose**: Live application
- **URL**: https://app.duckpools.io
- **Ergo Network**: Mainnet
- **Database**: PostgreSQL (production instance)
- **Wallet**: Production house wallet (mainnet)
- **SSL/TLS**: Required

---

## Prerequisites

### Infrastructure

- **Server**: Ubuntu 22.04 LTS or later
- **RAM**: Minimum 8GB (16GB recommended)
- **Storage**: 100GB+ (Ergo node blockchain data grows ~100GB/month)
- **CPU**: 4+ cores recommended
- **Network**: Stable connection with ~50Mbps bandwidth

### Software Dependencies

```bash
# System packages
sudo apt update
sudo apt install -y \
  python3.12 \
  python3-pip \
  nodejs \
  npm \
  nginx \
  postgresql \
  postgresql-contrib \
  certbot \
  pm2 \
  git

# Verify versions
python3 --version  # Should be 3.12+
node --version     # Should be 20+
npm --version      # Should be 10+
pm2 --version
```

### Ergo Node

Ergo node must be running independently. See [Ergo Node Setup](docs/ERGO_NODE_SETUP.md) for details.

---

## Local Development Deployment

### Quick Start

```bash
# 1. Clone repository
git clone https://github.com/ducks/duckpools-coinflip.git
cd duckpools-coinflip

# 2. Install dependencies
# Backend
cd backend
pip install -r requirements.txt
cd ..

# Frontend
cd frontend
npm install
cd ..

# 3. Configure environment
cp .env.example .env
nano .env  # Edit configuration

# 4. Start Ergo node (separate process)
# See ergo-testnet setup

# 5. Start services
# Backend
cd backend
python api_server.py &

# Frontend
cd frontend
npm run dev

# Off-chain bot (optional)
cd off-chain-bot
python main.py &
```

### Using PM2 for Process Management

```bash
# Install PM2
npm install -g pm2

# Start all services
pm2 start ecosystem.config.js

# View status
pm2 status

# View logs
pm2 logs

# Restart service
pm2 restart api-server
pm2 restart frontend
pm2 restart off-chain-bot

# Stop all services
pm2 stop all
```

---

## Testnet Deployment

### Step 1: Server Preparation

```bash
# SSH into staging server
ssh user@staging.duckpools.io

# Create application directory
sudo mkdir -p /opt/duckpools
sudo chown $USER:$USER /opt/duckpools
cd /opt/duckpools

# Clone repository
git clone https://github.com/ducks/duckpools-coinflip.git
cd duckpools-coinflip

# Switch to deployment branch
git checkout testnet
```

### Step 2: Environment Configuration

```bash
# Create environment file
cp .env.example .env
nano .env
```

**Testnet .env configuration:**

```bash
# Ergo Node
NODE_URL=http://localhost:9052
EXPLORER_URL=https://testnet.ergoplatform.com

# Wallet
HOUSE_ADDRESS=3Wy...  # Testnet house address
WALLET_PASS=your_secure_password

# Contract NFT
COINFLIP_NFT_ID=b0a...  # Testnet NFT ID

# API
API_KEY=your_api_key_here
CORS_ORIGINS_STR=https://testnet.duckpools.io

# Logging
LOG_LEVEL=INFO

# Frontend (VITE_)
VITE_NETWORK=testnet
VITE_API_ENDPOINT=https://testnet.duckpools.io/api
VITE_EXPLORER_URL=https://testnet.ergoplatform.com
```

### Step 3: Install Dependencies

```bash
# Backend
cd /opt/duckpools/duckpools-coinflip/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd /opt/duckpools/duckpools-coinflip/frontend
npm ci --production
```

### Step 4: Database Setup

```bash
# Create PostgreSQL database
sudo -u postgres psql
```

```sql
CREATE DATABASE duckpools_testnet;
CREATE USER duckpools_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE duckpools_testnet TO duckpools_user;
\q
```

### Step 5: Build Frontend

```bash
cd /opt/duckpools/duckpools-coinflip/frontend
npm run build
# Output: dist/
```

### Step 6: Configure PM2

```bash
cd /opt/duckpools/duckpools-coinflip

# Update ecosystem.config.js for testnet
nano ecosystem.config.js
```

**Key changes for testnet:**

```javascript
{
  name: 'api-server',
  script: './backend/api_server.py',
  interpreter: 'python3',
  cwd: '/opt/duckpools/duckpools-coinflip',
  env: {
    NODE_ENV: 'production',
    ENVIRONMENT: 'testnet'
  }
}
```

### Step 7: Start Services

```bash
# Start PM2 processes
pm2 start ecosystem.config.js --env testnet

# Save PM2 configuration
pm2 save

# Setup PM2 startup script
pm2 startup
# Follow instructions to enable PM2 on boot
```

### Step 8: Configure Nginx

```bash
# Create Nginx config
sudo nano /etc/nginx/sites-available/testnet.duckpools.io
```

```nginx
server {
    listen 80;
    server_name testnet.duckpools.io;

    # Frontend static files
    location / {
        root /opt/duckpools/duckpools-coinflip/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # Backend API proxy
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support (for bet updates)
    location /ws/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/testnet.duckpools.io /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

### Step 9: SSL Certificate (Let's Encrypt)

```bash
# Install Certbot and Nginx plugin
sudo apt install -y certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d testnet.duckpools.io

# Auto-renewal is configured automatically
sudo certbot renew --dry-run
```

### Step 10: Verify Deployment

```bash
# Check PM2 status
pm2 status

# Check logs
pm2 logs

# Test API health
curl https://testnet.duckpools.io/api/health

# Test frontend
curl https://testnet.duckpools.io/

# Check Ergo node connectivity
curl http://localhost:9052/info | jq .
```

---

## Mainnet Deployment

⚠️ **WARNING**: Mainnet deployment involves real funds. Complete all testing on testnet first.

### Pre-Deployment Checklist

- [ ] All tests passing on staging
- [ ] Security audit completed
- [ ] Smart contracts reviewed and verified
- [ ] House wallet funded with sufficient ERG
- [ ] Backup procedures tested
- [ ] Monitoring/alerting configured
- [ ] Rollback plan documented
- [ ] Team notified of deployment window

### Deployment Steps

#### 1. Create Release Branch

```bash
git checkout main
git pull origin main
git checkout -b release/v1.0.0-mainnet
```

#### 2. Update Configuration

```bash
# Create mainnet .env
cp .env.example .env.mainnet
nano .env.mainnet
```

**Mainnet .env configuration:**

```bash
# Ergo Node (mainnet)
NODE_URL=http://localhost:9052
EXPLORER_URL=https://explorer.ergoplatform.com

# Wallet (MAINNET - real funds)
HOUSE_ADDRESS=9h...  # Mainnet house address
WALLET_PASS=your_secure_password

# Contract NFT
COINFLIP_NFT_ID=...  # Mainnet NFT ID

# API
API_KEY=your_secure_api_key
CORS_ORIGINS_STR=https://app.duckpools.io

# Logging
LOG_LEVEL=WARNING  # Lower noise in production

# Frontend
VITE_NETWORK=mainnet
VITE_API_ENDPOINT=https://app.duckpools.io/api
VITE_EXPLORER_URL=https://explorer.ergoplatform.com
```

#### 3. Deploy Smart Contracts

```bash
cd /opt/duckpools/duckpools-coinflip

# Deploy contracts (this script handles NFT minting)
python deploy_coinflip.py --network mainnet

# Verify deployment
# Note down:
# - NFT token ID
# - PendingBet contract address
# - GameState contract address
# - LP pool contract address
```

#### 4. Build and Deploy

```bash
# Build frontend
cd frontend
npm run build

# Copy to production server
scp -r dist/* user@prod.duckpools.io:/opt/duckpools/frontend/dist/

# Deploy backend
cd ../backend
# Update code on server
git fetch origin release/v1.0.0-mainnet
git checkout release/v1.0.0-mainnet
```

#### 5. Database Migration

```bash
# Run database migrations
cd backend
python -m alembic upgrade head
```

#### 6. Update Nginx Configuration

```bash
# Create production config
sudo nano /etc/nginx/sites-available/app.duckpools.io
```

```nginx
server {
    listen 443 ssl http2;
    server_name app.duckpools.io;

    # SSL certificates
    ssl_certificate /etc/letsencrypt/live/app.duckpools.io/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.duckpools.io/privkey.pem;

    # SSL security
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Frontend static files
    location / {
        root /opt/duckpools/duckpools-coinflip/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # Backend API proxy
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support
    location /ws/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name app.duckpools.io;
    return 301 https://$server_name$request_uri;
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/app.duckpools.io /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### 7. Obtain SSL Certificate

```bash
sudo certbot --nginx -d app.duckpools.io
```

#### 8. Start Services

```bash
# Start PM2 with mainnet environment
pm2 restart ecosystem.config.js --env mainnet

# Verify status
pm2 status
pm2 logs --lines 50
```

#### 9. Smoke Tests

```bash
# API health check
curl https://app.duckpools.io/api/health | jq .

# Pool state
curl https://app.duckpools.io/api/pool/state | jq .

# Frontend load
curl -I https://app.duckpools.io/

# Test bet flow (small amount)
# Use Nautilus wallet to place test bet
```

#### 10. Monitor Initial Traffic

```bash
# Watch PM2 logs
pm2 logs api-server

# Monitor Ergo node
curl http://localhost:9052/info | jq .fullHeight

# Check for errors in logs
grep -i error /opt/duckpools/logs/*.log
```

---

## Monitoring and Observability

### PM2 Monitoring

```bash
# Real-time monitoring
pm2 monit

# Metrics dashboard
pm2 web
# Visit http://localhost:9615

# Custom monitoring setup
pm2 install pm2-logrotate
pm2 set pm2-logrotate:max_size 10M
pm2 set pm2-logrotate:retain 7
```

### Application Metrics

Monitor these metrics:

| Metric | Tool | Threshold |
|--------|------|-----------|
| API response time | PM2 / custom | < 200ms avg |
| Error rate | PM2 logs | < 1% |
| Memory usage | PM2 | < 2GB per process |
| CPU usage | PM2 | < 70% avg |
| Uptime | PM2 | 99.9%+ |
| Bet processing time | Custom | < 30s avg |
| Ergo node sync | Node API | Must be synced |

### Log Aggregation

```bash
# Centralized log directory
mkdir -p /var/log/duckpools

# Configure PM2 to output to logs
pm2 reload --log-date-format "YYYY-MM-DD HH:mm:ss Z"

# Set up logrotate for application logs
sudo nano /etc/logrotate.d/duckpools
```

```
/var/log/duckpools/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        pm2 reloadLogs
    endscript
}
```

### Alerting

**Critical Alerts:**

- API health check fails for > 5 minutes
- Error rate exceeds 5% for 10 minutes
- Ergo node desyncs
- Memory usage > 90%
- Unconfirmed transactions > 100

**Warning Alerts:**

- API response time > 500ms
- Pending bets > 1000
- House bankroll below threshold

---

## Rollback Procedures

### Automatic Rollback

If deployment fails immediately:

```bash
# Stop current deployment
pm2 stop api-server

# Revert to previous version
cd /opt/duckpools/duckpools-coinflip
git checkout previous_release_tag

# Restart services
pm2 start api-server

# Verify rollback
curl https://app.duckpools.io/api/health
```

### Manual Rollback

```bash
# 1. Stop all services
pm2 stop all

# 2. Revert code
cd /opt/duckpools/duckpools-coinflip
git fetch origin
git checkout v0.9.0  # Previous stable version

# 3. Rebuild frontend
cd frontend
npm run build

# 4. Restart services
pm2 restart all

# 5. Verify
pm2 logs --lines 100
curl https://app.duckpools.io/api/health
```

### Database Rollback

```bash
# 1. Stop backend
pm2 stop api-server

# 2. Backup current state
pg_dump duckpools > backup_before_rollback.sql

# 3. Rollback migrations
cd backend
alembic downgrade -1

# 4. Restart backend
pm2 start api-server

# 5. Verify data integrity
```

---

## Troubleshooting

### Common Issues

#### API Returns 502 Bad Gateway

**Cause:** Backend service not running or crashed.

**Solution:**
```bash
# Check PM2 status
pm2 status

# Check logs
pm2 logs api-server --lines 100

# Restart if needed
pm2 restart api-server
```

#### Frontend Shows "Connection Refused"

**Cause:** Frontend trying to reach backend on wrong port.

**Solution:**
```bash
# Check VITE_API_ENDPOINT in .env
# Should be: https://yourdomain.com/api

# Verify Nginx config
sudo nginx -t

# Check if backend is running
curl http://localhost:8000/health
```

#### Ergo Node Desynced

**Cause:** Node stopped or network issues.

**Solution:**
```bash
# Check node status
curl http://localhost:9052/info | jq .fullHeight

# Restart Ergo node
sudo systemctl restart ergo

# Monitor sync progress
watch -n 5 'curl -s http://localhost:9052/info | jq .fullHeight'
```

#### Bets Not Resolving

**Cause:** Off-chain bot stopped or crashed.

**Solution:**
```bash
# Check bot status
pm2 status off-chain-bot

# Check bot logs
pm2 logs off-chain-bot --lines 200

# Restart bot
pm2 restart off-chain-bot

# Check for pending bets
curl http://localhost:8000/api/bets/expired | jq .
```

#### High Memory Usage

**Cause:** Memory leak or insufficient resources.

**Solution:**
```bash
# Check memory usage
pm2 monit

# Restart services
pm2 restart all

# If persistent, check for memory leaks
# Add monitoring and profiling
```

### Getting Help

If issues persist:

1. Check logs: `pm2 logs --lines 500`
2. Review documentation in `/docs/`
3. Check GitHub issues: https://github.com/ducks/duckpools-coinflip/issues
4. Contact team: devops@duckpools.io

---

## Security Considerations

### Never Commit

- API keys (`API_KEY`)
- Wallet passwords (`WALLET_PASS`)
- Private keys
- Database credentials
- Secrets and tokens

### Use Environment Variables

All sensitive data must be in `.env` files (gitignored).

### Regular Updates

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Update Python dependencies
cd backend
pip install --upgrade -r requirements.txt

# Update Node dependencies
cd frontend
npm audit fix
```

### Firewall Rules

```bash
# Allow only necessary ports
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw deny 9052/tcp   # Ergo node (internal only)
sudo ufw enable
```

---

## Appendices

### A. Environment Variables Reference

See `.env.example` for complete list.

### B. Port Reference

| Port | Service | External |
|------|---------|----------|
| 22 | SSH | Yes |
| 80 | HTTP (Nginx) | Yes |
| 443 | HTTPS (Nginx) | Yes |
| 8000 | Backend API | No |
| 3000 | Frontend dev | No |
| 9052 | Ergo Node | No |
| 9615 | PM2 dashboard | No |

### C. Useful Commands

```bash
# Check disk space
df -h

# Check memory
free -h

# Check CPU
top

# View last 100 lines of logs
pm2 logs --lines 100

# Clear logs
pm2 flush

# Restart all services
pm2 restart all

# Update code
cd /opt/duckpools/duckpools-coinflip
git pull
pm2 restart all

# Backup database
pg_dump duckpools > backup_$(date +%Y%m%d).sql

# Check SSL certificate expiry
sudo certbot certificates
```

---

**Last Updated:** 2026-03-27
**Maintained by:** DevOps Team
**Contact:** devops@duckpools.io
