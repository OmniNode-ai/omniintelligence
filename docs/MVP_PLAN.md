# OmniIntelligence MVP Plan

**Date**: December 2, 2025
**Branch**: `feature/intelligence-nodes-migration`
**Goal**: Event-driven intelligence pipeline with local embedding support

---

## Executive Summary

Build an MVP that:
1. Uses **local MLX embeddings** (localhost:8001) - no external API dependencies
2. Communicates **entirely via Kafka events** - no direct node-to-node calls
3. Integrates with **Qdrant, Memgraph, PostgreSQL** storage backends
4. Migrates the **LLM provider system** from omninode_bridge

**Current State**: 8 nodes implemented (4 compute, 4 effect) but they only support direct calls, not event-driven communication.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    EVENT-DRIVEN INTELLIGENCE PIPELINE                    │
└─────────────────────────────────────────────────────────────────────────┘

                          Kafka/Redpanda (Event Bus)
    ┌──────────────────────────────────────────────────────────────────┐
    │  Topics: dev.omni-intelligence.{domain}.{operation}.v1           │
    └──────────────────────────────────────────────────────────────────┘
           ▲           ▲           ▲           ▲           ▲
           │           │           │           │           │
    ┌──────┴──┐  ┌─────┴────┐  ┌───┴────┐  ┌───┴───┐  ┌────┴────┐
    │ Ingest  │  │Vectorize │  │Extract │  │Relate │  │ Store   │
    │ API     │  │ Compute  │  │Entities│  │ ships │  │ Effects │
    └─────────┘  └──────────┘  └────────┘  └───────┘  └─────────┘
                      │
                      ▼
              ┌──────────────┐
              │ MLX Embeddings│
              │ localhost:8001│
              └──────────────┘
```

---

## Phase 1: Local MLX Embedding Integration

**Priority**: CRITICAL (blocks all vectorization)
**Effort**: 2-4 hours

### What Exists
- `VectorizationCompute` with OpenAI, SentenceTransformers, TF-IDF providers
- MLX server running at `http://localhost:8001/v1/embeddings`

### What's Missing
- No support for local OpenAI-compatible endpoints

### Implementation

**File**: `src/omniintelligence/nodes/vectorization_compute/v1_0_0/compute.py`

```python
# Add new provider enum
class EmbeddingProvider(str, Enum):
    OPENAI = "openai"
    LOCAL_OPENAI = "local-openai"  # NEW
    SENTENCE_TRANSFORMERS = "sentence-transformers"
    TFIDF = "tfidf"
    AUTO = "auto"

# Add environment variables
LOCAL_EMBEDDING_URL = os.getenv("LOCAL_EMBEDDING_URL", "http://localhost:8001/v1/embeddings")
LOCAL_EMBEDDING_MODEL = os.getenv("LOCAL_EMBEDDING_MODEL", "mlx-embedding")

# Add method _generate_local_openai_embedding()
async def _generate_local_openai_embedding(self, text: str) -> list[float]:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            LOCAL_EMBEDDING_URL,
            json={"input": text, "model": LOCAL_EMBEDDING_MODEL},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]
```

### Environment Variables
```bash
EMBEDDING_PROVIDER=local-openai
LOCAL_EMBEDDING_URL=http://localhost:8001/v1/embeddings
LOCAL_EMBEDDING_MODEL=mlx-embedding
```

### Docker Compose Update
```yaml
vectorization-compute:
  environment:
    - EMBEDDING_PROVIDER=local-openai
    - LOCAL_EMBEDDING_URL=http://host.docker.internal:8001/v1/embeddings
```

### Success Criteria
- [ ] `VectorizationCompute` can generate embeddings from MLX server
- [ ] Auto fallback chain: LOCAL_OPENAI → SentenceTransformers → TF-IDF
- [ ] Unit tests pass with mocked MLX endpoint

---

## Phase 2: Event-Driven Node Communication

**Priority**: HIGH
**Effort**: 1-2 days

### What Exists
- `NodeKafkaEventEffect` for publishing events
- `NodeIntelligenceAdapterEffect` with consumer loop pattern
- Intent-based in-memory routing

### What's Missing
- Consumer loops on compute/effect nodes
- Event models for each operation type
- Topic registry

### Implementation

#### 2.1 Create Base Event Consumer

**File**: `src/omniintelligence/shared/event_consumer.py`

```python
class NodeEventConsumer:
    """Base class for wrapping nodes with Kafka consumption."""

    def __init__(
        self,
        node: NodeCompute | NodeEffect,
        input_topic: str,
        output_topic: str,
        failure_topic: str,
        consumer_group: str,
    ):
        self.node = node
        self.input_topic = input_topic
        self.output_topic = output_topic
        self.failure_topic = failure_topic
        self.consumer_group = consumer_group

    async def run(self):
        """Main consumer loop."""
        consumer = Consumer({
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "group.id": self.consumer_group,
            "auto.offset.reset": "earliest",
        })
        consumer.subscribe([self.input_topic])

        while not self._shutdown:
            msg = consumer.poll(1.0)
            if msg and not msg.error():
                await self._process_message(msg)
```

#### 2.2 Event Topic Registry

**File**: `src/omniintelligence/shared/topic_registry.py`

```python
TOPIC_REGISTRY = {
    "ingestion": {
        "input": "dev.omni-intelligence.ingestion.document-received.v1",
        "output": "dev.omni-intelligence.ingestion.completed.v1",
        "failure": "dev.omni-intelligence.ingestion.failed.v1",
    },
    "vectorization": {
        "input": "dev.omni-intelligence.vectorization.requested.v1",
        "output": "dev.omni-intelligence.vectorization.completed.v1",
        "failure": "dev.omni-intelligence.vectorization.failed.v1",
    },
    "entity_extraction": {
        "input": "dev.omni-intelligence.entity.extraction-requested.v1",
        "output": "dev.omni-intelligence.entity.extraction-completed.v1",
        "failure": "dev.omni-intelligence.entity.extraction-failed.v1",
    },
    "relationship_detection": {
        "input": "dev.omni-intelligence.relationship.detection-requested.v1",
        "output": "dev.omni-intelligence.relationship.detection-completed.v1",
        "failure": "dev.omni-intelligence.relationship.detection-failed.v1",
    },
    "quality_scoring": {
        "input": "dev.omni-intelligence.quality.scoring-requested.v1",
        "output": "dev.omni-intelligence.quality.scoring-completed.v1",
        "failure": "dev.omni-intelligence.quality.scoring-failed.v1",
    },
}
```

#### 2.3 Event Models

**Files to create**:
- `src/omniintelligence/models/events/model_vectorization_events.py`
- `src/omniintelligence/models/events/model_entity_events.py`
- `src/omniintelligence/models/events/model_relationship_events.py`
- `src/omniintelligence/models/events/model_storage_events.py`

```python
# Example: model_vectorization_events.py
class VectorizationRequestedPayload(BaseModel):
    source_path: str
    content: str
    project_id: str | None = None
    metadata: dict[str, Any] = {}

class VectorizationCompletedPayload(BaseModel):
    source_path: str
    vector: list[float]
    dimension: int
    provider: str
    metadata: dict[str, Any] = {}
```

#### 2.4 Wrap Existing Compute Nodes

**File**: `src/omniintelligence/nodes/vectorization_compute/v1_0_0/__main__.py`

```python
# Update to run as event consumer
async def main():
    compute = VectorizationCompute()
    consumer = NodeEventConsumer(
        node=compute,
        input_topic=TOPIC_REGISTRY["vectorization"]["input"],
        output_topic=TOPIC_REGISTRY["vectorization"]["output"],
        failure_topic=TOPIC_REGISTRY["vectorization"]["failure"],
        consumer_group="omni-intelligence-vectorization",
    )
    await consumer.run()

if __name__ == "__main__":
    asyncio.run(main())
```

### Success Criteria
- [ ] All 4 compute nodes run as event consumers
- [ ] Events flow: request → compute → completed/failed
- [ ] Correlation IDs preserved across event chain
- [ ] DLQ routing for failed messages

---

## Phase 3: Storage Integration via Events

**Priority**: HIGH
**Effort**: 1-2 days

### What Exists
- 4 storage effect nodes (Qdrant, Memgraph, PostgreSQL, Kafka)
- All support direct `execute_effect()` calls

### What's Missing
- Event consumers on storage nodes
- Storage coordination (which storage for which output)

### Implementation

#### 3.1 Storage Router Pattern

Instead of adding consumers to each storage node, create a **Storage Router Effect**:

**File**: `src/omniintelligence/nodes/storage_router_effect/v1_0_0/effect.py`

```python
class NodeStorageRouter(NodeEffect):
    """
    Routes completed compute events to appropriate storage nodes.

    Consumes:
    - vectorization.completed.v1 → QdrantEffect.upsert
    - entity.extraction-completed.v1 → MemgraphEffect.CREATE_ENTITY
    - relationship.detection-completed.v1 → MemgraphEffect.CREATE_RELATIONSHIP
    - pattern.learned.v1 → PostgresEffect.store_pattern
    """

    async def _process_event(self, event: ModelEventEnvelope):
        event_type = event.event_type

        if "vectorization.completed" in event_type:
            await self._store_vector(event)
        elif "entity.extraction-completed" in event_type:
            await self._store_entities(event)
        elif "relationship.detection-completed" in event_type:
            await self._store_relationships(event)
        elif "pattern.learned" in event_type:
            await self._store_pattern(event)
```

#### 3.2 Cross-Storage ID Coordination

Create ID generation that links across storage systems:

```python
class StorageIdentifier:
    """Generate consistent IDs across storage systems."""

    @staticmethod
    def document_id(source_path: str, project_id: str) -> str:
        """ID used in Qdrant vector, Memgraph document node."""
        return f"doc:{project_id}:{hashlib.sha256(source_path.encode()).hexdigest()[:16]}"

    @staticmethod
    def entity_id(document_id: str, entity_name: str, entity_type: str) -> str:
        """ID used in Memgraph entity nodes."""
        return f"ent:{document_id}:{entity_type}:{entity_name}"
```

#### 3.3 Storage Event Topics

```python
STORAGE_TOPICS = {
    "vector_stored": "dev.omni-intelligence.storage.vector-stored.v1",
    "entity_stored": "dev.omni-intelligence.storage.entity-stored.v1",
    "relationship_stored": "dev.omni-intelligence.storage.relationship-stored.v1",
    "pattern_stored": "dev.omni-intelligence.storage.pattern-stored.v1",
}
```

### Success Criteria
- [ ] Storage router consumes compute completion events
- [ ] Vectors stored in Qdrant with document IDs
- [ ] Entities/relationships stored in Memgraph
- [ ] Storage completion events published
- [ ] Cross-storage ID consistency

---

## Phase 4: LLM Provider System Migration

**Priority**: MEDIUM (required for future features, not MVP blocking)
**Effort**: 2-3 days

### What to Migrate from omninode_bridge

| Component | Source | Target | Lines |
|-----------|--------|--------|-------|
| MixinLLMProvider | `agents/intelligence/mixin_llm_provider.py` | `providers/mixin_llm_provider.py` | 521 |
| LocalModelsAdapter | `agents/intelligence/adapters/local_models_adapter.py` | `providers/local_models_adapter.py` | 875 |
| Provider Models | `agents/intelligence/models.py` | `providers/models.py` | 476 |
| Exceptions | `agents/intelligence/exceptions.py` | `providers/exceptions.py` | 324 |
| AI Quorum | `agents/workflows/ai_quorum.py` | `quorum/ai_quorum.py` | 478 |

### Package Structure

```
src/omniintelligence/
├── providers/
│   ├── __init__.py
│   ├── mixin_llm_provider.py    # Abstract base with circuit breaker
│   ├── local_models_adapter.py   # vLLM/MLX endpoints
│   ├── models.py                 # LLMRequest, LLMResponse, etc.
│   └── exceptions.py             # LLMProviderError hierarchy
├── quorum/
│   ├── __init__.py
│   ├── ai_quorum.py              # 4-model consensus
│   └── llm_client.py             # Provider clients
```

### Database Migrations

**File**: `migrations/001_create_llm_cost_tracking.sql`

```sql
CREATE TABLE llm_provider_costs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    input_token_cost DECIMAL(10,8) NOT NULL,
    output_token_cost DECIMAL(10,8) NOT NULL,
    effective_date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE llm_request_costs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID,
    correlation_id UUID,
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    total_cost DECIMAL(10,6) NOT NULL,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Success Criteria
- [ ] LLM provider package migrated with tests
- [ ] LocalModelsAdapter supports embeddings endpoint
- [ ] Cost tracking tables created
- [ ] VectorizationCompute uses LLM provider interface

---

## Phase 5: End-to-End Pipeline Testing

**Priority**: HIGH
**Effort**: 1 day

### Test Scenario: Document Ingestion

```python
async def test_document_ingestion_pipeline():
    """
    Full pipeline test:
    1. Publish document-received event
    2. Verify vectorization event
    3. Verify entity extraction event
    4. Verify relationship detection event
    5. Verify storage events
    6. Query Qdrant for vector
    7. Query Memgraph for entities/relationships
    """
```

### Test Infrastructure

**File**: `tests/integration/test_ingestion_pipeline.py`

```python
@pytest.fixture
async def kafka_producer():
    producer = Producer({"bootstrap.servers": "localhost:29092"})
    yield producer
    producer.flush()

@pytest.fixture
async def qdrant_client():
    client = AsyncQdrantClient(url="http://localhost:6333")
    yield client
    await client.close()

@pytest.fixture
async def memgraph_driver():
    driver = AsyncGraphDatabase.driver("bolt://localhost:7687")
    yield driver
    await driver.close()
```

### Success Criteria
- [ ] Document flows through entire pipeline
- [ ] Vector stored in Qdrant
- [ ] Entities stored in Memgraph
- [ ] Relationships stored in Memgraph
- [ ] All events have correlation IDs
- [ ] Failed events route to DLQ

---

## Implementation Order

| Order | Phase | Duration | Dependencies |
|-------|-------|----------|--------------|
| 1 | Phase 1: MLX Integration | 2-4 hours | None |
| 2 | Phase 2: Event Consumers | 1-2 days | Phase 1 |
| 3 | Phase 3: Storage Integration | 1-2 days | Phase 2 |
| 4 | Phase 5: E2E Testing | 1 day | Phase 3 |
| 5 | Phase 4: LLM Migration | 2-3 days | Optional for MVP |

**Total MVP Timeline**: 4-6 days

---

## Docker Stack Updates

### docker-compose.nodes.yml

```yaml
services:
  vectorization-compute:
    environment:
      - EMBEDDING_PROVIDER=local-openai
      - LOCAL_EMBEDDING_URL=http://host.docker.internal:8001/v1/embeddings
      - KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092
      - KAFKA_CONSUMER_GROUP=omni-intelligence-vectorization
      - KAFKA_INPUT_TOPIC=dev.omni-intelligence.vectorization.requested.v1
      - KAFKA_OUTPUT_TOPIC=dev.omni-intelligence.vectorization.completed.v1

  storage-router:
    build:
      context: ../..
      dockerfile: deployment/docker/Dockerfile.node
    environment:
      - NODE_NAME=storage_router_effect
      - KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092
      - QDRANT_URL=http://omni-qdrant:6333
      - MEMGRAPH_HOST=omni-memgraph
      - DATABASE_URL=postgresql://postgres:PASSWORD@omninode-bridge-postgres:5432/omniintelligence
    depends_on:
      - omni-qdrant
      - omni-memgraph
    networks:
      - omninode-bridge-network
```

---

## Quick Start Commands

```bash
# Start infrastructure (from omninode-bridge)
cd ~/Code/omninode-bridge && docker compose up -d

# Start omniintelligence nodes
cd ~/Code/omniintelligence/deployment/docker
docker compose -f docker-compose.yml -f docker-compose.nodes.yml up -d --build

# Test MLX embeddings locally
curl -X POST http://localhost:8001/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input": "test text", "model": "mlx-embedding"}'

# Publish test event
python -c "
from confluent_kafka import Producer
import json
producer = Producer({'bootstrap.servers': 'localhost:29092'})
producer.produce(
    'dev.omni-intelligence.vectorization.requested.v1',
    json.dumps({'source_path': 'test.py', 'content': 'def hello(): pass'}).encode()
)
producer.flush()
"

# Check Qdrant
curl http://localhost:6333/collections

# Check Memgraph
docker exec omni-memgraph mgconsole -c "MATCH (n) RETURN n LIMIT 10;"
```

---

## Files to Create/Modify Summary

### New Files (15)
- `src/omniintelligence/shared/event_consumer.py`
- `src/omniintelligence/shared/topic_registry.py`
- `src/omniintelligence/shared/storage_identifier.py`
- `src/omniintelligence/models/events/model_vectorization_events.py`
- `src/omniintelligence/models/events/model_entity_events.py`
- `src/omniintelligence/models/events/model_relationship_events.py`
- `src/omniintelligence/models/events/model_storage_events.py`
- `src/omniintelligence/nodes/storage_router_effect/v1_0_0/__init__.py`
- `src/omniintelligence/nodes/storage_router_effect/v1_0_0/__main__.py`
- `src/omniintelligence/nodes/storage_router_effect/v1_0_0/effect.py`
- `src/omniintelligence/providers/__init__.py`
- `src/omniintelligence/providers/mixin_llm_provider.py`
- `src/omniintelligence/providers/local_models_adapter.py`
- `src/omniintelligence/providers/models.py`
- `src/omniintelligence/providers/exceptions.py`

### Modified Files (8)
- `src/omniintelligence/nodes/vectorization_compute/v1_0_0/compute.py`
- `src/omniintelligence/nodes/vectorization_compute/v1_0_0/__main__.py`
- `src/omniintelligence/nodes/entity_extraction_compute/v1_0_0/__main__.py`
- `src/omniintelligence/nodes/relationship_detection_compute/v1_0_0/__main__.py`
- `src/omniintelligence/nodes/quality_scoring_compute/v1_0_0/__main__.py`
- `deployment/docker/docker-compose.nodes.yml`
- `deployment/docker/.env`
- `migrations/001_create_llm_cost_tracking.sql`

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Event latency (request → completed) | < 500ms |
| Vector dimension from MLX | Match model output (e.g., 768) |
| Storage success rate | > 99% |
| DLQ message rate | < 1% |
| Cross-storage ID consistency | 100% |
| Correlation ID preservation | 100% |

---

**END OF MVP PLAN**
