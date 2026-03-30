# DuckPools CoinFlip - Deployment Guide

This guide provides detailed instructions for deploying the DuckPools CoinFlip system to production.

## Deployment Overview

The DuckPools CoinFlip system consists of multiple components that need to be deployed:
1. **Backend API Server**: FastAPI server for game operations
2. **Frontend Application**: React frontend for user interface
3. **Ergo Node**: Blockchain node for contract interaction
4. **Database**: PostgreSQL for off-chain state management
5. **Bot Services**: Background services for bet resolution

## Prerequisites

### Infrastructure Requirements

- **Servers**: 3-5 servers (backend, frontend, node, database, bot)
- **Operating System**: Linux (Ubuntu 20.04+ recommended)
- **Resources**: 
  - Backend: 2 CPU, 4GB RAM, 50GB storage
  - Frontend: 1 CPU, 2GB RAM, 20GB storage
  - Node: 4 CPU, 8GB RAM, 100GB storage
  - Database: 2 CPU, 8GB RAM, 100GB storage
- **Network**: Stable internet connection with proper firewall rules

### Software Requirements

- Docker and Docker Compose
- Git
- Python 3.8+
- Node.js 16+
- PostgreSQL 13+
- Nautilus wallet extension

## Production Environment Setup

### Environment Configuration

Create production environment files:

```bash
# Backend environment
cp backend/.env.example backend/.env.production

# Edit with production values
vim backend/.env.production
```

### Environment Variables

| Variable | Description | Production Value |
|----------|-------------|-----------------|
| `NODE_URL` | Ergo node endpoint | `https://api.ergo.org` |
| `VITE_NODE_URL` | Node URL for frontend | `https://api.ergo.org` |
| `NODE_API_KEY` | API key for node | Production API key |
| `BOT_API_KEY` | API key for bot endpoints | Production API key |
| `DATABASE_URL` | PostgreSQL connection | `postgresql://user:pass@db:5432/duckpools` |
| `SECRET_KEY` | Application secret key | Secure random string |
| `LOG_LEVEL` | Logging level | `INFO` or `WARNING` |
| `MAX_BET` | Maximum bet amount | `100000000000` (100 ERG) |
| `FEE_PERCENTAGE` | House fee percentage | `2.0` |
| `TIMEOUT_BLOCKS` | Timeout in blocks | `100` |

## Docker Production Deployment

### Docker Compose Configuration

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - NODE_URL=${NODE_URL}
      - VITE_NODE_URL=${VITE_NODE_URL}
      - NODE_API_KEY=${NODE_API_KEY}
      - DATABASE_URL=${DATABASE_URL}
      - SECRET_KEY=${SECRET_KEY}
      - LOG_LEVEL=${LOG_LEVEL}
      - MAX_BET=${MAX_BET}
      - FEE_PERCENTAGE=${FEE_PERCENTAGE}
      - TIMEOUT_BLOCKS=${TIMEOUT_BLOCKS}
    volumes:
      - ./backend/logs:/app/logs
    depends_on:
      - db
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    environment:
      - VITE_NODE_URL=${VITE_NODE_URL}
      - NODE_API_KEY=${NODE_API_KEY}
    restart: unless-stopped

  node:
    image: ergoplatform/ergo:5.0.11
    ports:
      - "9052:9052"
    volumes:
      - ./node/data:/opt/ergo/data
    command: ["-c", "/opt/ergo/conf/ergo.conf"]
    restart: unless-stopped

  db:
    image: postgres:13
    environment:
      - POSTGRES_USER=${DB_USER}
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=${DB_NAME}
    volumes:
      - ./db/data:/var/lib/postgresql/data
    restart: unless-stopped

  bot:
    build: ./bot
    environment:
      - NODE_URL=${NODE_URL}
      - VITE_NODE_URL=${VITE_NODE_URL}
      - NODE_API_KEY=${NODE_API_KEY}
      - DATABASE_URL=${DATABASE_URL}
      - BOT_API_KEY=${BOT_API_KEY}
    depends_on:
      - backend
      - node
      - db
    restart: unless-stopped
```

### Deployment Steps

```bash
# Build and start production services
docker-compose -f docker-compose.prod.yml up -d

# Check service status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f backend
```

## Manual Deployment

### Backend Deployment

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install production dependencies
pip install -r requirements.txt

# Set production environment
export NODE_URL="https://api.ergo.org"
export DATABASE_URL="postgresql://user:pass@db:5432/duckpools"
export SECRET_KEY="your_production_secret"

# Start production server
python api_server.py --prod
```

### Frontend Deployment

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Build production bundle
npm run build

# Serve with production server
npm run serve
```

### Database Setup

```bash
# Connect to database
psql -h db -U user -d duckpools

# Create tables
\i backend/migrations/001_initial_schema.sql

# Verify schema
\dt
```

## Configuration Management

### Configuration Files

- `backend/.env.production`: Backend configuration
- `frontend/.env.production`: Frontend configuration
- `node/ergo.conf`: Node configuration
- `docker-compose.prod.yml`: Docker configuration

### Configuration Management Best Practices

1. **Use environment variables**: Avoid hardcoding sensitive information
2. **Version control**: Keep configuration templates in version control
3. **Secret management**: Use secure secret management tools
4. **Backup configurations**: Regularly backup configuration files

## Monitoring and Logging

### Logging Configuration

```python
# backend/api_server.py example
import logging
from logging.handlers import RotatingFileHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('logs/app.log', maxBytes=10000000, backupCount=5),
        logging.StreamHandler()
    ]
)
```

### Monitoring Tools

- **Prometheus**: Metrics collection
- **Grafana**: Dashboard visualization
- **ELK Stack**: Logging and analytics
- **Sentry**: Error tracking

### Health Checks

```python
# backend/api_server.py health check
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "database": check_database_connection(),
            "node": check_node_connection(),
            "backend": "running"
        }
    }
```

## Security Hardening

### Production Security Measures

1. **CSP Hardening**: Remove unsafe-eval, use nonces
2. **Rate Limiting**: Implement strict rate limits
3. **HTTPS**: Use SSL/TLS for all connections
4. **Firewall Rules**: Restrict access to necessary ports
5. **Regular Updates**: Keep all components updated

### Security Headers

```python
# backend/api_server.py security headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Production security headers
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'nonce-<random>'; style-src 'self' 'unsafe-inline';"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    
    return response
```

## Backup and Recovery

### Database Backup

```bash
# Daily database backup
0 2 * * * pg_dump -h db -U user duckpools > /backups/duckpools_$(date +\%Y\%m\%d).sql

# Weekly full backup
0 3 * * 0 pg_dump -h db -U user -F c duckpools > /backups/duckpools_full_$(date +\%Y\%m\%d).dump
```

### Node Backup

```bash
# Backup node data
0 4 * * * rsync -av /opt/ergo/data /backups/node_data_$(date +\%Y\%m\%d)
```

### Recovery Procedures

1. **Database Recovery**: Restore from latest backup
2. **Node Recovery**: Restore node data and resync
3. **Application Recovery**: Restart services and verify health
4. **Data Consistency**: Verify data consistency across components

## Scaling and Load Balancing

### Horizontal Scaling

```yaml
# docker-compose.scale.yml
version: '3.8'

services:
  backend:
    scale: 3
  frontend:
    scale: 2
  bot:
    scale: 2
```

### Load Balancing

```yaml
# nginx.conf
http {
    upstream backend {
        server backend1:8000;
        server backend2:8000;
        server backend3:8000;
    }
    
    server {
        listen 80;
        server_name api.duckpools.com;
        
        location / {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
}
```

## Maintenance and Updates

### Update Procedures

1. **Backup**: Create full system backup
2. **Staging**: Test updates in staging environment
3. **Deploy**: Roll out updates gradually
4. **Monitor**: Monitor for issues
5. **Rollback**: Prepare rollback plan

### Maintenance Schedule

- **Daily**: Check logs and health
- **Weekly**: Database optimization and backups
- **Monthly**: Security updates and patches
- **Quarterly**: Performance tuning and scaling

## Disaster Recovery

### Recovery Plan

1. **Incident Detection**: Monitor system health and alerts
2. **Incident Response**: Isolate affected components
3. **Data Recovery**: Restore from backups
4. **System Restoration**: Rebuild affected components
5. **Verification**: Test system functionality
6. **Post-Incident Review**: Analyze root cause and improvements

### High Availability

- **Redundant Nodes**: Multiple node instances
- **Database Replication**: Master-slave replication
- **Load Balancing**: Distribute traffic
- **Failover**: Automatic failover mechanisms

## Performance Optimization

### Database Optimization

```sql
-- Index optimization
CREATE INDEX idx_bets_player_address ON bets(player_address);
CREATE INDEX idx_bets_status ON bets(status);
CREATE INDEX idx_bets_created_at ON bets(created_at);

-- Query optimization
EXPLAIN ANALYZE SELECT * FROM bets WHERE status = 'pending' ORDER BY created_at LIMIT 100;
```

### Application Optimization

```python
# Backend optimization
@app.get("/history/{address}")
async def get_history(address: str, limit: int = 100, offset: int = 0):
    # Use pagination to reduce load
    query = "SELECT * FROM bets WHERE player_address = %s ORDER BY created_at DESC LIMIT %s OFFSET %s"
    results = await database.fetch(query, address, limit, offset)
    return results
```

### Caching Strategies

```python
# Redis caching example
import redis

redis_client = redis.Redis(host='redis', port=6379)

@app.get("/player/stats/{address}")
async def get_player_stats(address: str):
    cache_key = f"player_stats:{address}"
    cached = redis_client.get(cache_key)
    
    if cached:
        return json.loads(cached)
    
    stats = await calculate_player_stats(address)
    redis_client.setex(cache_key, 300, json.dumps(stats))  # Cache for 5 minutes
    return stats
```

## Compliance and Security

### Security Compliance

- **PCI DSS**: Payment card industry compliance
- **GDPR**: Data protection regulations
- **KYC/AML**: Know your customer and anti-money laundering
- **Smart Contract Audits**: Regular security audits

### Security Audits

- **Code Review**: Regular code reviews
- **Penetration Testing**: External security testing
- **Vulnerability Scanning**: Regular vulnerability scans
- **Compliance Audits**: Regulatory compliance checks

## Monitoring and Alerting

### Monitoring Setup

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'backend'
    static_configs:
      - targets: ['backend:8000']
  - job_name: 'node'
    static_configs:
      - targets: ['node:9052']
```

### Alerting Configuration

```yaml
# alertmanager.yml
route:
  receiver: 'duckpools-team'
  repeat_interval: 1h

receivers:
  - name: 'duckpools-team'
    webhook_configs:
      - url: 'https://hooks.slack.com/services/...'
```

## Backup and Restore Procedures

### Full System Backup

```bash
# Create full system backup
tar -czf /backups/duckpools_full_$(date +\%Y\%m\%d).tar.gz \
  /opt/ergo/data \
  /var/lib/postgresql/data \
  /app/backend \
  /app/frontend
```

### Restore Procedure

```bash
# Restore from backup
tar -xzf /backups/duckpools_full_20230330.tar.gz -C /
docker-compose -f docker-compose.prod.yml up -d
```

## Final Verification

### Deployment Checklist

- [ ] All services running
- [ ] Health checks passing
- [ ] Database connections working
- [ ] Node synchronization complete
- [ ] Bot services operational
- [ ] Frontend accessible
- [ ] API endpoints responding
- [ ] Security headers in place
- [ ] Monitoring and logging configured
- [ ] Backups working
- [ ] Performance within acceptable limits

### Go/No-Go Decision

- **Go**: All checks pass, system stable
- **No-Go**: Critical issues found, require investigation

## Support and Maintenance

### Support Channels

- **Email**: support@duckpools.com
- **Slack**: duckpools-support
- **Phone**: 1-800-DUCKPOOL

### Maintenance Contacts

- **Backend Team**: backend@duckpools.com
- **Frontend Team**: frontend@duckpools.com
- **Blockchain Team**: blockchain@duckpools.com
- **Database Team**: dba@duckpools.com

## Further Resources

- [Docker Documentation](https://docs.docker.com/)
- [PostgreSQL Best Practices](https://www.postgresql.org/docs/)
- [Ergo Platform Documentation](https://ergoplatform.org/)
- [DuckPools Architecture](../ARCHITECTURE.md)

--- 
*Production deployment requires careful planning and testing. Always follow security best practices and have proper monitoring in place.*