#!/bin/bash
# =============================================================================
# DuckPools Coinflip - Development Startup Script
# =============================================================================
#
# This script helps developers quickly set up and start the DuckPools 
# development environment with Docker Compose.
#
# Usage: ./scripts/dev-start.sh [options]
#
# Options:
#   -b, --build       Rebuild images before starting
#   -c, --clean       Clean volumes before starting (fresh start)
#   -d, --detach      Start in detached mode
#   -h, --help        Show this help message
#
# =============================================================================

set -e

# Configuration
BUILD=false
CLEAN=false
DETACH=false
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Help message
show_help() {
    echo "DuckPools Development Startup Script"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -b, --build       Rebuild images before starting"
    echo "  -c, --clean       Clean volumes before starting (fresh start)"
    echo "  -d, --detach      Start in detached mode"
    echo "  -h, --help        Show this help message"
    echo ""
    echo "This script will:"
    echo "  1. Check prerequisites (Docker, .env file)"
    echo "  2. Verify Ergo node is running"
    echo "  3. Start Docker services"
    echo "  4. Run health checks"
    echo ""
    echo "Services started:"
    echo "  - Backend API: http://localhost:8000"
    echo "  - Frontend: http://localhost:3000"
    echo "  - API Docs: http://localhost:8000/docs"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -b|--build)
            BUILD=true
            shift
            ;;
        -c|--clean)
            CLEAN=true
            shift
            ;;
        -d|--detach)
            DETACH=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if port is available
port_available() {
    ! lsof -i :"$1" >/dev/null 2>&1
}

# Main execution
main() {
    echo ""
    echo "🦆 DuckPools Coinflip - Development Environment Setup"
    echo "======================================================"
    echo ""

    # Check prerequisites
    print_status "Checking prerequisites..."
    
    # Check Docker
    if ! command_exists docker; then
        print_error "Docker is not installed or not in PATH"
        echo "  Please install Docker from https://www.docker.com/get-started"
        exit 1
    fi

    if ! command_exists docker-compose; then
        print_error "Docker Compose is not installed or not in PATH"
        echo "  Please install Docker Compose"
        exit 1
    fi

    # Check if Docker is running
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker."
        exit 1
    fi

    print_success "✓ Docker is available and running"

    # Check .env file
    if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
        print_warning ".env file not found. Creating from template..."
        cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
        echo "  Please edit $PROJECT_ROOT/.env with your configuration before running the application"
        echo "  Important: Set your HOUSE_ADDRESS and WALLET_PASS"
        echo ""
    else
        print_success "✓ .env file exists"
    fi

    # Check required environment variables
    source "$PROJECT_ROOT/.env"
    if [[ -z "$HOUSE_ADDRESS" ]]; then
        print_warning "HOUSE_ADDRESS is not set in .env"
        echo "  Please set your testnet house address in $PROJECT_ROOT/.env"
        echo ""
    fi

    if [[ -z "$WALLET_PASS" ]]; then
        print_warning "WALLET_PASS is not set in .env"
        echo "  Please set your wallet password in $PROJECT_ROOT/.env"
        echo ""
    fi

    # Check Ergo node
    print_status "Checking Ergo node..."
    if ! curl -s -f http://localhost:9052/info >/dev/null 2>&1; then
        print_error "Ergo node is not running on http://localhost:9052"
        echo "  Please start your Ergo node before continuing"
        echo "  See: https://github.com/ergoplatform/ergo"
        echo ""
        exit 1
    fi
    print_success "✓ Ergo node is running"

    # Check port availability
    print_status "Checking port availability..."
    if ! port_available 8000; then
        print_warning "Port 8000 is already in use (Backend API)"
        echo "  This might cause conflicts if another service is running"
        echo ""
    fi

    if ! port_available 3000; then
        print_warning "Port 3000 is already in use (Frontend)"
        echo "  This might cause conflicts if another service is running"
        echo ""
    fi

    # Clean volumes if requested
    if [[ "$CLEAN" == "true" ]]; then
        print_status "Cleaning Docker volumes..."
        docker compose down -v >/dev/null 2>&1 || true
        print_success "✓ Volumes cleaned"
    fi

    # Build images if requested
    if [[ "$BUILD" == "true" ]]; then
        print_status "Building Docker images..."
        docker compose build --no-cache
        print_success "✓ Images built"
    fi

    # Start services
    print_status "Starting Docker services..."
    if [[ "$DETACH" == "true" ]]; then
        docker compose up -d
        print_success "✓ Services started in detached mode"
    else
        echo ""
        print_status "Starting services (Ctrl+C to stop)..."
        echo ""
        docker compose up
    fi

    # If detached, run health checks
    if [[ "$DETACH" == "true" ]]; then
        print_status "Running health checks..."
        if [[ -f "$PROJECT_ROOT/scripts/health-check.sh" ]]; then
            if "$PROJECT_ROOT/scripts/health-check.sh" --wait; then
                print_success "✓ All services are healthy"
            else
                print_warning "Some services are not healthy. Check logs with: docker compose logs"
            fi
        fi

        echo ""
        echo "🚀 DuckPools is running!"
        echo "======================="
        echo "Frontend:    http://localhost:3000"
        echo "Backend API: http://localhost:8000"
        echo "API Docs:   http://localhost:8000/docs"
        echo ""
        echo "Useful commands:"
        echo "  View logs:    docker compose logs -f [service]"
        echo "  Stop services: docker compose down"
        echo "  Health check: ./scripts/health-check.sh"
        echo ""
    fi
}

# Run main function
main "$@"