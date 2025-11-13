#!/bin/bash

# Deploy Performance Optimizations Script
# Safely deploys performance optimizations to Archon platform

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_ROOT/backups/$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$PROJECT_ROOT/performance_optimization_deployment.log"

# Functions
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Create backup directory
create_backup() {
    log "Creating backup directory: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"

    # Backup current docker-compose.yml
    if [ -f "$PROJECT_ROOT/deployment/docker-compose.yml" ]; then
        cp "$PROJECT_ROOT/deployment/docker-compose.yml" "$BACKUP_DIR/docker-compose.yml.bak"
        print_success "Backed up docker-compose.yml"
    fi

    # Backup any existing performance configs
    if [ -d "$PROJECT_ROOT/config/performance" ]; then
        cp -r "$PROJECT_ROOT/config/performance" "$BACKUP_DIR/performance_config.bak"
        print_success "Backed up existing performance config"
    fi
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker not found. Please install Docker first."
        exit 1
    fi

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose not found. Please install Docker Compose first."
        exit 1
    fi

    # Check if services are running
    if docker ps --format "table {{.Names}}" | grep -q archon; then
        print_warning "Archon services are currently running. They will need to be restarted."
    fi

    # Check available system resources
    local available_memory=$(free -g | awk '/^Mem:/{print $7}')
    if [ "$available_memory" -lt 4 ]; then
        print_warning "Less than 4GB of available memory detected. Performance optimizations may require more memory."
    fi

    print_success "Prerequisites check completed"
}

# Deploy configuration files
deploy_configs() {
    print_header "Deploying Performance Configurations"

    # Create performance config directory
    mkdir -p "$PROJECT_ROOT/config/performance"

    # Create data directories for optimized volumes
    mkdir -p "$PROJECT_ROOT/data/memgraph"
    mkdir -p "$PROJECT_ROOT/data/qdrant"
    mkdir -p "$PROJECT_ROOT/data/qdrant_snapshots"

    # Set permissions for data directories
    chmod 755 "$PROJECT_ROOT/data"/*

    # Copy performance configurations
    if [ -f "$PROJECT_ROOT/config/performance/database_optimization.py" ]; then
        print_success "Database optimization config already exists"
    else
        print_warning "Database optimization config not found - it should have been created by the optimization script"
    fi

    print_success "Configuration deployment completed"
}

# Update environment variables
update_environment() {
    print_header "Updating Environment Configuration"

    # Add performance-related environment variables to .env if they don't exist
    local env_file="$PROJECT_ROOT/.env"

    if [ ! -f "$env_file" ]; then
        print_warning ".env file not found. Creating from .env.example"
        cp "$PROJECT_ROOT/.env.example" "$env_file"
    fi

    # Performance tuning variables
    local perf_vars=(
        "MAX_BACKGROUND_TASKS=10"
        "TASK_TIMEOUT_SECONDS=300"
        "UVICORN_WORKERS=2"
        "INTELLIGENCE_WORKERS=1"
        "SEARCH_WORKERS=1"
        "HTTPX_POOL_CONNECTIONS=100"
        "HTTPX_POOL_MAXSIZE=100"
        "MAX_CONCURRENT_EXTRACTIONS=3"
        "EXTRACTION_TIMEOUT_SECONDS=120"
        "DB_POOL_SIZE=10"
        "DB_MAX_OVERFLOW=20"
        "SEARCH_CACHE_SIZE=500"
        "CACHE_TTL_SECONDS=300"
    )

    for var in "${perf_vars[@]}"; do
        local var_name=$(echo "$var" | cut -d'=' -f1)
        if ! grep -q "^${var_name}=" "$env_file"; then
            echo "$var" >> "$env_file"
            log "Added $var to .env"
        fi
    done

    print_success "Environment configuration updated"
}

# Run system health check
run_health_check() {
    print_header "Running System Health Check"

    # Check if services are accessible
    local services=("archon-server:8181" "archon-mcp:8051" "memgraph:7444" "qdrant:6333")

    for service in "${services[@]}"; do
        local name=$(echo "$service" | cut -d':' -f1)
        local port=$(echo "$service" | cut -d':' -f2)

        if nc -z localhost "$port" 2>/dev/null; then
            print_success "$name is accessible on port $port"
        else
            print_warning "$name is not accessible on port $port (this is normal if services aren't running)"
        fi
    done

    # System resource check
    local cpu_cores=$(nproc)
    local total_memory=$(free -g | awk '/^Mem:/{print $2}')
    local available_disk=$(df -BG / | awk 'NR==2{print $4}' | sed 's/G//')

    log "System Resources - CPU Cores: $cpu_cores, Memory: ${total_memory}GB, Available Disk: ${available_disk}GB"

    if [ "$cpu_cores" -lt 2 ]; then
        print_warning "Less than 2 CPU cores detected. Consider upgrading for better performance."
    fi

    if [ "$total_memory" -lt 8 ]; then
        print_warning "Less than 8GB total memory detected. Consider upgrading for optimal performance."
    fi

    print_success "Health check completed"
}

# Start optimized services
start_services() {
    print_header "Starting Optimized Services"

    # Stop existing services if running
    if docker ps --format "table {{.Names}}" | grep -q archon; then
        log "Stopping existing Archon services..."
        docker compose -f deployment/docker-compose.yml down || print_warning "Some services may not have stopped cleanly"
    fi

    # Start with performance optimizations
    log "Starting services with performance optimizations..."

    if [ -f "$PROJECT_ROOT/deployment/docker-compose.performance.yml" ]; then
        # Use performance overlay
        docker compose -f deployment/docker-compose.yml -f deployment/docker-compose.performance.yml up -d
        print_success "Started services with performance optimizations"
    else
        print_error "Performance optimization file not found. Starting with default configuration."
        docker compose -f deployment/docker-compose.yml up -d
    fi

    # Wait for services to be ready
    log "Waiting for services to become healthy..."
    sleep 30

    # Check service health
    local healthy_services=0
    local total_services=0

    for service in archon-server archon-mcp memgraph qdrant; do
        total_services=$((total_services + 1))
        if docker ps --filter "name=$service" --filter "status=running" --format "table {{.Names}}" | grep -q "$service"; then
            healthy_services=$((healthy_services + 1))
            print_success "$service is running"
        else
            print_warning "$service is not running"
        fi
    done

    log "Service health: $healthy_services/$total_services services running"

    if [ "$healthy_services" -eq "$total_services" ]; then
        print_success "All core services started successfully"
    elif [ "$healthy_services" -gt 0 ]; then
        print_warning "Some services started successfully ($healthy_services/$total_services)"
    else
        print_error "No services started successfully. Check logs with: docker compose logs"
        return 1
    fi
}

# Run performance baseline
run_baseline() {
    print_header "Running Performance Baseline"

    # Wait for services to stabilize
    log "Waiting for services to stabilize before baseline..."
    sleep 60

    # Run baseline measurement
    if [ -f "$PROJECT_ROOT/scripts/performance_baseline.py" ]; then
        log "Running performance baseline measurement..."

        if poetry run python "$PROJECT_ROOT/scripts/performance_baseline.py" --output "$PROJECT_ROOT/baseline_$(date +%Y%m%d_%H%M%S).json"; then
            print_success "Performance baseline completed successfully"
        else
            print_warning "Performance baseline failed - continuing with deployment"
        fi
    else
        print_warning "Performance baseline script not found"
    fi
}

# Cleanup function
cleanup_on_error() {
    print_error "Deployment failed. Cleaning up..."

    # Stop any services that were started
    docker compose -f deployment/docker-compose.yml down 2>/dev/null || true

    # Restore from backup if needed
    if [ -f "$BACKUP_DIR/docker-compose.yml.bak" ]; then
        cp "$BACKUP_DIR/docker-compose.yml.bak" "$PROJECT_ROOT/deployment/docker-compose.yml"
        print_success "Restored docker-compose.yml from backup"
    fi

    print_error "Deployment failed. Check $LOG_FILE for details."
    exit 1
}

# Main deployment function
main() {
    print_header "ARCHON PERFORMANCE OPTIMIZATION DEPLOYMENT"
    log "Starting performance optimization deployment"

    # Set error handler
    trap cleanup_on_error ERR

    # Create backup
    create_backup

    # Run checks and deployment steps
    check_prerequisites
    deploy_configs
    update_environment
    run_health_check
    start_services
    run_baseline

    print_header "DEPLOYMENT COMPLETED SUCCESSFULLY"
    print_success "Performance optimizations have been deployed!"
    print_success "Backup created at: $BACKUP_DIR"
    print_success "Logs available at: $LOG_FILE"

    echo ""
    echo -e "${BLUE}Next Steps:${NC}"
    echo "1. Monitor service performance with: docker compose logs -f"
    echo "2. Run continuous monitoring: poetry run python scripts/performance_baseline.py --monitor"
    echo "3. Check service health: curl http://localhost:8181/health"
    echo ""
    echo -e "${BLUE}Performance Targets:${NC}"
    echo "• Service startup time: <30 seconds"
    echo "• API response time: <2 seconds"
    echo "• Memory usage: <80% of allocated resources"
    echo "• CPU usage: <70% sustained load"
    echo "• Service availability: >99.9%"

    log "Performance optimization deployment completed successfully"
}

# Script execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
