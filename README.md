# DuckPools Coinflip

A provably-fair gambling protocol on Ergo blockchain using a commit-reveal scheme for fair randomness.

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose installed
- External Ergo node running (not included in this setup)
  - REST API on port 9052
  - API key: `blake2b256("hello")`

### Development Setup with Docker (Recommended)

#### 🔥 Easiest Way - Quick Start Script

For the fastest setup, use our quick start script:

```bash
# First time setup
./docker-quickstart.sh setup

# Start all services
./docker-quickstart.sh start

# View logs
./docker-quickstart.sh logs -f

# Stop services
./docker-quickstart.sh stop
```

#### Prerequisites

1. **Docker & Docker Compose**
   - Install Docker Desktop: [docker.com/get-started](https://www.docker.com/get-started)
   - Or install Docker CLI and Docker Compose separately

2. **External Ergo Node**
   - Run Ergo node natively (not in Docker) on port 9052
   - Configure API key in `ergo.conf`: `apiKeyHash: blake2b256("hello")`
   - Verify node is accessible: `curl http://localhost:9052/info`

#### Quick Start

1. **Clone and setup**
   ```bash
   git clone <repository-url>
   cd DuckPools
   
   # Copy environment configuration
   cp .env.example .env
   
   # Edit .env with your configuration (required values)
   nano .env
   ```

2. **Start development environment**
   ```bash
   # Method 1: Using management script (recommended)
   ./docker-manage.sh dev up
   
   # Method 2: Direct Docker Compose
   docker compose up -d
   ```

3. **Access services**
   - Frontend: http://localhost:3000 (React + Vite dev server)
   - Backend API: http://localhost:8000 (FastAPI with hot-reload)
   - API Docs: http://localhost:8000/docs (Swagger UI)
   - Health Check: http://localhost:8000/health

4. **Development workflow**
   ```bash
   # View logs (all services)
   docker compose logs -f
   
   # View logs for specific service
   docker compose logs -f backend
   docker compose logs -f frontend
   
   # Rebuild after major changes
   docker compose build
   
   # Stop services
   docker compose down
   ```

#### Advanced Docker Features

The Docker setup includes:

- **Hot Reload**: Code changes automatically reflect in running containers
- **Health Checks**: All services have automated health monitoring
- **Volume Mounts**: Persistent logs and hot-reload support
- **Network Isolation**: Services communicate via internal Docker network
- **Environment Variables**: Configurable via `.env` file
- **Development/Production Profiles**: Separate configs for dev and prod

#### Using the Docker Management Script

The `docker-manage.sh` script provides easy commands:

```bash
# Development commands
./docker-manage.sh dev up      # Start dev environment
./docker-manage.sh dev down    # Stop dev environment
./docker-manage.sh dev logs    # View logs
./docker-manage.sh dev build   # Rebuild images

# Production commands
./docker-manage.sh prod up     # Start production
./docker-manage.sh prod down   # Stop production
./docker-manage.sh prod logs   # View production logs

# Utilities
./docker-manage.sh status      # Check container status
./docker-manage.sh clean all   # Clean all Docker resources
```

#### Troubleshooting

Common Docker issues and solutions:

- **Port conflicts**: Stop other services using ports 3000/8000
- **Volume permissions**: Ensure Docker has access to project directories
- **Build errors**: Clean build cache with `docker builder prune`
- **Network issues**: Ensure Ergo node is running on host:9052

For detailed troubleshooting, see: [DOCKER.md](DOCKER.md)

### Manual Development (Without Docker)

#### Backend Setup

1. **Navigate to backend directory**
   ```bash
   cd backend
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the API server**
   ```bash
   uvicorn api_server:app --reload --host 0.0.0.0 --port 8000
   ```

#### Frontend Setup

1. **Navigate to frontend directory**
   ```bash
   cd frontend
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Start the dev server**
   ```bash
   npm run dev
   ```

## 🏗️ Architecture

The system consists of three main components:

1. **Frontend** (React + TypeScript) - User interface and wallet integration
2. **Backend** (FastAPI + Python) - API server, contract interaction, off-chain logic
3. **Blockchain Layer** (Ergo Node + Smart Contracts) - On-chain state and game logic

For detailed architecture documentation, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## 🐳 Docker Development

### Available Commands

```bash
# Start development environment
docker compose up

# Start in background
docker compose up -d

# View logs
docker compose logs -f

# View specific service logs
docker compose logs -f backend-api
docker compose logs -f frontend

# Stop services
docker compose down

# Rebuild and start
docker compose up --build

# Clean up volumes
docker compose down -v
```

### Service Details

#### Backend Service

- **Port**: 8000
- **Health Check**: http://localhost:8000/health
- **Hot-Reload**: Enabled (code changes trigger restart)
- **Environment Variables**:
  - `NODE_ENV`: development
  - `LOG_LEVEL`: DEBUG (in development override)
  - `ERGO_NODE_URL`: External Ergo node URL
  - `ERGO_API_KEY`: Ergo node API key
  - `CORS_ORIGINS`: Comma-separated list of allowed origins

#### Frontend Service

- **Port**: 3000
- **HMR Port**: 24678
- **Hot-Reload**: Enabled (code changes trigger refresh)
- **Environment Variables**:
  - `VITE_API_ENDPOINT`: Backend API URL
  - `VITE_ERGO_NODE_URL`: Ergo node URL
  - `CHOKIDAR_USEPOLLING`: Enable file polling in Docker

### Production Builds

To create optimized production builds:

```bash
# Build backend
docker build -t duckpools-backend:prod --target production backend/

# Build frontend
docker build -t duckpools-frontend:prod --target production frontend/
```

## 🔧 Configuration

### Ergo Node

The Docker setup assumes an external Ergo node is running:

- **REST API**: http://host.docker.internal:9052
- **API Key**: blake2b256("hello")

To configure a different Ergo node:

1. Update the `ERGO_NODE_URL` environment variable in `docker-compose.yml`
2. Update the `VITE_ERGO_NODE_URL` environment variable in `docker-compose.yml`

### Environment Variables

#### Backend

| Variable | Default | Description |
|----------|---------|-------------|
| `NODE_ENV` | development | Environment (development/production) |
| `LOG_LEVEL` | DEBUG | Logging level (development override) |
| `ERGO_NODE_URL` | http://host.docker.internal:9052 | Ergo node URL |
| `ERGO_API_KEY` | blake2b256("hello") | Ergo node API key |
| `CORS_ORIGINS` | http://localhost:3000 | Frontend URLs for CORS |

#### Frontend

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_ENDPOINT` | http://localhost:8000 | Backend API URL |
| `VITE_ERGO_NODE_URL` | http://localhost:9052 | Ergo node URL |
| `VITE_DEBUG_MODE` | true | Debug mode (development override) |

### Docker Compose Override

The `docker-compose.override.yml` file provides development-specific overrides:

- **Hot-reload**: Volume mounts for live code changes
- **Debug ports**: Additional ports for debugging
- **Resource limits**: Lower resource requirements for development
- **Debug logging**: Enhanced logging in development

## 📚 Documentation

- [Architecture Overview](docs/ARCHITECTURE.md) - Detailed system architecture
- [Getting Started](docs/GETTING_STARTED.md) - Development guide
- [Security](SECURITY.md) - Security considerations
- [Ergo Concepts](docs/ERGO_CONCEPTS.md) - Blockchain-specific concepts

## 🤝 Contributing

Please read [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for our contribution guidelines.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.