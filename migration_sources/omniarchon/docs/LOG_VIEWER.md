# Unified Log Viewer for Archon Pipeline

## Overview

The unified log viewer aggregates logs from all Archon Docker services into a single, filterable view. This makes it easy to trace operations across services, debug issues, and monitor the pipeline.

## Quick Start

### View All Recent Logs
```bash
./scripts/logs.sh all
```

### View Only Errors
```bash
./scripts/logs.sh errors
```

### View Only Warnings
```bash
./scripts/logs.sh warnings
```

### Trace a Specific Correlation ID
```bash
./scripts/logs.sh trace abc-123
# OR
python3 scripts/view_pipeline_logs.py --correlation-id abc-123
```

### Real-time Tail (Follow Mode)
```bash
./scripts/logs.sh follow
```

### View Logs from Specific Service
```bash
./scripts/logs.sh intelligence    # Intelligence service
./scripts/logs.sh bridge          # Bridge service
./scripts/logs.sh consumer        # Kafka consumer
./scripts/logs.sh search          # Search service
```

## Advanced Usage

### Python Script Direct Usage

```bash
# View all logs
python3 scripts/view_pipeline_logs.py

# Filter by service
python3 scripts/view_pipeline_logs.py --service archon-intelligence

# Filter by log level
python3 scripts/view_pipeline_logs.py --level ERROR

# Filter by text/emoji
python3 scripts/view_pipeline_logs.py --filter "❌"
python3 scripts/view_pipeline_logs.py --filter "Memgraph"

# Show logs since specific time
python3 scripts/view_pipeline_logs.py --since 1h
python3 scripts/view_pipeline_logs.py --since 30m

# Increase tail size
python3 scripts/view_pipeline_logs.py --tail 500

# Disable color output (for piping)
python3 scripts/view_pipeline_logs.py --no-color > logs.txt

# Combine filters
python3 scripts/view_pipeline_logs.py \
  --service intelligence \
  --level ERROR \
  --since 2h \
  --tail 200
```

## Services Monitored

The log viewer aggregates logs from these services:

- `archon-intelligence-consumer-1` - Intelligence consumer instance 1
- `archon-intelligence-consumer-2` - Intelligence consumer instance 2
- `archon-intelligence-consumer-3` - Intelligence consumer instance 3
- `archon-intelligence-consumer-4` - Intelligence consumer instance 4
- `archon-intelligence` - Main intelligence service
- `archon-bridge` - Event bridge service
- `archon-kafka-consumer` - Kafka consumer service
- `archon-search` - Search service

## Features

### Color-Coded Output
- **Red**: ERROR level logs
- **Yellow**: WARNING level logs
- **Green**: INFO level logs
- **Blue**: DEBUG level logs

### Log Format
```
[TIMESTAMP] | [SERVICE_NAME] | [LEVEL] | [CORRELATION_ID] [MESSAGE]
```

Example:
```
2025-11-06T07:07:57 | archon-intelligence  | INFO    |  INFO: 127.0.0.1:48374 - "GET /health HTTP/1.1" 200 OK
```

### Chronological Merging
Logs from all services are merged and sorted by timestamp for easy tracing of operations across services.

### Correlation ID Tracking
When a correlation ID is present in logs, it's displayed in the format `[abc12345]` for easy tracing.

## Common Use Cases

### Debug a Failed Ingestion
```bash
# Get correlation ID from error message
# Then trace all logs for that operation
python3 scripts/view_pipeline_logs.py --correlation-id <correlation-id>
```

### Monitor Real-time Processing
```bash
./scripts/logs.sh follow
```

### Find All Errors in Last Hour
```bash
python3 scripts/view_pipeline_logs.py --level ERROR --since 1h
```

### Check Intelligence Generation
```bash
python3 scripts/view_pipeline_logs.py \
  --service intelligence \
  --filter "intelligence" \
  --tail 100
```

### Search for Specific Operations
```bash
# Find all Memgraph operations
python3 scripts/view_pipeline_logs.py --filter "Memgraph"

# Find all failed operations (emoji indicator)
python3 scripts/view_pipeline_logs.py --filter "❌"

# Find all successful operations
python3 scripts/view_pipeline_logs.py --filter "✅"
```

## Tips

1. **Use `--tail` to control volume**: Default is 100 lines per service. Increase for more history.

2. **Combine filters**: Stack multiple filters to narrow down specific issues.

3. **Use `--no-color` for scripting**: When piping to files or other commands.

4. **Follow mode for monitoring**: Use `--follow` to watch logs in real-time.

5. **Correlation ID tracing**: Always grab correlation IDs from errors to trace the full operation flow.

## Troubleshooting

### No logs displayed
- Check that Docker services are running: `docker ps`
- Verify service names match: `docker ps --format "{{.Names}}"`
- Increase `--tail` value to see more history

### Missing correlation IDs
- Correlation IDs are only present in structured logs
- Some legacy log entries may not have them

### Performance with large tail values
- Large `--tail` values (1000+) can be slow
- Use `--since` to limit time range instead

## Architecture

The log viewer:
1. Uses `docker logs` to fetch logs from each service
2. Parses logs into structured format
3. Attempts to extract timestamps, log levels, and correlation IDs
4. Merges logs from all services chronologically
5. Applies filters (service, level, correlation ID, text)
6. Formats with color coding for display

## Related Documentation

- [OBSERVABILITY.md](OBSERVABILITY.md) - Overall monitoring and observability
- [VALIDATION_SCRIPT.md](VALIDATION_SCRIPT.md) - Data integrity validation
- [Slack Alerting](../python/docs/SLACK_ALERTING.md) - Container health alerts
