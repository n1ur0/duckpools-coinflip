# DuckPools Coinflip

A provably-fair gambling protocol on Ergo blockchain using a commit-reveal scheme for fair randomness.

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose installed
- External Ergo node running (not included in this setup)
  - REST API on port 9052
  - API key: `blake2b256("hello")`

### Development Setup with Docker

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd DuckPools
   ```

2. **Start the development stack**
   ```bash
   # Start both backend and frontend with hot-reload
   docker compose up
   
   # Or run in background
   docker compose up -d
   ```

3. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Health: http://localhost:8000/health

4. **Stop the services**
   ```bash
   docker compose down
   ```

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

#### Off-chain Bot Service

- **No Port Exposed**: Runs in background (no external access needed)
- **Health Check**: Process monitoring
- **Hot-Reload**: Enabled (code changes trigger restart)
- **Environment Variables**:
  - `NODE_ENV`: development
  - `LOG_LEVEL`: DEBUG
  - `ERGO_NODE_URL`: External Ergo node URL
  - `ERGO_API_KEY`: Ergo node API key

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