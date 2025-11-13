# Kafka Configuration for Intelligence Service

**Status**: MVP Day 3 - Docker & Environment Configuration Complete
**Version**: 1.0.0
**Last Updated**: 2025-10-15

## Overview

This document covers Kafka configuration for the Intelligence Service's event-driven handlers. The service consumes codegen events from Redpanda and publishes intelligent responses.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Docker Networks                          │
├──────────────────────────────────────────────────────────────┤
│  app-network              │ Internal Archon services        │
│  omninode-bridge-network  │ PostgreSQL traceability DB      │
│  omninode_bridge_         │ Redpanda Kafka cluster          │
│    omninode-bridge-network│                                  │
└──────────────────────────────────────────────────────────────┘
                                    ↓
┌──────────────────────────────────────────────────────────────┐
│              Intelligence Service (archon-intelligence)      │
├──────────────────────────────────────────────────────────────┤
│  Kafka Consumer                                              │
│  ├── Validate Handler  → omninode.codegen.request.validate.v1│
│  ├── Analyze Handler   → omninode.codegen.request.analyze.v1 │
│  ├── Pattern Handler   → omninode.codegen.request.pattern.v1 │
│  └── Mixin Handler     → omninode.codegen.request.mixin.v1   │
│                                                               │
│  Response Publisher (BaseResponsePublisher)                   │
│  ├── Validate Response → omninode.codegen.response.validate.v1│
│  ├── Analyze Response  → omninode.codegen.response.analyze.v1│
│  ├── Pattern Response  → omninode.codegen.response.pattern.v1│
│  └── Mixin Response    → omninode.codegen.response.mixin.v1  │
└──────────────────────────────────────────────────────────────┘
                                    ↓
┌──────────────────────────────────────────────────────────────┐
│                 Redpanda Kafka Cluster                       │
│  (omninode-bridge-redpanda:9092)                             │
└──────────────────────────────────────────────────────────────┘
```

## Environment Variables

### Connection Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `omninode-bridge-redpanda:9092` | Kafka bootstrap servers (Docker) |
| `KAFKA_CONSUMER_GROUP` | `archon-intelligence` | Consumer group ID |

**Docker vs Local**:
- **Docker**: `omninode-bridge-redpanda:9092` (internal network)
- **Local development**: `localhost:19092` (exposed port)

### Consumer Behavior

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_AUTO_OFFSET_RESET` | `earliest` | Where to start consuming (`earliest` or `latest`) |
| `KAFKA_ENABLE_AUTO_COMMIT` | `true` | Enable automatic offset commits |
| `KAFKA_MAX_POLL_RECORDS` | `500` | Maximum records per poll (1-10000) |
| `KAFKA_SESSION_TIMEOUT_MS` | `30000` | Consumer session timeout (1000-300000ms) |

**Best Practices**:
- **`earliest`**: Start from oldest message (for handlers that must process all events)
- **`latest`**: Start from newest message (for real-time monitoring)
- **Auto-commit**: Simplifies offset management but may cause duplicates on failure
- **Max poll records**: Balance throughput vs memory usage

### Request Topics

| Variable | Default | Handler |
|----------|---------|---------|
| `KAFKA_CODEGEN_VALIDATE_REQUEST` | `omninode.codegen.request.validate.v1` | Validate Handler |
| `KAFKA_CODEGEN_ANALYZE_REQUEST` | `omninode.codegen.request.analyze.v1` | Analyze Handler |
| `KAFKA_CODEGEN_PATTERN_REQUEST` | `omninode.codegen.request.pattern.v1` | Pattern Handler |
| `KAFKA_CODEGEN_MIXIN_REQUEST` | `omninode.codegen.request.mixin.v1` | Mixin Handler |

### Response Topics

| Variable | Default | Publisher |
|----------|---------|-----------|
| `KAFKA_CODEGEN_VALIDATE_RESPONSE` | `omninode.codegen.response.validate.v1` | BaseResponsePublisher |
| `KAFKA_CODEGEN_ANALYZE_RESPONSE` | `omninode.codegen.response.analyze.v1` | BaseResponsePublisher |
| `KAFKA_CODEGEN_PATTERN_RESPONSE` | `omninode.codegen.response.pattern.v1` | BaseResponsePublisher |
| `KAFKA_CODEGEN_MIXIN_RESPONSE` | `omninode.codegen.response.mixin.v1` | BaseResponsePublisher |

## Docker Compose Configuration

### Networks

The intelligence service connects to three Docker networks:

```yaml
networks:
  - app-network                              # Internal Archon services
  - omninode-bridge-network                  # PostgreSQL traceability DB
  - omninode_bridge_omninode-bridge-network  # Redpanda Kafka cluster
```

**Why multiple networks?**
- `app-network`: Communication with other Archon services (memgraph, bridge, search)
- `omninode-bridge-network`: Access to PostgreSQL for pattern traceability
- `omninode_bridge_omninode-bridge-network`: Access to Redpanda for event streaming

### Environment Variables in Docker Compose

All Kafka configuration is passed via environment variables with sensible defaults:

```yaml
environment:
  # Kafka Connection
  - KAFKA_BOOTSTRAP_SERVERS=${KAFKA_BOOTSTRAP_SERVERS:-omninode-bridge-redpanda:9092}
  - KAFKA_CONSUMER_GROUP=${KAFKA_CONSUMER_GROUP:-archon-intelligence}

  # Consumer Behavior
  - KAFKA_AUTO_OFFSET_RESET=${KAFKA_AUTO_OFFSET_RESET:-earliest}
  - KAFKA_ENABLE_AUTO_COMMIT=${KAFKA_ENABLE_AUTO_COMMIT:-true}
  - KAFKA_MAX_POLL_RECORDS=${KAFKA_MAX_POLL_RECORDS:-500}
  - KAFKA_SESSION_TIMEOUT_MS=${KAFKA_SESSION_TIMEOUT_MS:-30000}

  # Request Topics
  - KAFKA_CODEGEN_VALIDATE_REQUEST=${KAFKA_CODEGEN_VALIDATE_REQUEST:-omninode.codegen.request.validate.v1}
  - KAFKA_CODEGEN_ANALYZE_REQUEST=${KAFKA_CODEGEN_ANALYZE_REQUEST:-omninode.codegen.request.analyze.v1}
  - KAFKA_CODEGEN_PATTERN_REQUEST=${KAFKA_CODEGEN_PATTERN_REQUEST:-omninode.codegen.request.pattern.v1}
  - KAFKA_CODEGEN_MIXIN_REQUEST=${KAFKA_CODEGEN_MIXIN_REQUEST:-omninode.codegen.request.mixin.v1}

  # Response Topics
  - KAFKA_CODEGEN_VALIDATE_RESPONSE=${KAFKA_CODEGEN_VALIDATE_RESPONSE:-omninode.codegen.response.validate.v1}
  - KAFKA_CODEGEN_ANALYZE_RESPONSE=${KAFKA_CODEGEN_ANALYZE_RESPONSE:-omninode.codegen.response.analyze.v1}
  - KAFKA_CODEGEN_PATTERN_RESPONSE=${KAFKA_CODEGEN_PATTERN_RESPONSE:-omninode.codegen.response.pattern.v1}
  - KAFKA_CODEGEN_MIXIN_RESPONSE=${KAFKA_CODEGEN_MIXIN_RESPONSE:-omninode.codegen.response.mixin.v1}
```

### Overriding Defaults

Create a `.env` file in the project root to override defaults:

```bash
# .env (project root)
KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092
KAFKA_CONSUMER_GROUP=archon-intelligence-dev
KAFKA_MAX_POLL_RECORDS=1000
```

## Configuration Module Usage

### Loading Configuration

```python
from src.config import get_kafka_config

# Load configuration from environment
config = get_kafka_config()

# Access configuration
print(config.bootstrap_servers)  # "omninode-bridge-redpanda:9092"
print(config.topics.validate_request)  # "omninode.codegen.request.validate.v1"
print(config.consumer.group_id)  # "archon-intelligence"
```

### Converting to AIOKafkaConsumer Config

```python
from src.config import get_kafka_config

config = get_kafka_config()

# Convert to aiokafka consumer config
consumer_config = config.to_consumer_config()

# Use with AIOKafkaConsumer
from aiokafka import AIOKafkaConsumer

consumer = AIOKafkaConsumer(
    config.topics.validate_request,
    config.topics.analyze_request,
    **consumer_config
)
```

### Testing with Custom Configuration

```python
import os
from src.config import reset_kafka_config, get_kafka_config

# Set test environment variables
os.environ['KAFKA_BOOTSTRAP_SERVERS'] = 'localhost:19092'
os.environ['KAFKA_CONSUMER_GROUP'] = 'test-consumer'

# Reset global config to reload from environment
reset_kafka_config()

# Get fresh config
config = get_kafka_config()
assert config.bootstrap_servers == 'localhost:19092'
```

## Docker Networking Setup

### Verifying Network Connectivity

Check if the intelligence service can reach Redpanda:

```bash
# Enter intelligence service container
docker exec -it archon-intelligence bash

# Test Redpanda connectivity
telnet omninode-bridge-redpanda 9092

# Alternative: Use curl to check if port is open
timeout 5 bash -c "</dev/tcp/omninode-bridge-redpanda/9092" && echo "Connected" || echo "Failed"
```

### Troubleshooting Network Issues

**Problem**: `Cannot connect to Kafka broker`

**Solutions**:
1. Verify Redpanda is running:
   ```bash
   docker ps | grep redpanda
   ```

2. Check network exists:
   ```bash
   docker network ls | grep omninode-bridge
   ```

3. Verify intelligence service is on the network:
   ```bash
   docker network inspect omninode_bridge_omninode-bridge-network
   ```

4. Check for firewall or security group rules blocking port 9092

**Problem**: `Connection refused to localhost:19092`

**Solution**: This error occurs when using local development settings inside Docker. Use `omninode-bridge-redpanda:9092` for Docker environments.

## Connection Troubleshooting

### Health Checks

#### Check Kafka Connection

```python
from src.config import get_kafka_config
from aiokafka import AIOKafkaProducer
import asyncio

async def check_kafka_connection():
    config = get_kafka_config()

    try:
        producer = AIOKafkaProducer(
            bootstrap_servers=config.bootstrap_servers
        )
        await producer.start()
        print(f"✅ Connected to Kafka: {config.bootstrap_servers}")
        await producer.stop()
        return True
    except Exception as e:
        print(f"❌ Failed to connect to Kafka: {e}")
        return False

# Run check
asyncio.run(check_kafka_connection())
```

#### Check Topic Availability

```bash
# List all topics from within container
docker exec archon-intelligence python -c "
from aiokafka.admin import AIOKafkaAdminClient
import asyncio

async def list_topics():
    client = AIOKafkaAdminClient(
        bootstrap_servers='omninode-bridge-redpanda:9092'
    )
    await client.start()
    topics = await client.list_topics()
    print('Available topics:', topics)
    await client.close()

asyncio.run(list_topics())
"
```

### Common Issues

#### Issue: Consumer Not Receiving Messages

**Diagnosis**:
```python
from src.config import get_kafka_config
from aiokafka import AIOKafkaConsumer
import asyncio

async def diagnose_consumer():
    config = get_kafka_config()

    consumer = AIOKafkaConsumer(
        config.topics.validate_request,
        **config.to_consumer_config()
    )

    await consumer.start()

    # Check subscription
    print(f"Subscribed topics: {consumer.subscription()}")

    # Check partitions
    partitions = consumer.assignment()
    print(f"Assigned partitions: {partitions}")

    # Check offsets
    for partition in partitions:
        position = await consumer.position(partition)
        print(f"Partition {partition}: offset {position}")

    await consumer.stop()

asyncio.run(diagnose_consumer())
```

**Solutions**:
1. Verify topic exists in Redpanda
2. Check consumer group offset reset setting
3. Ensure messages are being produced to the topic
4. Check for consumer lag

#### Issue: High Consumer Lag

**Diagnosis**:
```bash
# Check consumer group lag
docker exec omninode-bridge-redpanda \
  rpk group describe archon-intelligence
```

**Solutions**:
1. Increase `KAFKA_MAX_POLL_RECORDS` for higher throughput
2. Optimize message processing logic
3. Scale horizontally by adding more consumer instances
4. Check for bottlenecks in downstream processing

#### Issue: Duplicate Message Processing

**Cause**: Auto-commit with processing failures

**Solutions**:
1. Set `KAFKA_ENABLE_AUTO_COMMIT=false`
2. Manually commit offsets after successful processing
3. Implement idempotent message handlers
4. Use transactional processing for critical workflows

## Performance Tuning

### Consumer Configuration Recommendations

| Use Case | `auto_offset_reset` | `max_poll_records` | `session_timeout_ms` |
|----------|---------------------|---------------------|---------------------|
| Real-time processing | `latest` | 100-500 | 30000 |
| Batch processing | `earliest` | 1000-5000 | 60000 |
| Critical handlers | `earliest` | 100 | 30000 |
| High-throughput | `latest` | 5000 | 45000 |

### Monitoring Metrics

Track these metrics for optimal performance:

- **Consumer Lag**: Time behind latest message
- **Processing Time**: Time to handle each message
- **Throughput**: Messages processed per second
- **Error Rate**: Failed message processing rate
- **Offset Commit Rate**: Successful offset commits

### Optimization Strategies

1. **Parallel Processing**: Process multiple messages concurrently within poll batch
2. **Batch Commits**: Commit offsets in batches rather than per-message
3. **Async I/O**: Use async operations for downstream service calls
4. **Circuit Breakers**: Fail fast on downstream service issues
5. **Backpressure**: Throttle consumption when system is overloaded

## Security Considerations

### Network Isolation

- Redpanda runs on isolated Docker network (`omninode_bridge_omninode-bridge-network`)
- Only services explicitly connected can access Kafka
- No external port exposure for production deployments

### Authentication (Future)

When SASL/SSL is enabled:

```python
# Future configuration with authentication
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=SCRAM-SHA-256
KAFKA_SASL_USERNAME=archon-intelligence
KAFKA_SASL_PASSWORD=<secure_password>
KAFKA_SSL_CA_LOCATION=/etc/kafka/ca.pem
```

### Message Encryption (Future)

- Enable SSL/TLS for in-transit encryption
- Implement message-level encryption for sensitive data
- Use Kafka ACLs to restrict topic access

## Development Workflow

### Local Development Setup

1. **Start Redpanda**:
   ```bash
   docker compose -f /path/to/omninode-bridge/docker-compose.yml up -d redpanda
   ```

2. **Export local environment**:
   ```bash
   export KAFKA_BOOTSTRAP_SERVERS=localhost:19092
   export KAFKA_CONSUMER_GROUP=archon-intelligence-dev
   ```

3. **Run intelligence service locally**:
   ```bash
   cd services/intelligence
   poetry run python -m src.main
   ```

### Docker Development Setup

1. **Start all services**:
   ```bash
   docker compose up -d
   ```

2. **View intelligence service logs**:
   ```bash
   docker logs -f archon-intelligence
   ```

3. **Test Kafka connectivity**:
   ```bash
   docker exec archon-intelligence python -c "from src.config import get_kafka_config; print(get_kafka_config())"
   ```

## Testing

### Unit Tests

```python
import pytest
from src.config import KafkaConfig, reset_kafka_config

def test_kafka_config_defaults():
    """Test default configuration values."""
    reset_kafka_config()
    config = KafkaConfig.from_env()

    assert config.bootstrap_servers == "omninode-bridge-redpanda:9092"
    assert config.consumer.group_id == "archon-intelligence"
    assert config.topics.validate_request == "omninode.codegen.request.validate.v1"

def test_kafka_config_from_env(monkeypatch):
    """Test configuration loading from environment."""
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    monkeypatch.setenv("KAFKA_CONSUMER_GROUP", "test-group")

    reset_kafka_config()
    config = KafkaConfig.from_env()

    assert config.bootstrap_servers == "localhost:9092"
    assert config.consumer.group_id == "test-group"
```

### Integration Tests

```python
import pytest
from src.config import get_kafka_config
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import asyncio

@pytest.mark.asyncio
async def test_kafka_connection():
    """Test actual connection to Kafka broker."""
    config = get_kafka_config()

    producer = AIOKafkaProducer(
        bootstrap_servers=config.bootstrap_servers
    )

    await producer.start()
    await producer.stop()

    # If no exception raised, connection successful
    assert True

@pytest.mark.asyncio
async def test_topic_publish_consume():
    """Test publishing and consuming messages."""
    config = get_kafka_config()

    # Producer
    producer = AIOKafkaProducer(
        bootstrap_servers=config.bootstrap_servers
    )
    await producer.start()

    # Consumer
    consumer = AIOKafkaConsumer(
        config.topics.validate_request,
        **config.to_consumer_config(),
        auto_offset_reset='earliest'
    )
    await consumer.start()

    # Publish test message
    await producer.send_and_wait(
        config.topics.validate_request,
        b'{"test": "message"}'
    )

    # Consume message
    async for msg in consumer:
        assert msg.value == b'{"test": "message"}'
        break

    await producer.stop()
    await consumer.stop()
```

## References

- **omnibase_core**: Event envelope models (`ModelEventEnvelope`)
- **omninode_bridge**: Publisher base classes (`BaseResponsePublisher`)
- **AIOKafka Documentation**: https://aiokafka.readthedocs.io/
- **Redpanda Documentation**: https://docs.redpanda.com/

## Next Steps

After configuration is complete:

1. **Implement Kafka Consumer**: Create event loop and message handling
2. **Integrate Handlers**: Connect validate/analyze/pattern/mixin handlers
3. **Add Response Publishing**: Use `BaseResponsePublisher` for responses
4. **Testing**: Integration tests with Redpanda
5. **Monitoring**: Add metrics and logging
6. **Deployment**: Production configuration and scaling

---

**Questions or Issues?** Check the troubleshooting section or review integration tests in `tests/handlers/test_integration_handlers.py`.
