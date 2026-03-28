#!/bin/bash

# DuckPools Docker Management Script
# This script provides easy commands for managing Docker environments

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

# Function to show help
show_help() {
    echo "DuckPools Docker Management Script"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  dev [up|down|logs|build]    Manage development environment"
    echo "  prod [up|down|logs|build]   Manage production environment"
    echo "  clean [all|images|volumes]  Clean Docker resources"
    echo "  status                      Show status of all containers"
    echo "  help                        Show this help message"
    echo ""
    echo "Development Commands:"
    echo "  $0 dev up       Start development environment"
    echo "  $0 dev down     Stop development environment"
    echo "  $0 dev logs     Follow logs of all services"
    echo "  $0 dev build    Build development images"
    echo ""
    echo "Production Commands:"
    echo "  $0 prod up      Start production environment"
    echo "  $0 prod down    Stop production environment"
    echo "  $0 prod logs    Follow logs of all services"
    echo "  $0 prod build   Build production images"
    echo ""
    echo "Clean Commands:"
    echo "  $0 clean all    Remove containers, images, and volumes"
    echo "  $0 clean images Remove all DuckPools images"
    echo "  $0 clean volumes Remove all DuckPools volumes"
    echo ""
    echo "Examples:"
    echo "  $0 dev up                Start development environment"
    echo "  $0 prod logs -f backend  Follow backend logs in production"
    echo "  $0 clean all            Clean all Docker resources"
}

# Function for development environment
dev_env() {
    check_docker
    case $1 in
        up)
            print_info "Starting development environment..."
            docker-compose up -d
            print_success "Development environment started!"
            echo "Frontend: http://localhost:3000"
            echo "Backend API: http://localhost:8000"
            echo "API Docs: http://localhost:8000/docs"
            ;;
        down)
            print_info "Stopping development environment..."
            docker-compose down
            print_success "Development environment stopped!"
            ;;
        logs)
            print_info "Showing logs..."
            if [ "$2" = "-f" ] || [ "$2" = "follow" ]; then
                docker-compose logs -f "${3:-}"
            else
                docker-compose logs "${2:-}"
            fi
            ;;
        build)
            print_info "Building development images..."
            docker-compose build
            print_success "Development images built!"
            ;;
        *)
            print_error "Unknown dev command: $1"
            echo "Available dev commands: up, down, logs, build"
            exit 1
            ;;
    esac
}

# Function for production environment
prod_env() {
    check_docker
    case $1 in
        up)
            print_info "Starting production environment..."
            if [ ! -f ".env.prod" ]; then
                print_warning "Production .env file not found. Creating from template..."
                cp .env.example .env.prod
                print_warning "Please edit .env.prod with your production settings before starting."
                exit 1
            fi
            docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d
            print_success "Production environment started!"
            ;;
        down)
            print_info "Stopping production environment..."
            docker-compose -f docker-compose.prod.yml down
            print_success "Production environment stopped!"
            ;;
        logs)
            print_info "Showing production logs..."
            if [ "$2" = "-f" ] || [ "$2" = "follow" ]; then
                docker-compose -f docker-compose.prod.yml logs -f "${3:-}"
            else
                docker-compose -f docker-compose.prod.yml logs "${2:-}"
            fi
            ;;
        build)
            print_info "Building production images..."
            docker-compose -f docker-compose.prod.yml build
            print_success "Production images built!"
            ;;
        *)
            print_error "Unknown prod command: $1"
            echo "Available prod commands: up, down, logs, build"
            exit 1
            ;;
    esac
}

# Function to clean Docker resources
clean_docker() {
    check_docker
    case $1 in
        all)
            print_warning "This will remove all DuckPools containers, images, and volumes!"
            read -p "Are you sure? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                print_info "Stopping all containers..."
                docker-compose down 2>/dev/null || true
                docker-compose -f docker-compose.prod.yml down 2>/dev/null || true
                
                print_info "Removing all DuckPools images..."
                docker images | grep duckpools | awk '{print $3}' | xargs -r docker rmi -f
                
                print_info "Removing all DuckPools volumes..."
                docker volume ls | grep duckpools | awk '{print $2}' | xargs -r docker volume rm
                
                print_success "All Docker resources cleaned!"
            else
                print_info "Clean cancelled."
            fi
            ;;
        images)
            print_info "Removing all DuckPools images..."
            docker images | grep duckpools | awk '{print $3}' | xargs -r docker rmi -f
            print_success "All DuckPools images removed!"
            ;;
        volumes)
            print_warning "This will remove all DuckPools volumes!"
            read -p "Are you sure? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                print_info "Removing all DuckPools volumes..."
                docker volume ls | grep duckpools | awk '{print $2}' | xargs -r docker volume rm
                print_success "All DuckPools volumes removed!"
            else
                print_info "Clean cancelled."
            fi
            ;;
        *)
            print_error "Unknown clean command: $1"
            echo "Available clean commands: all, images, volumes"
            exit 1
            ;;
    esac
}

# Function to show status
show_status() {
    check_docker
    print_info "DuckPools Container Status:"
    echo "----------------------------------------"
    docker ps --filter "name=duckpools" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    print_info "DuckPools Images:"
    echo "----------------------------------------"
    docker images | grep duckpools
}

# Main script logic
case $1 in
    dev)
        dev_env "${2:-}"
        ;;
    prod)
        prod_env "${2:-}"
        ;;
    clean)
        clean_docker "${2:-}"
        ;;
    status)
        show_status
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac