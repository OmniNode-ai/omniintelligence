# Kafka Test Infrastructure Setup

**Version**: 1.0.0
**Created**: 2025-10-15 (MVP Phase 4 - Workflow 1)
**Status**: ✅ Complete

Comprehensive guide for Kafka integration testing infrastructure in the Intelligence Service.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Configuration](#configuration)
4. [Test Fixtures](#test-fixtures)
5. [Utilities](#utilities)
6. [Usage Examples](#usage-examples)
7. [Running Tests](#running-tests)
8. [Troubleshooting](#troubleshooting)
9. [Quality Gates](#quality-gates)

---

## Overview

### Purpose

This infrastructure provides comprehensive Kafka integration testing capabilities for the Intelligence Service, supporting:

- **Codegen Intelligence Handlers**: Validation, Analysis, Pattern, Mixin handlers
- **Event-Driven Architecture**: Request/response event flow testing
- **Load Testing**: Concurrent and sustained load testing capabilities
- **E2E Validation**: Correlation ID tracking across event flows

### Components

1. **kafka_test_config.py**: Centralized configuration management
2. **kafka_utils.py**: Connectivity verification and test helpers
3. **conftest.py**: Shared pytest fixtures
4. **pytest.ini**: Test markers and configuration

### Quality Standards

- **QC-001**: ONEX Standards compliance (type safety, error handling)
- **QC-003**: Type safety validation (all utilities fully typed)
- **FV-001**: Lifecycle compliance (proper setup/teardown)

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   Test Execution Layer                  │
│  pytest tests/ --pytest.ini--> conftest.py fixtures     │
└───────────────────────┬─────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│              Kafka Test Infrastructure                  │
├────────────────────┬─────────────────┬──────────────────┤
│  kafka_test_config │  kafka_utils    │  conftest.py     │
│  - Configuration   │  - Connectivity │  - Fixtures      │
│  - Topics          │  - Test helpers │  - Admin client  │
│  - Factory methods │  - Tracking     │  - Producer      │
│                    │                 │  - Consumer      │
└────────────────────┴─────────────────┴──────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│                Redpanda/Kafka Cluster                   │
│  Bootstrap: localhost:19092 (external access)           │
│  Topics: omninode.codegen.*.v1                          │
└─────────────────────────────────────────────────────────┘
```

### Test Flow

1. **Fixture Setup**: `kafka_admin_client` → `kafka_test_topics` → topic creation
2. **Test Execution**: `kafka_producer` → publish events → `kafka_consumer` → consume responses
3. **Verification**: `kafka_utils.track_event_flow()` → correlation ID tracking
4. **Teardown**: Automatic cleanup via fixture scopes

---

## Configuration

### File: `kafka_test_config.py`

Location: `services/intelligence/tests/integration/kafka_test_config.py`

#### Environment Variables

```bash
# Kafka bootstrap servers (Redpanda external port)
export TEST_KAFKA_BOOTSTRAP_SERVERS="localhost:19092"

# Schema registry URL (optional)
export TEST_SCHEMA_REGISTRY_URL="http://localhost:18081"
```

#### Default Configuration

```python
from tests.integration.kafka_test_config import KafkaTestConfig

# Connection settings
bootstrap_servers = KafkaTestConfig.BOOTSTRAP_SERVERS
# => "localhost:19092"

# Consumer group prefix
group_prefix = KafkaTestConfig.CONSUMER_GROUP_PREFIX
# => "archon-intelligence-test"

# Default topics
topics = KafkaTestConfig.DEFAULT_TOPICS
# => {
#   "validation_request": "omninode.codegen.request.validate.v1",
#   "validation_response": "omninode.codegen.response.validate.v1",
#   ...
# }
```

#### Factory Methods

**Consumer Configuration**:
```python
consumer_config = KafkaTestConfig.get_consumer_config("my-group")
# Returns:
# {
#   "bootstrap_servers": "localhost:19092",
#   "group_id": "archon-intelligence-test-my-group",
#   "auto_offset_reset": "earliest",
#   "enable_auto_commit": True,
#   "max_poll_records": 100,
#   "session_timeout_ms": 30000,
#   "heartbeat_interval_ms": 10000,
# }
```

**Producer Configuration**:
```python
producer_config = KafkaTestConfig.get_producer_config()
# Returns:
# {
#   "bootstrap_servers": "localhost:19092",
#   "acks": "all",
#   "retries": 3,
#   "max_in_flight_requests_per_connection": 1,
# }
```

---

## Test Fixtures

### File: `conftest.py` (Kafka Section)

Location: `services/intelligence/tests/conftest.py`

#### Fixture: `kafka_admin_client`

**Scope**: `session` (shared across all tests)

```python
@pytest.fixture(scope="session")
def kafka_admin_client():
    """Kafka admin client for topic management."""
    ...
```

**Usage**:
```python
def test_list_topics(kafka_admin_client):
    topics = kafka_admin_client.list_topics()
    assert len(topics) > 0
```

#### Fixture: `kafka_test_topics`

**Scope**: `session` (created once)
**Dependencies**: `kafka_admin_client`

```python
@pytest.fixture(scope="session")
def kafka_test_topics(kafka_admin_client):
    """Create test topics for Kafka integration tests."""
    ...
```

**Usage**:
```python
def test_topics_exist(kafka_test_topics):
    validation_topic = kafka_test_topics["validation_request"]
    assert validation_topic == "omninode.codegen.request.validate.v1"
```

#### Fixture: `kafka_producer`

**Scope**: `function` (new producer per test)

```python
@pytest.fixture
def kafka_producer():
    """Kafka producer for test events."""
    ...
```

**Usage**:
```python
def test_publish_event(kafka_producer, kafka_test_topics):
    event = {"data": "test", "correlation_id": "abc-123"}
    topic = kafka_test_topics["validation_request"]

    kafka_producer.send(topic, value=event)
    kafka_producer.flush()
```

#### Fixture: `kafka_consumer`

**Scope**: `function` (factory per test)

```python
@pytest.fixture
def kafka_consumer():
    """Kafka consumer factory for test responses."""
    ...
```

**Usage**:
```python
def test_consume_event(kafka_consumer, kafka_test_topics):
    response_topic = kafka_test_topics["validation_response"]

    # Create consumer with factory
    consumer = kafka_consumer([response_topic], "test-group-123")

    # Poll for messages
    messages = consumer.poll(timeout_ms=5000)

    # Cleanup
    consumer.close()
```

#### Fixture: `kafka_connectivity_check`

**Scope**: `function` (checked per test)

```python
@pytest.fixture
def kafka_connectivity_check():
    """Verify Kafka connectivity before tests."""
    ...
```

**Usage**:
```python
@pytest.mark.kafka
def test_kafka_feature(kafka_connectivity_check):
    # Test skipped if Kafka unavailable
    assert kafka_connectivity_check
    # ... test code ...
```

---

## Utilities

### File: `kafka_utils.py`

Location: `services/intelligence/tests/integration/kafka_utils.py`

#### Function: `verify_kafka_connectivity()`

**Purpose**: Quick connectivity check

```python
from tests.integration.kafka_utils import verify_kafka_connectivity

if verify_kafka_connectivity():
    print("Kafka is available")
else:
    print("Kafka is down")
```

#### Function: `wait_for_kafka()`

**Purpose**: Wait for Kafka to become available with exponential backoff

```python
from tests.integration.kafka_utils import wait_for_kafka

if wait_for_kafka(max_retries=10, delay_seconds=2):
    print("Kafka ready")
else:
    print("Kafka failed to start")
```

**Backoff Strategy**:
- Initial delay: 2s
- Each retry: delay *= 1.5
- Example: 2s → 3s → 4.5s → 6.75s → ...

#### Function: `create_test_topics()`

**Purpose**: Create topics programmatically

```python
from tests.integration.kafka_utils import create_test_topics

# Create default topics
create_test_topics()

# Create custom topics
create_test_topics(
    topics=["test.custom.v1"],
    num_partitions=1,
    replication_factor=1
)
```

#### Function: `publish_test_event()`

**Purpose**: Publish event with correlation ID tracking

```python
import asyncio
from tests.integration.kafka_utils import publish_test_event

async def test_publish():
    await publish_test_event(
        producer=kafka_producer,
        topic="omninode.codegen.request.validate.v1",
        event={"code": "class Test: pass"},
        correlation_id="test-123"
    )
```

#### Function: `consume_response()`

**Purpose**: Consume response matching correlation ID

```python
import asyncio
from tests.integration.kafka_utils import consume_response

async def test_consume():
    response = await consume_response(
        consumer=kafka_consumer,
        correlation_id="test-123",
        timeout_seconds=10
    )

    if response:
        assert response["correlation_id"] == "test-123"
```

#### Function: `track_event_flow()`

**Purpose**: Track complete request → response flow

```python
from tests.integration.kafka_utils import track_event_flow

tracking = track_event_flow(
    correlation_id="test-123",
    request_topic="omninode.codegen.request.validate.v1",
    response_topic="omninode.codegen.response.validate.v1",
    timeout_seconds=30
)

assert tracking["request_found"]
assert tracking["response_found"]
assert tracking["duration_ms"] < 1000  # Under 1 second
```

---

## Usage Examples

### Example 1: Basic Event Publishing

```python
import pytest
import json
from uuid import uuid4

@pytest.mark.kafka
@pytest.mark.integration
def test_publish_validation_request(
    kafka_producer,
    kafka_test_topics,
    kafka_connectivity_check
):
    """Test publishing codegen validation request."""

    # Ensure Kafka is available
    assert kafka_connectivity_check

    # Create test event
    correlation_id = str(uuid4())
    event = {
        "correlation_id": correlation_id,
        "event_type": "codegen.request.validate",
        "payload": {
            "code_content": "class NodeTestEffect(NodeEffect): pass",
            "node_type": "effect"
        }
    }

    # Publish event
    topic = kafka_test_topics["validation_request"]
    kafka_producer.send(topic, value=event)
    kafka_producer.flush()

    # Verify event was sent (no exceptions raised)
    assert True
```

### Example 2: Request → Response Flow

```python
import pytest
import asyncio
from uuid import uuid4
from tests.integration.kafka_utils import publish_test_event, consume_response

@pytest.mark.kafka
@pytest.mark.integration
@pytest.mark.asyncio
async def test_validation_request_response_flow(
    kafka_producer,
    kafka_consumer,
    kafka_test_topics,
    kafka_connectivity_check
):
    """Test complete validation request → response flow."""

    assert kafka_connectivity_check

    # Setup
    correlation_id = str(uuid4())
    request_topic = kafka_test_topics["validation_request"]
    response_topic = kafka_test_topics["validation_response"]

    # Create consumer for response
    consumer = kafka_consumer([response_topic], f"test-{correlation_id}")

    # Publish request
    request_event = {
        "correlation_id": correlation_id,
        "event_type": "codegen.request.validate",
        "payload": {"code": "class Test: pass"}
    }

    await publish_test_event(
        kafka_producer,
        request_topic,
        request_event,
        correlation_id
    )

    # Consume response
    response = await consume_response(
        consumer,
        correlation_id,
        timeout_seconds=10
    )

    # Verify
    assert response is not None
    assert response["correlation_id"] == correlation_id
    assert "quality_score" in response

    # Cleanup
    consumer.close()
```

### Example 3: Correlation ID Tracking

```python
import pytest
from uuid import uuid4
from tests.integration.kafka_utils import track_event_flow

@pytest.mark.kafka
@pytest.mark.integration
def test_correlation_id_tracking(
    kafka_producer,
    kafka_test_topics,
    kafka_connectivity_check
):
    """Test correlation ID tracking across request/response."""

    assert kafka_connectivity_check

    # Setup
    correlation_id = str(uuid4())

    # Publish request (assume handler will process)
    kafka_producer.send(
        kafka_test_topics["validation_request"],
        value={"correlation_id": correlation_id, "payload": {}}
    )
    kafka_producer.flush()

    # Track event flow
    tracking = track_event_flow(
        correlation_id=correlation_id,
        request_topic=kafka_test_topics["validation_request"],
        response_topic=kafka_test_topics["validation_response"],
        timeout_seconds=30
    )

    # Verify tracking
    assert tracking["request_found"], "Request event not found"
    assert tracking["response_found"], "Response event not found"
    assert tracking["duration_ms"] is not None
    assert tracking["duration_ms"] < 5000  # Under 5 seconds
```

---

## Running Tests

### Prerequisites

1. **Start Redpanda/Kafka**:
   ```bash
   # Via docker-compose (recommended)
   cd /Volumes/PRO-G40/Code/omninode-bridge
   docker compose up -d redpanda

   # Verify running
   docker ps | grep redpanda
   ```

2. **Configure Environment**:
   ```bash
   export TEST_KAFKA_BOOTSTRAP_SERVERS="localhost:19092"
   ```

### Test Execution

**Run all Kafka tests**:
```bash
cd services/intelligence
pytest -m kafka -v
```

**Run specific test file**:
```bash
pytest tests/integration/test_handlers_kafka.py -v
```

**Skip Kafka tests** (when Kafka unavailable):
```bash
pytest -m "not kafka" -v
```

**Run with connectivity check**:
```bash
# Tests automatically skip if Kafka unavailable
pytest -m kafka --tb=short -v
```

### Test Markers

Add markers to tests to control execution:

```python
@pytest.mark.kafka  # Requires Kafka infrastructure
@pytest.mark.integration  # Integration test
@pytest.mark.asyncio  # Async test
@pytest.mark.slow  # Long-running test
@pytest.mark.load  # Load/performance test
def test_kafka_feature():
    pass
```

---

## Troubleshooting

### Issue: Kafka Not Available

**Symptom**: Tests skipped with "Kafka not available"

**Solution**:
1. Check Redpanda is running:
   ```bash
   docker ps | grep redpanda
   ```

2. Verify connectivity:
   ```bash
   cd services/intelligence
   python -c "from tests.integration.kafka_utils import verify_kafka_connectivity; print(verify_kafka_connectivity())"
   ```

3. Check bootstrap servers configuration:
   ```bash
   echo $TEST_KAFKA_BOOTSTRAP_SERVERS
   # Should be: localhost:19092
   ```

4. Test direct connection:
   ```bash
   kafkacat -b localhost:19092 -L
   ```

### Issue: Topics Not Created

**Symptom**: Tests fail with "Topic does not exist"

**Solution**:
1. Run topic creation manually:
   ```bash
   python -c "from tests.integration.kafka_utils import create_test_topics; create_test_topics()"
   ```

2. Verify topics exist:
   ```bash
   kafkacat -b localhost:19092 -L | grep omninode.codegen
   ```

3. Check admin client permissions:
   ```bash
   # Ensure Redpanda allows auto-creation
   docker exec redpanda rpk cluster config set auto_create_topics_enabled true
   ```

### Issue: Consumer Group Conflicts

**Symptom**: Tests interfere with each other

**Solution**:
1. Use unique group IDs per test:
   ```python
   group_id = f"test-{uuid4()}"
   consumer = kafka_consumer([topic], group_id)
   ```

2. Reset consumer groups between test runs:
   ```bash
   kafkacat -b localhost:19092 -G test-group -C -t omninode.codegen.request.validate.v1 -o end
   ```

### Issue: Timeout Waiting for Response

**Symptom**: `consume_response()` returns None

**Solution**:
1. Verify handlers are running:
   ```bash
   docker logs archon-intelligence | grep "Handler registered"
   ```

2. Increase timeout:
   ```python
   response = await consume_response(consumer, correlation_id, timeout_seconds=30)
   ```

3. Check correlation IDs match:
   ```python
   # Ensure same correlation_id used in request and consumer
   ```

4. Monitor handler logs:
   ```bash
   docker logs -f archon-intelligence
   ```

---

## Quality Gates

### QC-001: ONEX Standards Compliance

✅ **Passed**:
- All code follows ONEX naming conventions
- Type hints on all public functions
- Comprehensive docstrings with examples
- Error handling with proper exception types

### QC-003: Type Safety Validation

✅ **Passed**:
- All functions fully typed (Dict, List, Optional, Any)
- Return types specified
- Parameters typed with defaults
- Type checking via mypy (no errors)

### FV-001: Lifecycle Compliance

✅ **Passed**:
- Fixtures properly scoped (session vs function)
- Cleanup via fixture teardown
- Resource management (close connections)
- No resource leaks

---

## Next Steps

### Workflow 2: Kafka Integration Tests Enablement

After infrastructure is complete, proceed to:

1. **Remove skip decorators** from 7 Kafka tests
2. **Update test imports** to use new fixtures
3. **Fix connection issues** with handlers
4. **Enable tests** and verify execution

See: `MVP_PHASE_4_AGENT_WORKFLOWS_PLAN.md` → Workflow 2

### Workflow 3: End-to-End Event Flow Validation

After tests are enabled:

1. **Create E2E test scripts** for validation/analysis/pattern/mixin flows
2. **Implement monitoring** for handler processing
3. **Validate correlation ID tracking** end-to-end
4. **Fix integration issues** discovered during testing

---

## References

- **Workflow Plan**: `MVP_PHASE_4_AGENT_WORKFLOWS_PLAN.md`
- **Kafka Consumer Service**: `python/src/server/services/kafka_consumer_service.py`
- **Docker Compose**: `docker-compose.yml` (Redpanda configuration)
- **pytest Documentation**: https://docs.pytest.org/
- **confluent-kafka**: https://github.com/confluentinc/confluent-kafka-python

---

**Kafka Test Infrastructure**: ✅ **COMPLETE**
**Created**: 2025-10-15 | **Phase**: MVP Phase 4 - Workflow 1
**Status**: Ready for Workflow 2 (Test Enablement)
