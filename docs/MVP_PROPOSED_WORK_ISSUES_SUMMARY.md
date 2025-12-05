# OmniIntelligence Runtime Host Migration - Summary

**Target**: v0.5.0 | **Total Issues**: 56 (35 MVP, 16 Beta, 5 GA)

---

## TL;DR - What This Migration Does

**Why this migration exists:**
- **Autonomy → Determinism**: Nodes become pure functions, behavior is predictable
- **Zero I/O → Safety**: Nodes can't cause side effects, easier to test and reason about
- **Consolidation → Reliability**: Single Runtime Host simplifies debugging, reduces failure modes

- **Replaces** 10+ per-node Docker containers with 2-3 Runtime Host containers
- **Removes** all Kafka consumer loops from nodes (Runtime Host handles consumption)
- **Removes** all direct I/O (DB, Qdrant, Memgraph, HTTP) from nodes
- **Introduces** handler injection via SPI protocols
- **Introduces** contract-based node registration and validation
- **Reduces** memory from ~1.5GB to ≤400MB, containers from 10+ to ≤3
- **Enforces** pure compute nodes, effect nodes with injected handlers only

---

## How to Read This Document

**Reading time**: ~30 minutes (full) | ~5 minutes (essentials)

**Essential reading** (5 min):
1. TL;DR (above) - What this migration does
2. Architectural Invariants - The non-negotiable rules
3. Node Behavioral Boundaries - What each node type can/cannot do

**For new contributors**:
1. Start with TL;DR → Glossary → Architectural Invariants
2. Read "For External Contributors" section
3. Review "How to Write a New Node" step-by-step

**For active developers**:
1. Jump to the Phase relevant to your current work
2. Reference Node Migration Dashboard for status
3. Use Node Compliance Checklist when completing work

**Quick reference sections**:
- Glossary: Term definitions
- Code Examples: Before/After patterns
- Runtime Profiles: Container deployment options
- Risks & Unknowns: What to watch for

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Runtime Host                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  EventBus    │───▶│  NodeRuntime │───▶│ NodeInstance │  │
│  │  (Kafka)     │    │  (routing)   │    │ (execution)  │  │
│  └──────────────┘    └──────────────┘    └──────┬───────┘  │
│                                                  │          │
│                                          ┌───────▼───────┐  │
│                                          │   Handlers    │  │
│                                          │ (SPI impls)   │  │
│                                          └───────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Architectural Invariants

**These rules are non-negotiable:**

1. **Nodes NEVER talk to external services directly** - no DB, HTTP, Kafka, file I/O
2. **Nodes NEVER read environment variables** - config injected via constructor
3. **Nodes NEVER inspect envelope transport metadata** - prevents transport coupling
   **Examples**:
   - Forbidden: `msg.headers()`, `msg.partition()`, `msg.offset()` - Kafka transport metadata
   - Forbidden: `envelope.kafka_timestamp`, `envelope.consumer_group` - transport details
   - Allowed: `envelope.payload`, `envelope.correlation_id`, `envelope.node_id` - business data
   - Allowed: `context.trace_id`, `context.timestamp` - provided by EnvelopeContext
4. **Runtime Host is the ONLY Kafka consumer** - no competing consumers
5. **Handlers MUST be stateless** except connection pools
6. **Envelope schema frozen per minor version** - prevents contract drift
7. **Effect nodes MUST NOT retry internally** - retries belong to handlers/Runtime Host
8. **Orchestrators MUST produce deterministic output** for identical inputs
9. **Reducers MUST NOT mutate incoming payloads**

---

## What Runtime Host Replaces

| Before (Legacy) | After (Runtime Host) |
|-----------------|----------------------|
| Per-node `main.py` entrypoints | Single `RuntimeHostProcess` entrypoint |
| Per-node Kafka consumers | Centralized `ProtocolEventBus` |
| Direct DB/Qdrant/Memgraph imports | Injected `IHandler` protocols |
| 10+ Docker containers | 2-3 Runtime Host containers |
| Node-managed connections | Handler-managed connection pools |
| Implicit dependencies | Explicit contract declarations |

---

## Glossary

| Term | Definition |
|------|------------|
| **Runtime Host** | Process that loads nodes, manages handlers, routes envelopes |
| **NodeRuntime** | Core engine that executes nodes (in omnibase_core) |
| **NodeInstance** | Instantiated node with injected handlers |
| **Compute Node** | Pure data transformation, no I/O |
| **Effect Node** | Performs I/O via injected handlers |
| **Orchestrator** | Coordinates multi-step workflows |
| **Reducer** | Manages state/FSM transitions |
| **Handler** | I/O adapter implementing SPI protocol |
| **Protocol** | Interface contract (e.g., `IVectorStoreHandler`) |
| **EventBus** | Kafka abstraction for envelope consumption |
| **Contract** | YAML declaring node dependencies/subscriptions |
| **Profile** | Node subset for container deployment |

---

## Envelope Schema (Canonical Example)

This is the canonical envelope structure all nodes receive and produce:

```json
{
  "envelope_version": "1.0.0",
  "envelope_id": "550e8400-e29b-41d4-a716-446655440000",
  "correlation_id": "req-abc-123-def-456",
  "causation_id": "evt-xyz-789",
  "node_id": "vectorization_compute",
  "timestamp": "2025-12-03T10:15:30.123Z",
  "payload": {
    "code": "def example(): pass",
    "language": "python",
    "metadata": {}
  },
  "context": {
    "trace_id": "trace-123",
    "span_id": "span-456",
    "source_topic": "intelligence.code-analysis-requested.v1",
    "profile": "main"
  }
}
```

**Field requirements**:
| Field | Required | Mutable | Description |
|-------|----------|---------|-------------|
| `envelope_version` | Yes | No | Schema version (frozen per minor release) |
| `envelope_id` | Yes | No | Unique envelope identifier |
| `correlation_id` | Yes | No | Request correlation for tracing |
| `causation_id` | No | No | ID of event that caused this envelope |
| `node_id` | Yes | No | Target node identifier |
| `timestamp` | Yes | No | ISO 8601 creation timestamp |
| `payload` | Yes | **Yes** | Business data (node-specific) |
| `context` | Yes | No | Execution context (read-only to nodes) |

**What nodes can access**:
- `payload` - Read and transform
- `correlation_id`, `node_id` - Read only
- `context.trace_id`, `context.span_id` - For logging
- `context.source_topic` - Transport metadata, forbidden

---

## Node Behavioral Boundaries

| Kind | Allowed | Forbidden |
|------|---------|-----------|
| **COMPUTE** | Pure transforms, calculations, data mapping | Any I/O, handlers, state, side effects |
| **EFFECT** | I/O via injected handlers only | Direct imports, retries, consumer loops |
| **ORCHESTRATOR** | Coordinate compute/effect nodes, workflow logic | Direct I/O, handler calls, state mutation |
| **REDUCER** | FSM transitions, state emission | Side effects, direct DB access, I/O |

**The rule**: If you're unsure whether code belongs in a node, it probably belongs in a handler.

---

## Code Examples: Before & After

### Wrong: Effect Node with Direct I/O

```python
# BAD - direct imports, direct connections
from qdrant_client import QdrantClient
import os

class BadVectorEffect:
    def __init__(self):
        self.client = QdrantClient(os.getenv("QDRANT_URL"))  # Direct I/O

    async def execute(self, input):
        return await self.client.upsert(...)  # Direct call
```

### Correct: Effect Node with Handler Injection

```python
# GOOD - handler injected, no direct I/O
from omnibase_spi.handlers import IVectorStoreHandler

class GoodVectorEffect(NodeEffect):
    def __init__(self, vector_handler: IVectorStoreHandler):
        self._handler = vector_handler  # Injected

    async def execute(self, input):
        return await self._handler.upsert(...)  # Via handler
```

### Correct: Pure Compute Node

```python
# GOOD - pure transformation, no I/O
class QualityScoringCompute(NodeCompute):
    def __init__(self, config: ScoringConfig):
        self._config = config  # Config injected

    async def compute(self, input: CodeInput) -> ScoreOutput:
        score = self._calculate_score(input.code)  # Pure logic
        return ScoreOutput(score=score)
```

---

## Legend

| Term | Meaning |
|------|---------|
| **pure** | No I/O, no handlers needed |
| **optional** | Handler can be absent; node degrades gracefully |
| **required** | Handler must be present or node fails to load |
| **needs injection** | Currently has direct I/O, must be refactored |

---

## Breaking Change Details

- Old node entrypoints (`main.py`, per-node containers) **will be removed**
- All Kafka consumer logic in nodes **must be deleted entirely**
- Legacy orchestrator patterns **must be rewritten** for handler injection
- Any tool assuming direct DB/Qdrant/Memgraph access **must be updated**

### Cutover Strategy

**"Hard cutover" means:**
- Runtime path switchover is atomic - only Runtime Host consumes Kafka after cutover
- No parallel operation of old and new consumers (causes message duplication)
- Legacy code/Dockerfiles remain during 2-week validation window for potential rollback

**Rollback policy:**
- Rollback is supported during 2-week validation window only
- Rollback procedure: redeploy v0.4.x artifacts, disable Runtime Host profiles
- After validation window closes: fix-forward only, no rollback supported
- Legacy artifacts deleted in Phase 9 after validation passes

---

## NodeMetadata Specification

**Canonical name**: `NodeMetadata` (lives in `omnibase_core/runtime`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `node_id` | str | Yes | Unique identifier (e.g., `vectorization_compute`) |
| `version` | str | Yes | Semver (e.g., `1.1.0`) |
| `kind` | enum | Yes | `COMPUTE`, `EFFECT`, `ORCHESTRATOR`, `REDUCER` |
| `fingerprint` | str | Yes | `<semver>:<sha256_12>` (e.g., `1.1.0:a1b2c3d4e5f6`) |
| `contract_path` | str | Yes | Relative path to YAML contract |
| `handlers_required` | list[str] | No | Handler types this node requires |
| `handlers_optional` | list[str] | No | Handler types this node can optionally use |
| `profile_tags` | list[str] | No | Profiles this node belongs to |
| `concurrency` | enum | Yes | `parallelizable`, `sequential`, `strictly_sequential` |

**Used by**: Registry, host boot, healthchecks, profile selection, contract validation

---

## Contract Fingerprint Rules

**Format**: `<semver>:<sha256_12>`
- Example: `2.0.0:a1b2c3d4e5f6`
- Hash is first 12 chars of SHA256 of contract structure

**Where fingerprints appear**:
- Contract YAML files (`fingerprint` field)
- `NodeMetadata.fingerprint`
- Runtime host logs (for binding verification)

**When fingerprints must change**:
- Any change to contract structure or required fields
- Handler dependency changes
- Subscription topic changes
- **Policy**: Non-breaking semantic changes (comments, descriptions) do NOT require fingerprint change

---

## Contract Requirements (Quick Reference)

Every node contract YAML **must** contain these fields:

| Field | Type | Example | Validation |
|-------|------|---------|------------|
| `node_id` | string | `vectorization_compute` | Lowercase snake_case, ends with `_compute`/`_effect`/etc |
| `version` | semver | `1.1.0` | Valid semantic version |
| `kind` | enum | `COMPUTE` | One of: `COMPUTE`, `EFFECT`, `ORCHESTRATOR`, `REDUCER` |
| `fingerprint` | string | `1.1.0:a1b2c3d4e5f6` | `<semver>:<sha256_12>` format |
| `contract_path` | string | `nodes/vec/contracts/contract.yaml` | Valid relative path |

**Handler declaration** (required for EFFECT nodes, optional for others):

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `handlers` | list | See below | Empty list OK for pure COMPUTE |
| `handlers[].handler_type` | string | `kafka_producer` | Handler category |
| `handlers[].protocol` | string | `IKafkaProducerHandler` | SPI protocol interface |
| `handlers[].required` | bool | `true` | Fail load if missing |
| `handlers[].on_missing` | enum | `warn_and_skip` | Behavior when optional handler absent |

**Subscriptions** (required for nodes that consume events):

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `subscriptions` | list | See below | Empty list OK for compute-only nodes |
| `subscriptions[].topic` | string | `intelligence.code-analysis-requested.v1` | Kafka topic pattern |
| `subscriptions[].consumer_group` | string | `intelligence-main` | Consumer group ID |

**Metadata** (optional but recommended):

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `concurrency` | enum | `parallelizable` | `parallelizable`, `sequential`, `strictly_sequential` |
| `profile_tags` | list | `["main", "effects"]` | Which profiles include this node |
| `description` | string | `"Generates embeddings..."` | Human-readable purpose |

---

## Example Contracts

### Minimal Compute Node (Pure)

```yaml
# nodes/quality_scoring_compute/contracts/contract.yaml
node_id: quality_scoring_compute
version: "1.0.0"
kind: COMPUTE
fingerprint: "1.0.0:abc123def456"
contract_path: nodes/quality_scoring_compute/contracts/contract.yaml

description: "Calculates code quality score from metrics"

# Pure compute: no handlers needed
handlers: []

# Pure compute: no subscriptions (called by orchestrator)
subscriptions: []

concurrency: parallelizable
profile_tags:
  - main
  - local-dev

input_schema:
  type: object
  properties:
    code: { type: string }
    language: { type: string }
  required: [code, language]

output_schema:
  type: object
  properties:
    score: { type: number, minimum: 0, maximum: 100 }
    breakdown: { type: object }
  required: [score]
```

### Effect Node (With Required Handler)

```yaml
# nodes/qdrant_vector_effect/contracts/contract.yaml
node_id: qdrant_vector_effect
version: "2.0.0"
kind: EFFECT
fingerprint: "2.0.0:def456abc789"
contract_path: nodes/qdrant_vector_effect/contracts/contract.yaml

description: "Stores vectors in Qdrant via injected handler"

handlers:
  - handler_type: vector_store
    protocol: IVectorStoreHandler
    required: true
    on_missing: error  # Cannot function without vector store

  - handler_type: kafka_producer
    protocol: IKafkaProducerHandler
    required: false
    on_missing: warn_and_skip  # Can skip publishing if Kafka unavailable

subscriptions:
  - topic: intelligence.vectorization-completed.v1
    consumer_group: intelligence-effects

concurrency: parallelizable
profile_tags:
  - effects
  - local-dev

input_schema:
  type: object
  properties:
    vectors: { type: array, items: { type: array, items: { type: number } } }
    metadata: { type: object }
  required: [vectors]

output_schema:
  type: object
  properties:
    stored_count: { type: integer }
    collection: { type: string }
  required: [stored_count]
```

### Orchestrator & Reducer Contracts

Orchestrator and reducer contracts follow the same structure with additional fields:

- **Orchestrators**: Add `workflow_steps` array defining the execution graph
- **Reducers**: Add `state_machine` object defining FSM transitions

See Phase 5 issues (5.2, 5.3, 5.4) for detailed orchestrator/reducer contract specifications.

---

## Retry Semantics

| Layer | Who Handles Retries? | Allowed? | Config Location |
|-------|----------------------|----------|-----------------|
| Node (Compute/Effect/Orch/Reducer) | Node | **No** | n/a |
| Handler | Handler | **Yes** (within policy) | Handler config |
| Runtime Host | Host | **Yes** | Runtime config |

**Rules**:
- Nodes treat failures as hard failures, return error result immediately
- Handlers may retry internally (connection retries, transient failures)
- Handlers MUST surface single success/failure to node (no hidden multi-attempt)
- Runtime Host may retry envelope processing (with backoff policy)
- No hidden multi-attempt semantics visible at node boundary

---

## Optional Handler Behavior

| Handler Mode | Contract | Load Behavior | Execution Behavior |
|--------------|----------|---------------|-------------------|
| `required` | `"required": true` | Fail node load if missing | n/a (never reached) |
| `optional` | `"required": false` | Load succeeds | Node returns `HANDLER_UNAVAILABLE` or uses fallback |

**Contract syntax**:
```yaml
handlers:
  - handler_type: kafka_producer
    protocol: IKafkaProducerHandler
    required: false
    on_missing: warn_and_skip  # skip_silently | warn_and_skip | degrade | error
```

**Behaviors**:
- `skip_silently`: No log, operation skipped
- `warn_and_skip`: Log warning, operation skipped
- `degrade`: Mark node as degraded, continue execution
- `error`: Fail the operation (despite optional flag)

**Default**: `warn_and_skip`

---

## Concurrency Policy

**Configuration**: Host config, not node config

| Label | Meaning | Enforcement |
|-------|---------|-------------|
| `parallelizable` | Safe to run across workers | No locking, can run N instances |
| `sequential` | Single-threaded for this node type | Per-node-type mutex |
| `strictly_sequential` | Single-threaded + ordered | Global mutex + ordering guarantee |

**Host enforcement**:
- `parallelizable` nodes: dispatched to worker pool freely
- `sequential` nodes: per-node-type lock prevents concurrent execution
- `strictly_sequential` nodes: global lock + FIFO queue

**Initial deployment**: `--max-workers=1` (all nodes effectively sequential until validated)

---

## Envelope Ordering Guarantees

**Official stance**: Ordering is NOT guaranteed except where explicitly documented

| Scope | Guarantee |
|-------|-----------|
| Cross-partition | No ordering guarantee |
| Per-partition | Order preserved (Kafka semantics) |
| Cross-node | No ordering guarantee |

**Invariants**:
- Reducers MUST treat input as possibly out-of-order unless bound to single-partition stream
- Orchestrators MUST NOT assume ordering between workflow steps unless explicitly coordinated
- Nodes MUST be idempotent where possible

---

## Protocol Lockfile Specification

**File**: `runtime_protocol.lock.json`
**Location**: Repository root
**Generated by**: CI pipeline
**Enforced by**: Snapshot tests (Phase 8.13)

**Contents**:
```json
{
  "version": "1.0.0",
  "generated": "2025-12-03T00:00:00Z",
  "envelope_schema_version": "1.0.0",
  "handler_protocols": {
    "IVectorStoreHandler": { "version": "1.0.0", "methods": [...] },
    "IGraphDatabaseHandler": { "version": "1.0.0", "methods": [...] }
  },
  "node_contract_schema_version": "1.0.0"
}
```

**Change process**:
- Modifications require PR with `protocol-change` label
- Breaking changes require major version bump
- CI fails if lockfile doesn't match protocol definitions

---

## Runtime Host Boot Sequence

**Visual Overview**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        RUNTIME HOST BOOT SEQUENCE                        │
└─────────────────────────────────────────────────────────────────────────┘

  ┌──────────┐    ┌───────────┐    ┌────────────┐    ┌──────────┐
  │  CONFIG  │───▶│ CONTRACTS │───▶│ VALIDATION │───▶│ HANDLERS │
  │  (load)  │    │  (scan)   │    │  (schema)  │    │  (init)  │
  └──────────┘    └───────────┘    └────────────┘    └──────────┘
       │                                                    │
       │                                                    ▼
       │         ┌───────────┐    ┌─────────────┐    ┌──────────┐
       │         │  RUNNING  │◀───│ SUBSCRIBED  │◀───│ REGISTRY │
       │         │ (process) │    │  (Kafka)    │    │  (bind)  │
       │         └───────────┘    └─────────────┘    └──────────┘
       │               │
       │               ▼
       │         ┌───────────┐
       └────────▶│  DEGRADED │  (if optional handlers missing)
                 │  or ERROR │  (if required handlers missing)
                 └───────────┘

State Transitions:
  INITIALIZING ──▶ VALIDATING ──▶ BINDING ──▶ RUNNING
                        │            │           │
                        ▼            ▼           ▼
                      ERROR        ERROR     DEGRADED
```

**Boot Stages** (detailed below):

1. **Load runtime config** - environment variables, YAML config
2. **Load contracts from registry** - scan `IntelligenceNodeRegistry`
3. **Validate contracts** - schema validation, compute fingerprints
4. **Build NodeMetadata objects** - populate all required fields
5. **Initialize handlers** - call `initialize()` on each handler (idempotent)
6. **Validate handler bindings** - ensure required handlers available for each node
7. **Register NodeInstance objects** - inject handlers, create instances
8. **Subscribe to Kafka topics** - based on profile and contracts
9. **Start worker pool** - with `--max-workers` setting
10. **Begin processing** - poll EventBus, route envelopes

**Failure modes**:
- Steps 1-7: Fail fast, exit with error
- Steps 8-10: Retry with backoff, then fail

---

## RuntimeHost Constraints

**What RuntimeHost may NOT do:**

| Forbidden | Reason |
|-----------|--------|
| Mutate contracts at runtime | Contracts are immutable after load |
| Load nodes dynamically | All nodes must be in registry at boot |
| Bypass SPI handlers | All I/O must go through handler layer |
| Skip contract validation | Every node must have valid contract |
| Modify envelope payloads | Host routes, does not transform |
| Access node internals | Nodes are black boxes to host |

**RuntimeHost lifecycle states**:
```
INITIALIZING → VALIDATING → BINDING → RUNNING
                    ↓           ↓         ↓
                  ERROR      ERROR     DEGRADED/ERROR
```

---

## Performance Limits (Hard Requirements)

| Metric | Limit | Enforcement |
|--------|-------|-------------|
| P99 Latency | ≤500ms | GA |
| RAM per container | ≤400MB | GA |
| Idle CPU | ≤15% | GA |
| Cold start | TBD | Beta |
| Handler warmup | TBD | Beta |

---

## Milestones

| Milestone | Definition |
|-----------|------------|
| **MVP** | Basic runtime host with envelope routing |
| **Beta** | Production-ready with monitoring, chaos testing |
| **GA** | Full performance guarantees enforced |

---

## External Blockers (Must Complete First)

### omnibase_core
- Fix Core→SPI dependency inversion
- `NodeRuntime`, `NodeInstance`, `NodeCompute`, `NodeEffect` base classes
- `NodeRuntime` MUST enforce async-only execution
- `NodeMetadata` schema for node introspection
- Typed `EnvelopeContext` to pass metadata to nodes

### omnibase_spi
- Handler protocols: `IVectorStoreHandler`, `IGraphDatabaseHandler`, `IRelationalDatabaseHandler`, `IEmbeddingHandler`, `IKafkaProducerHandler`
- `ProtocolEventBus`
- Protocols need: `supported_operations`, `capabilities`, `describe()` method

### omnibase_infra
- Handler implementations: Qdrant, Memgraph, Asyncpg, OpenAI/Local Embedding, Kafka
- `BaseRuntimeHostProcess`
- **Requirement**: Handler initialization MUST be idempotent (calling `initialize()` N times must not leak connections/memory)

---

## Cross-Repo Alignment Gates

| OmniInt Phase | Core Requirement | SPI Requirement | Infra Requirement |
|---------------|------------------|-----------------|-------------------|
| Phase 1 (Tooling) | None (read-only) | None | None |
| Phase 2 (Contracts) | `BaseNodeContract` stable, `EnvelopeContext` defined | Contract fingerprint format frozen | None |
| Phase 3-4 (Node refactors) | `NodeRuntime`, `NodeCompute`, `NodeEffect` interfaces frozen | Handler protocols stable (no breaking changes) | Optional (mocks OK) |
| Phase 5 (Orch/Reducer) | `NodeOrchestrator`, `NodeReducer` interfaces frozen | Workflow contract schema frozen | Optional (mocks OK) |
| Phase 6 (Runtime Host) | `NodeInstance` + `NodeMetadata` stable | `ProtocolEventBus`, handler capability API stable | `BaseRuntimeHostProcess` + ≥1 handler |
| Phase 7 (Docker) | No changes | No changes | All handlers implemented |
| Phase 8 (Testing) | No changes | Protocol lockfile frozen | All handlers tested |

---

## Phase Summary

### Phase 1: Tooling & Validators (8 issues)
**Can start immediately** - Build validation infrastructure

| Issue | Title | Milestone |
|-------|-------|-----------|
| 1.1 | Contract Linter CLI | MVP |
| 1.2 | Envelope Shape Audit Test | MVP |
| 1.3 | Dependency Graph Validator | Beta |
| 1.4 | Contract Coverage Report Generator | Beta |
| 1.5 | Topic Naming Schema Validator | GA |
| 1.6 | Handler-to-Node Binding Map Generator | Beta |
| 1.7 | Runtime Host Dry Run Mode | MVP |
| 1.8 | Workflow Simulation CLI | GA |

### Phase 2: Contract Reconciliation (6 issues)
**After Phase 0** - Align contracts with Runtime Host

| Issue | Title | Milestone |
|-------|-------|-----------|
| 2.1 | Validate all contracts against BaseNodeContract | MVP |
| 2.2 | Upgrade compute node contracts to v1.1.0 | MVP |
| 2.3 | Upgrade effect node contracts to v2.0.0 | MVP |
| 2.4 | Upgrade orchestrator/reducer contracts to v1.5.0 | MVP |
| 2.5 | Create mandatory contract test fixtures | Beta |
| 2.6 | Document node versioning strategy | Beta |
| 2.7 | Contract Fingerprint Implementation | MVP |

### Phase 3: Compute Node Refactoring (4 issues)
**After Phase 2** - 8 compute nodes (7 pure, 1 needs handler injection)

| Issue | Title | Milestone |
|-------|-------|-----------|
| 3.1 | Refactor NodeVectorizationCompute for IEmbeddingHandler | MVP |
| 3.2 | Audit pure compute nodes for I/O violations | MVP |
| 3.3 | Update compute node contracts for v1.1.0 | MVP |
| 3.4 | Create compute node unit tests with mocked handlers | MVP |

### Phase 4: Effect Node Refactoring (7 issues)
**After Phase 0** - 5 effect nodes, remove all direct I/O

| Issue | Title | Milestone |
|-------|-------|-----------|
| 4.1 | Refactor NodeKafkaEventEffect → IKafkaProducerHandler | MVP |
| 4.2 | Refactor NodeQdrantVectorEffect → IVectorStoreHandler | MVP |
| 4.3 | Refactor NodeMemgraphGraphEffect → IGraphDatabaseHandler | MVP |
| 4.4 | Refactor NodePostgresPatternEffect → IRelationalDatabaseHandler | MVP |
| 4.5 | **CRITICAL**: Remove Kafka consumer from NodeIntelligenceAdapterEffect | MVP |
| 4.6 | Update effect node contracts with handler dependencies | MVP |
| 4.7 | Create effect node unit tests with mocked handlers | MVP |

### Phase 5: Orchestrator & Reducer Refactoring (4 issues)
**After Phase 4** - 2 orchestrators, 1 reducer

| Issue | Title | Milestone |
|-------|-------|-----------|
| 5.1 | Refactor NodeIntelligenceReducer → IRelationalDatabaseHandler | MVP |
| 5.2 | Refactor NodeIntelligenceOrchestrator for contract injection | MVP |
| 5.3 | Refactor NodePatternAssemblerOrchestrator for contract injection | MVP |
| 5.4 | Update orchestrator/reducer contracts with dependencies | MVP |

### Phase 6: Runtime Host Integration (8 issues)
**After Phase 5** - Wire nodes to Runtime Host

| Issue | Title | Milestone |
|-------|-------|-----------|
| 6.1 | Create IntelligenceNodeRegistry | MVP |
| 6.2 | Create IntelligenceRuntimeConfig | MVP |
| 6.3 | Create runtime host entrypoint main.py | MVP |
| 6.4 | Create runtime/__init__.py with exports | MVP |
| 6.5 | Add runtime entry point to pyproject.toml | MVP |
| 6.6 | Create Node Health & Lifecycle Integration | Beta |
| 6.7 | Create Local Development Mode Profile | Beta |
| 6.8 | Create Runtime Host Boot Diagram Documentation | MVP |
| 6.9 | Implement NodeMeta Model for Node-Level Metadata | MVP |

### Phase 7: Docker Consolidation (6 issues)
**After Phase 6** - Replace 10+ containers with 2-3

| Issue | Title | Milestone |
|-------|-------|-----------|
| 7.1 | Create unified runtime host Dockerfile | MVP/Beta |
| 7.2 | Create docker-compose.runtime.yml | MVP |
| 7.3 | Create runtime profiles for node selection | MVP |
| 7.4 | Archive legacy per-node Dockerfiles | Beta |
| 7.5 | Create Runtime Profile Compatibility Matrix | MVP |
| 7.6 | Docker Compose Autogeneration from Registry | Beta |

### Phase 8: Testing & Validation (13 issues)
**After Phase 7** - Comprehensive testing

| Issue | Title | Milestone |
|-------|-------|-----------|
| 8.1 | Create handler mock fixtures | MVP |
| 8.2 | Create integration tests with testcontainers | MVP |
| 8.3 | Create I/O audit test | MVP |
| 8.4 | Create performance benchmark tests | GA |
| 8.5 | Achieve >80% test coverage | Beta |
| 8.6 | Create Handler Compliance Tests | Beta |
| 8.7 | Create Runtime Host State Replay Tests | Beta |
| 8.8 | Create Stress & Chaos Tests for Effect Nodes | GA |
| 8.9 | Create Node Runtime Compliance Checklist | MVP |
| 8.10 | Create Performance Regression Tests | GA |
| 8.11 | Define Unified Error Taxonomy | Beta |
| 8.12 | Define Optional Handler Behavior Semantics | Beta |
| 8.13 | Add Protocol Lockfile Snapshot Tests | Beta |

### Phase 9: Legacy Cleanup (3 issues)
**After 2 weeks production validation**

| Issue | Title | Milestone |
|-------|-------|-----------|
| 9.1 | Remove per-node Dockerfiles | Beta |
| 9.2 | Remove any remaining direct I/O code | Beta |
| 9.3 | Update documentation for v0.5.0 | Beta |

---

## Platformization Plan

**These OmniIntelligence components are destined for omnibase_core:**

| Component | Current | Target | Move When |
|-----------|---------|--------|-----------|
| Dependency graph validator | omniintelligence | omnibase_core/validators | After v0.5.0 |
| Envelope validator | omniintelligence | omnibase_core/validators | After v0.5.0 |
| Health/Lifecycle enums | omniintelligence | omnibase_core/runtime | After v0.5.0 |
| RuntimeProfileDefinition | omniintelligence | omnibase_core/runtime | After v0.5.0 |
| NodeMetadata model | omniintelligence | omnibase_core/runtime | After v0.5.0 |
| Error taxonomy | omniintelligence | omnibase_core/errors | After v0.5.0 |

**Coordination with omnibase_core**:
- OmniInt v0.5.0 ships with local copies (marked `# TODO: Move to omnibase_core`)
- omnibase_core v0.5.x receives these components
- OmniInt v0.6.0 removes local copies, depends on core v0.5.x

**Why not move now?**: Reduces cross-repo coordination during migration. Ship working code first, refactor second.

---

## Node Migration Dashboard

### Compute Nodes (8)
| Node | Handler | Version | I/O Violations | Migration | Tests |
|------|---------|---------|----------------|-----------|-------|
| vectorization_compute | IEmbeddingHandler | v1.1.0 | OpenAI direct calls | TODO (3.1) | ❌ |
| quality_scoring_compute | None (pure) | v1.0.0 | None | READY | ❌ |
| entity_extraction_compute | None (pure) | v1.0.0 | None | READY | ❌ |
| relationship_detection_compute | None (pure) | v1.0.0 | None | READY | ❌ |
| intent_classifier_compute | None (pure) | v1.0.0 | None | READY | ❌ |
| context_keyword_extractor_compute | None (pure) | v1.0.0 | None | READY | ❌ |
| success_criteria_matcher_compute | None (pure) | v1.0.0 | None | READY | ❌ |
| execution_trace_parser_compute | None (pure) | v1.0.0 | None | READY | ❌ |

### Effect Nodes (5)
| Node | Handler | Version | I/O Violations | Migration | Tests |
|------|---------|---------|----------------|-----------|-------|
| kafka_event_effect | IKafkaProducerHandler | v2.0.0 | confluent_kafka direct | TODO (4.1) | ❌ |
| qdrant_vector_effect | IVectorStoreHandler | v2.0.0 | qdrant_client direct | TODO (4.2) | ❌ |
| memgraph_graph_effect | IGraphDatabaseHandler | v2.0.0 | neo4j direct | TODO (4.3) | ❌ |
| postgres_pattern_effect | IRelationalDatabaseHandler | v2.0.0 | asyncpg direct | TODO (4.4) | ❌ |
| intelligence_adapter | IKafkaProducerHandler (opt) | v2.0.0 | Kafka consumer loop | TODO (4.5) | ❌ |

> **Note**: `intelligence_adapter` has ambiguous responsibilities. Consider future split into `IntelligenceEnvelopeBuilderEffect` + `IntelligenceAdapterProducerEffect`.

### Orchestrators (2) & Reducer (1)
| Node | Dependencies | Version | I/O Violations | Migration | Tests |
|------|--------------|---------|----------------|-----------|-------|
| intelligence_orchestrator | 5 workflow contracts | v1.5.0 | File I/O (YAML) | TODO (5.2) | ❌ |
| pattern_assembler_orchestrator | 4-phase assembly | v1.5.0 | File I/O (YAML) | TODO (5.3) | ❌ |
| intelligence_reducer | IRelationalDatabaseHandler + FSM | v1.5.0 | asyncpg direct | TODO (5.1) | ❌ |

**Legend**: READY = no I/O violations | TODO (X.Y) = blocked on issue | ✅ = passing | ❌ = not written

---

## Runtime Profiles

| Profile | Nodes | Description | Production |
|---------|-------|-------------|------------|
| `main` | 11 | Orchestrators, reducer, compute | Yes |
| `effects` | 5 | Effect nodes only | Yes |
| `all` | 16 | All nodes | **No** |
| `local-dev` | 16 + mocks | Development with mock handlers | **No** |

> **Warning**: `all` profile is NOT recommended for production. Use `main` + `effects` split.

### Profile & Contract Interaction

**Profiles are**:
- Sets of node IDs to load
- Optional handler config overrides
- Profile-wide constraints (e.g., `local-dev` uses mock handlers)

**Contracts are**:
- Node-level declarations
- Independent of profiles
- Define handler requirements, not handler implementations

**Rules**:
- Profile selects which nodes to load
- Contract declares what each node needs
- Handler config (separate) provides implementations
- Profiles do NOT override contract requirements
- If profile loads node but handler unavailable → startup failure (required) or degraded (optional)

**Future requirements**:
- Profile version field for compatibility tracking
- Profile stability window to prevent thrashing
- Profile→node compatibility validator

---

## Success Criteria

### Core Metrics
| Metric | Current | Target | Milestone |
|--------|---------|--------|-----------|
| Container count | 10+ | ≤3 | MVP |
| Memory footprint | ~1.5GB | ≤400MB | GA |
| Message latency (p99) | TBD | ≤500ms | GA |
| Idle CPU | TBD | ≤15% | GA |
| Test coverage | TBD | ≥80% | Beta |
| Zero I/O in nodes | No | Yes | MVP |
| No Kafka consumer in nodes | No | Yes | MVP |
| Node compliance checklist | 0/17 | 17/17 | MVP |

### Additional Metrics (GA)
| Metric | Target |
|--------|--------|
| Envelope serialization cost | TBD |
| Node initialization time | TBD |
| Handler warmup time | TBD |
| Cold start latency | TBD |
| Peak memory under backpressure | TBD |
| Recovery time after downstream failure | TBD |

---

## Execution Order

```
Phase 1 (Tooling) ←── Start immediately
    ↓
BLOCKED: External Dependencies
    ↓ (when unblocked)
Phase 2 (Contracts)
    ↓
Phase 3 (Compute) ←→ Phase 4 (Effect) [parallel]
    ↓
Phase 5 (Orchestrator/Reducer)
    ↓
Phase 6 (Runtime Host)  ← MUST NOT start until ALL contracts validated
    ↓
Phase 7 (Docker)  ← Testcontainers integration tests MUST pass first
    ↓
Phase 8 (Testing)
    ↓
v0.5.0 Release
    ↓ (2 weeks validation)
Phase 9 (Cleanup)
```

**Critical gates**:
- Phase 6 MUST NOT start until every contract in Phases 2-5 is validated
- Testcontainers-based integration tests must pass before Docker consolidation
- Runtime Host MUST run with `--max-workers=1` initially (no parallelism)

---

## Risks & Unknowns

| Risk | Impact | Phase | Mitigation Check |
|------|--------|-------|------------------|
| Runtime Host exposes envelope ordering assumptions | High | 6 | Ordering tests in Phase 8.7 (replay with shuffled events) |
| Hidden I/O patterns in nodes | Medium | 3-4 | AST scan must pass before merging refactor PRs |
| Handler protocols need mid-milestone redesign | High | 3-4 | Protocol lockfile frozen before Phase 3 starts |
| Kafka throughput requires handler-layer batching | Medium | 6 | Design batching API in handler config before Phase 6 |
| Version skew between core/spi/infra | High | 2-6 | CI compatibility matrix updated each phase |
| Legacy contracts missing required metadata | Medium | 2 | Contract linter (1.1) catches before Phase 3 |
| Competing Kafka consumers in legacy code | High | 4 | `grep -r "Consumer" src/` audit before Phase 4.5 |

---

## Common Pitfalls

- Accidentally leaving I/O imports in compute nodes
- Handler protocol mismatches (signature drift)
- Missing contract version increments after changes
- Cyclic orchestrator workflow definitions
- Forgetting to update envelope schemas
- Assuming gradual migration is possible (it's not)

---

## Deployment Guidance

### Initial Production
- Runtime Host MUST run with `--max-workers=1` initially
- Disable parallelism until concurrency bugs are validated

### Handler Healthchecks
- DB handler: validate connection
- Vector handler: validate index existence
- Graph handler: verify topology
- Kafka handler: verify broker connectivity

### Safe Legacy Cleanup Criteria
- 2 consecutive releases with stable Runtime Host
- All nodes fully migrated
- All handler tests passing at ≥90% coverage

---

## Node Compliance Checklist

**Location**: `docs/NODE_COMPLIANCE_CHECKLIST.md` (to be created in Phase 8.9)

Every node must pass before migration is complete:

| # | Requirement | Verification |
|---|-------------|--------------|
| 1 | No direct I/O imports | `grep -r "confluent_kafka\|qdrant_client\|neo4j\|asyncpg\|httpx" <node>` returns empty |
| 2 | No environment variable access | `grep -r "os.environ\|os.getenv" <node>` returns empty |
| 3 | Contract validated | Contract linter (1.1) passes |
| 4 | Contract fingerprint present | `fingerprint` field in contract YAML |
| 5 | Uses injected handlers only | Code review: all I/O via `self._*_handler` |
| 6 | Envelope shape correct | Envelope audit test (1.2) passes |
| 7 | Deterministic flag set | `NodeMetadata.concurrency` set correctly |
| 8 | Handler dependencies declared | Listed in contract `handlers` section |
| 9 | Unit tests ≥80% coverage | Coverage report per-node |
| 10 | Has profile membership | Listed in `IntelligenceNodeRegistry` |
| 11 | Contract version updated | Matches migration table |
| 12 | Logging uses unified logger | Uses `omnibase_core.logging`, not `print()` |

---

## For External Contributors

**If you're working on OmniIntelligence:**

**DO NOT**:
- Add new nodes that bypass Runtime Host
- Add direct Kafka consumers (use `ProtocolEventBus`)
- Import I/O libraries directly in nodes
- Read environment variables in nodes
- Assume gradual migration is possible

**MUST**:
- Any new handler must implement SPI's `IHandler` protocol
- Any new node must have a contract YAML + fingerprint
- Any new node must have `NodeMetadata` defined
- Any I/O must go through injected handlers
- Any config must be constructor-injected

**PR Checklist**:
- [ ] No forbidden imports (run AST scan)
- [ ] Contract linter passes
- [ ] Unit tests with mocked handlers
- [ ] NodeMetadata defined
- [ ] Added to `IntelligenceNodeRegistry`

---

## How to Write a New Node

| Step | Action | Artifact |
|------|--------|----------|
| 1 | Create contract YAML | `nodes/<name>/contracts/contract.yaml` |
| 2 | Define NodeMetadata | Class property with all required fields |
| 3 | Declare handler dependencies | `handlers` section in contract |
| 4 | Implement node class | Inherit from `NodeCompute`/`NodeEffect`/etc |
| 5 | Write unit tests | Mock handlers, test pure logic |
| 6 | Add to registry | `IntelligenceNodeRegistry` |
| 7 | Add to profile | Update profile definitions |
| 8 | Run compliance checklist | All 12 checks must pass |

**Minimum viable node**: Contract + NodeMetadata + Class + Tests + Registry entry

---

## Node ID Naming Standard

**Format**: `<descriptive_name>_<kind>`

**Rules**:
- Lowercase snake_case only
- Must end with kind suffix: `_compute`, `_effect`, `_orchestrator`, `_reducer`
- Descriptive prefix (what it does, not how)
- No abbreviations unless universally understood

**Examples**:
- `vectorization_compute`
- `kafka_event_effect`
- `intelligence_orchestrator`
- `vec_comp` (abbreviation)
- `VectorizationCompute` (wrong case)
- `vectorization` (missing suffix)

---

**Generated**: 2025-12-03
