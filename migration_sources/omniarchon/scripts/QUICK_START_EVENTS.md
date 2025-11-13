# Quick Start: Event Publishing

**No more `docker exec`** - Publish events directly from Python!

## 🚀 Setup (One Time)

```bash
cd /Volumes/PRO-G40/Code/omniarchon/python
uv pip install confluent-kafka
```

## 📨 Publish Events

### Test PRD Analysis
```bash
python scripts/publish_test_event.py \
  --event-type analyze \
  --prd "Build a user authentication service with email/password login and JWT tokens"
```

### Test Code Validation
```bash
python scripts/publish_test_event.py \
  --event-type validate \
  --code-file services/example/node.py \
  --node-type effect
```

### Test Pattern Matching
```bash
python scripts/publish_test_event.py \
  --event-type pattern \
  --description "cache service with Redis" \
  --node-type effect
```

### Test Mixin Recommendations
```bash
python scripts/publish_test_event.py \
  --event-type mixin \
  --description "requires caching, event bus, and health checks"
```

## 📥 Consume Responses

### Option 1: kcat (if installed)
```bash
# Install kcat first: brew install kcat
kcat -b localhost:9092 -C -t omninode.codegen.response.analyze.v1
```

### Option 2: Python Consumer
```python
from confluent_kafka import Consumer

config = {
    "bootstrap.servers": "localhost:9092",
    "group.id": "test-consumer",
    "auto.offset.reset": "earliest"
}

consumer = Consumer(config)
consumer.subscribe(["omninode.codegen.response.analyze.v1"])

while True:
    msg = consumer.poll(1.0)
    if msg and not msg.error():
        print(msg.value().decode("utf-8"))
```

## 🔍 Verify Event Processing

```bash
# Check handler logs
docker compose logs archon-intelligence | grep -i "codegen"

# Check Kafka topics
docker compose exec archon-redpanda rpk topic list

# Check consumer groups
docker compose exec archon-redpanda rpk group list
```

## 🎯 Event Flow

```
publish_test_event.py → Kafka → KafkaConsumerService → Handler → Response
```

## 📚 Full Documentation

See `scripts/README_EVENT_PUBLISHING.md` for complete documentation.
