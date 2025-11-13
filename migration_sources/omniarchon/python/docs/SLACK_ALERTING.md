# Slack Alerting for Container Health Monitoring

**Status**: ✅ Production Ready
**Version**: 1.0.0
**Last Updated**: 2025-10-20

## Overview

Archon's container health monitoring system automatically detects unhealthy Docker containers and sends real-time Slack notifications with container logs. This helps ops teams respond quickly to service failures.

## Features

- ✅ **Real-time Monitoring**: Checks container health every 60 seconds (configurable)
- ✅ **Error Log Detection**: Automatically detects errors in container logs
- ✅ **Slack Notifications**: Color-coded alerts with severity levels
- ✅ **Container Logs**: Includes last 50 lines of logs in critical alerts
- ✅ **Log Sanitization**: Automatically removes sensitive data before sending (API keys, passwords, etc.)
- ✅ **Recovery Alerts**: Notifies when containers recover after failure
- ✅ **Cooldown Protection**: Prevents alert spam (5-minute default for health, 15-minute for errors)
- ✅ **Graceful Degradation**: Continues running even if Slack is unavailable
- ✅ **Integration**: Uses existing PipelineAlertingService infrastructure

## Architecture

```
┌─────────────────────────────────────────────────────┐
│          archon-server (FastAPI)                    │
│  ┌───────────────────────────────────────────────┐ │
│  │    ContainerHealthMonitor                     │ │
│  │  - Checks Docker health every 60s             │ │
│  │  - Detects unhealthy containers               │ │
│  │  - Retrieves container logs                   │ │
│  │  - Triggers alerts                            │ │
│  └──────────────────┬────────────────────────────┘ │
│                     ↓                               │
│  ┌───────────────────────────────────────────────┐ │
│  │    PipelineAlertingService                    │ │
│  │  - Manages alert rules                        │ │
│  │  - Handles cooldown periods                   │ │
│  │  - Routes notifications                       │ │
│  └──────────────────┬────────────────────────────┘ │
└────────────────────┼────────────────────────────────┘
                     ↓
           ┌─────────────────────┐
           │   Slack Webhook     │
           │   (HTTP POST)       │
           └─────────────────────┘
                     ↓
           ┌─────────────────────┐
           │  Slack Channel      │
           │  #archon-alerts     │
           └─────────────────────┘
```

## Setup

### 1. Create Slack Webhook

1. Go to [Slack Apps](https://api.slack.com/apps)
2. Click "Create New App" → "From scratch"
3. Name it "Archon Health Monitor"
4. Select your workspace
5. Click "Incoming Webhooks" → Enable
6. Click "Add New Webhook to Workspace"
7. Choose channel (e.g., `#archon-alerts`)
8. Copy the webhook URL:
   ```
   https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX
   ```

**Important**: The webhook URL **must** follow this exact format:
- ✅ Must start with `https://hooks.slack.com/services/`
- ✅ Must have 3 path segments: `T{workspace}/B{channel}/{token}`
- ✅ Workspace/channel IDs are alphanumeric and case-insensitive (e.g., T123abc or T123ABC)
- ✅ Token is alphanumeric and case-insensitive
- ✅ Length: 60-150 characters
- ❌ No trailing slashes, query parameters, or extra paths
- ❌ Must use HTTPS, not HTTP

**Validation**: Archon automatically validates webhook URLs on startup and logs errors/warnings if misconfigured.

### 2. Configure Environment Variables

Add to your `.env` file:

```bash
# Slack Webhook for service health alerts
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX

# Alert Configuration (defaults shown)
ENABLE_SLACK_ALERTS=true
ALERT_CHECK_INTERVAL_SECONDS=60  # Check every 60 seconds
ALERT_COOLDOWN_SECONDS=300       # 5 minutes between duplicate alerts

# Optional: Email Alerts (Disabled by Default)
ENABLE_EMAIL_ALERTS=false
ALERT_EMAIL_SMTP_SERVER=smtp.gmail.com
ALERT_EMAIL_SMTP_PORT=587
ALERT_EMAIL_FROM=alerts@archon.dev
ALERT_EMAIL_TO=ops-team@archon.dev
ALERT_EMAIL_USERNAME=
ALERT_EMAIL_PASSWORD=
```

**⚠️ SECURITY WARNING: Email Credentials**

For **production environments**, do NOT use plain environment variables for email passwords. Use Docker secrets instead:

#### Using Docker Secrets for Email Password (Production)

1. **Create the secret**:
```bash
# Create secret from stdin
echo "your-smtp-password" | docker secret create alert_email_password -

# OR create from file
echo "your-smtp-password" > /tmp/email_password.txt
docker secret create alert_email_password /tmp/email_password.txt
rm /tmp/email_password.txt
```

2. **Update docker-compose.yml**:
```yaml
services:
  archon-server:
    secrets:
      - alert_email_password
    environment:
      # Remove ALERT_EMAIL_PASSWORD env var
      # Add secret file path instead
      - ALERT_EMAIL_PASSWORD_FILE=/run/secrets/alert_email_password

secrets:
  alert_email_password:
    external: true
```

3. **Update application code** to read from secret file:
```python
# In pipeline_alerting_service.py or container_health_monitor.py
password_file = os.getenv("ALERT_EMAIL_PASSWORD_FILE")
if password_file and os.path.exists(password_file):
    with open(password_file, 'r') as f:
        email_password = f.read().strip()
else:
    email_password = os.getenv("ALERT_EMAIL_PASSWORD", "")
```

**Current Status**: Email alerts are **disabled by default** (`ENABLE_EMAIL_ALERTS=false`). Plain environment variable is acceptable for development/testing, but implement Docker secrets before enabling in production.

### 3. Restart Services

```bash
# If using Docker Compose
cd deployment
docker compose restart archon-server

# Check logs to verify monitoring started
docker logs archon-server -f | grep "Container health monitoring"
# Expected output: "🏥 Container health monitoring started"
```

## Alert Types

### 1. Critical: Container Unhealthy

**Trigger**: Container health check fails
**Severity**: 🔴 CRITICAL
**Channels**: Slack, Logs, Email (optional)
**Cooldown**: 5 minutes

**Example Alert**:
```
🚨 Pipeline Alert: Container Unhealthy: archon-intelligence

Severity: CRITICAL
Metric: container_health
Current Value: 0.0
Threshold: 1.0

Description:
Container archon-intelligence failed health check

Recent Logs:
```
Traceback (most recent call last):
  File "/app/src/main.py", line 123, in health_check
    result = await check_memgraph()
neo4j.exceptions.ServiceUnavailable: Cannot resolve address memgraph:7687
```
```

### 2. Info: Container Recovered

**Trigger**: Previously unhealthy container passes health check
**Severity**: 🟢 INFO
**Channels**: Slack, Logs
**Cooldown**: 5 minutes

**Example Alert**:
```
✅ Pipeline Alert: Container Recovered: archon-intelligence

Severity: INFO
Metric: container_health
Current Value: 1.0
Threshold: 0.0

Description:
Container archon-intelligence is now healthy
```

### 3. Critical: Container Critical Errors

**Trigger**: Critical errors detected in container logs (CRITICAL, FATAL, ServiceUnavailable, ConnectionError, etc.)
**Severity**: 🔴 CRITICAL
**Channels**: Slack, Logs, Email (optional)
**Cooldown**: 15 minutes

**Example Alert**:
```
🚨 Pipeline Alert: Critical Errors: archon-intelligence

Severity: CRITICAL
Metric: container_errors
Current Value: 3.0
Threshold: 0.0

Description:
Container archon-intelligence has critical errors

**Detected Errors (3):**
```
• neo4j.exceptions.ServiceUnavailable: Cannot resolve address memgraph:7687
• CRITICAL: Database connection pool exhausted
• FATAL: Unable to initialize service
```
```

### 4. Warning: Container Errors Detected

**Trigger**: Warning-level errors detected in container logs (ERROR, Exception, Traceback, TimeoutError, etc.)
**Severity**: 🟡 WARNING
**Channels**: Slack, Logs
**Cooldown**: 15 minutes

**Example Alert**:
```
⚠️ Pipeline Alert: Errors Detected: archon-search

Severity: WARNING
Metric: container_errors
Current Value: 2.0
Threshold: 0.0

Description:
Container archon-search has warnings/errors

**Detected Errors (2):**
```
• ERROR: Request timeout after 5 seconds
• Exception in query execution: Invalid syntax
```
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SLACK_WEBHOOK_URL` | - | Slack webhook URL (required for alerts) |
| `ENABLE_SLACK_ALERTS` | `true` | Enable/disable Slack notifications |
| `ENABLE_EMAIL_ALERTS` | `false` | Enable/disable email notifications |
| `ALERT_CHECK_INTERVAL_SECONDS` | `60` | How often to check container health (seconds) |
| `ALERT_COOLDOWN_SECONDS` | `300` | Minimum time between duplicate health alerts (seconds) |
| `ENABLE_ERROR_MONITORING` | `true` | Enable/disable error log monitoring |
| `ERROR_LOG_WINDOW_SECONDS` | `300` | Check logs from last N seconds (default: 5 minutes) |
| `ERROR_COOLDOWN_SECONDS` | `900` | Minimum time between duplicate error alerts (seconds, default: 15 minutes) |
| `ENABLE_LOG_SANITIZATION` | `true` | Enable/disable log sanitization (removes sensitive data) |
| `SANITIZE_IP_ADDRESSES` | `false` | Enable/disable IP address sanitization (disabled by default) |
| `CUSTOM_SANITIZATION_PATTERNS` | - | Custom patterns to sanitize (format: `pattern\|replacement\|desc;...`) |

### Alert Rules

Alert rules are defined in `container_health_monitor.py` using `PipelineAlertingService`:

```python
AlertRule(
    rule_id="container_unhealthy",
    name="Container Unhealthy",
    description="Docker container failed health check",
    metric_name="container_health",
    comparison="lt",
    threshold_value=1.0,
    severity=AlertSeverity.CRITICAL,
    notification_channels=[
        NotificationChannel.SLACK,
        NotificationChannel.LOG,
    ],
    cooldown_seconds=300,  # 5 minutes
)
```

### Monitored Containers

All containers with prefix `archon-*` are monitored:

- ✅ `archon-server` (FastAPI + Socket.IO)
- ✅ `archon-mcp` (MCP server)
- ✅ `archon-intelligence` (Intelligence service)
- ✅ `archon-bridge` (Bridge service)
- ✅ `archon-search` (Search service)
- ✅ `archon-langextract` (LangExtract service)
- ✅ `archon-agents` (AI agents)
- ✅ `archon-frontend` (React UI)
- ✅ `archon-valkey` (Distributed cache)
- ✅ `archon-kafka-consumer` (Kafka consumer)

**Note**: Containers without health checks (`NONE` status) are skipped.

## Troubleshooting

### Invalid Webhook URL

**Symptoms**: Logs show "Invalid Slack webhook URL configuration" error on startup

**Causes**:
1. Wrong URL format (not from Slack)
2. HTTP instead of HTTPS
3. Trailing slashes or extra paths
4. Special characters in URL
5. Copy/paste errors (whitespace, line breaks)

**Solutions**:
1. **Verify webhook URL format**:
   ```bash
   # Check your webhook URL
   echo $SLACK_WEBHOOK_URL

   # Should match: https://hooks.slack.com/services/T{workspace}/B{channel}/{token}
   # Example: https://hooks.slack.com/services/T1234567890/B9876543210/AbCdEfGhIjKlMnOpQrStUvWx
   ```

2. **Check for common errors**:
   ```bash
   # ❌ Wrong: HTTP instead of HTTPS
   http://hooks.slack.com/services/...

   # ❌ Wrong: Trailing slash
   https://hooks.slack.com/services/T123/B456/abc123/

   # ❌ Wrong: Query parameters
   https://hooks.slack.com/services/T123/B456/abc123?param=value

   # ❌ Wrong: Wrong domain
   https://api.slack.com/webhooks/...

   # ✅ Correct format
   https://hooks.slack.com/services/T123/B456/abc123
   ```

3. **Check validation logs**:
   ```bash
   docker logs archon-server | grep "Slack webhook"

   # Success: "Slack webhook URL validated successfully"
   # Error: "Invalid Slack webhook URL configuration: <specific error>"
   ```

4. **Regenerate webhook if needed**:
   - Go to Slack Apps → Your App → Incoming Webhooks
   - Delete old webhook
   - Add new webhook to workspace
   - Copy new URL carefully (no extra characters)

### Alerts Not Appearing in Slack

1. **Check webhook URL validation**:
   ```bash
   docker logs archon-server | grep "Slack webhook"
   # Expected: "Slack webhook URL validated successfully"
   ```

2. **Test webhook manually**:
   ```bash
   # Test webhook manually
   curl -X POST ${SLACK_WEBHOOK_URL} \
     -H 'Content-Type: application/json' \
     -d '{"text":"Test alert from Archon"}'

   # Expected: "ok" response
   # If error, webhook URL is invalid or revoked
   ```

3. **Check environment variable**:
   ```bash
   docker exec archon-server env | grep SLACK_WEBHOOK_URL
   # Should show your webhook URL (partially redacted for security)
   ```

4. **Check logs**:
   ```bash
   docker logs archon-server | grep "Container health monitoring"
   # Expected: "🏥 Container health monitoring started"

   docker logs archon-server | grep "Slack notification"
   # Shows sent notifications or errors
   ```

5. **Check if disabled**:
   ```bash
   docker exec archon-server env | grep ENABLE_SLACK_ALERTS
   # Should show: ENABLE_SLACK_ALERTS=true
   ```

### Webhook URL Missing Warning

**Symptoms**: Logs show "Slack webhook URL is not configured" warning

**Cause**: Slack alerts are enabled but `SLACK_WEBHOOK_URL` is not set

**Solutions**:
1. Set `SLACK_WEBHOOK_URL` in `.env` file
2. Or disable Slack alerts: `ENABLE_SLACK_ALERTS=false`
3. Restart service: `docker compose restart archon-server`

### Monitoring Not Starting

1. **Check Docker socket mount**:
   ```bash
   docker inspect archon-server | grep -A 3 "Mounts"
   # Should include: /var/run/docker.sock:/var/run/docker.sock
   ```

2. **Check service logs**:
   ```bash
   docker logs archon-server | grep "Container health"
   # Look for startup messages or errors
   ```

3. **Verify Docker access**:
   ```bash
   docker exec archon-server docker ps
   # Should list containers (tests Docker access)
   ```

### Alert Spam

If receiving too many alerts:

1. **Increase cooldown period**:
   ```bash
   # In .env
   ALERT_COOLDOWN_SECONDS=600  # 10 minutes
   ```

2. **Increase check interval**:
   ```bash
   # In .env
   ALERT_CHECK_INTERVAL_SECONDS=120  # Check every 2 minutes
   ```

3. **Check for flapping services**:
   - Services repeatedly failing/recovering indicate underlying issue
   - Fix the service instead of tuning alerts

### Missing Container Logs

If alerts don't include logs:

1. Container may have no recent logs (check `docker logs <container>`)
2. Log retrieval timeout (default: 10 seconds)
3. Container exited immediately (check exit code)

## Testing

### Manual Health Check

```bash
# Enter archon-server container
docker exec -it archon-server bash

# Run health check manually
python3 << EOF
import asyncio
from src.server.services.container_health_monitor import get_health_monitor

async def test():
    monitor = get_health_monitor()
    await monitor.check_health_once()

asyncio.run(test())
EOF
```

### Force Container Unhealthy

```bash
# Stop a service to trigger alert
docker stop archon-intelligence

# Wait 60 seconds for health check
# Check Slack for alert

# Restart to trigger recovery alert
docker start archon-intelligence

# Wait 60 seconds for recovery
# Check Slack for recovery notification
```

### Test Slack Webhook

```bash
# Quick test
curl -X POST "${SLACK_WEBHOOK_URL}" \
  -H 'Content-Type: application/json' \
  -d '{
    "attachments": [{
      "color": "#ff0000",
      "title": "Test Alert: Container Unhealthy",
      "fields": [
        {"title": "Severity", "value": "CRITICAL", "short": true},
        {"title": "Container", "value": "archon-test", "short": true}
      ]
    }]
  }'
```

## Implementation Details

### Files

- **Health Monitor**: `python/src/server/services/container_health_monitor.py` (815 lines)
- **Log Sanitizer**: `python/src/server/services/log_sanitizer.py` (335 lines)
- **Alerting**: `python/src/server/services/pipeline_alerting_service.py` (with webhook validation)
- **Integration**: `python/src/server/main.py` (startup/shutdown hooks)
- **Tests**: `python/tests/test_log_sanitizer.py` (35 tests, 100% pass)
- **Configuration**: `python/.env.example`, `deployment/docker-compose.yml`
- **Tests**: `python/tests/test_pipeline_alerting_validation.py` (webhook validation tests)

### Webhook URL Validation

**Function**: `validate_slack_webhook_url(webhook_url: Optional[str]) -> tuple[bool, Optional[str]]`

**Location**: `src/server/services/pipeline_alerting_service.py`

**Validation Rules**:
1. URL must be a non-empty string
2. Must start with `https://hooks.slack.com/services/`
3. Must match pattern: `T{workspace}/B{channel}/{token}`
4. Workspace/channel IDs: Alphanumeric and case-insensitive (a-z, A-Z, 0-9)
5. Token: Alphanumeric and case-insensitive (a-z, A-Z, 0-9)
6. Length: 60-150 characters
7. No trailing slashes, query parameters, fragments, or extra paths

**Regex Pattern**:
```python
# Note: Slack workspace/channel IDs can be case-insensitive (e.g., T123abc or t123abc)
SLACK_WEBHOOK_PATTERN = re.compile(
    r"^https://hooks\.slack\.com/services/[Tt][A-Za-z0-9]+/[Bb][A-Za-z0-9]+/[A-Za-z0-9]+$"
)
```

**Validation Timing**:
- Runs during `PipelineAlertingService.__init__()`
- Logs validation results (INFO/WARNING/ERROR)
- Does not raise exceptions (graceful degradation)

**Example Validation Errors**:
```python
# Empty URL
validate_slack_webhook_url("")
# → (False, "Slack webhook URL is empty or None")

# Wrong prefix
validate_slack_webhook_url("https://example.com/webhook")
# → (False, "Invalid Slack webhook URL format. Must start with 'https://hooks.slack.com/services/'")

# Invalid structure
validate_slack_webhook_url("https://hooks.slack.com/services/T123/B456/abc-123")
# → (False, "Invalid Slack webhook URL structure. Expected format: ...")

# Valid URL
validate_slack_webhook_url("https://hooks.slack.com/services/T1234567890/B9876543210/AbCdEfGhIjKlMnOp")
# → (True, None)
```

### Dependencies

- Docker CLI (for `docker ps`, `docker inspect`, `docker logs`)
- Docker socket mount (`/var/run/docker.sock`)
- httpx (for Slack webhook HTTP requests)
- Existing `PipelineAlertingService` infrastructure

### Performance

- **Check interval**: 60 seconds (configurable)
- **Check duration**: ~1-2 seconds (all containers)
- **Memory overhead**: ~5-10 MB
- **CPU overhead**: Negligible (<1% avg)

### Security

- **Slack webhook URL**: Stored in environment variable (not in code)
- **Docker socket access**: Restricted to archon-server container
- **Log sanitization**: All sensitive data removed before sending alerts (enabled by default)
- **Alert cooldown**: Prevents potential DoS via alert spam
- **No credential leaks**: Logs are sanitized to remove API keys, passwords, tokens, etc.

## Production Recommendations

1. **Set up dedicated Slack channel**: `#archon-alerts` or `#ops-alerts`
2. **Configure mobile notifications**: Enable push for critical alerts
3. **Monitor alert volume**: High alert volume indicates systemic issues
4. **Document response procedures**: Create runbooks for common failures
5. **Integrate with incident management**: Connect to PagerDuty/OpsGenie
6. **Regular testing**: Monthly test alerts to verify webhook still works

## Prometheus Metrics

**Status**: ✅ Enabled
**Endpoint**: `http://localhost:8181/metrics`
**Version**: 1.0.0

### Overview

Container health monitoring exports Prometheus metrics for observability, alerting, and dashboarding. All metrics use the same registry as the main Archon server metrics.

### Configuration

```bash
# Enable/disable Prometheus metrics (default: true)
ENABLE_PROMETHEUS_METRICS=true
```

### Metrics Exported

#### Core Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `archon_health_checks_total` | Counter | `container`, `status` | Total container health checks performed |
| `archon_health_check_duration_seconds` | Histogram | - | Health check operation duration (buckets: 0.01-5.0s) |
| `archon_unhealthy_containers` | Gauge | - | Number of currently unhealthy containers |
| `archon_alerts_sent_total` | Counter | `severity`, `channel` | Total alerts sent |

#### Additional Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `archon_container_health_status` | Gauge | `container_name` | Health status (1=healthy, 0=unhealthy, -1=starting, -2=no_healthcheck) |
| `archon_container_error_patterns_total` | Counter | `container_name`, `severity`, `pattern_type` | Error patterns detected in logs |

### Example PromQL Queries

```promql
# Current unhealthy containers
archon_unhealthy_containers

# Health check success rate (last 5 minutes)
rate(archon_health_checks_total{status="healthy"}[5m])
/ rate(archon_health_checks_total[5m])

# 95th percentile health check duration
histogram_quantile(0.95, rate(archon_health_check_duration_seconds_bucket[5m]))

# Critical alerts sent to Slack (last hour)
sum(increase(archon_alerts_sent_total{severity="critical", channel="slack"}[1h]))

# Top 5 containers by error count (last 24h)
topk(5, sum by (container_name) (increase(archon_container_error_patterns_total[24h])))
```

### Prometheus Scrape Config

```yaml
scrape_configs:
  - job_name: 'archon-server'
    scrape_interval: 30s  # Match ALERT_CHECK_INTERVAL_SECONDS
    static_configs:
      - targets: ['localhost:8181']
        labels:
          service: 'archon-server'
```

### Example Alerting Rules

```yaml
groups:
  - name: archon_health
    rules:
      - alert: UnhealthyContainers
        expr: archon_unhealthy_containers > 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "{{ $value }} unhealthy containers detected"

      - alert: HighHealthCheckFailureRate
        expr: |
          rate(archon_health_checks_total{status="unhealthy"}[5m])
          / rate(archon_health_checks_total[5m]) > 0.2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "{{ $value | humanizePercentage }} health checks failing"
```

### Testing

```bash
# View metrics
curl http://localhost:8181/metrics | grep archon_health

# Expected output:
# archon_health_checks_total{container="archon-mcp",status="healthy"} 42
# archon_unhealthy_containers 0
# archon_alerts_sent_total{channel="slack",severity="critical"} 2
```

### Performance Overhead

- **Per health check**: <1μs (metrics recording)
- **Scrape endpoint**: <50ms (at 15-30s intervals)
- **Total impact**: Negligible (<0.01% CPU overhead)


## Log Sanitization

**Status**: ✅ Enabled by Default

All container logs are automatically sanitized before sending to external services (Slack, email) to prevent sensitive data leaks.

### Sanitized Patterns

The following sensitive data patterns are automatically removed:

#### API Keys & Tokens
- **OpenAI**: `sk-...` → `[OPENAI_API_KEY]`
- **GitHub**: `ghp_...`, `gho_...`, `github_pat_...` → `[GITHUB_TOKEN]`, `[GITHUB_OAUTH]`, `[GITHUB_PAT]`
- **GitLab**: `glpat-...` → `[GITLAB_TOKEN]`
- **Slack**: `xoxb-...`, `xoxp-...` → `[SLACK_BOT_TOKEN]`, `[SLACK_USER_TOKEN]`
- **Google**: `AIza...`, `ya29....` → `[GOOGLE_API_KEY]`, `[GOOGLE_OAUTH]`
- **AWS**: `AKIA...`, `aws_secret_access_key=...` → `[AWS_ACCESS_KEY]`, `[AWS_SECRET_KEY]`
- **Generic**: `api_key=...`, `api_secret=...`, `access_token=...` → `[API_KEY]`, `[API_SECRET]`, `[ACCESS_TOKEN]`

#### Passwords & Credentials
- **URL passwords**: `postgresql://user:password@host/db` → `postgresql://[USERNAME]:[PASSWORD]@[HOST]/[DB]`
- **Config passwords**: `password="secret"` → `password=[PASSWORD]`
- **Database strings**: Full connection strings sanitized

#### Webhook URLs
- **Slack webhooks**: `https://hooks.slack.com/services/T.../B.../XXX` → `[SLACK_WEBHOOK_URL]`
- **Discord webhooks**: `https://discord.com/api/webhooks/...` → `[DISCORD_WEBHOOK_URL]`

#### JWT Tokens
- **JWT**: `eyJ...` → `[JWT_TOKEN]`

#### Email Addresses
- **Emails**: `user@example.com` → `[EMAIL]`

#### Environment Variables
- **AI API Keys**: `OPENAI_API_KEY=sk-...` → `OPENAI_API_KEY=[API_KEY]`
- **Supabase**: `SUPABASE_SERVICE_KEY=...` → `SUPABASE_SERVICE_KEY=[SUPABASE_KEY]`
- **Auth tokens**: `SERVICE_AUTH_TOKEN=...` → `SERVICE_AUTH_TOKEN=[AUTH_TOKEN]`

#### Optional (Disabled by Default)
- **IP addresses**: `192.168.1.100` → `[IP_ADDRESS]` (enable with `SANITIZE_IP_ADDRESSES=true`)
- **IPv6**: `2001:0DB8:...` → `[IPv6_ADDRESS]` (enable with `SANITIZE_IP_ADDRESSES=true`)

### Before/After Examples

#### Example 1: Container Log with API Key
**Before sanitization:**
```
2025-10-20 10:15:33 DEBUG Using API key: sk-1234567890abcdefghijklmnopqrstuvwxyz
2025-10-20 10:15:34 INFO Connected to OpenAI successfully
```

**After sanitization:**
```
2025-10-20 10:15:33 DEBUG Using API key: [OPENAI_API_KEY]
2025-10-20 10:15:34 INFO Connected to OpenAI successfully
```

#### Example 2: Database Connection Error
**Before sanitization:**
```
ERROR: Failed to connect to postgresql://admin:MySecretPass123@db.local:5432/archon
Contact support@archon.dev for help
```

**After sanitization:**
```
ERROR: Failed to connect to postgresql://[USERNAME]:[PASSWORD]@[HOST]/[DB]
Contact [EMAIL] for help
```

#### Example 3: Webhook Alert Failure
**Before sanitization:**
```
CRITICAL: Failed to send alert to https://hooks.slack.com/services/T12345678/B12345678/XXXXXXXXXXXXXXXXXXXX
Authentication token: Bearer_sk-1234567890abcdefghijklmnopqrstuvwxyz
```

**After sanitization:**
```
CRITICAL: Failed to send alert to [SLACK_WEBHOOK_URL]
Authentication token: Bearer_[OPENAI_API_KEY]
```

#### Example 4: Multiple Sensitive Data
**Before sanitization:**
```
Traceback (most recent call last):
  File "main.py", line 100, in check_health
    connection = connect(password="SuperSecret123", api_key="sk-abc123")
ServiceUnavailable: Cannot reach admin@company.com at 192.168.1.100
```

**After sanitization:**
```
Traceback (most recent call last):
  File "main.py", line 100, in check_health
    connection = connect(password=[PASSWORD], api_key=[OPENAI_API_KEY])
ServiceUnavailable: Cannot reach [EMAIL] at 192.168.1.100
```
*Note: IP addresses not sanitized by default (use `SANITIZE_IP_ADDRESSES=true` to enable)*

### Configuration

```bash
# Enable/disable log sanitization (default: true)
ENABLE_LOG_SANITIZATION=true

# Sanitize IP addresses (default: false, as they may be needed for debugging)
SANITIZE_IP_ADDRESSES=false

# Add custom sanitization patterns (optional)
# Format: pattern|replacement|description;pattern2|replacement2|description2
CUSTOM_SANITIZATION_PATTERNS="CUSTOM_SECRET_\w+|[CUSTOM_SECRET]|Custom secret pattern"
```

### Custom Patterns

You can add custom sanitization patterns via environment variable:

```bash
# Example: Sanitize custom internal tokens
CUSTOM_SANITIZATION_PATTERNS="INTERNAL_TOKEN_\d{10}|[INTERNAL_TOKEN]|Internal token pattern;CUSTOM_API_\w+|[CUSTOM_API]|Custom API pattern"
```

### Performance

- **Compilation**: Patterns compiled once at startup (minimal overhead)
- **Execution**: ~0.1-1ms per log message (negligible impact)
- **Memory**: ~1-2 MB for pattern compilation

### Disabling Sanitization

For development/debugging, you can disable sanitization:

```bash
# Disable log sanitization (NOT recommended for production)
ENABLE_LOG_SANITIZATION=false
```

**Warning**: Only disable in isolated development environments. Never disable in production.

### Testing Sanitization

To test sanitization, trigger an alert and check Slack:

```bash
# Force a container unhealthy (will trigger alert)
docker stop archon-intelligence

# Check Slack message - should see sanitized logs
# Example: API keys replaced with [OPENAI_API_KEY], passwords with [PASSWORD]

# Restart container
docker start archon-intelligence
```

## Roadmap

### Future Enhancements

- [ ] **PagerDuty Integration**: Auto-create incidents for critical alerts
- [ ] **Alert Aggregation**: Group multiple failures into single notification
- [ ] **Historical Dashboard**: Track container health trends over time
- [ ] **Smart Cooldown**: Exponential backoff for repeated failures
- [ ] **Alert Routing**: Different channels for different services
- [x] **Metrics Export**: Prometheus metrics for container health ✅
- [ ] **Auto-Remediation**: Automatic restart of unhealthy containers
- [ ] **Slack Interactive Commands**: Acknowledge/snooze alerts from Slack
- [ ] **Grafana Dashboard Template**: Pre-built dashboard for container health

## Support

**Issues**: Create GitHub issue with label `alerting`
**Documentation**: This file + inline code comments
**Questions**: Ask in `#archon-dev` Slack channel

---

**Last Updated**: 2025-10-20
**Version**: 1.0.0
**Status**: ✅ Production Ready
