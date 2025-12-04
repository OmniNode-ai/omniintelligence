# OmniIntelligence MVP Plan

**Date**: December 3, 2025
**Branch**: `feature/intelligence-nodes-migration`
**Goal**: Declarative, event-driven intelligence pipeline with contract-driven nodes

---

## Executive Summary

Build an MVP that:
1. Uses **declarative contract-driven nodes** (YAML contracts + generic runtime)
2. Communicates **entirely via Kafka events** - no direct node-to-node calls
3. Integrates with **Qdrant, Memgraph, PostgreSQL** storage backends via protocol handlers
4. Uses **local MLX embeddings** (localhost:8001) - no external API dependencies

**Architecture Shift**: Moving from imperative Python node implementations to declarative YAML contracts executed by a generic runtime. See [DECLARATIVE_EFFECT_NODES_SPEC.md](specs/DECLARATIVE_EFFECT_NODES_SPEC.md) for full specification.

**Current State**:
- 8 legacy nodes in `src/omniintelligence/_legacy/nodes/` (imperative, to be replaced)
- New declarative architecture defined in spec
- Contract-driven nodes will replace legacy implementations

---

## Architecture Overview

```
+---------------------------------------------------------------------------+
|                 DECLARATIVE EVENT-DRIVEN INTELLIGENCE PIPELINE            |
+---------------------------------------------------------------------------+

                    +---------------------------+
                    |    Kafka Event Bus        |
                    | (Request/Response Topics) |
                    +-------------+-------------+
                                  |
                    +-------------v-------------+
                    |      Generic Runtime      |
                    |  (NodeEffect/NodeCompute) |
                    |  - Contract loading       |
                    |  - Protocol handlers      |
                    |  - Resilience policies    |
                    +-------------+-------------+
                                  |
         +------------------------+------------------------+
         |                        |                        |
+--------v--------+    +----------v----------+    +--------v--------+
|   YAML Contracts|    |  Protocol Handlers  |    |   Observability |
| - Effect nodes  |    | - HttpRestHandler   |    |   - Metrics     |
| - Compute nodes |    | - BoltHandler       |    |   - Traces      |
| - Resilience    |    | - PostgresHandler   |    |   - Logs        |
+-----------------+    | - KafkaHandler      |    +-----------------+
                       +----------+----------+
                                  |
                    +-------------v-------------+
                    |   External Systems        |
                    | - Qdrant (vectors)        |
                    | - Memgraph (graph)        |
                    | - PostgreSQL (patterns)   |
                    | - MLX (embeddings)        |
                    +---------------------------+
```

### Node Type Strategy

| Node Type | Pattern | Location |
|-----------|---------|----------|
| **Effect** | Declarative (YAML + runtime) | `src/omniintelligence/nodes/` |
| **Compute** | Declarative (YAML + runtime) | `src/omniintelligence/nodes/` |
| **Reducer** | Imperative (Python FSM) | Valid pattern, keep or migrate later |
| **Orchestrator** | Imperative (Python workflows) | Valid pattern, keep or migrate later |

### Legacy Nodes (To Be Replaced)

The following nodes are in `src/omniintelligence/_legacy/nodes/` and will be replaced by contract-driven equivalents:

**Effect Nodes (4)** - Will become YAML contracts:
- `qdrant_vector_effect/` -> `qdrant_vector_effect.yaml`
- `memgraph_graph_effect/` -> `memgraph_graph_effect.yaml`
- `postgres_pattern_effect/` -> `postgres_pattern_effect.yaml`
- `kafka_event_effect/` -> `kafka_event_effect.yaml`

**Compute Nodes (4)** - Will become YAML contracts:
- `vectorization_compute/` -> `vectorization_compute.yaml`
- `entity_extraction_compute/` -> `entity_extraction_compute.yaml`
- `relationship_detection_compute/` -> `relationship_detection_compute.yaml`
- `quality_scoring_compute/` -> `quality_scoring_compute.yaml`

**Orchestrator/Reducer (Keep for now)**:
- `intelligence_orchestrator/` - Workflow coordination (valid pattern)
- `intelligence_reducer/` - FSM state management (valid pattern)

---

## Phase 1: Declarative Runtime Foundation

**Priority**: CRITICAL (blocks all other phases)
**Effort**: 1-2 weeks

### Goal

Create the generic runtime infrastructure that loads YAML contracts and executes them using protocol handlers.

### Components to Create

**File Structure**:
```
src/omniintelligence/
├── nodes/
│   ├── effect_runtime/
│   │   ├── __init__.py
│   │   └── v1_0_0/
│   │       ├── __init__.py
│   │       ├── runtime.py           # NodeEffect base class
│   │       ├── handlers/
│   │       │   ├── __init__.py
│   │       │   ├── base.py          # ProtocolHandler ABC
│   │       │   ├── http_rest.py     # HttpRestHandler
│   │       │   ├── bolt.py          # BoltHandler (Memgraph)
│   │       │   ├── postgres.py      # PostgresHandler
│   │       │   ├── kafka.py         # KafkaHandler
│   │       │   └── registry.py      # ProtocolHandlerRegistry
│   │       ├── resilience/
│   │       │   ├── __init__.py
│   │       │   ├── retry.py         # RetryPolicy
│   │       │   ├── circuit_breaker.py
│   │       │   └── rate_limiter.py
│   │       ├── models.py            # ModelEffectInput/Output
│   │       ├── mapping.py           # JSONPath response mapping
│   │       └── validation.py        # Contract validation
│   └── compute_runtime/             # Similar structure for compute
│       └── v1_0_0/
│           ├── runtime.py           # NodeCompute base class
│           └── ...
├── schemas/
│   └── effect_contract_v1.json      # JSON Schema for validation
```

### Implementation Tasks

1. **Create base `ProtocolHandler` ABC**
   - `initialize()`, `shutdown()`, `execute()`, `health_check()`
   - Protocol-agnostic request/response models

2. **Implement `HttpRestHandler`**
   - Connection pooling with aiohttp
   - Variable substitution in URLs/bodies
   - Response parsing with JSONPath

3. **Implement `NodeEffect` runtime**
   - Load and validate YAML contracts
   - Route operations to handler
   - Apply resilience policies
   - Collect metrics

4. **Create contract validation**
   - JSON Schema for YAML contracts
   - Pydantic model generation from contracts

### Success Criteria

- [ ] `NodeEffect` class loads YAML contracts
- [ ] `HttpRestHandler` makes HTTP calls with variable substitution
- [ ] JSONPath response mapping works
- [ ] Contract validation catches schema errors
- [ ] Unit tests for runtime components

---

## Phase 2: Effect Node Contracts

**Priority**: HIGH
**Effort**: 1 week

### Goal

Create YAML contracts for the 4 effect nodes, replacing legacy Python implementations.

### Contracts to Create

**File**: `src/omniintelligence/nodes/qdrant_vector_effect/v1_0_0/contracts/qdrant_vector_effect.yaml`

```yaml
name: qdrant_vector_effect
version: { major: 1, minor: 0, patch: 0 }
description: "Vector storage operations for Qdrant"

protocol:
  type: http_rest
  version: "HTTP/1.1"
  content_type: application/json

connection:
  url: "http://${QDRANT_HOST}:${QDRANT_PORT}"
  timeout_ms: 30000
  pool:
    min_size: 1
    max_size: 10

operations:
  upsert:
    description: "Upsert vectors into collection"
    request:
      method: POST
      path: "/collections/${input.collection}/points"
      body:
        points:
          - id: "${input.vector_id}"
            vector: "${input.embeddings}"
            payload: "${input.metadata}"
    response:
      success_codes: [200]
      mapping:
        operation_id: "$.result.operation_id"
        status: "$.result.status"

  search:
    description: "Search for similar vectors"
    request:
      method: POST
      path: "/collections/${input.collection}/points/search"
      body:
        vector: "${input.query_vector}"
        limit: "${input.limit}"
        with_payload: true
    response:
      success_codes: [200]
      mapping:
        results: "$.result"
        scores: "$.result[*].score"

events:
  consume:
    topic: "dev.omni-intelligence.effect.qdrant-vector.request.v1"
    group_id: "omni-intelligence-qdrant-effect"
  produce:
    success_topic: "dev.omni-intelligence.effect.qdrant-vector.response.v1"
    dlq_topic: "dev.omni-intelligence.effect.qdrant-vector.request.v1.dlq"

resilience:
  retry:
    max_attempts: 3
    initial_delay_ms: 1000
    backoff_multiplier: 2.0
  circuit_breaker:
    failure_threshold: 5
    timeout_ms: 60000
```

### Contracts Summary

| Contract | Protocol | Key Operations |
|----------|----------|----------------|
| `qdrant_vector_effect.yaml` | HTTP REST | upsert, search, delete, get |
| `memgraph_graph_effect.yaml` | Bolt | create_entity, create_relationship, query |
| `postgres_pattern_effect.yaml` | PostgreSQL | store_pattern, query_patterns, update_pattern |
| `kafka_event_effect.yaml` | Kafka | publish, publish_batch |

### Success Criteria

- [ ] All 4 effect contracts created and validated
- [ ] Contracts match legacy node functionality
- [ ] Integration tests pass with real backends
- [ ] Contract-driven nodes produce same results as legacy

---

## Phase 3: MLX Embedding Adapter

**Priority**: HIGH (blocks vectorization)
**Effort**: 2-4 hours

### Goal

Create contract for local MLX embedding service (localhost:8001).

### Contract

**File**: `src/omniintelligence/nodes/mlx_embedding_adapter/v1_0_0/contracts/mlx_embedding_adapter.yaml`

```yaml
name: mlx_embedding_adapter
version: { major: 1, minor: 0, patch: 0 }
description: "Local MLX embedding generation via OpenAI-compatible API"

protocol:
  type: http_rest
  content_type: application/json

connection:
  url: "http://${MLX_HOST}:${MLX_PORT}"
  timeout_ms: 30000

operations:
  generate_embedding:
    description: "Generate embeddings for text"
    request:
      method: POST
      path: "/v1/embeddings"
      body:
        input: "${input.text}"
        model: "${input.model}"
    response:
      success_codes: [200]
      mapping:
        embedding: "$.data[0].embedding"
        model: "$.model"
        usage: "$.usage"

events:
  consume:
    topic: "dev.omni-intelligence.effect.mlx-embedding.request.v1"
    group_id: "omni-intelligence-mlx-embedding"
  produce:
    success_topic: "dev.omni-intelligence.effect.mlx-embedding.response.v1"

resilience:
  retry:
    max_attempts: 2
    initial_delay_ms: 500
```

### Environment Variables

```bash
MLX_HOST=localhost
MLX_PORT=8001
MLX_MODEL=mlx-embedding
```

### Success Criteria

- [ ] Contract generates embeddings from MLX server
- [ ] Fallback chain: MLX -> SentenceTransformers -> TF-IDF
- [ ] Unit tests pass with mocked endpoint

---

## Phase 4: Compute Node Contracts

**Priority**: MEDIUM
**Effort**: 1 week

### Goal

Create YAML contracts for compute nodes. Note: Compute nodes are pure functions with no I/O, so contracts define input/output schemas and processing steps.

### Contracts to Create

| Contract | Input | Output | Processing |
|----------|-------|--------|------------|
| `vectorization_compute.yaml` | text, metadata | embeddings, dimension | MLX adapter call |
| `entity_extraction_compute.yaml` | text, language | entities, types | NLP extraction |
| `relationship_detection_compute.yaml` | entities, context | relationships | Pattern matching |
| `quality_scoring_compute.yaml` | code, metrics | scores, recommendations | Rule-based scoring |

### Event Topics

```python
COMPUTE_TOPICS = {
    "vectorization": {
        "input": "dev.omni-intelligence.compute.vectorization.request.v1",
        "output": "dev.omni-intelligence.compute.vectorization.response.v1",
    },
    "entity_extraction": {
        "input": "dev.omni-intelligence.compute.entity-extraction.request.v1",
        "output": "dev.omni-intelligence.compute.entity-extraction.response.v1",
    },
    "relationship_detection": {
        "input": "dev.omni-intelligence.compute.relationship-detection.request.v1",
        "output": "dev.omni-intelligence.compute.relationship-detection.response.v1",
    },
    "quality_scoring": {
        "input": "dev.omni-intelligence.compute.quality-scoring.request.v1",
        "output": "dev.omni-intelligence.compute.quality-scoring.response.v1",
    },
}
```

### Success Criteria

- [ ] All 4 compute contracts created
- [ ] Event consumers wrap compute execution
- [ ] Correlation IDs preserved through pipeline

---

## Phase 5: Storage Router and Integration

**Priority**: HIGH
**Effort**: 1-2 days

### Goal

Create storage router that consumes compute outputs and routes to appropriate storage effects.

### Storage Router Pattern

Instead of adding consumers to each storage node, create a **Storage Router Effect** that coordinates storage:

```
Compute Output Events
         |
         v
  Storage Router Effect
         |
    +----+----+----+
    |    |    |    |
    v    v    v    v
Qdrant  Memgraph  PostgreSQL  Kafka
Effect   Effect    Effect    Effect
```

### Routing Rules

```yaml
# storage_router_effect.yaml
name: storage_router_effect
version: { major: 1, minor: 0, patch: 0 }

routing:
  - event_type: "vectorization.completed"
    target: "qdrant_vector_effect"
    operation: "upsert"
    mapping:
      collection: "${input.project_id}_vectors"
      vector_id: "${input.document_id}"
      embeddings: "${input.embeddings}"

  - event_type: "entity-extraction.completed"
    target: "memgraph_graph_effect"
    operation: "create_entity"
    mapping:
      entity_type: "${input.entity_type}"
      entity_name: "${input.entity_name}"
      properties: "${input.properties}"

  - event_type: "relationship-detection.completed"
    target: "memgraph_graph_effect"
    operation: "create_relationship"
    mapping:
      source_id: "${input.source_entity_id}"
      target_id: "${input.target_entity_id}"
      relationship_type: "${input.relationship_type}"
```

### Cross-Storage ID Coordination

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

### Success Criteria

- [ ] Storage router consumes compute completion events
- [ ] Vectors stored in Qdrant with document IDs
- [ ] Entities/relationships stored in Memgraph
- [ ] Cross-storage ID consistency (100%)

---

## Phase 6: End-to-End Pipeline Testing

**Priority**: HIGH
**Effort**: 1 day

### Test Scenario: Document Ingestion

```python
async def test_document_ingestion_pipeline():
    """
    Full pipeline test:
    1. Publish document-received event
    2. Verify vectorization request/response
    3. Verify entity extraction request/response
    4. Verify relationship detection request/response
    5. Verify storage events (Qdrant, Memgraph)
    6. Query Qdrant for vector
    7. Query Memgraph for entities/relationships
    """
```

### Test Infrastructure

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
- [ ] All events have correlation IDs (100% preservation)
- [ ] Failed events route to DLQ

---

## Phase 7: LLM Provider System (Optional)

**Priority**: LOW (post-MVP)
**Effort**: 2-3 days

### Migrate from omninode_bridge

| Component | Source | Target |
|-----------|--------|--------|
| MixinLLMProvider | `omninode_bridge/agents/intelligence/` | `providers/` |
| LocalModelsAdapter | `omninode_bridge/agents/intelligence/adapters/` | `providers/` |
| AI Quorum | `omninode_bridge/agents/workflows/` | `quorum/` |

This is **not required for MVP** - defer to post-MVP.

---

## Implementation Order

| Order | Phase | Duration | Dependencies |
|-------|-------|----------|--------------|
| 1 | Phase 1: Declarative Runtime | 1-2 weeks | None |
| 2 | Phase 2: Effect Contracts | 1 week | Phase 1 |
| 3 | Phase 3: MLX Adapter | 2-4 hours | Phase 1 |
| 4 | Phase 4: Compute Contracts | 1 week | Phase 1 |
| 5 | Phase 5: Storage Router | 1-2 days | Phases 2, 4 |
| 6 | Phase 6: E2E Testing | 1 day | Phase 5 |
| 7 | Phase 7: LLM Migration | 2-3 days | Optional, post-MVP |

**Total MVP Timeline**: 3-4 weeks

---

## Docker Stack Updates

### docker-compose.nodes.yml

```yaml
services:
  # Generic effect node runtime
  effect-runtime:
    build:
      context: ../..
      dockerfile: deployment/docker/Dockerfile.effect
    environment:
      - KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092
      - QDRANT_URL=http://omni-qdrant:6333
      - MEMGRAPH_HOST=omni-memgraph
      - POSTGRES_HOST=omninode-bridge-postgres
      - MLX_HOST=host.docker.internal
      - MLX_PORT=8001
    volumes:
      - ../../src/omniintelligence/nodes:/app/nodes:ro
    depends_on:
      - omni-qdrant
      - omni-memgraph
    networks:
      - omninode-bridge-network

  # Storage router
  storage-router:
    build:
      context: ../..
      dockerfile: deployment/docker/Dockerfile.storage-router
    environment:
      - KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092
      - NODE_CONTRACTS_PATH=/app/contracts
    volumes:
      - ../../src/omniintelligence/nodes:/app/contracts:ro
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

# Validate effect contract
python -m omniintelligence.tools.contract_linter \
  src/omniintelligence/nodes/qdrant_vector_effect/v1_0_0/contracts/qdrant_vector_effect.yaml

# Publish test event
python -c "
from confluent_kafka import Producer
import json
producer = Producer({'bootstrap.servers': 'localhost:29092'})
producer.produce(
    'dev.omni-intelligence.compute.vectorization.request.v1',
    json.dumps({
        'source_path': 'test.py',
        'content': 'def hello(): pass',
        'correlation_id': 'test-123'
    }).encode()
)
producer.flush()
"

# Check Qdrant
curl http://localhost:6333/collections

# Check Memgraph
docker exec omni-memgraph mgconsole -c "MATCH (n) RETURN n LIMIT 10;"
```

---

## Files to Create Summary

### New Files (Core Runtime)

```
src/omniintelligence/
├── nodes/
│   ├── effect_runtime/v1_0_0/
│   │   ├── runtime.py                    # NodeEffect base class
│   │   ├── handlers/base.py              # ProtocolHandler ABC
│   │   ├── handlers/http_rest.py         # HttpRestHandler
│   │   ├── handlers/bolt.py              # BoltHandler
│   │   ├── handlers/postgres.py          # PostgresHandler
│   │   ├── handlers/kafka.py             # KafkaHandler
│   │   ├── handlers/registry.py          # ProtocolHandlerRegistry
│   │   ├── resilience/retry.py           # RetryPolicy
│   │   ├── resilience/circuit_breaker.py # CircuitBreaker
│   │   ├── models.py                     # Pydantic models
│   │   ├── mapping.py                    # JSONPath mapping
│   │   └── validation.py                 # Contract validation
│   └── compute_runtime/v1_0_0/
│       └── runtime.py                    # NodeCompute base class
├── schemas/
│   └── effect_contract_v1.json           # JSON Schema
```

### New Files (Contracts)

```
src/omniintelligence/nodes/
├── qdrant_vector_effect/v1_0_0/contracts/
│   └── qdrant_vector_effect.yaml
├── memgraph_graph_effect/v1_0_0/contracts/
│   └── memgraph_graph_effect.yaml
├── postgres_pattern_effect/v1_0_0/contracts/
│   └── postgres_pattern_effect.yaml
├── kafka_event_effect/v1_0_0/contracts/
│   └── kafka_event_effect.yaml
├── mlx_embedding_adapter/v1_0_0/contracts/
│   └── mlx_embedding_adapter.yaml
├── vectorization_compute/v1_0_0/contracts/
│   └── vectorization_compute.yaml
├── entity_extraction_compute/v1_0_0/contracts/
│   └── entity_extraction_compute.yaml
├── relationship_detection_compute/v1_0_0/contracts/
│   └── relationship_detection_compute.yaml
├── quality_scoring_compute/v1_0_0/contracts/
│   └── quality_scoring_compute.yaml
└── storage_router_effect/v1_0_0/contracts/
    └── storage_router_effect.yaml
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Event latency (request -> completed) | < 500ms |
| Contract validation time | < 50ms |
| Protocol handler initialization | < 1s |
| Storage success rate | > 99% |
| DLQ message rate | < 1% |
| Cross-storage ID consistency | 100% |
| Correlation ID preservation | 100% |
| Circuit breaker false opens | < 0.1% |

---

## References

- [DECLARATIVE_EFFECT_NODES_SPEC.md](specs/DECLARATIVE_EFFECT_NODES_SPEC.md) - Full specification
- [Legacy Nodes](../src/omniintelligence/_legacy/nodes/) - Imperative implementations (deprecated)
- [Contract Linter](../src/omniintelligence/tools/README.md) - YAML contract validation tool

---

**END OF MVP PLAN**
