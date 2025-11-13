# Orphan Monitoring - Quick Reference

**Purpose**: Monitor orphaned FILE nodes in Memgraph and track data quality metrics.

## Quick Commands

### Check Current Orphan Count
```bash
python3 scripts/monitor_orphans.py
```

### View Dashboard
```bash
python3 scripts/data_quality_dashboard.py
```

### Check for Alerts
```bash
python3 scripts/orphan_alerting.py
```

### API Endpoints
```bash
# Orphan count
curl http://localhost:8053/api/data-quality/orphan-count | python3 -m json.tool

# Tree health
curl http://localhost:8053/api/data-quality/tree-health | python3 -m json.tool

# Health check
curl http://localhost:8053/api/data-quality/health | python3 -m json.tool
```

## Continuous Monitoring

### Start Monitoring (Background)
```bash
# Start metrics collection (every 5 minutes)
nohup python3 scripts/monitor_orphans.py --continuous > logs/monitor_orphans.log 2>&1 &

# Start alerting (every 5 minutes)
nohup python3 scripts/orphan_alerting.py --continuous > logs/orphan_alerting.log 2>&1 &
```

### View Dashboard (Auto-refresh)
```bash
# Refresh every 30 seconds
python3 scripts/data_quality_dashboard.py --refresh 30
```

### Stop Monitoring
```bash
# Find process IDs
ps aux | grep monitor_orphans
ps aux | grep orphan_alerting

# Kill processes
kill <PID>
```

## Troubleshooting

### No Historical Data
**Issue**: Dashboard shows "No historical data available"
**Solution**: Run metrics collection first:
```bash
python3 scripts/monitor_orphans.py
```

### High Orphan Count
**Issue**: Dashboard shows orphan count > 0
**Solution**: Run tree building:
```bash
python3 scripts/quick_fix_tree.py
```

### API Endpoints Not Found (404)
**Issue**: Data quality endpoints return 404
**Solution**: Rebuild and restart archon-intelligence:
```bash
cd deployment
docker compose -f docker-compose.yml -f docker-compose.services.yml build archon-intelligence
docker compose -f docker-compose.yml -f docker-compose.services.yml up -d archon-intelligence
```

## Slack Integration

### Setup
```bash
export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### Test Alert
```bash
python3 scripts/orphan_alerting.py --test
```

### Enable Slack Alerts
```bash
python3 scripts/orphan_alerting.py --continuous --slack-webhook $SLACK_WEBHOOK_URL
```

## Files & Locations

- **Scripts**: `/scripts/monitor_orphans.py`, `/scripts/data_quality_dashboard.py`, `/scripts/orphan_alerting.py`
- **Metrics**: `/logs/orphan_metrics.json`
- **Alerts**: `/logs/orphan_alerts.json`
- **API**: `http://localhost:8053/api/data-quality/*`

## Documentation

See `/ORPHAN_MONITORING_IMPLEMENTATION.md` for complete documentation.
