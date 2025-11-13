# Archon Health Monitoring Dashboard

**Version**: 1.0.0
**Last Updated**: 2025-10-20
**Status**: Production Ready

## Overview

Comprehensive Grafana dashboard for monitoring Archon container health, alerts, and service availability. Provides real-time visibility into container health status, error patterns, and system reliability.

## Features

- ✅ **Real-time Container Health**: Live health status for all Archon services
- ✅ **Alert Tracking**: Alert rate monitoring and timeline visualization
- ✅ **Performance Metrics**: Health check duration histograms
- ✅ **Availability Monitoring**: Service uptime percentage tracking
- ✅ **Error Detection**: Log pattern analysis and error trend visualization
- ✅ **Recovery Tracking**: Container recovery event monitoring
- ✅ **Multi-Container Filtering**: Filter by specific containers or view all

## Prerequisites

1. **Prometheus** - Running and scraping Archon metrics
2. **Grafana** - Version 9.0+ recommended
3. **Archon Services** - Running with Prometheus metrics enabled
4. **Network Access** - Grafana can reach Prometheus endpoint

## Quick Start

### 1. Configure Prometheus to Scrape Archon Metrics

Add to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'archon-server'
    scrape_interval: 15s
    static_configs:
      - targets: ['archon-server:8181']
    metrics_path: '/metrics'

  - job_name: 'archon-intelligence'
    scrape_interval: 15s
    static_configs:
      - targets: ['archon-intelligence:8053']
    metrics_path: '/metrics'

  - job_name: 'archon-mcp'
    scrape_interval: 15s
    static_configs:
      - targets: ['archon-mcp:8151']
    metrics_path: '/metrics'
```

**Note**: Adjust targets based on your deployment. If using Docker Compose, use service names. For Kubernetes, use service DNS names.

### 2. Import Dashboard to Grafana

**Option A: Via Grafana UI**

1. Open Grafana web interface
2. Navigate to **Dashboards** → **Import**
3. Click **Upload JSON file**
4. Select `archon-health-dashboard.json`
5. Choose Prometheus data source
6. Click **Import**

**Option B: Via Grafana API**

```bash
# Set your Grafana credentials
GRAFANA_URL="http://localhost:3000"
GRAFANA_API_KEY="your-api-key"

# Import dashboard
curl -X POST \
  -H "Authorization: Bearer ${GRAFANA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d @archon-health-dashboard.json \
  "${GRAFANA_URL}/api/dashboards/db"
```

**Option C: Via Docker Volume Mount**

```yaml
# In docker-compose.yml
grafana:
  image: grafana/grafana:latest
  volumes:
    - ./deployment/grafana:/etc/grafana/provisioning/dashboards
    - ./grafana-data:/var/lib/grafana
```

Create provisioning config at `deployment/grafana/dashboard-provider.yml`:

```yaml
apiVersion: 1

providers:
  - name: 'Archon'
    orgId: 1
    folder: 'Archon Monitoring'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
```

### 3. Configure Data Source

1. In Grafana, go to **Configuration** → **Data Sources**
2. Click **Add data source**
3. Select **Prometheus**
4. Configure:
   - **Name**: `Prometheus` (must match dashboard variable)
   - **URL**: `http://prometheus:9090` (adjust for your setup)
   - **Scrape interval**: `15s`
5. Click **Save & Test**

## Dashboard Panels

### 1. Container Health Status (Gauge)
- **Location**: Top left (12x8)
- **Metric**: `archon_container_health_status`
- **Description**: Shows current health status for each container
- **Values**:
  - `1` = Healthy (Green)
  - `0` = Unhealthy (Red)
  - `-1` = Starting (Yellow)
  - `-2` = No Healthcheck (Gray)
- **Use Case**: Quick visual check of all service health states

### 2. Unhealthy Container Count (Gauge)
- **Location**: Top center (6x8)
- **Metric**: `archon_container_unhealthy_count`
- **Description**: Total number of unhealthy containers
- **Thresholds**:
  - Green: 0 unhealthy
  - Yellow: 1-2 unhealthy
  - Red: 3+ unhealthy
- **Use Case**: High-level system health indicator

### 3. Service Availability (Gauge)
- **Location**: Top right (6x8)
- **Metric**: Calculated from `archon_container_health_status`
- **Formula**: `(healthy_count / total_count) * 100`
- **Thresholds**:
  - Red: < 95%
  - Yellow: 95-99%
  - Green: > 99%
- **Use Case**: SLA monitoring and reliability tracking

### 4. Alert Rate Over Time (Time Series)
- **Location**: Middle left (12x9)
- **Metric**: `rate(archon_container_alerts_total)`
- **Description**: Rate of alerts sent per second
- **Legend**: Shows container name, alert type, and severity
- **Colors**:
  - Red: Unhealthy alerts
  - Green: Recovery alerts
- **Use Case**: Identify alert storms and trends

### 5. Health Check Duration (Histogram)
- **Location**: Middle right (12x9)
- **Metric**: `archon_container_health_check_duration_seconds`
- **Description**: P95 and P99 latency for health checks
- **Buckets**: 0.1s, 0.25s, 0.5s, 1s, 2.5s, 5s, 10s
- **Use Case**: Performance monitoring and bottleneck detection

### 6. Recent Alerts Timeline (Time Series)
- **Location**: Bottom (24x9)
- **Metric**: `delta(archon_container_alerts_total)`
- **Description**: Timeline showing when alerts occurred
- **Points**: Each point represents an alert event
- **Colors**:
  - Red: CRITICAL severity
  - Yellow: WARNING severity
  - Green: INFO severity (recoveries)
- **Use Case**: Incident timeline and correlation analysis

### 7. Error Log Patterns Detected (Stacked Area)
- **Location**: Bottom left (12x9)
- **Metric**: `rate(archon_container_error_patterns_total)`
- **Description**: Rate of error patterns detected in logs
- **Stacking**: Errors stacked by severity
- **Colors**:
  - Red: CRITICAL errors
  - Yellow: WARNING errors
- **Use Case**: Error trend analysis and pattern detection

### 8. Container Recoveries (Bar Chart)
- **Location**: Bottom right (12x9)
- **Metric**: `increase(archon_container_recovery_total)`
- **Description**: Number of recovery events per 5-minute window
- **Use Case**: Service stability and auto-recovery tracking

## Dashboard Variables

### Data Source
- **Name**: `datasource`
- **Type**: Data source
- **Query**: `prometheus`
- **Description**: Select Prometheus instance
- **Default**: First Prometheus data source

### Container Filter
- **Name**: `container`
- **Type**: Query
- **Query**: `label_values(archon_container_health_status, container_name)`
- **Multi-select**: Yes
- **Include All**: Yes
- **Default**: All containers
- **Description**: Filter dashboard to specific containers

## Prometheus Metrics Reference

### Health Status Metrics

```promql
# Container health status
archon_container_health_status{container_name="archon-server"}

# Unhealthy container count
archon_container_unhealthy_count

# Health check duration
archon_container_health_check_duration_seconds{container_name="archon-server"}
```

### Alert Metrics

```promql
# Total alerts sent
archon_container_alerts_total{container_name="archon-server", alert_type="unhealthy", severity="CRITICAL"}

# Alert rate
rate(archon_container_alerts_total[5m])

# Container recoveries
archon_container_recovery_total{container_name="archon-server"}
```

### Error Pattern Metrics

```promql
# Error patterns detected
archon_container_error_patterns_total{container_name="archon-server", severity="CRITICAL", pattern_type="ServiceUnavailable"}

# Error pattern rate
rate(archon_container_error_patterns_total[5m])
```

## Alerting Rules (Optional)

Add to Prometheus `rules.yml` for automated alerting:

```yaml
groups:
  - name: archon_health
    interval: 30s
    rules:
      # Alert on unhealthy containers
      - alert: ArchonContainerUnhealthy
        expr: archon_container_health_status == 0
        for: 2m
        labels:
          severity: critical
          team: platform
        annotations:
          summary: "Archon container {{ $labels.container_name }} is unhealthy"
          description: "Container {{ $labels.container_name }} has been unhealthy for 2 minutes"

      # Alert on multiple unhealthy containers
      - alert: ArchonMultipleContainersUnhealthy
        expr: archon_container_unhealthy_count >= 3
        for: 1m
        labels:
          severity: critical
          team: platform
        annotations:
          summary: "Multiple Archon containers unhealthy"
          description: "{{ $value }} containers are currently unhealthy"

      # Alert on low availability
      - alert: ArchonLowAvailability
        expr: (sum(archon_container_health_status == 1) / count(archon_container_health_status >= -1)) * 100 < 95
        for: 5m
        labels:
          severity: warning
          team: platform
        annotations:
          summary: "Archon availability below 95%"
          description: "Current availability: {{ $value }}%"

      # Alert on high error rate
      - alert: ArchonHighErrorRate
        expr: rate(archon_container_error_patterns_total{severity="CRITICAL"}[5m]) > 0.5
        for: 2m
        labels:
          severity: warning
          team: platform
        annotations:
          summary: "High error rate in {{ $labels.container_name }}"
          description: "Critical errors detected: {{ $value }} errors/sec"
```

## Troubleshooting

### Dashboard shows "No data"

1. **Check Prometheus scraping**:
   ```bash
   # Verify Prometheus is scraping Archon
   curl http://prometheus:9090/api/v1/targets

   # Check if metrics exist
   curl http://prometheus:9090/api/v1/query?query=archon_container_health_status
   ```

2. **Verify metrics endpoint**:
   ```bash
   # Test Archon metrics endpoint
   curl http://archon-server:8181/metrics

   # Should see:
   # archon_container_health_status{container_name="archon-server"} 1.0
   ```

3. **Check time range**: Ensure dashboard time range includes recent data

### Metrics not updating

1. **Check scrape interval**: Prometheus should scrape every 15-30 seconds
2. **Verify container health monitoring is running**:
   ```bash
   docker logs archon-server | grep "Container health monitoring"
   # Expected: "🏥 Container health monitoring started"
   ```

3. **Check for errors**:
   ```bash
   docker logs archon-server | grep -i error
   ```

### Container filter is empty

1. **Verify metric exists**:
   ```bash
   curl http://prometheus:9090/api/v1/label/container_name/values
   ```

2. **Check Prometheus retention**: Data may have been deleted if retention is too short

3. **Refresh dashboard variables**: Click refresh icon next to Container dropdown

### Panels show incorrect data

1. **Verify PromQL queries**: Test queries in Prometheus UI
2. **Check metric labels**: Ensure `container_name` labels match
3. **Validate time range**: Ensure sufficient data exists for selected range

## Docker Compose Integration

Add Prometheus and Grafana to your `docker-compose.yml`:

```yaml
services:
  prometheus:
    image: prom/prometheus:latest
    container_name: archon-prometheus
    volumes:
      - ./deployment/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
    ports:
      - "9090:9090"
    networks:
      - archon-network

  grafana:
    image: grafana/grafana:latest
    container_name: archon-grafana
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-admin}
      - GF_INSTALL_PLUGINS=grafana-clock-panel
    volumes:
      - ./deployment/grafana:/etc/grafana/provisioning/dashboards
      - grafana-data:/var/lib/grafana
    ports:
      - "3000:3000"
    networks:
      - archon-network
    depends_on:
      - prometheus

volumes:
  prometheus-data:
  grafana-data:

networks:
  archon-network:
    driver: bridge
```

## Performance Considerations

- **Scrape Interval**: 15-30 seconds recommended (balance between freshness and load)
- **Retention**: 30 days default (adjust based on storage capacity)
- **Query Performance**: Most queries use rate/increase with 5m windows for efficiency
- **Dashboard Refresh**: 30 seconds default (adjust based on monitoring needs)

## Security

1. **Authentication**: Enable Grafana authentication in production
2. **TLS**: Use HTTPS for Grafana in production
3. **Prometheus Access**: Restrict Prometheus access to internal network
4. **API Keys**: Use API keys instead of credentials for automation

## Customization

### Add Custom Panels

1. Edit dashboard in Grafana UI
2. Add new panel
3. Select visualization type
4. Write PromQL query
5. Configure display options
6. Save dashboard
7. Export to JSON for version control

### Modify Alert Thresholds

Edit panel → Field → Thresholds → Add/modify threshold values

### Change Time Windows

Edit panel → Query options → Min interval / Rate interval

## Support

- **Documentation**: `/Volumes/PRO-G40/Code/omniarchon/python/docs/SLACK_ALERTING.md`
- **Metrics**: `/Volumes/PRO-G40/Code/omniarchon/python/src/server/middleware/metrics_middleware.py`
- **Health Monitor**: `/Volumes/PRO-G40/Code/omniarchon/python/src/server/services/container_health_monitor.py`
- **Issues**: Create GitHub issue with label `monitoring`

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-10-20 | Initial release with 8 panels and full health monitoring |

## License

Part of Archon project. See main repository for license information.

---

**Archon Health Monitoring Dashboard** - Real-time visibility into container health and service reliability.
