# Archon Production Monitoring Stack

Comprehensive 24/7 production monitoring and observability solution for Archon microservices platform with AI-powered insights and intelligent alerting.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Archon Production Monitoring                     │
├─────────────────┬─────────────────┬─────────────────────────────────┤
│   Data Sources  │   Collection    │         Visualization           │
├─────────────────┼─────────────────┼─────────────────────────────────┤
│ • FastAPI Apps  │ • Prometheus    │ • Grafana Dashboards           │
│ • PostgreSQL    │ • Node Exporter │ • Alertmanager UI              │
│ • Redis         │ • cAdvisor      │ • Jaeger Tracing UI            │
│ • Docker        │ • Promtail      │ • Uptime Kuma                  │
│ • System Logs   │ • Exporters     │                                 │
├─────────────────┼─────────────────┼─────────────────────────────────┤
│   Storage       │   Analysis      │         Intelligence            │
├─────────────────┼─────────────────┼─────────────────────────────────┤
│ • Prometheus    │ • Loki          │ • AI Anomaly Detection         │
│ • Loki          │ • Elasticsearch │ • Predictive Alerting          │
│ • Jaeger        │ • Grafana       │ • Performance Optimization     │
│ • Elasticsearch │ • AlertManager  │ • Root Cause Analysis          │
└─────────────────┴─────────────────┴─────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- At least 4GB RAM available for monitoring stack
- Ports 3000, 9090, 9093, 3100, 16686 available

### 1. Deploy Monitoring Stack

```bash
# Clone and setup
cd /path/to/archon
./monitoring/deploy-monitoring.sh

# Or manually with Docker Compose
docker-compose -f monitoring/docker-compose.monitoring.yml up -d
```

### 2. Access Dashboards

- **Grafana**: http://localhost:3000 (admin/admin123)
- **Prometheus**: http://localhost:9090
- **AlertManager**: http://localhost:9093
- **Jaeger**: http://localhost:16686
- **Uptime Kuma**: http://localhost:3001

### 3. Start Archon with Monitoring

```bash
# Start Archon services with monitoring enabled
docker-compose up -d

# Verify metrics are being collected
curl http://localhost:8181/monitoring/metrics
curl http://localhost:8181/monitoring/health/intelligent
```

## 📊 Monitoring Components

### Core Services

| Service | Port | Purpose |
|---------|------|---------|
| Prometheus | 9090 | Metrics collection and storage |
| Grafana | 3000 | Visualization and dashboards |
| AlertManager | 9093 | Alert management and notifications |
| Loki | 3100 | Log aggregation |
| Jaeger | 16686 | Distributed tracing |
| Node Exporter | 9100 | System metrics |
| cAdvisor | 8080 | Container metrics |
| Uptime Kuma | 3001 | Uptime monitoring |

### Exporters

- **PostgreSQL Exporter**: Database metrics
- **Redis Exporter**: Cache metrics  
- **Blackbox Exporter**: Endpoint probing
- **Promtail**: Log shipping to Loki

## 🤖 AI-Enhanced Monitoring

Archon includes intelligent monitoring capabilities that provide:

### Anomaly Detection
- Real-time statistical anomaly detection
- AI-powered pattern recognition
- Contextual alerting with confidence scores

### Predictive Analytics
- Trend analysis and forecasting
- Performance degradation prediction
- Resource usage projections

### Intelligent Alerting
- Correlation-based alert grouping  
- Root cause analysis suggestions
- Automated remediation recommendations

### Usage

```bash
# Start intelligent monitoring
curl -X POST http://localhost:8181/monitoring/intelligence/start_analysis

# Get AI insights
curl http://localhost:8181/monitoring/intelligence/insights

# View current anomalies
curl http://localhost:8181/monitoring/intelligence/anomalies

# Get performance predictions
curl http://localhost:8181/monitoring/intelligence/predictions
```

## 📈 Key Metrics Monitored

### Application Metrics
- **Request Rate**: Requests per second by service/endpoint
- **Response Time**: P50, P95, P99 latencies
- **Error Rate**: 4xx/5xx error percentages
- **RAG Performance**: Query duration and success rates
- **Intelligence Analysis**: AI analysis rates and performance

### System Metrics  
- **CPU Usage**: Per-service and system-wide
- **Memory Usage**: RSS, VMS, available memory
- **Disk Usage**: Used/free space and I/O
- **Network**: Throughput and connection counts

### Business Metrics
- **WebSocket Connections**: Active real-time connections
- **Background Tasks**: Pending/active task queues
- **Database Connections**: Connection pool utilization
- **Cache Performance**: Hit/miss rates

### Custom Metrics
- **Quality Scores**: ONEX compliance metrics
- **Performance Baselines**: Established benchmarks
- **Optimization Opportunities**: AI-identified improvements

## 🔔 Alerting Configuration

### Alert Severity Levels

- **Critical**: Immediate action required (5-15min SLA)
- **Warning**: Attention needed (30min-4hr SLA)
- **Info**: Informational/predictive (24hr SLA)

### Alert Types

1. **System Alerts**: CPU, memory, disk space
2. **Application Alerts**: Error rates, response times
3. **Database Alerts**: Connection issues, performance
4. **Container Alerts**: Resource limits, restarts
5. **Business Alerts**: Feature-specific metrics
6. **Predictive Alerts**: AI-powered trend warnings

### Notification Channels

Configure in `.env.monitoring`:

```bash
# Email notifications
ALERT_EMAIL_CRITICAL=critical@yourcompany.com
ALERT_EMAIL_DEFAULT=ops@yourcompany.com

# Slack webhooks  
SLACK_WEBHOOK_CRITICAL=https://hooks.slack.com/...
SLACK_WEBHOOK_SYSTEM=https://hooks.slack.com/...

# PagerDuty integration
PAGERDUTY_ROUTING_KEY=your_routing_key
```

## 📋 Dashboard Templates

### 1. Production Overview
- Service health status
- Request rates and latencies
- Resource utilization
- Error rates and trends

### 2. Performance Deep Dive
- Detailed response time analysis
- Database query performance
- RAG query optimization
- Cache hit rates

### 3. Infrastructure Monitoring
- System resource usage
- Container metrics
- Network performance
- Storage utilization

### 4. AI Intelligence Dashboard
- Anomaly detection results
- Performance predictions
- Optimization recommendations
- Alert correlation analysis

## 🛠️ Operations Guide

### Daily Operations

```bash
# Check monitoring stack health
./monitoring/deploy-monitoring.sh status

# View recent alerts
curl http://localhost:9093/api/v1/alerts

# Check metric collection
curl http://localhost:9090/api/v1/targets

# View intelligent insights
curl http://localhost:8181/monitoring/intelligence/insights
```

### Maintenance Tasks

```bash
# Update monitoring stack
./monitoring/deploy-monitoring.sh update

# Backup monitoring data
./monitoring/deploy-monitoring.sh backup

# View service logs
./monitoring/deploy-monitoring.sh logs grafana
```

### Scaling Recommendations

- **Light Load** (< 100 RPS): Default configuration
- **Medium Load** (100-1000 RPS): Scale Prometheus, add redundancy
- **Heavy Load** (> 1000 RPS): Multi-instance setup, external storage

## 🔧 Configuration Files

### Key Configuration Files

```
monitoring/
├── prometheus/
│   ├── prometheus.yml          # Main Prometheus config
│   └── rules/
│       └── archon_alerts.yml   # Alert rules
├── grafana/
│   ├── provisioning/           # Auto-provisioning
│   └── dashboards/             # Dashboard definitions
├── alertmanager/
│   └── alertmanager.yml        # Alert routing config
├── loki/
│   └── loki-config.yml         # Log aggregation config
└── promtail/
    └── promtail-config.yml     # Log collection config
```

### Environment Configuration

```bash
# Copy and customize
cp .env.monitoring.example .env.monitoring

# Key settings
GRAFANA_ADMIN_PASSWORD=secure_password
ALERT_EMAIL_DEFAULT=your-email@domain.com
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
```

## 📊 Performance Tuning

### Prometheus Optimization

```yaml
# prometheus.yml
global:
  scrape_interval: 15s          # Default scraping frequency
  evaluation_interval: 15s      # Rule evaluation frequency

storage:
  tsdb:
    retention.time: 30d         # Data retention period
    retention.size: 10GB        # Maximum storage size
```

### Grafana Optimization

- Enable caching for dashboards
- Use template variables for dynamic queries
- Optimize query time ranges
- Enable alerting for critical metrics

### Resource Requirements

| Service | CPU | Memory | Disk |
|---------|-----|--------|------|
| Prometheus | 1-2 cores | 2-4GB | 10-50GB |
| Grafana | 0.5 cores | 512MB | 1GB |
| AlertManager | 0.25 cores | 128MB | 1GB |
| Loki | 0.5 cores | 1GB | 10-100GB |
| Exporters | 0.1 cores | 64MB | Minimal |

## 🚨 Troubleshooting

### Common Issues

**Metrics not appearing**
```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Verify Archon metrics endpoint
curl http://localhost:8181/monitoring/metrics

# Check service connectivity
docker-compose logs prometheus
```

**Alerts not firing**
```bash
# Check alert rules
curl http://localhost:9090/api/v1/rules

# Verify AlertManager config
curl http://localhost:9093/api/v1/config

# Test notification channels
docker-compose logs alertmanager
```

**High resource usage**
```bash
# Check Prometheus metrics
curl "http://localhost:9090/api/v1/query?query=prometheus_tsdb_symbol_table_size_bytes"

# Monitor container resources
docker stats

# Adjust retention settings
```

### Log Locations

```bash
# Service logs
docker-compose -f monitoring/docker-compose.monitoring.yml logs [service]

# Archon monitoring logs  
docker-compose logs archon-server | grep monitoring

# System logs (container host)
tail -f /var/log/syslog | grep docker
```

## 🔒 Security Considerations

### Network Security
- Use internal Docker networks
- Restrict external port exposure
- Configure firewalls appropriately

### Access Control
- Change default Grafana credentials
- Use HTTPS in production
- Implement OAuth/LDAP if needed
- Restrict AlertManager access

### Data Protection
- Encrypt data at rest if required
- Secure communication channels
- Regular security updates
- Monitor for vulnerabilities

## 📚 Additional Resources

### Documentation Links
- [Prometheus Configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
- [Grafana Dashboard Guide](https://grafana.com/docs/grafana/latest/dashboards/)
- [AlertManager Setup](https://prometheus.io/docs/alerting/latest/alertmanager/)
- [Loki Configuration](https://grafana.com/docs/loki/latest/configuration/)

### Community Resources
- [Awesome Prometheus](https://github.com/roaldnefs/awesome-prometheus)
- [Grafana Community Dashboards](https://grafana.com/grafana/dashboards/)
- [Monitoring Best Practices](https://prometheus.io/docs/practices/)

---

**Need help?** Check the troubleshooting section or open an issue with:
- Service versions
- Configuration files
- Error logs
- Expected vs actual behavior
