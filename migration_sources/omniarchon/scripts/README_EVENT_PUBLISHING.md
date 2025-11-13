# Event Publishing Tools

Tools for publishing test events to Kafka/Redpanda without needing docker exec commands.

## Quick Start

### Install Dependencies

```bash
# Using uv (recommended)
cd python
uv pip install --group dev

# Or install just Kafka client
uv pip install confluent-kafka

# Or using pip
pip install confluent-kafka
```

### Publish Test Events

```bash
# PRD Analysis Event
python scripts/publish_test_event.py --event-type analyze --prd "Build a user authentication service with email/password login"

# Code Validation Event (inline code)
python scripts/publish_test_event.py --event-type validate --code "def hello(): pass"

# Code Validation Event (from file)
python scripts/publish_test_event.py --event-type validate --code-file src/example.py --node-type effect

# Pattern Matching Event
python scripts/publish_test_event.py --event-type pattern --description "cache service with Redis" --node-type effect

# Mixin Recommendation Event
python scripts/publish_test_event.py --event-type mixin --description "requires caching and event bus"
```

### Connect to Different Kafka Instance

```bash
# Connect to docker compose Redpanda
python scripts/publish_test_event.py --bootstrap-servers localhost:9092 --event-type analyze --prd "Test"

# Connect to remote Kafka cluster
python scripts/publish_test_event.py --bootstrap-servers kafka.example.com:9092 --event-type analyze --prd "Test"
```

## Event Types

### 1. Analysis Events (`analyze`)

**Purpose**: PRD semantic analysis via LangExtract

**Topic**: `omninode.codegen.request.analyze.v1`

**Handler**: `CodegenAnalysisHandler`

**Example**:
```bash
python scripts/publish_test_event.py \
  --event-type analyze \
  --prd "Build a REST API for user management with CRUD operations and JWT authentication"
```

**Response Topic**: `omninode.codegen.response.analyze.v1`

**Response Contains**:
- Semantic concepts (database, api, authentication)
- Entities (PostgreSQL, JWT, REST)
- Relationships
- Node type hints (effect: 0.8, compute: 0.2)

### 2. Validation Events (`validate`)

**Purpose**: Code quality and ONEX compliance validation

**Topic**: `omninode.codegen.request.validate.v1`

**Handler**: `CodegenValidationHandler`

**Example**:
```bash
# Inline code
python scripts/publish_test_event.py \
  --event-type validate \
  --code 'class UserService: pass' \
  --node-type effect

# From file
python scripts/publish_test_event.py \
  --event-type validate \
  --code-file services/user/node.py \
  --node-type effect
```

**Response Topic**: `omninode.codegen.response.validate.v1`

**Response Contains**:
- Quality score (0.0-1.0)
- ONEX compliance score (0.0-1.0)
- Violations (critical issues)
- Warnings (non-blocking issues)
- Suggestions (improvements)
- is_valid boolean

### 3. Pattern Events (`pattern`)

**Purpose**: Find similar existing nodes

**Topic**: `omninode.codegen.request.pattern.v1`

**Handler**: `CodegenPatternHandler`

**Example**:
```bash
python scripts/publish_test_event.py \
  --event-type pattern \
  --description "cache service with expiration" \
  --node-type effect
```

**Response Topic**: `omninode.codegen.response.pattern.v1`

**Response Contains**:
- Similar nodes with similarity scores
- Mixins used in similar nodes
- Contracts from similar nodes
- Code snippets

### 4. Mixin Events (`mixin`)

**Purpose**: Recommend mixins based on requirements

**Topic**: `omninode.codegen.request.mixin.v1`

**Handler**: `CodegenMixinHandler`

**Example**:
```bash
python scripts/publish_test_event.py \
  --event-type mixin \
  --description "needs caching, event bus, and health checks" \
  --node-type effect
```

**Response Topic**: `omninode.codegen.response.mixin.v1`

**Response Contains**:
- Mixin recommendations with confidence scores
- Reason for each recommendation
- Required configuration for each mixin

## Advanced Usage

### Custom Topics

```bash
# Publish to custom topic
python scripts/publish_test_event.py \
  --event-type analyze \
  --prd "Test" \
  --topic custom.topic.v1
```

### Consume Responses

The script only publishes events. To consume responses, you can:

1. **Use omniclaude consumer** (recommended):
   ```bash
   # omniclaude has consumers for response topics
   ```

2. **Use kcat** (if installed):
   ```bash
   kcat -b localhost:9092 -C -t omninode.codegen.response.analyze.v1
   ```

3. **Use Python consumer**:
   ```python
   from confluent_kafka import Consumer

   config = {
       "bootstrap.servers": "localhost:9092",
       "group.id": "test-consumer",
       "auto.offset.reset": "earliest",
   }

   consumer = Consumer(config)
   consumer.subscribe(["omninode.codegen.response.analyze.v1"])

   while True:
       msg = consumer.poll(1.0)
       if msg:
           print(msg.value().decode("utf-8"))
   ```

## Alternative: Native kcat Tool

If you prefer the native kcat tool (formerly kafkacat):

### Install kcat

```bash
# macOS
brew install kcat

# Ubuntu/Debian
sudo apt-get install kafkacat

# Or build from source
git clone https://github.com/edenhill/kcat.git
cd kcat
./configure
make
sudo make install
```

### Publish with kcat

```bash
# Publish analysis event
echo '{"correlation_id":"test-123","event_type":"codegen.request.analyze","payload":{"prd_content":"Build a user service"}}' | \
  kcat -b localhost:9092 -t omninode.codegen.request.analyze.v1 -P

# Consume responses
kcat -b localhost:9092 -C -t omninode.codegen.response.analyze.v1 -f '%t [%p:%o] %k: %s\n'
```

### kcat vs Python Script

**Python Script (`publish_test_event.py`)**:
- ✅ Part of project dependencies
- ✅ Structured event creation
- ✅ Validation and error handling
- ✅ Cross-platform (Windows, macOS, Linux)
- ✅ No external installation required

**Native kcat**:
- ✅ Lightweight C binary
- ✅ Raw message control
- ✅ Advanced Kafka operations
- ✅ Metadata inspection
- ❌ Requires separate installation
- ❌ Manual JSON construction

**Recommendation**: Use Python script for testing intelligence handlers, use kcat for debugging Kafka infrastructure.

## Troubleshooting

### Connection Refused

```bash
# Check Redpanda is running
docker compose ps

# Check port mapping
docker compose port archon-redpanda 9092
```

### Module Not Found: confluent_kafka

```bash
# Install confluent-kafka
cd python
uv pip install confluent-kafka

# Or system-wide
pip install confluent-kafka
```

### Event Not Consumed

1. Check handler is registered:
   ```bash
   # Check logs
   docker compose logs archon-intelligence | grep "Registered.*Handler"
   ```

2. Check topic exists:
   ```bash
   kcat -b localhost:9092 -L
   ```

3. Check consumer group:
   ```bash
   docker compose exec archon-redpanda rpk group list
   ```

### Invalid Event Format

The script validates events before publishing. If you see errors:
- Check required fields for event type
- Verify JSON serialization
- Check bootstrap servers are correct

## Event Flow Reference

```
Python Script
    ↓
[Kafka: omninode.codegen.request.{type}.v1]
    ↓
KafkaConsumerService
    ↓
Handler (CodegenAnalysisHandler, etc.)
    ↓
Intelligence Service (LangExtract, QualityScorer, etc.)
    ↓
HybridEventRouter
    ↓
[Kafka: omninode.codegen.response.{type}.v1]
    ↓
omniclaude Consumer
```

## See Also

- `MVP_PLAN_INTELLIGENCE_SERVICES_V2.md` - Intelligence services architecture
- `services/intelligence/src/handlers/` - Event handler implementations
- `services/intelligence/src/services/kafka_consumer_service.py` - Consumer management
