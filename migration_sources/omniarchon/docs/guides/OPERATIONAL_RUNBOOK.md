# MCP Document Indexing Pipeline - Operational Runbook

**Version**: 1.0.0  
**Effective Date**: 2024-12-22  
**Classification**: Internal Operations  
**Owner**: DevOps Team

## Table of Contents

1. [Service Overview](#service-overview)
2. [Startup Procedures](#startup-procedures)
3. [Configuration Management](#configuration-management)
4. [Monitoring & Alerting](#monitoring--alerting)
5. [Backup & Recovery](#backup--recovery)
6. [Scaling Operations](#scaling-operations)
7. [Maintenance Procedures](#maintenance-procedures)
8. [Emergency Response](#emergency-response)
9. [Performance Tuning](#performance-tuning)
10. [Security Operations](#security-operations)

## Service Overview

### Service Topology

```
┌─────────────────────────────────────────────────────────────┐
│                     Archon MCP Platform                     │
├─────────────────┬─────────────────┬─────────────────────────┤
│   Application   │   Data Layer    │    External Services    │
│   Services      │                 │                         │
├─────────────────┼─────────────────┼─────────────────────────┤
│ Intelligence    │ Qdrant          │ Ollama                  │
│ (8053)          │ (6333)          │ (192.168.86.200:11434)  │
│                 │                 │                         │
│ Search          │ Memgraph        │ Supabase                │
│ (8055)          │ (7687)          │ (external)              │
│                 │                 │                         │
│ Bridge          │ PostgreSQL      │                         │
│ (8054)          │ (5432)          │                         │
└─────────────────┴─────────────────┴─────────────────────────┘
```

### Service Dependencies

| Service | Depends On | Critical? | Startup Order |
|---------|------------|-----------|---------------|
| Qdrant | None | Yes | 1 |
| Memgraph | None | Yes | 1 |
| Bridge | Supabase | Yes | 2 |
| Intelligence | Memgraph, Ollama | Yes | 3 |
| Search | Qdrant, Ollama | Yes | 3 |
| MCP Server | All application services | Yes | 4 |

## Startup Procedures

### Standard Startup Sequence

#### Phase 1: Infrastructure Services

```bash
#!/bin/bash
# 01-start-infrastructure.sh

echo "🚀 Starting infrastructure services..."

# Start data layer services
docker-compose up -d qdrant memgraph

# Wait for databases to be ready
echo "⏳ Waiting for databases..."
sleep 30

# Verify database connectivity
until curl -f -s http://localhost:6333/health > /dev/null; do
    echo "⏳ Waiting for Qdrant..."
    sleep 5
done

until curl -f -s http://localhost:7687 > /dev/null 2>&1; do
    echo "⏳ Waiting for Memgraph..."
    sleep 5
done

echo "✅ Infrastructure services ready"
```

#### Phase 2: Application Services

```bash
#!/bin/bash
# 02-start-applications.sh

echo "🚀 Starting application services..."

# Start bridge service first (data coordination)
docker-compose up -d archon-bridge

# Wait for bridge service
until curl -f -s http://localhost:8054/health > /dev/null; do
    echo "⏳ Waiting for Bridge service..."
    sleep 5
done

# Start intelligence and search services in parallel
docker-compose up -d archon-intelligence archon-search

# Wait for application services
sleep 45

# Verify services
services=("intelligence:8053" "search:8055")
for service in "${services[@]}"; do
    name=$(echo $service | cut -d: -f1)
    port=$(echo $service | cut -d: -f2)

    until curl -f -s "http://localhost:$port/health" > /dev/null; do
        echo "⏳ Waiting for $name service..."
        sleep 10
    done
    echo "✅ $name service ready"
done

echo "✅ Application services ready"
```

#### Phase 3: MCP Server

```bash
#!/bin/bash
# 03-start-mcp.sh

echo "🚀 Starting MCP server..."

# Start MCP server
docker-compose up -d archon-mcp

# Wait for MCP server
until curl -f -s http://localhost:8051/health > /dev/null; do
    echo "⏳ Waiting for MCP server..."
    sleep 5
done

echo "✅ MCP server ready"

# Run post-startup validation
./scripts/validate-deployment.sh
```

### Complete Startup Script

```bash
#!/bin/bash
# start-archon.sh - Complete startup sequence

set -e

echo "🏁 Starting Archon MCP Platform..."

# Check prerequisites
./scripts/01-start-infrastructure.sh
./scripts/02-start-applications.sh  
./scripts/03-start-mcp.sh

# Final health check
echo "🔍 Running final health checks..."
./scripts/health-check-all.sh

if [ $? -eq 0 ]; then
    echo "🎉 Archon MCP Platform started successfully!"
    echo "📊 Dashboard: http://localhost:3737"
    echo "🔧 MCP Server: http://localhost:8051"
    echo "📈 Health Status: ./scripts/health-check-all.sh"
else
    echo "❌ Startup validation failed. Check logs for details."
    exit 1
fi
```

### Cold Start Procedure

```bash
#!/bin/bash
# cold-start.sh - Start from completely stopped state

echo "🧊 Cold start procedure initiated..."

# Ensure all containers are stopped
docker-compose down --remove-orphans

# Clean up any orphaned resources
docker system prune -f
docker volume prune -f --filter label=project=archon

# Pull latest images
docker-compose pull

# Verify external dependencies
echo "🔍 Checking external dependencies..."

# Test Ollama connectivity
if ! curl -f -s "http://192.168.86.200:11434/api/tags" > /dev/null; then
    echo "❌ Ollama service unavailable at 192.168.86.200:11434"
    echo "   Please verify Ollama is running and accessible"
    exit 1
fi

# Test Supabase connectivity
if ! curl -f -s "$SUPABASE_URL/rest/v1/" -H "apikey: $SUPABASE_SERVICE_KEY" > /dev/null; then
    echo "❌ Supabase unavailable or credentials invalid"
    echo "   Please verify SUPABASE_URL and SUPABASE_SERVICE_KEY"
    exit 1
fi

echo "✅ External dependencies verified"

# Start the platform
./start-archon.sh
```

## Configuration Management

### Environment Configuration

#### Production Environment (.env.production)

```bash
# === Core Service Configuration ===
ARCHON_ENVIRONMENT=production
LOG_LEVEL=INFO
DEBUG_MODE=false

# === Service Ports ===
INTELLIGENCE_SERVICE_PORT=8053
SEARCH_SERVICE_PORT=8055
BRIDGE_SERVICE_PORT=8054
MCP_SERVER_PORT=8051

# === Database Configuration ===
QDRANT_URL=http://qdrant:6333
MEMGRAPH_URI=bolt://memgraph:7687
SUPABASE_URL=${SUPABASE_URL}
SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}

# === External Services ===
OLLAMA_BASE_URL=http://192.168.86.200:11434
EMBEDDING_MODEL=rjmalagon/gte-qwen2-1.5b-instruct-embed-f16:latest
EMBEDDING_DIMENSION=768

# === Performance Tuning ===
BATCH_SIZE=25
MAX_CONCURRENT_EMBEDDINGS=3
VECTOR_SEARCH_TIMEOUT=5000
AUTO_REFRESH_ENABLED=true
INDEX_OPTIMIZATION_INTERVAL=3600

# === Security ===
SERVICE_AUTH_TOKEN=${SERVICE_AUTH_TOKEN}
CORS_ALLOWED_ORIGINS=https://app.yourdomain.com

# === Monitoring ===
ENABLE_METRICS=true
METRICS_PORT=9090
HEALTH_CHECK_INTERVAL=30
```

#### Development Environment (.env.development)

```bash
# === Development Overrides ===
ARCHON_ENVIRONMENT=development
LOG_LEVEL=DEBUG
DEBUG_MODE=true

# === Relaxed Performance Settings ===
BATCH_SIZE=10
MAX_CONCURRENT_EMBEDDINGS=2
VECTOR_SEARCH_TIMEOUT=10000

# === Development Security ===
CORS_ALLOWED_ORIGINS=*
SERVICE_AUTH_TOKEN=dev-token-123

# === Development Features ===
ENABLE_API_DOCS=true
ENABLE_SWAGGER_UI=true
MOCK_EXTERNAL_SERVICES=false
```

### Configuration Validation Script

```bash
#!/bin/bash
# validate-config.sh

echo "🔍 Validating configuration..."

# Required environment variables
required_vars=(
    "SUPABASE_URL"
    "SUPABASE_SERVICE_KEY"
    "OLLAMA_BASE_URL"
    "EMBEDDING_DIMENSION"
)

missing_vars=()
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "❌ Missing required environment variables:"
    printf "   %s\n" "${missing_vars[@]}"
    exit 1
fi

# Validate service URLs
echo "🔗 Testing service connectivity..."

# Test Ollama
if ! curl -f -s "$OLLAMA_BASE_URL/api/tags" > /dev/null; then
    echo "❌ Cannot connect to Ollama at $OLLAMA_BASE_URL"
    exit 1
fi

# Test Supabase
if ! curl -f -s "$SUPABASE_URL/rest/v1/" -H "apikey: $SUPABASE_SERVICE_KEY" > /dev/null; then
    echo "❌ Cannot connect to Supabase at $SUPABASE_URL"
    exit 1
fi

# Validate embedding dimensions
if [ "$EMBEDDING_DIMENSION" -lt 100 ] || [ "$EMBEDDING_DIMENSION" -gt 4096 ]; then
    echo "❌ Invalid embedding dimension: $EMBEDDING_DIMENSION (should be 100-4096)"
    exit 1
fi

echo "✅ Configuration validation passed"
```

### Dynamic Configuration Updates

```bash
#!/bin/bash
# update-config.sh - Update configuration without full restart

CONFIG_FILE="${1:-production}"
NEW_CONFIG=".env.$CONFIG_FILE"

if [ ! -f "$NEW_CONFIG" ]; then
    echo "❌ Configuration file not found: $NEW_CONFIG"
    exit 1
fi

echo "🔄 Updating configuration with $NEW_CONFIG..."

# Validate new configuration
if ! ./scripts/validate-config.sh; then
    echo "❌ Configuration validation failed"
    exit 1
fi

# Create backup of current configuration
cp .env ".env.backup.$(date +%Y%m%d-%H%M%S)"

# Apply new configuration
cp "$NEW_CONFIG" .env

# Restart services that require configuration reload
docker-compose restart archon-intelligence archon-search archon-bridge

# Wait for services to be ready
sleep 30

# Validate deployment
if ./scripts/health-check-all.sh; then
    echo "✅ Configuration update successful"
else
    echo "❌ Configuration update failed, rolling back..."
    cp .env.backup.* .env
    docker-compose restart archon-intelligence archon-search archon-bridge
    exit 1
fi
```

## Monitoring & Alerting

### Health Check System

#### Comprehensive Health Check Script

```bash
#!/bin/bash
# health-check-all.sh

ALERT_EMAIL="devops@yourdomain.com"
SLACK_WEBHOOK="https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
LOG_FILE="/var/log/archon/health-check.log"

send_alert() {
    local service=$1
    local status=$2
    local details=$3

    # Log the issue
    echo "$(date): ALERT $service: $status - $details" >> $LOG_FILE

    # Send email alert
    echo "ALERT: $service is $status - $details" | mail -s "Archon Service Alert" $ALERT_EMAIL

    # Send Slack alert
    curl -X POST $SLACK_WEBHOOK \
        -H 'Content-Type: application/json' \
        -d "{\"text\":\"🚨 Archon Alert: $service is $status - $details\"}"
}

check_service_health() {
    local service=$1
    local url=$2
    local timeout=${3:-10}

    if timeout $timeout curl -f -s "$url" > /dev/null 2>&1; then
        echo "✅ $service: HEALTHY"
        return 0
    else
        echo "❌ $service: UNHEALTHY"
        send_alert "$service" "UNHEALTHY" "Health check failed at $url"
        return 1
    fi
}

check_service_performance() {
    local service=$1
    local url=$2
    local max_time=${3:-2.0}

    response_time=$(curl -w "%{time_total}" -s -o /dev/null "$url" 2>/dev/null)

    if (( $(echo "$response_time > $max_time" | bc -l) )); then
        echo "⚠️  $service: SLOW ($response_time s)"
        send_alert "$service" "PERFORMANCE_DEGRADED" "Response time: ${response_time}s (threshold: ${max_time}s)"
        return 1
    else
        echo "✅ $service: FAST ($response_time s)"
        return 0
    fi
}

# Check core services
echo "🔍 Checking core services..."
check_service_health "Intelligence Service" "http://localhost:8053/health"
check_service_health "Search Service" "http://localhost:8055/health"
check_service_health "Bridge Service" "http://localhost:8054/health"
check_service_health "MCP Server" "http://localhost:8051/health"

# Check data layer
echo "🔍 Checking data layer..."
check_service_health "Qdrant" "http://localhost:6333/health"
check_service_health "Memgraph" "http://localhost:7687" 5

# Check external dependencies
echo "🔍 Checking external services..."
check_service_health "Ollama" "http://192.168.86.200:11434/api/tags"
check_service_health "Supabase" "$SUPABASE_URL/rest/v1/" 15

# Performance checks
echo "🚀 Checking performance..."
check_service_performance "Intelligence Service" "http://localhost:8053/health" 2.0
check_service_performance "Search Service" "http://localhost:8055/health" 1.0

# Functional tests
echo "🧪 Running functional tests..."

# Test document vectorization
test_doc='{"document_id":"health_test_'$(date +%s)'","content":"Health check test","metadata":{"test":true}}'
if curl -f -s -m 30 -X POST "http://localhost:8055/vectorize/document" \
   -H "Content-Type: application/json" -d "$test_doc" > /dev/null; then
    echo "✅ Vectorization: FUNCTIONAL"
else
    echo "❌ Vectorization: FAILED"
    send_alert "Vectorization Pipeline" "FAILED" "Document vectorization test failed"
fi

# Test search functionality
if curl -f -s -m 10 -X POST "http://localhost:8055/search" \
   -H "Content-Type: application/json" \
   -d '{"query":"test","mode":"semantic","limit":5}' > /dev/null; then
    echo "✅ Search: FUNCTIONAL"
else
    echo "❌ Search: FAILED"
    send_alert "Search Pipeline" "FAILED" "Search functionality test failed"
fi

echo "🏁 Health check complete"
```

### Monitoring Dashboard Setup

#### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'archon-services'
    static_configs:
      - targets:
        - 'localhost:8053'  # Intelligence service
        - 'localhost:8055'  # Search service
        - 'localhost:8054'  # Bridge service
        - 'localhost:8051'  # MCP server
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'qdrant'
    static_configs:
      - targets: ['localhost:6333']
    metrics_path: '/metrics'

  - job_name: 'memgraph'
    static_configs:
      - targets: ['localhost:7687']
    metrics_path: '/metrics'

rule_files:
  - "archon_alerts.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093
```

#### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Archon MCP Platform",
    "panels": [
      {
        "title": "Service Health",
        "type": "stat",
        "targets": [
          {
            "expr": "up{job=\"archon-services\"}",
            "legendFormat": "{{instance}}"
          }
        ]
      },
      {
        "title": "Response Times",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          }
        ]
      },
      {
        "title": "Vector Operations/sec",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(vector_operations_total[1m])",
            "legendFormat": "Operations/sec"
          }
        ]
      }
    ]
  }
}
```

### Alerting Rules

```yaml
# archon_alerts.yml
groups:
- name: archon_alerts
  rules:
  - alert: ServiceDown
    expr: up{job="archon-services"} == 0
    for: 30s
    labels:
      severity: critical
    annotations:
      summary: "Archon service {{ $labels.instance }} is down"
      description: "Service {{ $labels.instance }} has been down for more than 30 seconds"

  - alert: HighResponseTime
    expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "High response time for {{ $labels.instance }}"
      description: "95th percentile response time is {{ $value }}s"

  - alert: VectorIndexingFailed
    expr: rate(vector_indexing_failures_total[5m]) > 0.1
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "High vector indexing failure rate"
      description: "Vector indexing failure rate is {{ $value }} per second"

  - alert: QdrantStorageHigh
    expr: qdrant_storage_usage_bytes / qdrant_storage_capacity_bytes > 0.8
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Qdrant storage usage high"
      description: "Qdrant storage is {{ $value | humanizePercentage }} full"
```

## Backup & Recovery

### Backup Strategy

#### Daily Backup Script

```bash
#!/bin/bash
# daily-backup.sh

BACKUP_DIR="/backups/archon/$(date +%Y%m%d)"
S3_BUCKET="archon-backups"
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"

echo "🗄️ Starting daily backup..."

# Backup Qdrant data
echo "📦 Backing up Qdrant..."
docker exec qdrant sh -c "cd /qdrant && tar czf - storage/" > "$BACKUP_DIR/qdrant.tar.gz"

# Backup Memgraph data
echo "📦 Backing up Memgraph..."
docker exec memgraph sh -c "echo 'DUMP DATABASE;' | mgconsole" > "$BACKUP_DIR/memgraph.cypher"

# Backup configuration
echo "📦 Backing up configuration..."
cp .env "$BACKUP_DIR/"
cp docker-compose*.yml "$BACKUP_DIR/"
cp -r config/ "$BACKUP_DIR/" 2>/dev/null || true

# Create backup metadata
cat > "$BACKUP_DIR/metadata.json" << EOF
{
  "backup_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "version": "$(git rev-parse HEAD 2>/dev/null || echo 'unknown')",
  "services": {
    "qdrant": "$(docker exec qdrant qdrant --version 2>/dev/null || echo 'unknown')",
    "memgraph": "$(docker exec memgraph mg_version 2>/dev/null || echo 'unknown')"
  }
}
EOF

# Upload to S3 (if configured)
if [ -n "$AWS_ACCESS_KEY_ID" ]; then
    echo "☁️ Uploading to S3..."
    aws s3 sync "$BACKUP_DIR" "s3://$S3_BUCKET/$(date +%Y%m%d)/"
fi

# Cleanup old backups
echo "🧹 Cleaning up old backups..."
find /backups/archon -type d -mtime +$RETENTION_DAYS -exec rm -rf {} +

echo "✅ Backup complete: $BACKUP_DIR"
```

#### Point-in-Time Recovery

```bash
#!/bin/bash
# restore-from-backup.sh

BACKUP_DATE=${1:-$(date +%Y%m%d)}
BACKUP_DIR="/backups/archon/$BACKUP_DATE"

if [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ Backup directory not found: $BACKUP_DIR"
    exit 1
fi

echo "⚠️  WARNING: This will overwrite current data!"
echo "Backup date: $BACKUP_DATE"
echo "Backup location: $BACKUP_DIR"
read -p "Continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Restore cancelled"
    exit 0
fi

echo "🔄 Starting restore from backup..."

# Stop services
echo "🛑 Stopping services..."
docker-compose down

# Restore Qdrant
echo "📥 Restoring Qdrant..."
docker volume rm archon_qdrant_data 2>/dev/null || true
docker run --rm -v archon_qdrant_data:/qdrant -v "$BACKUP_DIR":/backup alpine \
    sh -c "cd /qdrant && tar xzf /backup/qdrant.tar.gz"

# Restore Memgraph
echo "📥 Restoring Memgraph..."
docker volume rm archon_memgraph_data 2>/dev/null || true
docker-compose up -d memgraph
sleep 10
docker exec memgraph sh -c "mgconsole < /backup/memgraph.cypher" || true

# Restore configuration
echo "📥 Restoring configuration..."
cp "$BACKUP_DIR/.env" .
cp "$BACKUP_DIR"/docker-compose*.yml .
cp -r "$BACKUP_DIR/config/" . 2>/dev/null || true

# Start services
echo "🚀 Starting services..."
./start-archon.sh

echo "✅ Restore complete"
echo "📊 Verifying restore..."
./scripts/health-check-all.sh
```

### Disaster Recovery Plan

#### Recovery Time Objectives (RTO)

| Incident Type | Target RTO | Maximum RTO |
|---------------|------------|-------------|
| Single service failure | 5 minutes | 15 minutes |
| Database corruption | 30 minutes | 2 hours |
| Complete system failure | 1 hour | 4 hours |
| Data center outage | 4 hours | 24 hours |

#### Recovery Point Objectives (RPO)

| Data Type | Target RPO | Maximum RPO |
|-----------|------------|-------------|
| Vector data | 1 hour | 4 hours |
| Knowledge graph | 1 hour | 4 hours |
| Configuration | 0 minutes | 1 hour |
| Application data | 15 minutes | 1 hour |

#### Disaster Recovery Procedure

```bash
#!/bin/bash
# disaster-recovery.sh

RECOVERY_SITE=${1:-primary}
BACKUP_SOURCE=${2:-latest}

echo "🚨 DISASTER RECOVERY INITIATED"
echo "Recovery site: $RECOVERY_SITE"
echo "Backup source: $BACKUP_SOURCE"

# Step 1: Assess damage
echo "🔍 Assessing system state..."
./scripts/health-check-all.sh > /tmp/health-status.log 2>&1

# Step 2: Determine recovery strategy
if grep -q "HEALTHY" /tmp/health-status.log; then
    echo "ℹ️ Partial failure detected - attempting service recovery"
    RECOVERY_TYPE="partial"
else
    echo "💥 Complete failure detected - initiating full recovery"
    RECOVERY_TYPE="full"
fi

# Step 3: Execute recovery plan
case $RECOVERY_TYPE in
    "partial")
        echo "🔧 Executing partial recovery..."
        ./scripts/restart-failed-services.sh
        ;;
    "full")
        echo "🏗️ Executing full recovery..."
        ./scripts/restore-from-backup.sh $BACKUP_SOURCE
        ;;
esac

# Step 4: Validate recovery
echo "✅ Validating recovery..."
sleep 60
if ./scripts/health-check-all.sh; then
    echo "🎉 Recovery successful!"
    echo "📧 Sending recovery notification..."
    echo "Recovery completed at $(date)" | mail -s "Archon Recovery Complete" devops@yourdomain.com
else
    echo "❌ Recovery failed - escalating to engineering team"
    echo "Recovery failed at $(date)" | mail -s "Archon Recovery FAILED" devops@yourdomain.com
    exit 1
fi
```

## Scaling Operations

### Horizontal Scaling Procedures

#### Search Service Scaling

```bash
#!/bin/bash
# scale-search-service.sh

REPLICAS=${1:-3}

echo "📈 Scaling search service to $REPLICAS replicas..."

# Update docker-compose with replicas
cat > docker-compose.scale.yml << EOF
version: '3.8'
services:
  archon-search:
    deploy:
      replicas: $REPLICAS
    environment:
      - INSTANCE_ID=\${HOSTNAME}
EOF

# Deploy scaled configuration
docker-compose -f docker-compose.yml -f docker-compose.scale.yml up -d archon-search

# Setup load balancer (if using Docker Swarm)
if docker node ls >/dev/null 2>&1; then
    docker service update --replicas $REPLICAS archon_archon-search
fi

echo "✅ Search service scaled to $REPLICAS replicas"
```

#### Auto-Scaling Configuration

```yaml
# docker-compose.autoscale.yml
version: '3.8'
services:
  archon-search:
    deploy:
      replicas: 2
      update_config:
        parallelism: 1
        delay: 10s
        failure_action: rollback
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '0.5'
          memory: 1G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8055/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Vertical Scaling

#### Resource Optimization Script

```bash
#!/bin/bash
# optimize-resources.sh

ENVIRONMENT=${1:-production}

echo "⚡ Optimizing resources for $ENVIRONMENT environment..."

case $ENVIRONMENT in
    "development")
        CPU_LIMIT="1.0"
        MEMORY_LIMIT="2G"
        MEMORY_RESERVATION="512M"
        ;;
    "staging")
        CPU_LIMIT="2.0"
        MEMORY_LIMIT="4G"
        MEMORY_RESERVATION="1G"
        ;;
    "production")
        CPU_LIMIT="4.0"
        MEMORY_LIMIT="8G"
        MEMORY_RESERVATION="2G"
        ;;
esac

# Update resource limits
cat > docker-compose.resources.yml << EOF
version: '3.8'
services:
  archon-intelligence:
    deploy:
      resources:
        limits:
          cpus: '$CPU_LIMIT'
          memory: $MEMORY_LIMIT
        reservations:
          cpus: '0.5'
          memory: $MEMORY_RESERVATION

  archon-search:
    deploy:
      resources:
        limits:
          cpus: '$CPU_LIMIT'
          memory: $MEMORY_LIMIT
        reservations:
          cpus: '0.5'
          memory: $MEMORY_RESERVATION

  qdrant:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '0.5'
          memory: 1G
EOF

docker-compose -f docker-compose.yml -f docker-compose.resources.yml up -d

echo "✅ Resources optimized for $ENVIRONMENT"
```

## Maintenance Procedures

### Regular Maintenance Tasks

#### Weekly Maintenance Script

```bash
#!/bin/bash
# weekly-maintenance.sh

echo "🔧 Starting weekly maintenance..."

# 1. Update system packages
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# 2. Clean Docker resources
echo "🧹 Cleaning Docker resources..."
docker system prune -f
docker image prune -f
docker volume prune -f

# 3. Optimize Qdrant collections
echo "🗂️ Optimizing Qdrant collections..."
curl -X POST "http://localhost:6333/collections/archon_vectors/index" \
  -H "Content-Type: application/json" \
  -d '{"wait": true}'

# 4. Backup vector indices
echo "💾 Backing up vector indices..."
./scripts/daily-backup.sh

# 5. Rotate logs
echo "📝 Rotating logs..."
docker-compose exec archon-intelligence logrotate /etc/logrotate.conf

# 6. Check disk space
echo "💿 Checking disk space..."
df -h | grep -E "(^/dev|docker)"

# 7. Performance baseline
echo "📊 Updating performance baseline..."
curl -X POST "http://localhost:8053/performance/baseline" \
  -H "Content-Type: application/json" \
  -d '{"operation_name": "weekly_maintenance", "duration_minutes": 5}'

echo "✅ Weekly maintenance complete"
```

#### Security Updates

```bash
#!/bin/bash
# security-updates.sh

echo "🔒 Applying security updates..."

# Update base images
docker-compose pull

# Rebuild services with latest base images
docker-compose build --no-cache

# Update dependencies
for service in intelligence search bridge; do
    echo "Updating $service dependencies..."
    docker-compose exec archon-$service pip install --upgrade pip
    docker-compose exec archon-$service pip check
done

# Restart services with updated images
docker-compose down
docker-compose up -d

# Verify security update
./scripts/health-check-all.sh

echo "✅ Security updates complete"
```

## Emergency Response

### Critical Issue Response

#### P0 (Critical) Response Procedure

```bash
#!/bin/bash
# p0-response.sh - Critical issue response

ISSUE_DESCRIPTION="$1"
INCIDENT_ID="$(date +%Y%m%d-%H%M%S)"

echo "🚨 P0 INCIDENT RESPONSE INITIATED"
echo "Incident ID: $INCIDENT_ID"
echo "Description: $ISSUE_DESCRIPTION"

# 1. Immediate assessment
echo "🔍 Performing immediate assessment..."
./scripts/health-check-all.sh > "/tmp/incident-$INCIDENT_ID-health.log"

# 2. Isolate the issue
echo "🔒 Isolating affected components..."
# Stop non-essential services to preserve resources
docker-compose stop archon-frontend archon-agents

# 3. Attempt automated recovery
echo "🔧 Attempting automated recovery..."
if ! ./scripts/restart-failed-services.sh; then
    echo "❌ Automated recovery failed - initiating manual intervention"

    # 4. Emergency notification
    echo "📢 Sending emergency notifications..."
    echo "P0 INCIDENT: $ISSUE_DESCRIPTION (ID: $INCIDENT_ID)" | \
        mail -s "🚨 P0 INCIDENT - Archon MCP Platform" \
        devops@yourdomain.com,engineering@yourdomain.com

    # Slack notification
    curl -X POST "$SLACK_WEBHOOK" \
        -H 'Content-Type: application/json' \
        -d "{\"text\":\"🚨 P0 INCIDENT\\nID: $INCIDENT_ID\\nDescription: $ISSUE_DESCRIPTION\\nStatus: Manual intervention required\"}"
fi

# 5. Create incident report
cat > "/tmp/incident-$INCIDENT_ID-report.md" << EOF
# Incident Report: $INCIDENT_ID

## Summary
- **Incident ID**: $INCIDENT_ID
- **Severity**: P0 (Critical)
- **Description**: $ISSUE_DESCRIPTION
- **Start Time**: $(date)
- **Status**: Active

## Timeline
- $(date): Incident detected
- $(date): Automated recovery attempted

## Actions Taken
- Health check performed
- Non-essential services stopped
- Emergency notifications sent

## Next Steps
- [ ] Manual investigation required
- [ ] Root cause analysis
- [ ] Permanent fix implementation
- [ ] Post-incident review
EOF

echo "📋 Incident report created: /tmp/incident-$INCIDENT_ID-report.md"
```

### Service Recovery Procedures

```bash
#!/bin/bash
# restart-failed-services.sh

echo "🔄 Restarting failed services..."

# Check each service and restart if unhealthy
services=("archon-intelligence:8053" "archon-search:8055" "archon-bridge:8054")

for service_port in "${services[@]}"; do
    service=$(echo $service_port | cut -d: -f1)
    port=$(echo $service_port | cut -d: -f2)

    if ! curl -f -s "http://localhost:$port/health" > /dev/null; then
        echo "🔄 Restarting $service..."
        docker-compose restart $service

        # Wait for service to be ready
        timeout=60
        while [ $timeout -gt 0 ]; do
            if curl -f -s "http://localhost:$port/health" > /dev/null; then
                echo "✅ $service is healthy"
                break
            fi
            sleep 5
            timeout=$((timeout - 5))
        done

        if [ $timeout -eq 0 ]; then
            echo "❌ $service failed to restart properly"
            return 1
        fi
    else
        echo "✅ $service is already healthy"
    fi
done

echo "✅ Service restart complete"
```

## Performance Tuning

### Performance Monitoring

```bash
#!/bin/bash
# performance-monitor.sh

echo "📊 Performance monitoring report"
echo "================================"

# Service response times
echo "🚀 Service Response Times:"
for service in "intelligence:8053" "search:8055" "bridge:8054"; do
    name=$(echo $service | cut -d: -f1)
    port=$(echo $service | cut -d: -f2)

    response_time=$(curl -w "%{time_total}" -s -o /dev/null "http://localhost:$port/health")
    echo "  $name: ${response_time}s"
done

# Vector operations performance
echo "🔍 Vector Operations:"
vector_stats=$(curl -s "http://localhost:8055/search/stats" | jq -r '.vector_index')
echo "  $vector_stats"

# Resource utilization
echo "💾 Resource Utilization:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"

# Qdrant performance
echo "🗂️ Qdrant Performance:"
qdrant_stats=$(curl -s "http://localhost:6333/collections/archon_vectors" | jq -r '.result.status')
echo "  Collection status: $qdrant_stats"
```

### Optimization Recommendations

```bash
#!/bin/bash
# optimize-performance.sh

echo "⚡ Applying performance optimizations..."

# 1. Optimize Qdrant settings
echo "🗂️ Optimizing Qdrant..."
curl -X PATCH "http://localhost:6333/collections/archon_vectors" \
  -H "Content-Type: application/json" \
  -d '{
    "optimizers_config": {
      "indexing_threshold": 10000,
      "flush_interval_sec": 30
    }
  }'

# 2. Tune JVM settings for services
echo "☕ Tuning JVM settings..."
export JAVA_OPTS="-Xmx2g -Xms1g -XX:+UseG1GC"

# 3. Optimize Docker settings
echo "🐳 Optimizing Docker..."
# Increase Docker daemon settings
sudo tee /etc/docker/daemon.json << EOF
{
  "storage-driver": "overlay2",
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "default-ulimits": {
    "nofile": {
      "name": "nofile",
      "hard": 65536,
      "soft": 65536
    }
  }
}
EOF

sudo systemctl restart docker

echo "✅ Performance optimizations applied"
```

---

**Document Status**: ✅ Complete  
**Review Cycle**: Quarterly  
**Next Review**: 2024-03-22  
**Owner**: DevOps Team  
**Approver**: Engineering Lead
