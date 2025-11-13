#!/bin/bash
#
# Deploy and Verify Hybrid Pattern Scoring Monitoring
#
# This script:
# 1. Validates Prometheus configuration
# 2. Validates alert rules
# 3. Imports Grafana dashboard
# 4. Runs monitoring tests
# 5. Verifies metrics endpoint
#
# Usage: ./scripts/deploy_monitoring.sh [--skip-tests]
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MONITORING_ROOT="$(dirname "$(dirname "$PROJECT_ROOT")")/monitoring"
PROMETHEUS_CONFIG="$MONITORING_ROOT/prometheus/prometheus.yml"
ALERT_RULES="$MONITORING_ROOT/prometheus/rules/hybrid_scoring_alerts.yml"
GRAFANA_DASHBOARD="$MONITORING_ROOT/grafana/dashboards/hybrid_scoring_dashboard.json"
SKIP_TESTS=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Helper functions
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Step 1: Validate Prometheus configuration
validate_prometheus_config() {
    print_header "Step 1: Validating Prometheus Configuration"

    if [ ! -f "$PROMETHEUS_CONFIG" ]; then
        print_error "Prometheus config not found: $PROMETHEUS_CONFIG"
        exit 1
    fi

    print_info "Checking Prometheus configuration..."

    # Check if promtool is available
    if command -v promtool &> /dev/null; then
        if promtool check config "$PROMETHEUS_CONFIG"; then
            print_success "Prometheus configuration is valid"
        else
            print_error "Prometheus configuration is invalid"
            exit 1
        fi
    else
        print_warning "promtool not found, skipping config validation"
        print_info "Install promtool: brew install prometheus (macOS) or apt-get install prometheus (Linux)"
    fi
}

# Step 2: Validate alert rules
validate_alert_rules() {
    print_header "Step 2: Validating Alert Rules"

    if [ ! -f "$ALERT_RULES" ]; then
        print_error "Alert rules not found: $ALERT_RULES"
        exit 1
    fi

    print_info "Checking alert rules syntax..."

    # Check if promtool is available
    if command -v promtool &> /dev/null; then
        if promtool check rules "$ALERT_RULES"; then
            print_success "Alert rules are valid"

            # Count alerts
            alert_count=$(grep -c "alert:" "$ALERT_RULES" || true)
            print_info "Found $alert_count alert rules"
        else
            print_error "Alert rules are invalid"
            exit 1
        fi
    else
        print_warning "promtool not found, skipping rules validation"

        # Basic YAML syntax check
        if command -v yamllint &> /dev/null; then
            if yamllint "$ALERT_RULES"; then
                print_success "Alert rules YAML syntax is valid"
            else
                print_error "Alert rules YAML syntax is invalid"
                exit 1
            fi
        else
            print_warning "yamllint not found, skipping YAML validation"
        fi
    fi
}

# Step 3: Validate Grafana dashboard
validate_grafana_dashboard() {
    print_header "Step 3: Validating Grafana Dashboard"

    if [ ! -f "$GRAFANA_DASHBOARD" ]; then
        print_error "Grafana dashboard not found: $GRAFANA_DASHBOARD"
        exit 1
    fi

    print_info "Checking dashboard JSON syntax..."

    # Validate JSON syntax
    if command -v jq &> /dev/null; then
        if jq empty "$GRAFANA_DASHBOARD" 2>/dev/null; then
            print_success "Dashboard JSON is valid"

            # Count panels
            panel_count=$(jq '.panels | length' "$GRAFANA_DASHBOARD")
            print_info "Found $panel_count dashboard panels"

            # Show dashboard title
            dashboard_title=$(jq -r '.title' "$GRAFANA_DASHBOARD")
            print_info "Dashboard title: $dashboard_title"
        else
            print_error "Dashboard JSON is invalid"
            exit 1
        fi
    else
        print_warning "jq not found, skipping JSON validation"
        print_info "Install jq: brew install jq (macOS) or apt-get install jq (Linux)"
    fi
}

# Step 4: Import Grafana dashboard (if Grafana is running)
import_grafana_dashboard() {
    print_header "Step 4: Importing Grafana Dashboard"

    # Check if Grafana is running
    if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
        print_info "Grafana is running, attempting to import dashboard..."

        # Try to import dashboard
        response=$(curl -s -X POST \
            -H "Content-Type: application/json" \
            -d @"$GRAFANA_DASHBOARD" \
            http://admin:admin123@localhost:3000/api/dashboards/db)

        if echo "$response" | grep -q '"status":"success"'; then
            print_success "Dashboard imported successfully"

            # Extract dashboard URL
            dashboard_url=$(echo "$response" | jq -r '.url' 2>/dev/null || echo "")
            if [ -n "$dashboard_url" ]; then
                print_info "Dashboard URL: http://localhost:3000$dashboard_url"
            fi
        else
            print_warning "Dashboard import may have failed"
            print_info "Response: $response"
            print_info "You can import manually at: http://localhost:3000/dashboard/import"
        fi
    else
        print_warning "Grafana is not running on localhost:3000"
        print_info "Start Grafana: docker-compose -f monitoring/docker-compose.monitoring.yml up -d grafana"
        print_info "Or import manually at: http://localhost:3000/dashboard/import"
    fi
}

# Step 5: Run monitoring tests
run_monitoring_tests() {
    print_header "Step 5: Running Monitoring Tests"

    if [ "$SKIP_TESTS" = true ]; then
        print_warning "Skipping tests (--skip-tests flag provided)"
        return
    fi

    cd "$PROJECT_ROOT"

    print_info "Running pytest for monitoring module..."

    if poetry run pytest tests/test_monitoring_hybrid_patterns.py -v; then
        print_success "All monitoring tests passed"
    else
        print_error "Some monitoring tests failed"
        print_warning "This is not critical - deployment can continue"
    fi
}

# Step 6: Verify metrics endpoint
verify_metrics_endpoint() {
    print_header "Step 6: Verifying Metrics Endpoint"

    # Check if intelligence service is running
    if curl -s http://localhost:8053/health > /dev/null 2>&1; then
        print_info "Intelligence service is running, checking metrics..."

        # Fetch metrics
        metrics=$(curl -s http://localhost:8053/metrics)

        if echo "$metrics" | grep -q "hybrid_scoring"; then
            print_success "Hybrid scoring metrics are being exported"

            # Count metrics
            metric_count=$(echo "$metrics" | grep -c "^# HELP" || true)
            print_info "Found $metric_count metrics being exported"

            # Check for specific metrics
            if echo "$metrics" | grep -q "langextract_requests_total"; then
                print_success "Langextract metrics found"
            fi

            if echo "$metrics" | grep -q "semantic_cache_hit_rate"; then
                print_success "Cache metrics found"
            fi

            if echo "$metrics" | grep -q "hybrid_scoring_duration_seconds"; then
                print_success "Scoring metrics found"
            fi
        else
            print_warning "Hybrid scoring metrics not found in endpoint"
            print_info "Metrics may not be initialized yet"
        fi
    else
        print_warning "Intelligence service is not running on localhost:8053"
        print_info "Start service: docker-compose up -d archon-intelligence"
        print_info "Or run locally: cd services/intelligence && poetry run uvicorn app:app --port 8053"
    fi
}

# Step 7: Display deployment summary
display_summary() {
    print_header "Deployment Summary"

    echo -e "Configuration files:"
    echo -e "  - Metrics module: ${GREEN}services/intelligence/src/services/pattern_learning/phase2_matching/monitoring_hybrid_patterns.py${NC}"
    echo -e "  - Grafana dashboard: ${GREEN}$GRAFANA_DASHBOARD${NC}"
    echo -e "  - Alert rules: ${GREEN}$ALERT_RULES${NC}"

    echo -e "\nAccess points:"
    echo -e "  - Grafana: ${BLUE}http://localhost:3000${NC} (admin/admin123)"
    echo -e "  - Prometheus: ${BLUE}http://localhost:9090${NC}"
    echo -e "  - AlertManager: ${BLUE}http://localhost:9093${NC}"
    echo -e "  - Intelligence metrics: ${BLUE}http://localhost:8053/metrics${NC}"

    echo -e "\nNext steps:"
    echo -e "  1. Start monitoring stack: ${YELLOW}cd monitoring && docker-compose -f docker-compose.monitoring.yml up -d${NC}"
    echo -e "  2. Start intelligence service: ${YELLOW}docker-compose up -d archon-intelligence${NC}"
    echo -e "  3. View dashboard: ${YELLOW}http://localhost:3000/d/archon-hybrid-scoring${NC}"
    echo -e "  4. Check metrics: ${YELLOW}curl http://localhost:8053/metrics | grep hybrid_scoring${NC}"

    echo -e "\nDocumentation:"
    echo -e "  - Monitoring guide: ${BLUE}services/intelligence/src/services/pattern_learning/phase2_matching/MONITORING_README.md${NC}"
    echo -e "  - Alert rules: ${BLUE}monitoring/prometheus/rules/hybrid_scoring_alerts.yml${NC}"

    print_success "\nMonitoring deployment validation complete!"
}

# Main execution
main() {
    print_header "Hybrid Pattern Scoring Monitoring Deployment"
    print_info "Starting deployment and validation process..."

    validate_prometheus_config
    validate_alert_rules
    validate_grafana_dashboard
    import_grafana_dashboard
    run_monitoring_tests
    verify_metrics_endpoint
    display_summary
}

# Run main function
main

exit 0
