#!/bin/bash

# DuckPools Coinflip - Docker Quick Start Script
# This script provides the fastest way to get started with Docker development

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
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

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running or not accessible. Please start Docker."
        exit 1
    fi
}

# Function to check if Ergo node is accessible
check_ergo_node() {
    if ! curl -s http://localhost:9052/info > /dev/null 2>&1; then
        print_warning "Ergo node not accessible on localhost:9052"
        print_info "Make sure Ergo node is running before proceeding"
        echo -n "Continue anyway? (y/N): "
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            print_info "Exiting. Please start Ergo node first."
            exit 0
        fi
    else
        print_success "Ergo node is accessible on localhost:9052"
    fi
}

# Function to setup environment
setup_env() {
    if [ ! -f ".env" ]; then
        print_info "Creating .env file from template..."
        cp .env.example .env
        print_warning "Please edit .env file with your configuration before starting services"
        echo "Required settings:"
        echo "  - HOUSE_ADDRESS=your_testnet_address"
        echo "  - WALLET_PASS=your_wallet_password"
        echo "  - NODE_API_KEY=your_api_key"
        echo ""
        echo -n "Edit .env file now? (Y/n): "
        read -r response
        if [[ ! "$response" =~ ^[Nn]$ ]]; then
            ${EDITOR:-nano} .env
        fi
    else
        print_success ".env file already exists"
    fi
}

# Function to show status
show_status() {
    print_info "Container Status:"
    echo "----------------------------------------"
    docker ps --filter "name=duckpools" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "No duckpools containers running"
    echo ""
    print_info "Service URLs:"
    echo "----------------------------------------"
    echo "Frontend:  http://localhost:3000"
    echo "Backend:   http://localhost:8000"
    echo "API Docs:  http://localhost:8000/docs"
    echo "Health:    http://localhost:8000/health"
}

# Main script logic
case "${1:-help}" in
    setup)
        print_info "Setting up Docker development environment..."
        check_docker
        setup_env
        check_ergo_node
        print_success "Setup complete! Run './docker-quickstart.sh start' to begin"
        ;;
    
    start)
        print_info "Starting DuckPools development environment..."
        check_docker
        setup_env
        check_ergo_node
        
        print_info "Starting services..."
        docker compose up -d
        
        print_success "Services started!"
        show_status
        print_info "View logs with: ./docker-quickstart.sh logs"
        ;;
    
    stop)
        print_info "Stopping DuckPools services..."
        docker compose down
        print_success "Services stopped"
        ;;
    
    restart)
        print_info "Restarting DuckPools services..."
        docker compose down
        docker compose up -d
        print_success "Services restarted"
        show_status
        ;;
    
    logs)
        if [ "$2" = "follow" ] || [ "$2" = "-f" ]; then
            print_info "Following logs (Ctrl+C to stop)..."
            docker compose logs -f "${3:-}"
        else
            print_info "Showing logs..."
            docker compose logs "${2:-}"
        fi
        ;;
    
    status)
        show_status
        ;;
    
    build)
        print_info "Building Docker images..."
        docker compose build
        print_success "Images built successfully"
        ;;
    
    clean)
        print_warning "This will remove all DuckPools containers, images, and volumes!"
        echo -n "Are you sure? (y/N): "
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            print_info "Stopping containers..."
            docker compose down 2>/dev/null || true
            print_info "Removing images..."
            docker images | grep duckpools | awk '{print $3}' | xargs -r docker rmi -f 2>/dev/null || true
            print_info "Removing volumes..."
            docker volume ls | grep duckpools | awk '{print $2}' | xargs -r docker volume rm 2>/dev/null || true
            print_success "Clean complete"
        else
            print_info "Clean cancelled"
        fi
        ;;
    
    help|--help|-h|"")
        echo "DuckPools Docker Quick Start Script"
        echo ""
        echo "Usage: $0 [COMMAND]"
        echo ""
        echo "Commands:"
        echo "  setup     Setup environment and .env file"
        echo "  start     Start all services (alias: up)"
        echo "  stop      Stop all services (alias: down)"
        echo "  restart   Restart all services"
        echo "  logs      Show logs (add '-f' to follow)"
        echo "  status    Show container status and URLs"
        echo "  build     Rebuild Docker images"
        echo "  clean     Remove all Docker resources"
        echo "  help      Show this help message"
        echo ""
        echo "Quick Start:"
        echo "  $0 setup  # First time setup"
        echo "  $0 start  # Start services"
        echo "  $0 logs -f # Follow logs"
        echo ""
        echo "For advanced commands, use: ./docker-manage.sh"
        ;;
    
    *)
        print_error "Unknown command: $1"
        $0 help
        exit 1
        ;;
esac