#!/bin/bash
# ==============================================================================
# FinanceGPT Quick Start Script
# ==============================================================================
# Usage: ./run.sh [command]
#
# Commands:
#   start   - Start FinanceGPT (default)
#   stop    - Stop FinanceGPT
#   restart - Restart FinanceGPT
#   logs    - Show logs (follow mode)
#   status  - Show container status
#   update  - Pull latest image and restart
#   clean   - Stop and remove all data (DESTRUCTIVE!)

set -e

COMPOSE_FILE="docker-compose.quickstart.yml"
CONTAINER_NAME="financegpt"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_banner() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════╗"
    echo "║         FinanceGPT All-in-One             ║"
    echo "╚═══════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        echo "  → https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi
}

start() {
    print_banner
    check_docker
    
    echo "Starting FinanceGPT..."
    
    # Check if .env exists
    if [ -f ".env" ]; then
        print_status "Using configuration from .env"
    else
        print_warning "No .env file found. Using defaults."
        echo "  → Copy .env.example to .env to customize settings"
    fi
    
    # Pull latest image if not exists
    echo ""
    echo "Pulling latest image (if needed)..."
    docker compose -f "$COMPOSE_FILE" pull
    
    # Start container
    echo ""
    echo "Starting container..."
    docker compose -f "$COMPOSE_FILE" up -d
    
    echo ""
    print_status "FinanceGPT is starting!"
    echo ""
    echo "  Frontend:  http://localhost:${FRONTEND_PORT:-3000}"
    echo "  Backend:   http://localhost:${BACKEND_PORT:-8000}"
    echo "  API Docs:  http://localhost:${BACKEND_PORT:-8000}/docs"
    echo ""
    echo "  Note: First startup takes ~2 minutes to initialize databases."
    echo "  Run './run.sh logs' to watch startup progress."
}

stop() {
    print_banner
    echo "Stopping FinanceGPT..."
    docker compose -f "$COMPOSE_FILE" down
    print_status "FinanceGPT stopped."
}

restart() {
    print_banner
    echo "Restarting FinanceGPT..."
    docker compose -f "$COMPOSE_FILE" restart
    print_status "FinanceGPT restarted."
}

logs() {
    docker compose -f "$COMPOSE_FILE" logs -f
}

status() {
    print_banner
    echo "Container Status:"
    echo ""
    docker compose -f "$COMPOSE_FILE" ps
    echo ""
    
    # Check if running and show health
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo "unknown")
        echo "Health: $HEALTH"
        
        if [ "$HEALTH" = "healthy" ]; then
            print_status "FinanceGPT is running and healthy!"
        elif [ "$HEALTH" = "starting" ]; then
            print_warning "FinanceGPT is still starting up..."
        else
            print_warning "Health status: $HEALTH"
        fi
    else
        print_warning "FinanceGPT is not running."
    fi
}

update() {
    print_banner
    echo "Updating FinanceGPT..."
    
    echo "Pulling latest image..."
    docker compose -f "$COMPOSE_FILE" pull
    
    echo "Restarting with new image..."
    docker compose -f "$COMPOSE_FILE" up -d
    
    print_status "FinanceGPT updated!"
}

clean() {
    print_banner
    print_warning "This will DELETE all FinanceGPT data!"
    echo ""
    read -p "Are you sure? Type 'yes' to confirm: " confirm
    
    if [ "$confirm" = "yes" ]; then
        echo "Stopping and removing containers..."
        docker compose -f "$COMPOSE_FILE" down -v
        
        echo "Removing data volume..."
        docker volume rm financegpt-data 2>/dev/null || true
        
        print_status "All FinanceGPT data has been removed."
    else
        echo "Cancelled."
    fi
}

# Main command handler
case "${1:-start}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    logs)
        logs
        ;;
    status)
        status
        ;;
    update)
        update
        ;;
    clean)
        clean
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|logs|status|update|clean}"
        echo ""
        echo "Commands:"
        echo "  start   - Start FinanceGPT (default)"
        echo "  stop    - Stop FinanceGPT"
        echo "  restart - Restart FinanceGPT"
        echo "  logs    - Show logs (follow mode)"
        echo "  status  - Show container status"
        echo "  update  - Pull latest image and restart"
        echo "  clean   - Stop and remove all data (DESTRUCTIVE!)"
        exit 1
        ;;
esac
