# Slack Alerting System

**Version**: 1.0.0
**Status**: Production Ready
**Purpose**: Comprehensive Slack alerting for Archon infrastructure with intelligent throttling

## Overview

The Slack Alerting System provides real-time monitoring and notifications for all Archon containers with intelligent throttling to prevent alert flooding. It monitors container health, resource usage, health check endpoints, and consumer lag, sending formatted alerts to Slack channels.

## Features

### Monitoring Capabilities

- **Container Health**: Detect crashes, restarts, status changes
- **Resource Usage**: CPU and memory thresholds with warning/critical levels
- **Health Checks**: HTTP endpoint monitoring with consecutive failure tracking
- **Consumer Lag**: Kafka consumer lag detection (ready for integration)
- **Service Availability**: Track service uptime and downtime

### Intelligent Throttling

- **Rate Limiting**: Max 1 alert per 5 minutes per service per error type
- **Error Aggregation**: Group similar errors (e.g., 10 errors → 1 alert)
- **Deduplication**: Prevent duplicate alerts within 60 seconds
- **Escalation**: Increase severity for repeated failures
- **Recovery Alerts**: Notify when services recover (optional)

### Alert Management

- **Severity Levels**: Info, Warning, Critical
- **Alert Types**: crash, restart, health_failure, high_cpu, high_memory, consumer_lag
- **State Persistence**: Maintains state across restarts
- **Configurable Thresholds**: All thresholds configurable via environment variables

## Quick Start

### 1. Set Up Slack Webhook

1. Go to your Slack workspace settings
2. Navigate to "Apps" → "Incoming Webhooks"
3. Create a new webhook for your channel
4. Copy the webhook URL (format: `https://hooks.slack.com/services/YOUR/WEBHOOK/URL`)

### 2. Configure Environment

Add to your `.env` file:

```bash
# Slack Webhook URL (REQUIRED)
ALERT_NOTIFICATION_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Optional: Customize thresholds
ALERT_THRESHOLD_CONTAINER_RESTART_COUNT=3
ALERT_THRESHOLD_CPU_PERCENT_WARNING=80.0
ALERT_THRESHOLD_CPU_PERCENT_CRITICAL=95.0
ALERT_THRESHOLD_MEMORY_MB_WARNING=3072.0
ALERT_THRESHOLD_MEMORY_MB_CRITICAL=3686.4
ALERT_THRESHOLD_CONSUMER_LAG_CRITICAL=500
ALERT_THRESHOLD_ERROR_RATE_WARNING=10
ALERT_THRESHOLD_ERROR_RATE_CRITICAL=50

# Optional: Customize throttling
ALERT_THROTTLE_RATE_LIMIT_WINDOW_SECONDS=300
ALERT_THROTTLE_MAX_ALERTS_PER_WINDOW=1
ALERT_THROTTLE_ERROR_AGGREGATION_WINDOW_SECONDS=300
ALERT_THROTTLE_MIN_ERRORS_FOR_AGGREGATION=10
ALERT_THROTTLE_ESCALATION_THRESHOLD=3

# Optional: Monitoring settings
MONITORING_CHECK_INTERVAL_SECONDS=30
MONITORING_HEALTH_CHECK_INTERVAL_SECONDS=60
```

### 3. Run Alerting

**One-shot check** (test configuration):
```bash
python scripts/slack_alerting.py --webhook https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

**Daemon mode** (continuous monitoring):
```bash
python scripts/slack_alerting.py --webhook https://hooks.slack.com/services/YOUR/WEBHOOK/URL --daemon
```

**Using environment variable**:
```bash
export ALERT_NOTIFICATION_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
python scripts/slack_alerting.py --daemon
```

### 4. Production Deployment

**Option A: systemd service** (recommended for Linux servers)

Create `/etc/systemd/system/archon-alerting.service`:

```ini
[Unit]
Description=Archon Slack Alerting Service
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=your-user
WorkingDirectory=/Volumes/PRO-G40/Code/omniarchon
Environment="ALERT_NOTIFICATION_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
ExecStart=/usr/bin/python3 scripts/slack_alerting.py --daemon
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable archon-alerting
sudo systemctl start archon-alerting
sudo systemctl status archon-alerting
```

**Option B: Docker container** (recommended for containerized environments)

Create `deployment/docker-compose.alerting.yml`:

```yaml
services:
  archon-alerting:
    build:
      context: ..
      dockerfile: Dockerfile.alerting
    container_name: archon-alerting
    environment:
      ALERT_NOTIFICATION_SLACK_WEBHOOK_URL: ${ALERT_NOTIFICATION_SLACK_WEBHOOK_URL}
      MONITORING_CHECK_INTERVAL_SECONDS: 30
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    restart: unless-stopped
```

**Option C: tmux/screen** (simple development setup)

```bash
tmux new -s alerting
cd /Volumes/PRO-G40/Code/omniarchon
source .env
python scripts/slack_alerting.py --daemon
# Detach: Ctrl+B, D
```

## Configuration Reference

### Alert Thresholds

| Variable | Default | Description |
|----------|---------|-------------|
| `ALERT_THRESHOLD_CONTAINER_RESTART_COUNT` | 3 | Restarts before critical alert |
| `ALERT_THRESHOLD_CPU_PERCENT_WARNING` | 80.0 | CPU % for warning alert |
| `ALERT_THRESHOLD_CPU_PERCENT_CRITICAL` | 95.0 | CPU % for critical alert |
| `ALERT_THRESHOLD_MEMORY_MB_WARNING` | 3072.0 | Memory MB for warning |
| `ALERT_THRESHOLD_MEMORY_MB_CRITICAL` | 3686.4 | Memory MB for critical |
| `ALERT_THRESHOLD_CONSUMER_LAG_WARNING` | 100 | Consumer lag for warning |
| `ALERT_THRESHOLD_CONSUMER_LAG_CRITICAL` | 500 | Consumer lag for critical |
| `ALERT_THRESHOLD_ERROR_RATE_WARNING` | 10 | Errors in 5min for warning |
| `ALERT_THRESHOLD_ERROR_RATE_CRITICAL` | 50 | Errors in 5min for critical |
| `ALERT_THRESHOLD_HEALTH_CHECK_TIMEOUT_SECONDS` | 10.0 | Health check timeout |
| `ALERT_THRESHOLD_CONSECUTIVE_HEALTH_FAILURES` | 3 | Failures before alert |

### Throttling Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ALERT_THROTTLE_RATE_LIMIT_WINDOW_SECONDS` | 300 | Rate limit window (5min) |
| `ALERT_THROTTLE_MAX_ALERTS_PER_WINDOW` | 1 | Max alerts per window |
| `ALERT_THROTTLE_ERROR_AGGREGATION_WINDOW_SECONDS` | 300 | Error aggregation window |
| `ALERT_THROTTLE_MIN_ERRORS_FOR_AGGREGATION` | 10 | Min errors to aggregate |
| `ALERT_THROTTLE_ESCALATION_THRESHOLD` | 3 | Consecutive failures to escalate |
| `ALERT_THROTTLE_ESCALATION_MULTIPLIER` | 2.0 | Escalation severity multiplier |
| `ALERT_THROTTLE_RECOVERY_COOLDOWN_SECONDS` | 300 | Cooldown after recovery |
| `ALERT_THROTTLE_DEDUPLICATION_WINDOW_SECONDS` | 60 | Duplicate alert window |

### Monitoring Services

| Variable | Default | Description |
|----------|---------|-------------|
| `ALERT_SERVICE_MONITORED_CONTAINERS` | See below | List of containers to monitor |
| `ALERT_SERVICE_CRITICAL_SERVICES` | See below | Critical services (bypass rate limit) |

**Default Monitored Containers**:
- `archon-intelligence`
- `archon-bridge`
- `archon-search`
- `archon-langextract`
- `archon-kafka-consumer`
- `archon-intelligence-consumer-1/2/3/4`
- `archon-qdrant`
- `archon-memgraph`
- `archon-valkey`

**Default Critical Services**:
- `archon-intelligence`
- `archon-bridge`
- `archon-qdrant`
- `archon-memgraph`

### Notification Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `ALERT_NOTIFICATION_SLACK_WEBHOOK_URL` | *(required)* | Slack webhook URL |
| `ALERT_NOTIFICATION_INCLUDE_METRICS` | true | Include detailed metrics |
| `ALERT_NOTIFICATION_INCLUDE_RECOVERY_ALERTS` | true | Send recovery notifications |
| `ALERT_NOTIFICATION_EMOJI_CRITICAL` | 🚨 | Critical alert emoji |
| `ALERT_NOTIFICATION_EMOJI_WARNING` | ⚠️ | Warning alert emoji |
| `ALERT_NOTIFICATION_EMOJI_INFO` | ℹ️ | Info alert emoji |
| `ALERT_NOTIFICATION_EMOJI_RECOVERY` | ✅ | Recovery alert emoji |
| `ALERT_NOTIFICATION_ALERT_PREFIX` | [Archon Alert] | Alert message prefix |

### Monitoring Loop

| Variable | Default | Description |
|----------|---------|-------------|
| `MONITORING_CHECK_INTERVAL_SECONDS` | 30 | Main check interval |
| `MONITORING_HEALTH_CHECK_INTERVAL_SECONDS` | 60 | Health check interval |
| `MONITORING_METRICS_COLLECTION_INTERVAL_SECONDS` | 120 | Metrics collection interval |
| `MONITORING_STATE_FILE_PATH` | /tmp/archon_alerting_state.json | State persistence path |
| `MONITORING_MAX_HISTORY_ENTRIES` | 1000 | Max alert history size |
| `MONITORING_LOG_LEVEL` | INFO | Logging level |

## Alert Types

### Container Crash

**Trigger**: Container stops running unexpectedly
**Severity**: Critical
**Throttling**: Bypassed for critical services

Example:
```
🚨 [Archon Alert] Crash
archon-intelligence has crashed (status: exited)
Service: archon-intelligence
Severity: CRITICAL
Status: exited
Container ID: abc123def456
```

### Container Restart

**Trigger**: Container restart count increases
**Severity**: Warning (< 3 restarts), Critical (≥ 3 restarts)
**Throttling**: Rate limited

Example:
```
⚠️ [Archon Alert] Restart
archon-bridge has restarted (1 time(s))
Service: archon-bridge
Severity: WARNING
Restart Count: 4
New Restarts: 1
```

### Health Check Failure

**Trigger**: HTTP health endpoint fails
**Severity**: Warning (< 3 failures), Critical (≥ 3 failures)
**Throttling**: Rate limited, escalation after 3 failures

Example:
```
🚨 [Archon Alert] Health Failure
archon-search health check failing (5 consecutive failures)
Service: archon-search
Severity: CRITICAL
Consecutive Failures: 5
Escalation Level: 2
```

### High CPU Usage

**Trigger**: CPU usage exceeds thresholds
**Severity**: Warning (≥80%), Critical (≥95%)
**Throttling**: Rate limited

Example:
```
⚠️ [Archon Alert] High CPU
archon-intelligence CPU usage high: 87.3%
Service: archon-intelligence
Severity: WARNING
CPU Percent: 87.30
```

### High Memory Usage

**Trigger**: Memory usage exceeds thresholds
**Severity**: Warning (≥3GB), Critical (≥3.6GB)
**Throttling**: Rate limited

Example:
```
🚨 [Archon Alert] High Memory
archon-qdrant memory usage critical: 3845MB
Service: archon-qdrant
Severity: CRITICAL
Memory MB: 3845.00
```

### Aggregated Errors

**Trigger**: Multiple errors aggregated over time window
**Severity**: Warning
**Throttling**: Sent after 10 errors in 5 minutes

Example:
```
⚠️ [Archon Alert] Health Failure Aggregated
archon-bridge had 15 health_failure errors in the last 300s
Service: archon-bridge
Severity: WARNING
Count: 15
Window Seconds: 300
```

### Recovery

**Trigger**: Service recovers from failure state
**Severity**: Info
**Throttling**: Optional (configurable)

Example:
```
✅ [Archon Alert] Service Recovered
archon-intelligence has recovered from health_check
Service: archon-intelligence
Recovery Type: health_check
Previous Failures: 5
```

## Throttling Behavior

### Rate Limiting

**Purpose**: Prevent alert spam from single service
**Mechanism**: Max 1 alert per 5 minutes per service per alert type
**Bypass**: Critical services bypass rate limiting

**Example**:
- `archon-bridge` health check fails at 10:00 → Alert sent
- `archon-bridge` health check fails at 10:01 → Suppressed (rate limited)
- `archon-bridge` health check fails at 10:05 → Alert sent (window expired)

### Error Aggregation

**Purpose**: Group similar errors into summary alerts
**Mechanism**: Accumulate errors, send summary after threshold
**Threshold**: 10 errors in 5 minutes

**Example**:
- `archon-search` has 15 health failures over 5 minutes
- Instead of 15 alerts → 1 aggregated alert: "15 health_failure errors in 300s"

### Deduplication

**Purpose**: Prevent identical alerts in short timeframe
**Mechanism**: Track alert IDs, suppress duplicates within 60 seconds
**Alert ID**: Generated from service + type + key details

**Example**:
- Alert ID: `health-archon-intelligence-3`
- Same alert ID within 60s → Suppressed

### Escalation

**Purpose**: Increase urgency for persistent problems
**Mechanism**: Track consecutive failures, escalate after threshold
**Threshold**: 3 consecutive failures

**Example**:
- 1st failure: Warning, escalation_level=0
- 2nd failure: Warning, escalation_level=0
- 3rd failure: Critical, escalation_level=1
- 4th failure: Critical, escalation_level=2

## State Persistence

The alerting system maintains state across restarts to:
- Track restart counts accurately
- Prevent duplicate alerts after restart
- Maintain escalation levels

**State File**: `/tmp/archon_alerting_state.json`

**State Contents**:
```json
{
  "service_states": {
    "archon-intelligence": {
      "container_id": "abc123def456",
      "running": true,
      "restart_count": 2
    }
  },
  "timestamp": "2025-11-06T10:30:00"
}
```

## Monitoring & Debugging

### Check Status

```bash
# View logs (systemd)
sudo journalctl -u archon-alerting -f

# View logs (tmux/screen)
tmux attach -t alerting

# Check state file
cat /tmp/archon_alerting_state.json | jq
```

### Test Alert

Send a test alert:

```bash
# One-shot check (will alert on any issues)
python scripts/slack_alerting.py --webhook $WEBHOOK_URL --verbose

# Manual test alert
curl -X POST $WEBHOOK_URL \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "Test alert from Archon alerting system"
  }'
```

### Common Issues

**Issue**: "Failed to connect to Docker"
```bash
# Solution: Ensure Docker socket accessible
ls -la /var/run/docker.sock
sudo chmod 666 /var/run/docker.sock  # Or add user to docker group
```

**Issue**: "Rate limit exceeded, wait 240s"
```bash
# Solution: Increase rate limit window or max alerts
export ALERT_THROTTLE_MAX_ALERTS_PER_WINDOW=3
```

**Issue**: "Too many aggregated alerts"
```bash
# Solution: Increase aggregation threshold
export ALERT_THROTTLE_MIN_ERRORS_FOR_AGGREGATION=20
```

**Issue**: "Webhook URL required"
```bash
# Solution: Set webhook URL via env or CLI
export ALERT_NOTIFICATION_SLACK_WEBHOOK_URL=https://hooks.slack.com/...
```

## Integration with Existing Monitoring

### health_monitor.py Integration

The Slack alerting system complements `health_monitor.py`:

- **health_monitor.py**: Dashboard view, interactive recovery, detailed metrics
- **slack_alerting.py**: Push notifications, passive alerting, team notifications

**Run both**:
```bash
# Terminal 1: Dashboard monitoring
python scripts/health_monitor.py --dashboard --auto-recovery

# Terminal 2: Slack alerting
python scripts/slack_alerting.py --daemon
```

### Prometheus Integration (Future)

Ready for Prometheus metrics integration:

```python
# Example: Add Prometheus metrics
from prometheus_client import Counter, Gauge

alert_counter = Counter('archon_alerts_total', 'Total alerts sent', ['service', 'type', 'severity'])
health_gauge = Gauge('archon_service_health', 'Service health status', ['service'])
```

## Best Practices

### Alert Fatigue Prevention

1. **Start Conservative**: Begin with high thresholds, tune down based on baselines
2. **Use Aggregation**: Enable error aggregation for noisy services
3. **Configure Recovery Alerts**: Useful for awareness, but optional if too noisy
4. **Critical Services Only**: Consider monitoring only critical services initially

### Threshold Tuning

**CPU Usage**:
- Development: Warning=80%, Critical=95%
- Production: Warning=70%, Critical=85%

**Memory Usage**:
- Adjust based on container limits in docker-compose.yml
- Warning: 75% of limit, Critical: 90% of limit

**Consumer Lag**:
- Low traffic: Warning=100, Critical=500
- High traffic: Warning=1000, Critical=5000

### Alert Channel Strategy

**Option 1: Single channel** (simple)
- All alerts → `#archon-alerts`

**Option 2: Severity-based** (recommended)
- Critical → `#archon-critical` (pager duty)
- Warning/Info → `#archon-monitoring`

**Option 3: Service-based**
- Infrastructure → `#archon-infra` (qdrant, memgraph, kafka)
- Application → `#archon-app` (intelligence, bridge, search)

## Performance Impact

**Resource Usage**:
- CPU: <1% (mostly idle)
- Memory: ~50MB
- Disk: <1MB (state file)
- Network: Minimal (only on alerts)

**Monitoring Overhead**:
- Container stats API: <10ms per container
- Health checks: <100ms per endpoint
- Total per cycle: <2 seconds (12 containers)

**Recommended**:
- Check interval: 30 seconds (default)
- Health check interval: 60 seconds
- Metrics interval: 120 seconds

## Future Enhancements

**Planned Features**:
1. ✅ Container monitoring (implemented)
2. ✅ Resource usage monitoring (implemented)
3. ✅ Health check monitoring (implemented)
4. ✅ Intelligent throttling (implemented)
5. ⏳ Consumer lag monitoring (ready for Kafka integration)
6. ⏳ Log parsing for error detection
7. ⏳ Anomaly detection (ML-based)
8. ⏳ Multi-channel support (PagerDuty, email, webhooks)
9. ⏳ Alert routing rules
10. ⏳ Maintenance windows

## Support

**Documentation**:
- Configuration: `config/alerting_config.py`
- Main script: `scripts/slack_alerting.py`
- This guide: `docs/SLACK_ALERTING.md`

**Related**:
- Health monitoring: `scripts/health_monitor.py`
- Validation: `scripts/validate_integrations.sh`
- Log viewing: `scripts/view_pipeline_logs.py`

---

**Archon Slack Alerting** - Production-ready monitoring with intelligent throttling to prevent alert flooding.
