## Docker Quick Start

The fastest way to run DuckPools Coinflip is using Docker Compose:

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Edit .env with your configuration
nano .env

# 3. Start all services
docker compose up -d

# 4. Access the application
#   Frontend: http://localhost:3000
#   Backend: http://localhost:8000
```

For detailed Docker setup instructions, see [DOCKER.md](DOCKER.md).

**Note**: Docker setup requires the Ergo node to be running natively on host port 9052 (not in a container).

