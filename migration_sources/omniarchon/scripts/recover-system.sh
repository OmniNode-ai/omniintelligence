#!/bin/bash
#
# ARCHON SYSTEM RECOVERY SCRIPT
# =============================
#
# Comprehensive system recovery wrapper for Archon platform
#
# Usage:
#   ./scripts/recover-system.sh                    # Full system recovery
#   ./scripts/recover-system.sh --monitor          # Start continuous monitoring
#   ./scripts/recover-system.sh --validate         # Validate system stability
#   ./scripts/recover-system.sh --quick            # Quick recovery (skip some steps)
#

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Log function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check dependencies
check_dependencies() {
    log "Checking dependencies..."

    # Check if Python 3 is available
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is required but not installed"
        exit 1
    fi

    # Check if Docker is available and running
    if ! command -v docker &> /dev/null; then
        error "Docker is required but not installed"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        error "Docker is not running"
        exit 1
    fi

    # Check if docker-compose is available
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        error "Docker Compose is required but not installed"
        exit 1
    fi

    success "All dependencies are available"
}

# Install Python dependencies
install_python_deps() {
    log "Installing Python dependencies for recovery scripts..."

    cd "$PROJECT_ROOT"

    # Install poetry if not available
    if ! command -v poetry &> /dev/null; then
        pip install poetry
    fi

    # Install dependencies with poetry
    poetry install --no-interaction --no-ansi

    success "Python dependencies installed"
}

# Quick status check
quick_status() {
    log "Performing quick system status check..."

    echo ""
    echo "=== DOCKER CONTAINER STATUS ==="
    docker ps -a --filter "name=archon" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

    echo ""
    echo "=== SERVICE HEALTH CHECKS ==="

    # Check key services
    local services=(
        "localhost:8181/health:Main Server"
        "localhost:8051:MCP Server"
        "localhost:8053/health:Intelligence Service"
        "localhost:6333:Qdrant Vector DB"
        "localhost:7444:Memgraph Knowledge Graph"
    )

    for service in "${services[@]}"; do
        IFS=':' read -r url name <<< "$service"
        if curl -s --max-time 5 "http://$url" > /dev/null 2>&1; then
            echo -e "  ${GREEN}✓${NC} $name ($url)"
        else
            echo -e "  ${RED}✗${NC} $name ($url)"
        fi
    done

    echo ""
}

# Full system recovery
full_recovery() {
    log "Starting full system recovery..."

    cd "$PROJECT_ROOT"

    # Run the Python recovery script with poetry
    log "Executing Python recovery system..."
    poetry run python "$SCRIPT_DIR/system_recovery.py" --action recovery

    local exit_code=$?

    if [ $exit_code -eq 0 ]; then
        success "System recovery completed successfully"

        # Optional: Start monitoring
        read -p "Start continuous monitoring? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            start_monitoring
        fi
    else
        error "System recovery failed (exit code: $exit_code)"
        warning "Check the logs for details: system_recovery.log"
        exit $exit_code
    fi
}

# Start monitoring
start_monitoring() {
    log "Starting health monitoring..."

    cd "$PROJECT_ROOT"

    echo ""
    echo "Choose monitoring mode:"
    echo "1. Dashboard (real-time visual dashboard)"
    echo "2. Background (log-based monitoring)"
    echo "3. Auto-recovery (monitoring with automatic recovery)"

    read -p "Enter choice (1-3) [1]: " -n 1 -r
    echo

    case $REPLY in
        2)
            poetry run python "$SCRIPT_DIR/health_monitor.py"
            ;;
        3)
            poetry run python "$SCRIPT_DIR/health_monitor.py" --auto-recovery
            ;;
        *)
            poetry run python "$SCRIPT_DIR/health_monitor.py" --dashboard
            ;;
    esac
}

# Validate system
validate_system() {
    log "Validating system stability..."

    cd "$PROJECT_ROOT"

    poetry run python "$SCRIPT_DIR/system_recovery.py" --action validate

    local exit_code=$?

    if [ $exit_code -eq 0 ]; then
        success "System validation passed"
    else
        error "System validation failed"
        exit $exit_code
    fi
}

# Emergency stop
emergency_stop() {
    log "Performing emergency stop of all services..."

    cd "$PROJECT_ROOT"

    # Stop all Archon containers
    docker ps -q --filter "name=archon" | xargs -r docker stop

    # Stop docker-compose services
    docker compose -f deployment/docker-compose.yml down

    success "Emergency stop completed"
}

# Show usage
show_usage() {
    cat << EOF
ARCHON SYSTEM RECOVERY

Usage: $0 [OPTIONS]

OPTIONS:
    --monitor           Start continuous health monitoring
    --validate          Validate system stability
    --quick            Quick recovery (skip some validation steps)
    --status           Show current system status
    --emergency-stop   Emergency stop all services
    --help             Show this help message

EXAMPLES:
    $0                        # Full system recovery
    $0 --monitor             # Start monitoring dashboard
    $0 --validate            # Check system stability
    $0 --status              # Quick status check

EOF
}

# Main script logic
main() {
    echo ""
    echo "==============================================="
    echo "🚀 ARCHON SYSTEM RECOVERY"
    echo "==============================================="
    echo ""

    # Parse arguments
    case "${1:-}" in
        --monitor)
            check_dependencies
            install_python_deps
            start_monitoring
            ;;
        --validate)
            check_dependencies
            install_python_deps
            validate_system
            ;;
        --status)
            quick_status
            ;;
        --emergency-stop)
            emergency_stop
            ;;
        --quick)
            check_dependencies
            install_python_deps
            log "Starting quick recovery (limited validation)..."
            cd "$PROJECT_ROOT"
            poetry run python "$SCRIPT_DIR/system_recovery.py" --action cleanup
            success "Quick recovery completed"
            ;;
        --help)
            show_usage
            ;;
        "")
            # Default: full recovery
            check_dependencies
            install_python_deps
            quick_status

            echo ""
            read -p "Proceed with full system recovery? (Y/n): " -n 1 -r
            echo ""

            if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                full_recovery
            else
                log "Recovery cancelled by user"
            fi
            ;;
        *)
            error "Unknown option: $1"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
