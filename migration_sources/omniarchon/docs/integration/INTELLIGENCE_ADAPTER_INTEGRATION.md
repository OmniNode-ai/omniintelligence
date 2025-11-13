# Intelligence Adapter Integration Guide

**Version**: 1.0.0
**Last Updated**: 2025-10-21
**Status**: Production Ready ✅

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Container Configuration](#container-configuration)
6. [Kafka Topics Setup](#kafka-topics-setup)
7. [Environment Variables](#environment-variables)
8. [Basic Integration](#basic-integration)
9. [Event-Driven Integration](#event-driven-integration)
10. [Deployment Guide](#deployment-guide)
11. [Monitoring](#monitoring)
12. [Troubleshooting](#troubleshooting)

---

## Overview

The Intelligence Adapter Effect Node provides omniarchon applications with access to the Archon Intelligence Service for code quality analysis, performance optimization, and ONEX compliance validation.

**What You Get**:
- Strongly-typed Python API for intelligence operations
- Automatic retry, circuit breaker, and error handling
- Event-driven Kafka integration for asynchronous workflows
- Comprehensive security validation
- Performance monitoring and metrics
- Production-ready resilience patterns

---

## Prerequisites

### Required Services

1. **Archon Intelligence Service**
   - Running at `http://localhost:8053` (or configured URL)
   - Health endpoint: `http://localhost:8053/health`

2. **ONEX Container** (omnibase_core)
   - Installed via `pip install omnibase-core` or Poetry
   - Version: ≥1.0.0

3. **Kafka** (for event-driven workflows)
   - Broker: `localhost:9092` (or configured broker)
   - Topics: Pre-created (see [Kafka Topics Setup](#kafka-topics-setup))

### Optional Services

1. **Valkey/Redis** (for caching)
   - URL: `redis://localhost:6379` (configured via Intelligence Service)

---

## Installation

### Step 1: Install Dependencies

```bash
# Navigate to python directory
cd python

# Install with Poetry
poetry install

# Or with pip
pip install -e .
```

### Step 2: Verify Installation

```bash
# Test imports
poetry run python -c "
from intelligence.nodes import NodeIntelligenceAdapterEffect
from intelligence.models import ModelIntelligenceConfig
from intelligence.security import IntelligenceSecurityValidator
print('✅ Intelligence Adapter installed successfully')
"
```

### Step 3: Verify Intelligence Service

```bash
# Check service health
curl http://localhost:8053/health

# Expected response:
# {"status":"healthy","service_version":"1.0.0","uptime_seconds":...}
```

---

## Configuration

### Configuration File (Recommended)

Create `/config/intelligence-adapter.json`:

```json
{
  "base_url": "http://localhost:8053",
  "timeout_seconds": 30.0,
  "max_retries": 3,
  "retry_delay_ms": 1000,
  "circuit_breaker_enabled": true,
  "circuit_breaker_threshold": 5,
  "circuit_breaker_timeout_seconds": 60.0,
  "enable_event_publishing": true,
  "input_topics": [
    "dev.archon-intelligence.intelligence.code-analysis-requested.v1"
  ],
  "output_topics": {
    "completed": "dev.archon-intelligence.intelligence.code-analysis-completed.v1",
    "failed": "dev.archon-intelligence.intelligence.code-analysis-failed.v1"
  },
  "consumer_group_id": "intelligence-adapter-consumers"
}
```

### Environment-Based Configuration

```python
from intelligence.models import ModelIntelligenceConfig

# Development
config = ModelIntelligenceConfig.for_environment("development")

# Staging
config = ModelIntelligenceConfig.for_environment("staging")

# Production
config = ModelIntelligenceConfig.for_environment("production")
```

### Programmatic Configuration

```python
from intelligence.models import ModelIntelligenceConfig

config = ModelIntelligenceConfig(
    base_url="http://archon-intelligence:8053",
    timeout_seconds=60.0,
    max_retries=5,
    circuit_breaker_enabled=True,
    circuit_breaker_threshold=10,
    circuit_breaker_timeout_seconds=60.0,
)
```

---

## Container Configuration

### ONEX Container Setup

```python
from omnibase_core.models.container.model_onex_container import ModelONEXContainer

# Create container
container = ModelONEXContainer()

# Configure container services (if needed)
# container.register_service("intelligence_client", intelligence_client)
```

### Container Services Used

The Intelligence Adapter retrieves these services from the container:

1. **HTTP Client** (optional): For custom HTTP configuration
2. **Event Bus** (optional): For Kafka event publishing
3. **Logger** (optional): For structured logging

**Note**: If services are not found in the container, the adapter creates default instances.

---

## Kafka Topics Setup

### Topic Naming Convention

```
{environment}.{service}.{domain}.{event}.{version}
```

### Development Topics

```bash
# Create topics (Kafka CLI)
kafka-topics.sh --create \
  --bootstrap-server localhost:9092 \
  --topic dev.archon-intelligence.intelligence.code-analysis-requested.v1 \
  --partitions 3 \
  --replication-factor 1

kafka-topics.sh --create \
  --bootstrap-server localhost:9092 \
  --topic dev.archon-intelligence.intelligence.code-analysis-completed.v1 \
  --partitions 3 \
  --replication-factor 1

kafka-topics.sh --create \
  --bootstrap-server localhost:9092 \
  --topic dev.archon-intelligence.intelligence.code-analysis-failed.v1 \
  --partitions 3 \
  --replication-factor 1
```

### Production Topics

```bash
# Production environment
kafka-topics.sh --create \
  --bootstrap-server kafka-prod:9092 \
  --topic prod.archon-intelligence.intelligence.code-analysis-requested.v1 \
  --partitions 10 \
  --replication-factor 3

kafka-topics.sh --create \
  --bootstrap-server kafka-prod:9092 \
  --topic prod.archon-intelligence.intelligence.code-analysis-completed.v1 \
  --partitions 10 \
  --replication-factor 3

kafka-topics.sh --create \
  --bootstrap-server kafka-prod:9092 \
  --topic prod.archon-intelligence.intelligence.code-analysis-failed.v1 \
  --partitions 10 \
  --replication-factor 3
```

### Verify Topics

```bash
# List all topics
kafka-topics.sh --list --bootstrap-server localhost:9092

# Describe topic
kafka-topics.sh --describe \
  --bootstrap-server localhost:9092 \
  --topic dev.archon-intelligence.intelligence.code-analysis-requested.v1
```

---

## Environment Variables

### Required Variables

```bash
# Intelligence Service URL
INTELLIGENCE_BASE_URL=http://localhost:8053

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
ENVIRONMENT=development
```

### Optional Variables

```bash
# Timeout Settings
INTELLIGENCE_TIMEOUT_SECONDS=30.0

# Retry Configuration
INTELLIGENCE_MAX_RETRIES=3
INTELLIGENCE_RETRY_DELAY_MS=1000

# Circuit Breaker
INTELLIGENCE_CIRCUIT_BREAKER_ENABLED=true
INTELLIGENCE_CIRCUIT_BREAKER_THRESHOLD=5
INTELLIGENCE_CIRCUIT_BREAKER_TIMEOUT_SECONDS=60.0

# Event Publishing
INTELLIGENCE_ENABLE_EVENT_PUBLISHING=true

# Logging
LOG_LEVEL=INFO
```

### Docker Compose Environment

```yaml
services:
  intelligence-adapter:
    image: omniarchon/intelligence-adapter:latest
    environment:
      INTELLIGENCE_BASE_URL: http://archon-intelligence:8053
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092
      ENVIRONMENT: production
      INTELLIGENCE_TIMEOUT_SECONDS: 60.0
      LOG_LEVEL: INFO
    networks:
      - archon-network
```

---

## Basic Integration

### Synchronous API Calls

```python
from omnibase_core.models.container.model_onex_container import ModelONEXContainer
from intelligence.nodes import NodeIntelligenceAdapterEffect
from services.intelligence.onex.contracts import ModelIntelligenceInput

async def analyze_code_quality(source_code: str, file_path: str) -> dict:
    """
    Analyze code quality using Intelligence Adapter.

    Args:
        source_code: Python source code to analyze
        file_path: File path for context

    Returns:
        Dict with quality_score, onex_compliance, issues, recommendations
    """
    # Initialize adapter
    container = ModelONEXContainer()
    adapter = NodeIntelligenceAdapterEffect(container)
    await adapter.initialize()

    try:
        # Create input
        input_data = ModelIntelligenceInput(
            operation_type="assess_code_quality",
            content=source_code,
            source_path=file_path,
            language="python",
            options={"include_recommendations": True},
        )

        # Analyze code
        result = await adapter.analyze_code(input_data)

        # Return results
        return {
            "quality_score": result.quality_score,
            "onex_compliance": result.onex_compliance,
            "complexity": result.complexity_score,
            "issues": result.issues,
            "recommendations": result.recommendations,
            "patterns": result.patterns,
            "processing_time_ms": result.processing_time_ms,
        }

    finally:
        # Cleanup
        await adapter._cleanup_node_resources()


# Usage
if __name__ == "__main__":
    import asyncio

    code = """
    def calculate_sum(numbers: list[int]) -> int:
        total = 0
        for num in numbers:
            total += num
        return total
    """

    result = asyncio.run(analyze_code_quality(code, "src/utils.py"))
    print(f"Quality: {result['quality_score']:.2f}")
    print(f"ONEX: {result['onex_compliance']:.2f}")
```

---

## Event-Driven Integration

### Kafka Producer (Request Events)

```python
from uuid import uuid4
from aiokafka import AIOKafkaProducer
from services.intelligence.src.events.models import (
    create_request_event,
    EnumAnalysisOperationType,
    IntelligenceAdapterEventHelpers,
    EnumCodeAnalysisEventType,
)

async def publish_analysis_request(
    source_path: str,
    content: str,
    language: str,
    kafka_broker: str = "localhost:9092",
) -> str:
    """
    Publish code analysis request to Kafka.

    Returns:
        Correlation ID (str) for tracking
    """
    # Create producer
    producer = AIOKafkaProducer(bootstrap_servers=kafka_broker)
    await producer.start()

    try:
        # Generate correlation ID
        correlation_id = uuid4()

        # Create request event
        request_event = create_request_event(
            source_path=source_path,
            content=content,
            language=language,
            operation_type=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
            correlation_id=correlation_id,
            options={"include_recommendations": True},
        )

        # Get topic
        topic = IntelligenceAdapterEventHelpers.get_kafka_topic(
            EnumCodeAnalysisEventType.CODE_ANALYSIS_REQUESTED
        )

        # Publish event
        await producer.send_and_wait(
            topic,
            value=json.dumps(request_event).encode("utf-8"),
            key=str(correlation_id).encode("utf-8"),
        )

        print(f"✅ Published request: {correlation_id}")
        return str(correlation_id)

    finally:
        await producer.stop()


# Usage
if __name__ == "__main__":
    import asyncio

    correlation_id = asyncio.run(
        publish_analysis_request(
            source_path="src/api/endpoints.py",
            content="def handler(): pass",
            language="python",
        )
    )
    print(f"Track with correlation ID: {correlation_id}")
```

### Kafka Consumer (Result Events)

```python
from aiokafka import AIOKafkaConsumer
from services.intelligence.src.events.models import (
    IntelligenceAdapterEventHelpers,
    EnumCodeAnalysisEventType,
)
import json

async def consume_analysis_results(
    kafka_broker: str = "localhost:9092",
    consumer_group: str = "results-consumers",
):
    """
    Consume code analysis results from Kafka.
    """
    # Get topics
    completed_topic = IntelligenceAdapterEventHelpers.get_kafka_topic(
        EnumCodeAnalysisEventType.CODE_ANALYSIS_COMPLETED
    )
    failed_topic = IntelligenceAdapterEventHelpers.get_kafka_topic(
        EnumCodeAnalysisEventType.CODE_ANALYSIS_FAILED
    )

    # Create consumer
    consumer = AIOKafkaConsumer(
        completed_topic,
        failed_topic,
        bootstrap_servers=kafka_broker,
        group_id=consumer_group,
        auto_offset_reset="earliest",
    )
    await consumer.start()

    try:
        async for message in consumer:
            # Parse event
            event_envelope = json.loads(message.value.decode("utf-8"))

            # Deserialize event
            event_type, payload = IntelligenceAdapterEventHelpers.deserialize_event(
                event_envelope
            )

            # Handle by event type
            if event_type == EnumCodeAnalysisEventType.CODE_ANALYSIS_COMPLETED.value:
                print(f"✅ Analysis completed:")
                print(f"   Quality: {payload.quality_score:.2f}")
                print(f"   ONEX: {payload.onex_compliance:.2f}")
                print(f"   Correlation: {event_envelope['correlation_id']}")

            elif event_type == EnumCodeAnalysisEventType.CODE_ANALYSIS_FAILED.value:
                print(f"❌ Analysis failed:")
                print(f"   Error: {payload.error_message}")
                print(f"   Retry: {payload.retry_allowed}")
                print(f"   Correlation: {event_envelope['correlation_id']}")

            # Commit offset
            await consumer.commit()

    finally:
        await consumer.stop()


# Usage
if __name__ == "__main__":
    import asyncio

    asyncio.run(consume_analysis_results())
```

---

## Deployment Guide

### Docker Deployment

**Dockerfile**:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry install --no-dev

# Copy application
COPY python/src /app/src

# Set environment
ENV PYTHONPATH=/app/src
ENV LOG_LEVEL=INFO

# Run adapter
CMD ["poetry", "run", "python", "-m", "intelligence.adapter.main"]
```

**docker-compose.yml**:

```yaml
version: "3.9"

services:
  intelligence-adapter:
    build: .
    environment:
      INTELLIGENCE_BASE_URL: http://archon-intelligence:8053
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092
      ENVIRONMENT: production
      INTELLIGENCE_CIRCUIT_BREAKER_THRESHOLD: 10
      LOG_LEVEL: INFO
    depends_on:
      - archon-intelligence
      - kafka
    networks:
      - archon-network
    restart: unless-stopped

  archon-intelligence:
    image: archon/intelligence:latest
    ports:
      - "8053:8053"
    networks:
      - archon-network

  kafka:
    image: confluentinc/cp-kafka:latest
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
    networks:
      - archon-network

networks:
  archon-network:
    driver: bridge
```

### Kubernetes Deployment

**deployment.yaml**:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: intelligence-adapter
  namespace: archon
spec:
  replicas: 3
  selector:
    matchLabels:
      app: intelligence-adapter
  template:
    metadata:
      labels:
        app: intelligence-adapter
    spec:
      containers:
        - name: adapter
          image: omniarchon/intelligence-adapter:1.0.0
          env:
            - name: INTELLIGENCE_BASE_URL
              value: "http://archon-intelligence-service:8053"
            - name: KAFKA_BOOTSTRAP_SERVERS
              value: "kafka-service:9092"
            - name: ENVIRONMENT
              value: "production"
            - name: LOG_LEVEL
              value: "INFO"
          resources:
            requests:
              memory: "256Mi"
              cpu: "200m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 5
```

---

## Monitoring

### Health Checks

```python
# Check adapter health
stats = adapter.get_analysis_stats()

if stats['circuit_breaker_state'] == 'open':
    print("⚠️ Circuit breaker is open - service degraded")

if stats['success_rate'] < 0.95:
    print(f"⚠️ Low success rate: {stats['success_rate']:.1%}")
```

### Prometheus Metrics (Future)

```python
# Example metrics to expose
from prometheus_client import Counter, Histogram, Gauge

# Counters
analysis_requests_total = Counter(
    "intelligence_adapter_requests_total",
    "Total analysis requests",
    ["operation_type", "status"],
)

# Histograms
analysis_duration_seconds = Histogram(
    "intelligence_adapter_duration_seconds",
    "Analysis duration in seconds",
    ["operation_type"],
)

# Gauges
circuit_breaker_state = Gauge(
    "intelligence_adapter_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
)
```

---

## Troubleshooting

### Issue 1: Connection Refused

**Error**: `ConnectionRefusedError: [Errno 61] Connection refused`

**Solution**:
```bash
# Verify Intelligence Service is running
curl http://localhost:8053/health

# Check Docker network
docker network inspect archon-network

# Verify environment variable
echo $INTELLIGENCE_BASE_URL
```

### Issue 2: Circuit Breaker Opens

**Error**: `Circuit breaker is OPEN`

**Solution**:
```python
# Check circuit breaker state
stats = adapter.get_analysis_stats()
print(f"Circuit breaker: {stats['circuit_breaker_state']}")

# Wait for recovery timeout (default: 60s)
# Or increase threshold
config.circuit_breaker_threshold = 10
```

### Issue 3: Kafka Connection Failed

**Error**: `KafkaConnectionError`

**Solution**:
```bash
# Verify Kafka broker
nc -zv localhost 9092

# Check topic exists
kafka-topics.sh --list --bootstrap-server localhost:9092

# Verify consumer group
kafka-consumer-groups.sh --list --bootstrap-server localhost:9092
```

---

## See Also

- [Node README](../../python/src/intelligence/nodes/README.md)
- [Event Schemas](../../services/intelligence/docs/INTELLIGENCE_ADAPTER_EVENTS.md)
- [Security Validation](../../python/src/intelligence/security/intelligence_security_validator.py)
- [Configuration Guide](../../python/src/intelligence/models/model_intelligence_config.py)

---

**Status**: Production Ready ✅
**Support**: Archon Intelligence Team
**Last Updated**: 2025-10-21
