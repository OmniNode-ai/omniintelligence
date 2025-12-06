# OmniIntelligence Runtime Host Refactoring Plan

**Version**: 1.2.0
**Date**: 2025-12-03
**Status**: Planning Complete

---

## Executive Summary

This document outlines the plan to refactor OmniIntelligence from the current **1-container-per-node** architecture to the new **Runtime Host** architecture. This refactoring will:

- Reduce container count from **10+ containers** to **2-3 containers**
- Reduce memory footprint from **~1.5GB** to **~300MB**
- Remove all direct I/O from OmniIntelligence nodes
- Enable nodes to be pure business logic with injected dependencies from `omnibase_infra`

---

## Why This Architecture Matters

This architecture ensures:

- **OmniIntelligence is portable and testable** - nodes can run with mock handlers
- **I/O is centralized and controlled** - all external calls go through handlers
- **Core logic is decoupled from infra** - business logic has no infrastructure dependencies
- **Runtime Host can scale independently of node logic** - horizontal scaling without code changes

---

## Repository Boundaries

### What Belongs Where

| Repository | Responsibility | Contains |
|------------|----------------|----------|
| `omnibase_core` | Pure runtime logic | `NodeRuntime`, `NodeInstance`, Pydantic models, contracts |
| `omnibase_spi` | Protocol interfaces only | `IVectorStoreHandler`, `IEmbeddingHandler`, `ProtocolEventBus`, etc. (no implementations, no I/O) |
| `omnibase_infra` | Concrete handlers, runtime host | `QdrantVectorHandler`, `KafkaEventBus`, `BaseRuntimeHostProcess`, container entrypoints |
| `omniintelligence` | Application layer | Node contracts, domain logic, node registry, scenario configs |

### Critical Rule

> **OmniIntelligence MUST NOT contain**: Raw Kafka clients, DB clients, HTTP clients, or any direct I/O library imports in nodes.

### Architectural Guarantees

**OmniIntelligence nodes MUST only depend on:**
- Base node classes (`NodeCompute`, `NodeEffect`, `NodeReducer`, `NodeOrchestrator`)
- Pydantic models for inputs/outputs
- SPI handler interfaces (never concrete handlers)

**OmniIntelligence nodes may NEVER:**
- Import from `omnibase_infra`
- Import from `confluent_kafka`, `asyncpg`, `qdrant_client`, `neo4j`, `httpx`
- Instantiate I/O clients directly

**OmniIntelligence must have ZERO protocol definitions.** All protocols belong in `omnibase_spi` and are consumed directly via imports.

### Correct Placement Table

| Component | WRONG Location | CORRECT Location |
|-----------|----------------|------------------|
| `IVectorStoreHandler` protocol | `omniintelligence/protocols/` | `omnibase_spi/handlers/` |
| `IEmbeddingHandler` protocol | `omniintelligence/protocols/` | `omnibase_spi/handlers/` |
| `ProtocolEventBus` | `omniintelligence/` | `omnibase_spi/` |
| `QdrantVectorHandler` impl | `omniintelligence/handlers/` | `omnibase_infra/handlers/` |
| `KafkaEventBus` impl | `omniintelligence/` | `omnibase_infra/` |
| `BaseRuntimeHostProcess` | `omniintelligence/runtime/` | `omnibase_infra/runtime/` |
| `IntelligenceNodeRegistry` | — | `omniintelligence/runtime/` ✓ |
| `IntelligenceRuntimeConfig` | — | `omniintelligence/runtime/` ✓ |

---

## Current State Analysis

### Node Inventory (17 nodes)

| Type | Count | Nodes |
|------|-------|-------|
| **COMPUTE** | 8 | vectorization, quality_scoring, entity_extraction, relationship_detection, intent_classifier, context_keyword_extractor, success_criteria_matcher, execution_trace_parser |
| **EFFECT** | 5 | kafka_event, qdrant_vector, memgraph_graph, postgres_pattern, intelligence_adapter |
| **ORCHESTRATOR** | 2 | intelligence_orchestrator, pattern_assembler_orchestrator |
| **REDUCER** | 1 | intelligence_reducer |

### Current Resource Usage

| Metric | Current | Target |
|--------|---------|--------|
| Containers | 10+ | 2-3 |
| Kafka connections | 10+ | 1-3 |
| Memory | ~1.5GB | ~300MB |
| DB connection pools | Per-node | Shared |

### I/O Operations to Extract (to omnibase_infra)

| Handler Protocol (SPI) | Handler Impl (Infra) | Used By Nodes |
|------------------------|----------------------|---------------|
| `IVectorStoreHandler` | `QdrantVectorHandler` | qdrant_vector |
| `IGraphDatabaseHandler` | `MemgraphGraphHandler` | memgraph_graph |
| `IRelationalDatabaseHandler` | `AsyncpgDatabaseHandler` | postgres_pattern, intelligence_reducer |
| `IEmbeddingHandler` | `OpenAIEmbeddingHandler`, `LocalEmbeddingHandler` | vectorization_compute |
| `IKafkaProducerHandler` | `KafkaProducerHandler` | kafka_event (for explicit publish operations) |

> **Note**: `IKafkaConsumerHandler` is NOT used by OmniIntelligence nodes. Event consumption is handled exclusively by `RuntimeHostProcess` via `ProtocolEventBus` (`KafkaEventBus` in omnibase_infra).

---

## Target Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     RuntimeHostProcess (omnibase_infra)                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │              ProtocolEventBus / KafkaEventBus (infra)             │  │
│  │      Consumes Kafka → wraps into ModelOnexEnvelope → routes       │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                              │                                          │
│                              ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    NodeRuntime (omnibase_core)                    │  │
│  │     Does NOT own event bus loop. Receives envelopes from host.   │  │
│  ├───────────────────────────────────────────────────────────────────┤  │
│  │                                                                   │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │  │
│  │  │ NodeInstance│  │ NodeInstance│  │ NodeInstance│  ...          │  │
│  │  │ (vectorize) │  │ (quality)   │  │ (entity)    │               │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘               │  │
│  │                                                                   │  │
│  │  Node classes from omniintelligence (pure logic, no I/O)         │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    Handler Pool (omnibase_infra)                  │  │
│  ├───────────────────────────────────────────────────────────────────┤  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ │  │
│  │  │ Qdrant   │ │ Memgraph │ │ Postgres │ │Embedding │ │ Kafka   │ │  │
│  │  │ Handler  │ │ Handler  │ │ Handler  │ │ Handler  │ │Producer │ │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └─────────┘ │  │
│  │  (implements SPI protocols - for node-initiated operations)      │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  Config from: omniintelligence/runtime/IntelligenceRuntimeConfig        │
│  Nodes from:  omniintelligence/runtime/IntelligenceNodeRegistry         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Package | Responsibility |
|-----------|---------|----------------|
| `BaseRuntimeHostProcess` | omnibase_infra | Process lifecycle, handler wiring, event bus consumption |
| `ProtocolEventBus` | omnibase_spi | Event bus interface (Kafka abstraction) |
| `KafkaEventBus` | omnibase_infra | Kafka consumer implementation, envelope wrapping |
| `NodeRuntime` | omnibase_core | Node lifecycle, dependency injection, envelope routing |
| `NodeInstance` | omnibase_core | Individual node execution context |
| Handler protocols | omnibase_spi | Interfaces only (e.g., `IVectorStoreHandler`) |
| Handler implementations | omnibase_infra | Concrete I/O (e.g., `QdrantVectorHandler`) |
| `IntelligenceNodeRegistry` | omniintelligence | Which nodes exist, their contracts |
| `IntelligenceRuntimeConfig` | omniintelligence | Which handlers to bind, topics, config |

### Critical: NodeRuntime Does NOT Own Event Bus

> **NodeRuntime does NOT own the event bus loop.** `RuntimeHostProcess` drives `NodeRuntime` by passing envelopes from `ProtocolEventBus` (`KafkaEventBus`). NodeRuntime is purely an in-memory orchestrator.

### Event Bus vs Kafka Handler (Distinct Concepts)

| Concept | Abstraction | Location | Purpose |
|---------|-------------|----------|---------|
| Event Bus | `ProtocolEventBus` / `KafkaEventBus` | SPI / Infra | Transport - feeds envelopes into RuntimeHost |
| Kafka Producer Handler | `IKafkaProducerHandler` | SPI / Infra | Operation - nodes explicitly publish events |

These are distinct concerns: **event_bus** is transport (consumption), **kafka_handler** is an operation (production).

---

## Naming Convention

### Standard (Contract-Driven) - DEFAULT

```python
NodeEffect           # Base class for effect nodes
NodeCompute          # Base class for compute nodes
NodeReducer          # Base class for reducer nodes
NodeOrchestrator     # Base class for orchestrator nodes

# Implementations
NodeQdrantVectorEffect
NodeKafkaEventEffect
NodeVectorizationCompute
NodeIntelligenceReducer
NodeIntelligenceOrchestrator
```

---

## Refactoring Phases

### Phase 0: Prerequisites (Blocked)

**Status**: OmniIntelligence is blocked on omnibase_core/spi work.

**Dependencies** (work happens in other repos):
- [ ] `omnibase_core`: Fix Core→SPI dependency inversion
- [ ] `omnibase_core`: Implement `NodeRuntime` class
- [ ] `omnibase_core`: Implement `NodeInstance` class
- [ ] `omnibase_spi`: Define handler protocols (Phase 1)
- [ ] `omnibase_spi`: Define `ProtocolEventBus`
- [ ] `omnibase_infra`: Implement handlers (Phase 2)
- [ ] `omnibase_infra`: Implement `KafkaEventBus`

**No omniintelligence changes in this phase.**

---

### Phase 1: Handler Protocol Definitions

**Goal**: Define handler interfaces in `omnibase_spi`.

**Location**: `omnibase_spi/handlers/`

**Protocols to Define**:

| Protocol | File |
|----------|------|
| `IVectorStoreHandler` | `omnibase_spi/handlers/vector_store.py` |
| `IGraphDatabaseHandler` | `omnibase_spi/handlers/graph_database.py` |
| `IRelationalDatabaseHandler` | `omnibase_spi/handlers/relational_database.py` |
| `IEmbeddingHandler` | `omnibase_spi/handlers/embedding.py` |
| `IKafkaProducerHandler` | `omnibase_spi/handlers/kafka.py` |
| `ProtocolEventBus` | `omnibase_spi/event_bus.py` |

> **Note**: `IKafkaConsumerHandler` is NOT needed by OmniIntelligence. Event consumption is handled by `ProtocolEventBus` in RuntimeHostProcess.

**Shared Models** (in `omnibase_core`):
- Config models: `VectorStoreConfig`, `EmbeddingConfig`, etc.
- Result models: `SearchResult`, `EmbeddingResult`, etc.

**Deliverables** (in omnibase_spi):
- [ ] `omnibase_spi/handlers/vector_store.py`
- [ ] `omnibase_spi/handlers/graph_database.py`
- [ ] `omnibase_spi/handlers/relational_database.py`
- [ ] `omnibase_spi/handlers/embedding.py`
- [ ] `omnibase_spi/handlers/kafka.py` (producer only)
- [ ] `omnibase_spi/event_bus.py`

**OmniIntelligence work**: None. Import protocols from SPI when available.

---

### Phase 2: Handler Implementations

**Goal**: Implement handlers in `omnibase_infra`.

**Location**: `omnibase_infra/handlers/`

**Handlers to Implement**:

| Handler | Implements | Library |
|---------|------------|---------|
| `QdrantVectorHandler` | `IVectorStoreHandler` | qdrant-client |
| `AsyncpgDatabaseHandler` | `IRelationalDatabaseHandler` | asyncpg |
| `MemgraphGraphHandler` | `IGraphDatabaseHandler` | neo4j |
| `OpenAIEmbeddingHandler` | `IEmbeddingHandler` | openai |
| `LocalEmbeddingHandler` | `IEmbeddingHandler` | sentence-transformers |
| `KafkaProducerHandler` | `IKafkaProducerHandler` | confluent-kafka |
| `KafkaEventBus` | `ProtocolEventBus` | confluent-kafka |

> **Note**: `KafkaEventBus` implements `ProtocolEventBus`, not `ProtocolHandler`. It is the transport feeding envelopes into NodeRuntime, not a per-operation handler.

**Deliverables** (in omnibase_infra):
- [ ] Handler implementations with full test coverage
- [ ] Connection pooling and lifecycle management
- [ ] Retry and circuit breaker integration
- [ ] Metrics and observability hooks

**OmniIntelligence work**: None. Reference handlers via SPI protocols only.

---

### Phase 3: Node Refactoring - Compute Nodes

**Goal**: Refactor compute nodes to accept injected handlers via SPI protocols.

**Nodes** (8 total):
1. `NodeVectorizationCompute` - Needs `IEmbeddingHandler`
2. `NodeQualityScoringCompute` - Pure, no changes needed
3. `NodeEntityExtractionCompute` - Pure, no changes needed
4. `NodeRelationshipDetectionCompute` - Pure, no changes needed
5. `NodeIntentClassifierCompute` - Pure, no changes needed
6. `NodeContextKeywordExtractorCompute` - Pure, no changes needed
7. `NodeSuccessCriteriaMatcherCompute` - Pure, no changes needed
8. `NodeExecutionTraceParserCompute` - Pure, no changes needed

**Pattern** (correct):
```python
from omnibase_spi.handlers.embedding import IEmbeddingHandler

class NodeVectorizationCompute(NodeCompute[VectorizationInput, VectorizationOutput]):
    """Vectorization compute node - no direct I/O."""

    def __init__(
        self,
        config: VectorizationConfig,
        embedding_handler: IEmbeddingHandler,  # Injected from SPI
    ):
        self._config = config
        self._embedding_handler = embedding_handler

    async def compute(self, input: VectorizationInput) -> VectorizationOutput:
        # Node talks in terms of "embedding service" - doesn't know if OpenAI or local
        embeddings = await self._embedding_handler.embed_texts(
            texts=input.texts,
            model_name=self._config.model_name,
        )
        return VectorizationOutput(embeddings=embeddings)
```

**Acceptance Criteria**:
- [ ] No OmniIntelligence node imports `openai`, `sentence_transformers`, or `httpx` directly
- [ ] All external calls go through SPI handler interfaces
- [ ] Existing functionality maintained

---

### Phase 4: Node Refactoring - Effect Nodes

**Goal**: Extract all I/O from effect nodes into handlers.

**Nodes** (5 total):

#### 4.1 NodeKafkaEventEffect
- Remove: `from confluent_kafka import Producer`
- Inject: `IKafkaProducerHandler` (from SPI) - optional, for explicit publish
- Keep: Event envelope creation, serialization, circuit breaker logic

#### 4.2 NodeQdrantVectorEffect
- Remove: `from qdrant_client import AsyncQdrantClient`
- Inject: `IVectorStoreHandler` (from SPI)
- Keep: Dimension validation, collection logic, result transformation

#### 4.3 NodeMemgraphGraphEffect
- Remove: `from neo4j import AsyncGraphDatabase`
- Inject: `IGraphDatabaseHandler` (from SPI)
- Keep: Cypher query construction, entity/relationship models

#### 4.4 NodePostgresPatternEffect
- Remove: `import asyncpg`
- Inject: `IRelationalDatabaseHandler` (from SPI)
- Keep: SQL query construction, pattern ID generation, hashing

#### 4.5 NodeIntelligenceAdapterEffect
- Remove: ALL Kafka consumer logic (polling, offset commit, subscribe)
- Remove: `from confluent_kafka import Consumer, Producer`
- Inject: `IKafkaProducerHandler` (optional, for explicit publish)
- Inject: `IEmbeddingHandler` (if needed)
- Keep: Payload transformation and event routing (no polling)

> **Critical**: `NodeIntelligenceAdapterEffect` is an application-level adapter, NOT a bus adapter. It MUST NOT poll Kafka, commit offsets, or subscribe to topics. All event consumption is handled by `RuntimeHostProcess` via `ProtocolEventBus`.

**Acceptance Criteria** (HARD REQUIREMENT):
- [ ] No OmniIntelligence node imports `confluent_kafka`
- [ ] No OmniIntelligence node imports `qdrant_client`
- [ ] No OmniIntelligence node imports `neo4j`
- [ ] No OmniIntelligence node imports `asyncpg`
- [ ] No OmniIntelligence node imports `httpx`
- [ ] All I/O goes through SPI handler interfaces
- [ ] No node runs a Kafka consumer loop

---

### Phase 5: Node Refactoring - Orchestrator & Reducer

**Goal**: Refactor coordination nodes.

#### 5.1 NodeIntelligenceOrchestrator
- Current: Loads YAML workflows from disk
- Change: Accept workflow contracts via injection
- Keep: Workflow execution logic, step coordination

#### 5.2 NodeIntelligenceReducer
- Remove: Direct PostgreSQL access
- Inject: `IRelationalDatabaseHandler` (from SPI)
- Keep: FSM transition logic, intent emission

**Deliverables**:
- [ ] Refactored orchestrator with contract injection
- [ ] Refactored reducer with handler injection
- [ ] FSM contract loading externalized

---

### Phase 6: Runtime Host Integration

**Goal**: Wire OmniIntelligence nodes into the shared Runtime Host from `omnibase_infra`.

**In `omnibase_infra`** (not omniintelligence):
- `BaseRuntimeHostProcess` - generic runtime host
- Handler pooling and lifecycle
- `KafkaEventBus` - event bus consumption
- Generic health endpoint
- Event loop management

**In `omniintelligence`** (application-specific):
```
src/omniintelligence/
└── runtime/
    ├── __init__.py
    ├── node_registry.py              # IntelligenceNodeRegistry
    ├── runtime_config.py             # IntelligenceRuntimeConfig
    └── main.py                       # Thin entrypoint
```

**OmniIntelligence responsibilities**:
- `IntelligenceNodeRegistry` - which NodeInstances exist
- `IntelligenceRuntimeConfig` - which handlers to bind, topics, contracts
- `main.py` - thin entrypoint that calls `BaseRuntimeHostProcess`

**OmniIntelligence does NOT own**:
- Event loop implementation
- Event bus consumption (Kafka polling)
- Handler pool management
- Connection lifecycle

**Runtime Contract Clarification**:

```yaml
# event_bus refers to ProtocolEventBus (KafkaEventBus in infra)
# This is the transport that feeds envelopes into RuntimeHost
event_bus:
  enabled: true
  bootstrap_servers: "${KAFKA_BOOTSTRAP_SERVERS}"
  consumer_group: "intelligence-runtime"
  topics:
    commands: "onex.intelligence.cmd.v1"
    events: "onex.intelligence.evt.v1"

# handlers.kafka refers to explicit KafkaProducerHandler
# This is for nodes that need to explicitly publish events
handlers:
  - handler_type: kafka_producer
    enabled: true
    config:
      bootstrap_servers: "${KAFKA_BOOTSTRAP_SERVERS}"
```

**Deliverables**:
- [ ] `IntelligenceNodeRegistry` class
- [ ] `IntelligenceRuntimeConfig` class
- [ ] `main.py` entrypoint using `BaseRuntimeHostProcess`

---

### Phase 7: Docker Consolidation

**Goal**: Consolidate OmniIntelligence nodes into 2-3 runtime host containers.

**Out of scope**:
- Kafka, Postgres, Qdrant, Memgraph deployment topology
- Those remain in shared infra docker-compose

**Current** (10+ services):
```
deployment/docker/
├── Dockerfile.compute
├── Dockerfile.effect
├── Dockerfile.orchestrator
├── Dockerfile.reducer
└── docker-compose.nodes.yml  # 10 services
```

**Target** (2-3 services):
```
deployment/docker/
├── Dockerfile.runtime-host           # Single runtime host image
├── docker-compose.runtime.yml        # 2-3 services
└── archived/                         # Old files for reference
```

**Container Topology**:

| Container | Nodes | Description |
|-----------|-------|-------------|
| `intelligence-runtime-main` | orchestrator, reducer, all compute | Main processing |
| `intelligence-runtime-effects` | all effect nodes | I/O heavy nodes |

All data plane dependencies (Kafka, Qdrant, etc.) are consumed via handlers - not part of these images.

**Deliverables**:
- [ ] Single runtime host Dockerfile
- [ ] New docker-compose with 2-3 services
- [ ] Environment variable configuration
- [ ] Health check integration

---

### Phase 8: Testing & Validation

**Goal**: Comprehensive testing of new architecture.

**Test Categories**:

1. **Unit Tests** (in each repo)
   - [ ] Handler protocol compliance tests (omnibase_spi)
   - [ ] Handler implementation tests (omnibase_infra)
   - [ ] Node logic tests with mocked handlers (omniintelligence)

2. **Integration Tests**
   - [ ] Handler tests with real services (testcontainers)
   - [ ] Node tests with real handlers
   - [ ] End-to-end workflow tests

3. **Performance Tests**
   - [ ] Memory footprint comparison
   - [ ] Throughput comparison
   - [ ] Connection pool efficiency

**Deliverables**:
- [ ] >80% test coverage
- [ ] Performance benchmark report
- [ ] Deployment runbook

---

### Phase 9: Cleanup

**Goal**: Remove deprecated code after validation.

**Cleanup Tasks**:
- [ ] Remove per-node Dockerfiles
- [ ] Remove any remaining direct I/O imports from nodes
- [ ] Update documentation
- [ ] Archive source references

**Timeline**: After 2 weeks of production validation

---

## Dependency Graph

```
Phase 0 (omnibase_core / omnibase_spi) ────────────────────┐
                                                           │
Phase 1 (Protocols in omnibase_spi) ──────────────────────┤
         │                                                 │
         ▼                                                 │
Phase 2 (Handlers in omnibase_infra) ─────────────────────┤
         │                                                 │
         ├──────────────┬──────────────┐                   │
         ▼              ▼              ▼                   │
Phase 3 (Compute)  Phase 4 (Effect)  Phase 5 (Orch/Red)   │ ← omniintelligence
         │              │              │                   │
         └──────────────┴──────────────┘                   │
                        │                                  │
                        ▼                                  │
        Phase 6 (Runtime Host wiring in omniintelligence) ◄┘
                        │
                        ▼
                Phase 7 (Docker)
                        │
                        ▼
                Phase 8 (Testing)
                        │
                        ▼
                Phase 9 (Cleanup)
```

---

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| omnibase_core/spi delays | HIGH | MEDIUM | OmniIntelligence is blocked - be explicit about this |
| Breaking changes | HIGH | LOW | Feature flags, phased rollout |
| Performance regression | MEDIUM | LOW | Benchmark before/after, connection pooling |
| Handler complexity | MEDIUM | MEDIUM | Start with simple handlers (Qdrant), iterate |
| Testing gaps | MEDIUM | MEDIUM | Require >80% coverage, integration tests |

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Container count | ≤3 (from 10+) |
| Memory footprint | ≤400MB (from ~1.5GB) |
| Test coverage | ≥80% |
| Zero I/O in OmniIntelligence nodes | All I/O via SPI handlers |
| No direct library imports | No `confluent_kafka`, `qdrant_client`, `neo4j`, `asyncpg`, `httpx` in nodes |
| No Kafka consumer in nodes | All consumption via RuntimeHostProcess |

---

## Appendix A: OmniIntelligence File Changes

### New Files (Phase 6 only)
```
src/omniintelligence/
└── runtime/
    ├── __init__.py
    ├── node_registry.py         # IntelligenceNodeRegistry
    ├── runtime_config.py        # IntelligenceRuntimeConfig
    └── main.py                  # Thin entrypoint
```

### Modified Files (Phases 3-5)
```
src/omniintelligence/nodes/
├── kafka_event_effect/v1_0_0/effect.py      # Remove confluent_kafka import
├── qdrant_vector_effect/v1_0_0/effect.py    # Remove qdrant_client import
├── memgraph_graph_effect/v1_0_0/effect.py   # Remove neo4j import
├── postgres_pattern_effect/v1_0_0/effect.py # Remove asyncpg import
├── intelligence_adapter/node_*.py           # Remove ALL Kafka consumer logic
├── vectorization_compute/v1_0_0/compute.py  # Use IEmbeddingHandler
├── intelligence_reducer/v1_0_0/reducer.py   # Use IRelationalDatabaseHandler
└── intelligence_orchestrator/v1_0_0/*.py    # Contract injection
```

### NOT in OmniIntelligence
```
# These DO NOT belong here - OmniIntelligence has ZERO protocol definitions:
src/omniintelligence/protocols/     # WRONG - goes to omnibase_spi
src/omniintelligence/handlers/      # WRONG - goes to omnibase_infra
```

### Deleted Files (Phase 9)
```
deployment/docker/
├── Dockerfile.compute
├── Dockerfile.effect
├── Dockerfile.orchestrator
├── Dockerfile.reducer
└── docker-compose.nodes.yml
```

---

## Appendix B: Code Examples

### Correct: Effect Node with Injected Handler
```python
# In omniintelligence - node has NO I/O imports
from omnibase_spi.handlers.vector_store import IVectorStoreHandler

class NodeQdrantVectorEffect(NodeEffect[VectorInput, VectorOutput]):
    """Vector store effect - delegates all I/O to handler."""

    def __init__(
        self,
        config: VectorConfig,
        vector_handler: IVectorStoreHandler,  # Injected
    ):
        self._config = config
        self._vector_handler = vector_handler  # From omnibase_infra via DI

    async def execute(self, input: VectorInput) -> VectorOutput:
        # Pure logic: validation
        self._validate_dimensions(input.embeddings)

        # I/O delegated to handler
        result = await self._vector_handler.upsert(
            collection=self._config.collection,
            id=input.id,
            vector=input.embeddings,
            metadata=input.metadata,
        )

        return VectorOutput(success=result.success)
```

### Correct: Compute Node with Embedding Handler
```python
# In omniintelligence - node has NO OpenAI/httpx imports
from omnibase_spi.handlers.embedding import IEmbeddingHandler

class NodeVectorizationCompute(NodeCompute[VectorizationInput, VectorizationOutput]):
    """Vectorization compute - doesn't know if OpenAI or local."""

    def __init__(
        self,
        config: VectorizationConfig,
        embedding_handler: IEmbeddingHandler,  # Could be OpenAI, local, or mock
    ):
        self._config = config
        self._embedding_handler = embedding_handler

    async def compute(self, input: VectorizationInput) -> VectorizationOutput:
        embeddings = await self._embedding_handler.embed_texts(
            texts=input.texts,
            model_name=self._config.model_name,
        )
        return VectorizationOutput(embeddings=embeddings)
```

### WRONG: Node with Kafka Consumer (DO NOT DO THIS)
```python
# WRONG - OmniIntelligence nodes must NEVER consume Kafka
from confluent_kafka import Consumer  # ❌ NEVER import this

class NodeIntelligenceAdapterEffect:
    def __init__(self):
        self._consumer = Consumer(...)  # ❌ NEVER do this

    async def _consume_loop(self):  # ❌ NEVER have a consume loop
        while True:
            msg = self._consumer.poll(1.0)  # ❌ Polling belongs in RuntimeHost
```

---

## Appendix C: Event Consumption Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                    RuntimeHostProcess (infra)                    │
│                                                                  │
│  1. KafkaEventBus.poll() → raw Kafka message                     │
│  2. Wrap into ModelOnexEnvelope                                  │
│  3. Call NodeRuntime.route_envelope(envelope)                    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                      NodeRuntime (core)                          │
│                                                                  │
│  4. Route envelope to appropriate NodeInstance                   │
│  5. NodeInstance.handle(envelope)                                │
│  6. Node executes pure logic, delegates I/O to handlers          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                 NodeInstance (omniintelligence)                  │
│                                                                  │
│  7. Transform payload (pure logic)                               │
│  8. If needs I/O: call injected handler (e.g., IVectorHandler)   │
│  9. Return result envelope                                       │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

> **OmniIntelligence does not implement a Kafka consumer loop.** All event consumption is performed by `RuntimeHostProcess` via `ProtocolEventBus` (`KafkaEventBus` implementation in `omnibase_infra`). OmniIntelligence nodes never interact directly with `KafkaConsumerHandler`.

---

## Appendix D: Related Documents

| Document | Location | Purpose |
|----------|----------|---------|
| MVP Plan | `/docs/MVP_PLAN.md` | Original implementation plan |
| Effect Nodes Spec | `/docs/specs/DECLARATIVE_EFFECT_NODES_SPEC.md` | Contract-driven node specification |
| Core Dependency Refactoring | `omnibase_core/docs/DEPENDENCY_REFACTORING_PLAN.md` | Core→SPI dependency fix |
| Core Runtime Phased Plan | `omnibase_core/docs/MINIMAL_RUNTIME_PHASED_PLAN.md` | Runtime host implementation |
| Infra Effect Nodes Plan | `omnibase_infra/docs/DECLARATIVE_EFFECT_NODES_PLAN.md` | Handler placement rules |
| SPI Protocol Interfaces | `omnibase_spi/docs/PROTOCOL_INTERFACES_PLAN.md` | Handler protocol definitions |
