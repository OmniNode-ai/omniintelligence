# Archon Grafana Dashboard - Setup Checklist

**Version**: 1.0.0
**Status**: Ready for Production
**Estimated Setup Time**: 15-30 minutes

## 📋 Pre-Setup Checklist

Before starting, ensure you have:

- [ ] Docker and Docker Compose installed
- [ ] Archon services running with health monitoring enabled
- [ ] Network access between monitoring stack and Archon services
- [ ] Sufficient disk space (5GB+ recommended for Prometheus data)
- [ ] Admin access to deploy monitoring services

## 🚀 Quick Setup (Recommended)

### Step 1: Start Monitoring Stack (5 minutes)

```bash
# Navigate to deployment directory
cd /Volumes/PRO-G40/Code/omniarchon/deployment

# Copy example configuration
cp grafana/prometheus-example.yml prometheus/prometheus.yml

# Start Prometheus and Grafana
docker compose -f grafana/docker-compose-monitoring.yml up -d

# Verify services are running
docker ps | grep -E "prometheus|grafana"
```

**Expected Output**:
```
archon-prometheus   Up 10 seconds   0.0.0.0:9090->9090/tcp
archon-grafana      Up 10 seconds   0.0.0.0:3000->3000/tcp
```

### Step 2: Verify Prometheus is Scraping Metrics (3 minutes)

```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job, health}'

# Test specific metric
curl "http://localhost:9090/api/v1/query?query=archon_container_health_status" | jq .
```

**Expected**: All targets should show `"health": "up"`

### Step 3: Access Grafana (2 minutes)

```bash
# Open Grafana in browser
open http://localhost:3000

# Default credentials (change immediately):
# Username: admin
# Password: admin
```

**On first login**: You'll be prompted to change the password. Choose a strong password and save it securely.

### Step 4: Import Dashboard (5 minutes)

**Option A: Automatic (Provisioning)**

Dashboard is already imported if you mounted the grafana directory in docker-compose. Navigate to:
1. Dashboards → Browse
2. Open "Archon" folder
3. Click "Archon Health Monitoring"

**Option B: Manual Import**

1. Click ➕ → Import
2. Click "Upload JSON file"
3. Select: `/Volumes/PRO-G40/Code/omniarchon/deployment/grafana/archon-health-dashboard.json`
4. Select data source: **Prometheus**
5. Click **Import**

### Step 5: Verify Dashboard (5 minutes)

Check each panel displays data:
- [ ] Container Health Status shows all containers
- [ ] Unhealthy Container Count shows 0
- [ ] Service Availability shows >95%
- [ ] Alert Rate shows timeline (may be empty if no alerts)
- [ ] Health Check Duration shows histograms
- [ ] Recent Alerts Timeline loads
- [ ] Error Log Patterns shows data (may be 0)
- [ ] Container Recoveries displays

**If panels show "No data"**: See Troubleshooting section below

---

## 🔧 Advanced Setup

### Custom Prometheus Configuration

Edit `prometheus.yml` to add/remove targets:

```yaml
scrape_configs:
  - job_name: 'archon-server'
    static_configs:
      - targets: ['archon-server:8181']  # Adjust port/host
```

### Custom Grafana Configuration

Create `deployment/grafana/grafana.ini`:

```ini
[server]
root_url = https://monitoring.yourcompany.com

[security]
admin_user = admin
admin_password = ${GRAFANA_ADMIN_PASSWORD}

[auth]
disable_login_form = false

[auth.anonymous]
enabled = false
```

### SSL/TLS Configuration

For production, use nginx reverse proxy:

```nginx
server {
    listen 443 ssl;
    server_name grafana.yourcompany.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## ✅ Verification Checklist

### Prometheus Health

- [ ] Prometheus UI accessible at http://localhost:9090
- [ ] All Archon targets show "UP" status
- [ ] Query `up{job="archon-server"}` returns 1
- [ ] Metrics `archon_container_health_status` exist
- [ ] Storage disk usage is reasonable (<1GB after 1 day)

### Grafana Health

- [ ] Grafana UI accessible at http://localhost:3000
- [ ] Can login with credentials
- [ ] Prometheus data source shows "✓ Data source is working"
- [ ] Dashboard imports successfully
- [ ] All panels display data (or show "No data" if no alerts yet)

### Metrics Collection

```bash
# Test each metric category

# Health status
curl "http://localhost:9090/api/v1/query?query=archon_container_health_status"

# Unhealthy count
curl "http://localhost:9090/api/v1/query?query=archon_container_unhealthy_count"

# Health check duration
curl "http://localhost:9090/api/v1/query?query=archon_container_health_check_duration_seconds_bucket"

# Alerts total
curl "http://localhost:9090/api/v1/query?query=archon_container_alerts_total"

# Error patterns
curl "http://localhost:9090/api/v1/query?query=archon_container_error_patterns_total"

# Recoveries
curl "http://localhost:9090/api/v1/query?query=archon_container_recovery_total"
```

---

## 🐛 Troubleshooting

### Issue: Panels show "No data"

**Diagnosis**:
```bash
# Check if Prometheus is scraping
curl http://localhost:9090/api/v1/targets

# Check if metrics exist
curl http://localhost:8181/metrics | grep archon_container

# Check Prometheus logs
docker logs archon-prometheus --tail 50
```

**Solutions**:
1. **If targets are "DOWN"**: Check network connectivity between Prometheus and Archon services
2. **If metrics don't exist**: Verify health monitoring is enabled in Archon (check `ENABLE_SLACK_ALERTS=true`)
3. **If Prometheus errors**: Check prometheus.yml syntax

### Issue: Container filter is empty

**Diagnosis**:
```bash
# Check if label exists
curl "http://localhost:9090/api/v1/label/container_name/values"
```

**Solutions**:
1. Wait 15-30 seconds for first scrape
2. Refresh dashboard variables (click refresh icon)
3. Verify `container_name` label exists in metrics

### Issue: Grafana shows "Data source is not working"

**Diagnosis**:
```bash
# Test Prometheus from Grafana container
docker exec archon-grafana wget -O- http://prometheus:9090/-/healthy

# Check network
docker network inspect archon-network
```

**Solutions**:
1. Ensure Prometheus and Grafana are on same network
2. Update data source URL to correct Prometheus address
3. Check Prometheus is running: `docker ps | grep prometheus`

### Issue: High Prometheus disk usage

**Solutions**:
```bash
# Check current usage
docker exec archon-prometheus du -sh /prometheus

# Reduce retention (in prometheus.yml)
# --storage.tsdb.retention.time=15d
# --storage.tsdb.retention.size=5GB

# Restart Prometheus
docker restart archon-prometheus
```

### Issue: Dashboard panels load slowly

**Solutions**:
1. Reduce time range (use last 1h instead of last 24h)
2. Increase Prometheus query timeout in data source settings
3. Add more resources to Prometheus container
4. Optimize queries (use recording rules)

### Issue: Alerts not appearing in timeline

**Diagnosis**:
```bash
# Check if alerts were triggered
curl "http://localhost:9090/api/v1/query?query=archon_container_alerts_total"

# Check container logs
docker logs archon-server | grep "Sent.*alert"
```

**Solutions**:
1. If counter is 0: No alerts have been sent yet (this is good!)
2. If counter > 0 but panel empty: Adjust time range to when alerts occurred
3. Trigger test alert by stopping a container: `docker stop archon-intelligence`

---

## 🔐 Security Hardening

### Production Deployment Checklist

- [ ] Change default Grafana admin password
- [ ] Enable HTTPS/TLS for Grafana
- [ ] Restrict Prometheus access to internal network only
- [ ] Use secret management for credentials (not .env files)
- [ ] Enable Grafana audit logging
- [ ] Set up authentication (LDAP, OAuth, SAML)
- [ ] Configure role-based access control (RBAC)
- [ ] Enable Prometheus authentication if exposed
- [ ] Set resource limits in Docker Compose
- [ ] Configure backup for Grafana dashboards and Prometheus data
- [ ] Set up monitoring for the monitoring stack (meta-monitoring)

### Environment Variables

```bash
# Add to .env file (do NOT commit to git)
GRAFANA_ADMIN_PASSWORD=<strong-random-password>
PROMETHEUS_RETENTION_DAYS=30
PROMETHEUS_STORAGE_SIZE=10GB
```

### Backup Configuration

```bash
# Backup Grafana dashboards
docker exec archon-grafana grafana-cli admin export-dashboard \
  archon-health-dashboard > backup-$(date +%Y%m%d).json

# Backup Prometheus data
docker run --rm -v archon-prometheus-data:/data \
  -v $(pwd)/backup:/backup \
  alpine tar czf /backup/prometheus-$(date +%Y%m%d).tar.gz /data
```

---

## 📊 Performance Tuning

### Prometheus Optimization

```yaml
# In prometheus.yml
global:
  scrape_interval: 15s      # Balance between freshness and load
  scrape_timeout: 10s       # Prevent slow targets from blocking
  evaluation_interval: 15s  # How often to evaluate rules

# Reduce cardinality
metric_relabel_configs:
  - source_labels: [__name__]
    regex: 'archon_http_request_duration_seconds_bucket'
    target_label: le
    replacement: '${1}'
```

### Grafana Optimization

```ini
# In grafana.ini
[database]
wal = true
max_open_conn = 100
max_idle_conn = 10

[dataproxy]
timeout = 30
keep_alive_seconds = 30
```

---

## 📈 Next Steps

After successful setup:

1. **Set Up Alerting**:
   - Configure Prometheus alert rules (see README.md)
   - Set up Alertmanager for routing
   - Integrate with PagerDuty/Slack

2. **Add More Dashboards**:
   - Application performance dashboard
   - Business metrics dashboard
   - Infrastructure overview

3. **Monitoring Best Practices**:
   - Define SLOs (Service Level Objectives)
   - Create runbooks for common alerts
   - Document incident response procedures
   - Schedule regular dashboard reviews

4. **Training**:
   - Train team on dashboard usage
   - Document common troubleshooting scenarios
   - Create team playbooks

---

## 📞 Support

- **Documentation**: `/Volumes/PRO-G40/Code/omniarchon/deployment/grafana/README.md`
- **Dashboard Preview**: `DASHBOARD_PREVIEW.md`
- **GitHub Issues**: Create issue with label `monitoring`
- **Slack**: `#archon-monitoring` channel

---

## ✨ Quick Reference

### Useful URLs
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090
- Prometheus Targets: http://localhost:9090/targets
- Prometheus Alerts: http://localhost:9090/alerts

### Useful Commands

```bash
# Restart monitoring stack
docker compose -f grafana/docker-compose-monitoring.yml restart

# View Prometheus config
docker exec archon-prometheus cat /etc/prometheus/prometheus.yml

# Check Grafana logs
docker logs archon-grafana -f

# Check Prometheus logs
docker logs archon-prometheus -f

# Test metric endpoint
curl http://localhost:8181/metrics | grep archon_container

# Reload Prometheus config (no restart needed)
curl -X POST http://localhost:9090/-/reload
```

---

**Setup Complete!** 🎉

You now have a fully functional Grafana dashboard monitoring Archon container health!

**Last Updated**: 2025-10-20
**Version**: 1.0.0
