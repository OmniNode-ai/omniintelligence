# Intelligence Consumer Service

Asynchronous consumer service for document enrichment through the intelligence platform.

## Overview

The intelligence consumer service processes document enrichment requests from Kafka, sends them through the intelligence service for analysis, and publishes completion events. It implements robust error handling with exponential backoff retry logic and dead letter queue (DLQ) routing for failed messages.

**Architecture Phase**: Phase 3 - Async Intelligence Architecture
**Status**: Production Ready
**Version**: 1.0.0

## Features

### Core Functionality
- ✅ **Kafka Consumer**: Consumes enrichment events from `dev.archon-intelligence.enrich-document.v1`
- ✅ **Intelligence Service Integration**: Processes documents through intelligence service
- ✅ **Completion Events**: Publishes success/failure events to completion topic
- ✅ **Manual Offset Management**: Commits offsets only after successful processing

### Reliability Features
- ✅ **Retry Logic**: Exponential backoff (2s → 4s → 8s) with 3 retry attempts
- ✅ **Dead Letter Queue**: Routes failed messages to DLQ after exhausting retries
- ✅ **Circuit Breaker**: Protects intelligence service from cascading failures
- ✅ **Graceful Shutdown**: Waits for in-flight processing before shutdown

### Observability
- ✅ **Health Checks**: HTTP endpoints for liveness and readiness probes
- ✅ **Metrics**: Consumer lag, error stats, circuit breaker state
- ✅ **Structured Logging**: JSON logs with correlation IDs
- ✅ **Error Classification**: Non-retryable errors skip retry and route to DLQ

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Kafka Event Bus                       │
│                 (Redpanda/Kafka)                         │
└──────────┬────────────────────────────────────┬──────────┘
           │                                    │
           │ Enrichment Topic                   │ DLQ Topic
           │ (enrich-document.v1)              │ (enrich-document-dlq.v1)
           ↓                                    ↑
┌──────────────────────────────────────────────┼──────────┐
│  Intelligence Consumer Service               │          │
│  ┌───────────────────────────────────────────┼────────┐ │
│  │  Consumer Loop                            │        │ │
│  │  - Consumes messages                      │        │ │
│  │  - Concurrency control (5 concurrent)     │        │ │
│  │  - Manual offset commit                   │        │ │
│  └───────────────────────┬───────────────────┼────────┘ │
│                          ↓                   │          │
│  ┌───────────────────────────────────────────┼────────┐ │
│  │  Message Processor                        │        │ │
│  │  - Validates payload                      │        │ │
│  │  - Calls intelligence service             │        │ │
│  │  - Publishes completion event             │        │ │
│  └───────────────────────┬───────────────────┼────────┘ │
│                          ↓                   │          │
│  ┌───────────────────────────────────────────┼────────┐ │
│  │  Error Handler                            │        │ │
│  │  - Classifies errors (retryable/not)      │        │ │
│  │  - Exponential backoff retry              │        │ │
│  │  - DLQ routing after max retries ─────────┘        │ │
│  └───────────────────────┬──────────────────────────┘ │
└────────────────────────────┼──────────────────────────┘
                            ↓
              ┌─────────────────────────────┐
              │  Intelligence Service        │
              │  (archon-intelligence:8053)  │
              │  - Document processing       │
              │  - Entity extraction         │
              │  - Quality analysis          │
              └─────────────────────────────┘
                            ↓
              ┌─────────────────────────────┐
              │  Memgraph                    │
              │  (Knowledge Graph)           │
              │  - Entity storage            │
              │  - Relationship tracking     │
              └─────────────────────────────┘
```

## Topics

### Input Topics
- **Enrichment Requests**: `dev.archon-intelligence.enrich-document.v1`
  - Contains document path, content, and project metadata
  - Processed with concurrency limit (default: 5)

### Output Topics
- **Completion Events**: `dev.archon-intelligence.enrich-document-completed.v1`
  - Success/failure status
  - Intelligence data (if successful)
  - Error message (if failed)

- **Dead Letter Queue**: `dev.archon-intelligence.enrich-document-dlq.v1`
  - Failed messages after retry exhaustion
  - Includes error details, retry history, failure reason

## Configuration

### Environment Variables

#### Kafka Configuration
```bash
KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092  # Kafka brokers
KAFKA_TOPIC_PREFIX=dev.archon-intelligence            # Topic prefix
KAFKA_CONSUMER_GROUP=archon-intelligence-consumer-group
KAFKA_AUTO_OFFSET_RESET=earliest                      # earliest or latest
KAFKA_MAX_POLL_RECORDS=10                             # Batch size
KAFKA_ENABLE_AUTO_COMMIT=false                        # Manual commit
```

#### Intelligence Service Configuration
```bash
INTELLIGENCE_SERVICE_URL=http://archon-intelligence:8053
INTELLIGENCE_TIMEOUT=60                               # Seconds
```

#### Memgraph Configuration
```bash
MEMGRAPH_URI=bolt://memgraph:7687
MEMGRAPH_USERNAME=                                    # Optional
MEMGRAPH_PASSWORD=                                    # Optional
```

#### Retry Configuration
```bash
MAX_RETRY_ATTEMPTS=3                                  # Retry attempts
RETRY_BACKOFF_BASE=2                                  # Backoff base (seconds)
RETRY_BACKOFF_MAX=60                                  # Max backoff (seconds)
```

#### Circuit Breaker Configuration
```bash
CIRCUIT_BREAKER_THRESHOLD=5                           # Failures to open circuit
CIRCUIT_BREAKER_TIMEOUT=30                            # Seconds before half-open
CIRCUIT_BREAKER_SUCCESS_THRESHOLD=3                   # Successes to close circuit
```

#### Health Check Configuration
```bash
HEALTH_CHECK_PORT=8080                                # Health endpoint port
```

#### Logging Configuration
```bash
LOG_LEVEL=INFO                                        # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=json                                       # json or console
```

#### Performance Configuration
```bash
PROCESSING_CONCURRENCY=5                              # Concurrent processors
SHUTDOWN_TIMEOUT=30                                   # Graceful shutdown (seconds)
```

## Health Endpoints

### Liveness Probe
```bash
GET /health
```

Returns 200 if service is alive:
```json
{
  "status": "healthy",
  "service": "intelligence-consumer",
  "uptime_seconds": 3600.5,
  "timestamp": "2025-10-30T16:30:00Z"
}
```

### Readiness Probe
```bash
GET /ready
```

Returns 200 if ready to process messages, 503 otherwise:
```json
{
  "ready": true,
  "checks": {
    "consumer": true,
    "intelligence_service": true,
    "circuit_breaker": {
      "healthy": true,
      "state": "closed"
    }
  },
  "timestamp": "2025-10-30T16:30:00Z"
}
```

### Metrics
```bash
GET /metrics
```

Returns consumer metrics:
```json
{
  "service": "intelligence-consumer",
  "uptime_seconds": 3600.5,
  "consumer": {
    "lag_by_partition": {
      "0": 5,
      "1": 3
    },
    "total_lag": 8,
    "partition_count": 2
  },
  "errors": {
    "active_retries": 2,
    "retry_states": {
      "correlation-id-1": 1,
      "correlation-id-2": 2
    }
  },
  "circuit_breaker": {
    "state": "closed"
  },
  "timestamp": "2025-10-30T16:30:00Z"
}
```

## Running Locally

### With Docker Compose

```bash
# Start service (from deployment directory)
cd deployment
docker compose up archon-intelligence-consumer -d

# View logs
docker compose logs -f archon-intelligence-consumer

# Check health
curl http://localhost:8060/health
curl http://localhost:8060/ready
curl http://localhost:8060/metrics
```

### With Poetry

```bash
# Install dependencies
cd services/intelligence-consumer
poetry install

# Set environment variables
export KAFKA_BOOTSTRAP_SERVERS=192.168.86.200:29092  # Host access uses external port
export INTELLIGENCE_SERVICE_URL=http://localhost:8053
export MEMGRAPH_URI=bolt://localhost:7687

# Run service
poetry run intelligence-consumer
```

## Error Handling

### Retry Strategy

1. **First attempt fails** → Wait 2s → Retry (attempt 2)
2. **Second attempt fails** → Wait 4s → Retry (attempt 3)
3. **Third attempt fails** → Wait 8s → Retry (attempt 4)
4. **Fourth attempt fails** → Route to DLQ

### Circuit Breaker States

```
CLOSED (normal) ──[5 failures]──> OPEN (rejecting)
                                    │
                    [30s timeout]   │
                                    ↓
CLOSED <──[3 successes]── HALF_OPEN (testing)
```

### Non-Retryable Errors

These errors skip retry and route directly to DLQ:
- `ValueError` - Invalid input data
- `KeyError` - Missing required fields
- `JSONDecodeError` - Malformed JSON
- `ValidationError` - Schema validation failed

### DLQ Event Structure

```json
{
  "event_type": "enrichment_failed",
  "failure_timestamp": "2025-10-30T16:30:00Z",
  "failure_reason": "Intelligence service timeout",
  "failure_type": "TimeoutError",
  "retry_count": 3,
  "original_event": { /* original enrichment event */ },
  "error_details": {
    "error_message": "Request timed out after 60 seconds",
    "error_type": "TimeoutError",
    "retry_history": [
      {"attempt": 1, "backoff_seconds": 2},
      {"attempt": 2, "backoff_seconds": 4},
      {"attempt": 3, "backoff_seconds": 8}
    ],
    "final_retry_count": 3
  }
}
```

## Development

### Project Structure

```
services/intelligence-consumer/
├── src/
│   ├── __init__.py           # Package initialization
│   ├── main.py               # Entry point, graceful shutdown
│   ├── config.py             # Configuration management
│   ├── consumer.py           # Kafka consumer logic
│   ├── enrichment.py         # Intelligence service client
│   ├── error_handler.py      # Retry logic, DLQ routing
│   └── health.py             # Health check endpoints
├── Dockerfile                # Container image
├── pyproject.toml            # Dependencies
└── README.md                 # This file
```

### Running Tests

```bash
# Run tests
poetry run pytest tests/ -v

# With coverage
poetry run pytest tests/ --cov=src --cov-report=html
```

## Monitoring

### Key Metrics to Monitor

1. **Consumer Lag**: Total lag across partitions
   - Alert if lag > 100 for 5 minutes
   - Critical if lag > 500

2. **Active Retries**: Number of messages in retry state
   - Alert if active retries > 10
   - Investigate if consistently high

3. **Circuit Breaker State**: Should be "closed" in normal operation
   - Alert immediately if "open"
   - Indicates intelligence service issues

4. **DLQ Rate**: Messages routed to DLQ
   - Track trend over time
   - Investigate sudden spikes

### Log Examples

**Successful Processing**:
```json
{
  "event": "message_processed_successfully",
  "correlation_id": "abc123",
  "file_path": "/path/to/file.py",
  "timestamp": "2025-10-30T16:30:00Z"
}
```

**Retry Attempt**:
```json
{
  "event": "retrying_after_delay",
  "correlation_id": "abc123",
  "retry_count": 1,
  "delay_seconds": 2,
  "attempt": 2,
  "timestamp": "2025-10-30T16:30:00Z"
}
```

**DLQ Routing**:
```json
{
  "event": "routing_to_dlq",
  "correlation_id": "abc123",
  "retry_count": 3,
  "error_type": "TimeoutError",
  "timestamp": "2025-10-30T16:30:00Z"
}
```

## Troubleshooting

### Service Won't Start

**Symptoms**: Container exits immediately

**Check**:
1. Kafka connectivity: `nc -zv omninode-bridge-redpanda 9092`
2. Environment variables: `docker compose config | grep KAFKA_`
3. Container logs: `docker compose logs archon-intelligence-consumer`

### High Consumer Lag

**Symptoms**: Lag > 100 and growing

**Solutions**:
1. Increase concurrency: `PROCESSING_CONCURRENCY=10`
2. Check intelligence service performance
3. Scale horizontally (multiple consumer instances)

### Circuit Breaker Open

**Symptoms**: All requests failing, circuit state "open"

**Solutions**:
1. Check intelligence service health: `curl http://archon-intelligence:8053/health`
2. Review intelligence service logs
3. Wait for circuit timeout (30s) to attempt recovery

### Messages in DLQ

**Symptoms**: DLQ topic has messages

**Investigation**:
1. Consume DLQ messages: `rpk topic consume dev.archon-intelligence.enrich-document-dlq.v1`
2. Check `failure_reason` and `error_details`
3. Fix underlying issue (data validation, service configuration)
4. Reprocess DLQ messages manually if needed

## Performance

### Throughput

- **Target**: 100 messages/second
- **Actual**: ~50-80 messages/second (depends on intelligence service latency)
- **Bottleneck**: Intelligence service processing time (~500-1000ms per document)

### Resource Usage

- **Memory**: 128-256 MB (typical), 512 MB (limit)
- **CPU**: 0.1-0.3 cores (typical), 0.5 cores (limit)
- **Network**: ~1-5 MB/s (depends on document size)

## Related Documentation

- **Async Architecture**: `docs/ASYNC_INTELLIGENCE_ARCHITECTURE.md`
- **Event Schemas**: Phase 1.2 output (event schema definitions)
- **Bridge Service**: `services/bridge/README.md` (event producer)
- **Intelligence Service**: `services/intelligence/README.md`

## Changelog

### Version 1.0.0 (2025-10-30)

Initial release:
- Kafka consumer with manual offset management
- Intelligence service integration with circuit breaker
- Exponential backoff retry logic (3 attempts)
- Dead letter queue routing
- Health check endpoints (liveness, readiness, metrics)
- Graceful shutdown handling
- Structured logging with correlation IDs
- Error classification (retryable/non-retryable)
