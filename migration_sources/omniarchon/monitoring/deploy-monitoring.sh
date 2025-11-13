#!/bin/bash
# Archon Production Monitoring Deployment Script
# Deploys comprehensive monitoring stack with Prometheus, Grafana, AlertManager, Loki, and Jaeger

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
MONITORING_ENV_FILE="${MONITORING_ENV_FILE:-.env.monitoring}"
ARCHON_ENV_FILE="${ARCHON_ENV_FILE:-.env}"

echo -e "${BLUE}🚀 Archon Production Monitoring Deployment${NC}"
echo "=============================================="

# Function to print status messages
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if Docker and Docker Compose are installed
check_prerequisites() {
    echo "Checking prerequisites..."

    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi

    print_status "Docker and Docker Compose are installed"
}

# Create monitoring environment file if it doesn't exist
create_monitoring_env() {
    if [[ ! -f "$MONITORING_ENV_FILE" ]]; then
        echo "Creating monitoring environment file..."
        cat > "$MONITORING_ENV_FILE" << EOF
# Grafana Configuration
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin123
GRAFANA_SECRET_KEY=$(openssl rand -base64 32)

# SMTP Configuration (optional)
SMTP_ENABLED=false
SMTP_HOST=smtp.gmail.com:587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=grafana@yourdomain.com

# Alert Notification Configuration
ALERT_EMAIL_DEFAULT=ops@yourdomain.com
ALERT_EMAIL_CRITICAL=critical@yourdomain.com
ALERT_EMAIL_SYSTEM=system@yourdomain.com
ALERT_EMAIL_DATABASE=database@yourdomain.com
ALERT_EMAIL_PERFORMANCE=performance@yourdomain.com
ALERT_EMAIL_INFRASTRUCTURE=infrastructure@yourdomain.com
ALERT_EMAIL_AI=ai@yourdomain.com
ALERT_EMAIL_BUSINESS=business@yourdomain.com
ALERT_EMAIL_PREDICTIVE=predictive@yourdomain.com

# Slack Webhook URLs (optional)
SLACK_WEBHOOK_CRITICAL=
SLACK_WEBHOOK_SYSTEM=
SLACK_WEBHOOK_DATABASE=
SLACK_WEBHOOK_PERFORMANCE=
SLACK_WEBHOOK_INFRASTRUCTURE=
SLACK_WEBHOOK_AI=
SLACK_WEBHOOK_BUSINESS=
SLACK_WEBHOOK_PREDICTIVE=

# PagerDuty Integration (optional)
PAGERDUTY_ROUTING_KEY=

# Database Configuration for Exporters
POSTGRES_USER=archon
POSTGRES_PASSWORD=your_postgres_password
POSTGRES_DB=archon
EOF
        print_status "Created $MONITORING_ENV_FILE"
        print_warning "Please edit $MONITORING_ENV_FILE with your specific configuration"
    else
        print_status "Using existing $MONITORING_ENV_FILE"
    fi
}

# Create required directories
create_directories() {
    echo "Creating monitoring directories..."

    # Create data directories with correct permissions
    mkdir -p monitoring/data/{prometheus,grafana,loki,alertmanager,elasticsearch,jaeger}

    # Set permissions for data directories
    sudo chown -R 472:472 monitoring/data/grafana 2>/dev/null || echo "Note: Could not set Grafana permissions (this is normal on some systems)"
    sudo chown -R 65534:65534 monitoring/data/prometheus 2>/dev/null || echo "Note: Could not set Prometheus permissions (this is normal on some systems)"

    print_status "Monitoring directories created"
}

# Validate configuration files
validate_config() {
    echo "Validating monitoring configuration files..."

    # Check if required config files exist
    if [[ ! -f "monitoring/prometheus/prometheus.yml" ]]; then
        print_error "Prometheus configuration file not found at monitoring/prometheus/prometheus.yml"
        exit 1
    fi

    if [[ ! -f "monitoring/alertmanager/alertmanager.yml" ]]; then
        print_error "AlertManager configuration file not found at monitoring/alertmanager/alertmanager.yml"
        exit 1
    fi

    if [[ ! -f "monitoring/prometheus/rules/archon_alerts.yml" ]]; then
        print_error "Alert rules file not found at monitoring/prometheus/rules/archon_alerts.yml"
        exit 1
    fi

    print_status "Configuration files validated"
}

# Update Archon services with monitoring
update_archon_services() {
    echo "Updating Archon services with monitoring capabilities..."

    # Check if main Archon is running
    if docker compose -f ../deployment/docker-compose.yml ps | grep -q archon-server; then
        print_warning "Archon services are running. Restarting to enable monitoring..."
        docker compose -f ../deployment/docker-compose.yml restart archon-server archon-mcp archon-agents archon-intelligence archon-bridge archon-search
        print_status "Archon services restarted with monitoring enabled"
    else
        print_warning "Archon services not running. Monitoring will be enabled when you start them."
    fi
}

# Deploy monitoring stack
deploy_monitoring() {
    echo "Deploying monitoring stack..."

    # Start monitoring services
    docker-compose -f monitoring/docker-compose.monitoring.yml --env-file "$MONITORING_ENV_FILE" up -d

    print_status "Monitoring stack deployed"
}

# Wait for services to be healthy
wait_for_services() {
    echo "Waiting for services to become healthy..."

    # Wait for Prometheus
    echo -n "Waiting for Prometheus..."
    for i in {1..30}; do
        if curl -s http://localhost:9090/-/healthy > /dev/null 2>&1; then
            echo " ✓"
            break
        fi
        echo -n "."
        sleep 2
    done

    # Wait for Grafana
    echo -n "Waiting for Grafana..."
    for i in {1..30}; do
        if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
            echo " ✓"
            break
        fi
        echo -n "."
        sleep 2
    done

    # Wait for AlertManager
    echo -n "Waiting for AlertManager..."
    for i in {1..30}; do
        if curl -s http://localhost:9093/-/healthy > /dev/null 2>&1; then
            echo " ✓"
            break
        fi
        echo -n "."
        sleep 2
    done

    print_status "All services are healthy"
}

# Display access information
display_access_info() {
    echo ""
    echo -e "${BLUE}📊 Monitoring Services Access Information${NC}"
    echo "========================================="
    echo ""
    echo -e "${GREEN}Grafana Dashboard:${NC}"
    echo "  URL: http://localhost:3000"
    echo "  Username: $(grep GRAFANA_ADMIN_USER $MONITORING_ENV_FILE | cut -d'=' -f2)"
    echo "  Password: $(grep GRAFANA_ADMIN_PASSWORD $MONITORING_ENV_FILE | cut -d'=' -f2)"
    echo ""
    echo -e "${GREEN}Prometheus:${NC}"
    echo "  URL: http://localhost:9090"
    echo "  Targets: http://localhost:9090/targets"
    echo "  Rules: http://localhost:9090/rules"
    echo ""
    echo -e "${GREEN}AlertManager:${NC}"
    echo "  URL: http://localhost:9093"
    echo "  Silences: http://localhost:9093/#/silences"
    echo "  Alerts: http://localhost:9093/#/alerts"
    echo ""
    echo -e "${GREEN}Loki (Logs):${NC}"
    echo "  URL: http://localhost:3100"
    echo "  Access via Grafana Explore or Dashboards"
    echo ""
    echo -e "${GREEN}Jaeger (Tracing):${NC}"
    echo "  URL: http://localhost:16686"
    echo ""
    echo -e "${GREEN}Additional Services:${NC}"
    echo "  Node Exporter: http://localhost:9100/metrics"
    echo "  cAdvisor: http://localhost:8080"
    echo "  Uptime Kuma: http://localhost:3001"
    echo ""
    echo -e "${GREEN}Archon Monitoring Endpoints:${NC}"
    echo "  Metrics: http://localhost:8181/monitoring/metrics"
    echo "  Health: http://localhost:8181/monitoring/health/intelligent"
    echo "  Performance: http://localhost:8181/monitoring/performance/trends"
    echo ""
}

# Display helpful commands
display_commands() {
    echo -e "${BLUE}🛠 Useful Commands${NC}"
    echo "=================="
    echo ""
    echo "View monitoring logs:"
    echo "  docker-compose -f monitoring/docker-compose.monitoring.yml logs -f [service_name]"
    echo ""
    echo "Scale monitoring services:"
    echo "  docker-compose -f monitoring/docker-compose.monitoring.yml scale prometheus=2"
    echo ""
    echo "Update monitoring stack:"
    echo "  docker-compose -f monitoring/docker-compose.monitoring.yml pull"
    echo "  docker-compose -f monitoring/docker-compose.monitoring.yml up -d"
    echo ""
    echo "Backup monitoring data:"
    echo "  docker run --rm -v monitoring_prometheus_data:/data -v \$(pwd):/backup busybox tar czf /backup/prometheus-backup-\$(date +%Y%m%d).tar.gz -C /data ."
    echo ""
    echo "Stop monitoring stack:"
    echo "  docker-compose -f monitoring/docker-compose.monitoring.yml down"
    echo ""
    echo "Stop and remove all monitoring data:"
    echo "  docker-compose -f monitoring/docker-compose.monitoring.yml down -v"
    echo ""
}

# Main deployment function
main() {
    echo "Starting Archon Production Monitoring deployment..."
    echo ""

    # Run deployment steps
    check_prerequisites
    create_monitoring_env
    create_directories
    validate_config
    deploy_monitoring
    wait_for_services
    update_archon_services

    echo ""
    print_status "Archon Production Monitoring deployed successfully!"
    echo ""

    # Display access information
    display_access_info
    display_commands

    echo -e "${GREEN}🎉 Deployment Complete!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Configure alert notification channels in $MONITORING_ENV_FILE"
    echo "2. Customize Grafana dashboards at http://localhost:3000"
    echo "3. Set up alert rules in AlertManager at http://localhost:9093"
    echo "4. Monitor your Archon services and infrastructure!"
    echo ""
}

# Handle script arguments
case "${1:-deploy}" in
    deploy)
        main
        ;;
    stop)
        echo "Stopping monitoring stack..."
        docker-compose -f monitoring/docker-compose.monitoring.yml --env-file "$MONITORING_ENV_FILE" down
        print_status "Monitoring stack stopped"
        ;;
    status)
        echo "Checking monitoring stack status..."
        docker-compose -f monitoring/docker-compose.monitoring.yml --env-file "$MONITORING_ENV_FILE" ps
        ;;
    logs)
        service="${2:-}"
        if [[ -n "$service" ]]; then
            docker-compose -f monitoring/docker-compose.monitoring.yml --env-file "$MONITORING_ENV_FILE" logs -f "$service"
        else
            docker-compose -f monitoring/docker-compose.monitoring.yml --env-file "$MONITORING_ENV_FILE" logs -f
        fi
        ;;
    update)
        echo "Updating monitoring stack..."
        docker-compose -f monitoring/docker-compose.monitoring.yml --env-file "$MONITORING_ENV_FILE" pull
        docker-compose -f monitoring/docker-compose.monitoring.yml --env-file "$MONITORING_ENV_FILE" up -d
        print_status "Monitoring stack updated"
        ;;
    backup)
        echo "Creating monitoring backup..."
        backup_dir="backups/monitoring-$(date +%Y%m%d-%H%M%S)"
        mkdir -p "$backup_dir"
        docker run --rm -v monitoring_prometheus_data:/data -v "$(pwd)/$backup_dir":/backup busybox tar czf /backup/prometheus-data.tar.gz -C /data .
        docker run --rm -v monitoring_grafana_data:/data -v "$(pwd)/$backup_dir":/backup busybox tar czf /backup/grafana-data.tar.gz -C /data .
        cp -r monitoring/prometheus/rules "$backup_dir/"
        cp -r monitoring/grafana/dashboards "$backup_dir/"
        cp "$MONITORING_ENV_FILE" "$backup_dir/"
        print_status "Backup created in $backup_dir"
        ;;
    *)
        echo "Usage: $0 {deploy|stop|status|logs [service]|update|backup}"
        echo ""
        echo "Commands:"
        echo "  deploy  - Deploy the monitoring stack (default)"
        echo "  stop    - Stop the monitoring stack"
        echo "  status  - Show status of monitoring services"
        echo "  logs    - Show logs (optionally for specific service)"
        echo "  update  - Update monitoring stack images"
        echo "  backup  - Create backup of monitoring data"
        exit 1
        ;;
esac
