# Archon Grafana Monitoring - File Inventory

**Version**: 1.0.0
**Last Updated**: 2025-10-20

## 📁 File Structure

```
deployment/grafana/
├── archon-health-dashboard.json          # Grafana dashboard definition
├── DASHBOARD_PREVIEW.md                   # Visual preview and layout guide
├── docker-compose-monitoring.yml          # Prometheus + Grafana Docker setup
├── FILES.md                              # This file - inventory
├── prometheus-example.yml                # Prometheus configuration example
├── README.md                             # Complete setup documentation
├── SETUP_CHECKLIST.md                    # Step-by-step setup guide
└── provisioning/                         # Grafana auto-provisioning
    ├── dashboards/
    │   └── archon.yml                    # Dashboard provisioning config
    └── datasources/
        └── prometheus.yml                # Prometheus datasource config
```

## 📄 File Descriptions

### Core Dashboard Files

#### `archon-health-dashboard.json` (Main Dashboard)
- **Purpose**: Grafana dashboard JSON definition
- **Size**: ~25 KB
- **Panels**: 8 visualization panels
- **Variables**: 2 (datasource, container filter)
- **Refresh**: Auto-refresh every 30 seconds
- **Import**: Via Grafana UI or API

**Panels Included**:
1. Container Health Status (Gauge)
2. Unhealthy Container Count (Gauge)
3. Service Availability % (Gauge)
4. Alert Rate Over Time (Time Series)
5. Health Check Duration Histogram (Time Series)
6. Recent Alerts Timeline (Time Series)
7. Error Log Patterns Detected (Stacked Area)
8. Container Recoveries (Bar Chart)

**Metrics Used**:
- `archon_container_health_status`
- `archon_container_unhealthy_count`
- `archon_container_health_check_duration_seconds`
- `archon_container_alerts_total`
- `archon_container_error_patterns_total`
- `archon_container_recovery_total`

---

### Documentation Files

#### `README.md` (Complete Documentation)
- **Purpose**: Comprehensive setup and usage guide
- **Size**: ~45 KB
- **Sections**:
  - Overview and features
  - Prerequisites
  - Quick start guide
  - Panel descriptions (detailed)
  - Dashboard variables
  - Prometheus metrics reference
  - Alerting rules examples
  - Troubleshooting guide
  - Docker Compose integration
  - Performance considerations
  - Security best practices
  - Customization guide

#### `DASHBOARD_PREVIEW.md` (Visual Guide)
- **Purpose**: ASCII art visual preview of dashboard layout
- **Size**: ~22 KB
- **Contents**:
  - Dashboard layout diagrams
  - Panel visualization examples
  - Control descriptions
  - Color scheme reference
  - Use case examples
  - Interactive elements guide

#### `SETUP_CHECKLIST.md` (Setup Guide)
- **Purpose**: Step-by-step setup instructions
- **Size**: ~18 KB
- **Contents**:
  - Pre-setup checklist
  - Quick setup (recommended)
  - Advanced setup options
  - Verification checklist
  - Troubleshooting guide
  - Security hardening
  - Performance tuning
  - Next steps

#### `FILES.md` (This File)
- **Purpose**: File inventory and descriptions
- **Contents**: Complete file manifest with purposes

---

### Configuration Files

#### `docker-compose-monitoring.yml` (Docker Setup)
- **Purpose**: Docker Compose config for Prometheus + Grafana
- **Services**:
  - `prometheus`: Metrics collection and storage
  - `grafana`: Visualization and dashboards
  - `alertmanager`: (Optional) Alert routing
- **Volumes**:
  - `prometheus-data`: Time-series storage
  - `grafana-data`: Dashboard and config storage
- **Ports**:
  - `9090`: Prometheus UI
  - `3000`: Grafana UI
  - `9093`: Alertmanager UI (optional)

**Usage**:
```bash
docker compose -f deployment/grafana/docker-compose-monitoring.yml up -d
```

#### `prometheus-example.yml` (Prometheus Config)
- **Purpose**: Prometheus scrape configuration
- **Jobs Configured**:
  - archon-server (port 8181)
  - archon-intelligence (port 8053)
  - archon-mcp (port 8151)
  - archon-bridge (port 8054)
  - archon-search (port 8055)
  - archon-langextract (port 8156)
  - archon-agents (port 8052)
  - prometheus (self-monitoring)
  - qdrant (optional)
  - valkey (optional)
- **Scrape Interval**: 15 seconds
- **Retention**: 30 days / 10GB
- **Remote Write**: Commented (for Cortex/Thanos)

**Deployment**:
```bash
cp deployment/grafana/prometheus-example.yml deployment/prometheus/prometheus.yml
```

---

### Provisioning Files

#### `provisioning/datasources/prometheus.yml`
- **Purpose**: Auto-configure Prometheus data source in Grafana
- **Configuration**:
  - Name: Prometheus
  - Type: prometheus
  - URL: http://prometheus:9090
  - Default: true
  - HTTP Method: POST
  - Query Timeout: 60s

**Effect**: Grafana automatically connects to Prometheus on startup (no manual configuration needed)

#### `provisioning/dashboards/archon.yml`
- **Purpose**: Auto-import dashboards on Grafana startup
- **Configuration**:
  - Provider: Archon Health Monitoring
  - Folder: Archon
  - Path: /etc/grafana/provisioning/dashboards
  - Auto-update: true
  - UI Updates: Allowed

**Effect**: Dashboard appears in "Archon" folder automatically

---

## 🔄 File Dependencies

```
archon-health-dashboard.json
  ├─> Requires: Prometheus data source
  ├─> Queries: archon_container_* metrics
  └─> Variables: datasource, container

docker-compose-monitoring.yml
  ├─> Mounts: prometheus-example.yml → /etc/prometheus/prometheus.yml
  ├─> Mounts: provisioning/ → /etc/grafana/provisioning/
  └─> Networks: archon-network

prometheus-example.yml
  ├─> Targets: archon-server:8181/metrics
  ├─> Targets: archon-intelligence:8053/metrics
  ├─> Targets: archon-mcp:8151/metrics
  └─> ... (other services)

provisioning/datasources/prometheus.yml
  └─> Configures: Prometheus → http://prometheus:9090

provisioning/dashboards/archon.yml
  └─> Imports: archon-health-dashboard.json
```

## 📊 Metrics Source Files

**Backend Implementation**:
```
python/src/server/services/container_health_monitor.py
  ├─> Exports: archon_container_health_status
  ├─> Exports: archon_container_unhealthy_count
  ├─> Exports: archon_container_health_check_duration_seconds
  ├─> Exports: archon_container_alerts_total
  ├─> Exports: archon_container_error_patterns_total
  └─> Exports: archon_container_recovery_total

python/src/server/middleware/metrics_middleware.py
  ├─> Exports: archon_http_requests_total
  ├─> Exports: archon_http_request_duration_seconds
  ├─> Exports: archon_system_cpu_usage_percent
  ├─> Exports: archon_system_memory_usage_bytes
  └─> ... (other system metrics)
```

## 🚀 Quick Start Files

**Minimum Required Files**:
1. `archon-health-dashboard.json` - Dashboard definition
2. `prometheus-example.yml` - Prometheus config
3. `docker-compose-monitoring.yml` - Docker setup

**Recommended Files**:
4. `README.md` - Setup documentation
5. `SETUP_CHECKLIST.md` - Step-by-step guide
6. `provisioning/datasources/prometheus.yml` - Auto-config
7. `provisioning/dashboards/archon.yml` - Auto-import

**Optional Files**:
8. `DASHBOARD_PREVIEW.md` - Visual reference
9. `FILES.md` - This inventory

## 📥 Import Instructions

### Dashboard Only (Manual)
```bash
# Copy just the dashboard file
cp archon-health-dashboard.json /path/to/grafana/dashboards/

# Import via Grafana UI:
# 1. Login to Grafana
# 2. Click ➕ → Import
# 3. Upload archon-health-dashboard.json
# 4. Select Prometheus data source
# 5. Click Import
```

### Complete Setup (Docker)
```bash
# Use all files
cd /Volumes/PRO-G40/Code/omniarchon/deployment

# Copy Prometheus config
mkdir -p prometheus
cp grafana/prometheus-example.yml prometheus/prometheus.yml

# Start monitoring stack
docker compose -f grafana/docker-compose-monitoring.yml up -d

# Access Grafana (dashboard auto-imported)
open http://localhost:3000
```

### Kubernetes Deployment
```bash
# Create ConfigMaps
kubectl create configmap prometheus-config \
  --from-file=prometheus.yml=grafana/prometheus-example.yml

kubectl create configmap grafana-dashboard \
  --from-file=archon-health-dashboard.json=grafana/archon-health-dashboard.json

# Apply manifests (create separately)
kubectl apply -f k8s/prometheus.yaml
kubectl apply -f k8s/grafana.yaml
```

## 🔐 Sensitive Files (Not Included)

**Do NOT commit these files**:
- `grafana.ini` - Contains admin credentials
- `.env` - Contains passwords and secrets
- `alertmanager.yml` - May contain webhook URLs/tokens

**Add to `.gitignore`**:
```gitignore
# Grafana
deployment/grafana/grafana.ini
deployment/grafana/*.env

# Prometheus
deployment/prometheus/alertmanager.yml

# Data
prometheus-data/
grafana-data/
```

## 📦 Distribution

### Complete Package
```bash
# Create distribution archive
cd /Volumes/PRO-G40/Code/omniarchon/deployment
tar czf archon-grafana-monitoring-v1.0.0.tar.gz grafana/

# Extract on target system
tar xzf archon-grafana-monitoring-v1.0.0.tar.gz
```

### Git Repository
```bash
# All files included in:
deployment/grafana/

# To update from git:
cd /Volumes/PRO-G40/Code/omniarchon
git pull origin main
```

## 🔄 Version History

| Version | Date | Files Added/Modified |
|---------|------|---------------------|
| 1.0.0 | 2025-10-20 | Initial release - all files created |

## 📝 Maintenance

**To Update Dashboard**:
1. Edit in Grafana UI
2. Export to JSON (Share → Export → Save to file)
3. Replace `archon-health-dashboard.json`
4. Commit to git

**To Update Prometheus Config**:
1. Edit `prometheus-example.yml`
2. Test: `promtool check config prometheus-example.yml`
3. Apply: `curl -X POST http://localhost:9090/-/reload`
4. Commit to git

**To Add New Metrics**:
1. Add metric to `container_health_monitor.py`
2. Update dashboard panels (via Grafana UI)
3. Export dashboard
4. Update `README.md` metrics reference
5. Commit all changes

## 📞 Support

**File Issues**:
- Missing file: Check file paths match this inventory
- Corrupt file: Re-download from repository
- Permission error: Ensure read/write access to deployment/grafana/

**Documentation**:
- Setup help: See `README.md` or `SETUP_CHECKLIST.md`
- Visual reference: See `DASHBOARD_PREVIEW.md`
- File questions: This document

---

**Total Files**: 8 files + 2 directories
**Total Size**: ~110 KB (excluding data volumes)
**Last Updated**: 2025-10-20
**Version**: 1.0.0
