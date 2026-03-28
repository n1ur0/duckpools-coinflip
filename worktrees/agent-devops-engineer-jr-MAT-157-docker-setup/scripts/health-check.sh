#!/bin/bash
# =============================================================================
# DuckPools Coinflip - Health Check Script
# =============================================================================
#
# This script checks the health of all Docker services.
# Usage: ./scripts/health-check.sh [options]
#
# Options:
#   -v, --verbose    Show detailed output
#   -w, --wait       Wait until all services are healthy
#   -t, --timeout N  Timeout in seconds (default: 60)
#   -h, --help       Show this help message
#
# =============================================================================

set -e

# Configuration
VERBOSE=false
WAIT=false
TIMEOUT=60
SERVICES=("backend-api" "frontend" "off-chain-bot")
HEALTH_URLS=(
    "http://localhost:8000/health"
    "http://localhost:3000"
    "none"  # off-chain-bot has no HTTP endpoint
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Help message
show_help() {
    echo "DuckPools Health Check Script"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -v, --verbose    Show detailed output"
    echo "  -w, --wait       Wait until all services are healthy"
    echo "  -t, --timeout N  Timeout in seconds (default: $TIMEOUT)"
    echo "  -h, --help       Show this help message"
    echo ""
    echo "Services checked:"
    for i in "${!SERVICES[@]}"; do
        echo "  - ${SERVICES[i]} (${HEALTH_URLS[i]})"
    done
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -w|--wait)
            WAIT=true
            shift
            ;;
        -t|--timeout)
            TIMEOUT="$2"
            shift 2
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

# Check if docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    exit 1
fi

# Function to check service health
check_service_health() {
    local service=$1
    local url=$2
    
    if [[ "$url" == "none" ]]; then
        # Check if container is running (no HTTP endpoint)
        if docker compose ps -q $service | xargs docker inspect -f '{{.State.Status}}' 2>/dev/null | grep -q "running"; then
            echo -e "${GREEN}✓${NC} $service: Container is running"
            return 0
        else
            echo -e "${RED}✗${NC} $service: Container is not running"
            return 1
        fi
    else
        # Check HTTP endpoint
        if curl -s -f --max-time 5 "$url" > /dev/null 2>&1; then
            echo -e "${GREEN}✓${NC} $service: Healthy ($url)"
            return 0
        else
            echo -e "${RED}✗${NC} $service: Unhealthy ($url)"
            return 1
        fi
    fi
}

# Function to get detailed service info
get_service_info() {
    local service=$1
    if [[ "$VERBOSE" == "true" ]]; then
        echo ""
        echo "=== $service Details ==="
        docker compose ps $service
        echo ""
    fi
}

# Main health check loop
check_all_services() {
    local all_healthy=true
    
    for i in "${!SERVICES[@]}"; do
        if ! check_service_health "${SERVICES[i]}" "${HEALTH_URLS[i]}"; then
            all_healthy=false
            get_service_info "${SERVICES[i]}"
        elif [[ "$VERBOSE" == "true" ]]; then
            get_service_info "${SERVICES[i]}"
        fi
    done
    
    if [[ "$all_healthy" == "true" ]]; then
        echo ""
        echo -e "${GREEN}All services are healthy!${NC}"
        return 0
    else
        echo ""
        echo -e "${RED}Some services are unhealthy${NC}"
        return 1
    fi
}

# Wait for services to be healthy
wait_for_healthy() {
    local start_time=$(date +%s)
    local current_time
    
    echo -e "${YELLOW}Waiting for services to be healthy...${NC}"
    
    while true; do
        current_time=$(date +%s)
        local elapsed=$((current_time - start_time))
        
        if [[ $elapsed -ge $TIMEOUT ]]; then
            echo -e "${RED}Timeout after $TIMEOUT seconds${NC}"
            exit 1
        fi
        
        if check_all_services; then
            exit 0
        fi
        
        sleep 5
    done
}

# Main execution
echo "DuckPools Health Check"
echo "======================"

if [[ "$WAIT" == "true" ]]; then
    wait_for_healthy
else
    check_all_services
fi