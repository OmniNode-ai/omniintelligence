# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Shared Infrastructure**: For PostgreSQL, Kafka/Redpanda, remote server topology (192.168.86.200), Docker networking, and environment variables, see **`~/.claude/CLAUDE.md`**. This file covers OmniIntelligence-specific architecture only.

## Overview

OmniIntelligence is the intelligence platform for the ONEX ecosystem, providing code quality analysis, pattern learning, semantic analysis, and Claude Code hook processing as first-class ONEX nodes. The system follows declarative node architecture where nodes are thin shells delegating all logic to handlers.

**Key Capabilities**:
- **Claude Code Hook Processing**: Receives and processes hook events from omniclaude
- **Pattern Learning**: ML-based pattern extraction, clustering, and lifecycle management
- **Quality Scoring**: Code quality assessment with ONEX compliance checking
- **Intent Classification**: User prompt intent analysis (pure computation, pattern matching)

> **Note**: Vector storage and graph operations (Qdrant, Memgraph) are handled by the `omnimemory` repository.

---

## Repository Invariants

These rules are non-negotiable. Violations will cause production issues or architectural drift.

**No backwards compatibility**: This repository has no external consumers. Schemas, APIs, and interfaces may change without deprecation periods. If something needs to change, change it.

| Invariant | Rationale |
|-----------|-----------|
| Node classes must be **thin shells** (<100 lines) | Declarative pattern; logic belongs in handlers |
| Effect nodes must **never block** on Kafka | Kafka is **required infrastructure**; emit events asynchronously — never block the calling thread waiting for acks |
| All event schemas are **frozen** (`frozen=True`) | Events are immutable after emission |
| Handlers must **return structured errors**, not raise | Domain errors are data, not exceptions |
| `correlation_id` must be **threaded through all operations** | End-to-end tracing is required |
| **No hardcoded environment variables** | All config via `.env` or Pydantic Settings; see `~/.claude/CLAUDE.md` |

---

## Non-Goals

This system explicitly does NOT optimize for:

- **Developer convenience** - Strictness over ergonomics. Boilerplate is acceptable if it enforces boundaries.
- **Framework agnosticism** - This is ONEX-native. No abstraction layers for hypothetical portability.
- **Flexibility** - Determinism and predictability over configurability. One way to do things.
- **Minimal code** - Explicit is better than clever. Verbose handlers over magic.
- **Backwards compatibility** - See Repository Invariants above. No deprecation periods, no shims.

---

## Development Commands

```bash
# Install dependencies (using uv)
uv sync --group dev        # Development dependencies
uv sync --group core       # Core node system + infrastructure
uv sync --group all        # Everything

# Run tests
pytest                     # All tests
pytest tests/unit          # Unit tests only
pytest tests/integration   # Integration tests (requires infrastructure)
pytest -k "test_name"      # Single test by name
pytest -m unit             # Only @pytest.mark.unit tests
pytest -m "not slow"       # Exclude slow tests
pytest -m audit            # I/O audit tests only
pytest --cov=src/omniintelligence --cov-report=html  # With coverage

# Code quality
ruff check src tests       # Lint (includes import sorting)
ruff check --fix src tests # Auto-fix lint issues
ruff format src tests      # Format code
mypy src                   # Type check
```

---

## Architecture

### Node Types

The system decomposes intelligence operations into specialized ONEX nodes:

| Type | Purpose | Base Class |
|------|---------|------------|
| **Orchestrator** | Coordinate workflows, route operations | `NodeOrchestrator` |
| **Reducer** | Manage FSM state transitions | `NodeReducer` |
| **Compute** | Pure data processing, no side effects | `NodeCompute` |
| **Effect** | External I/O (Kafka, PostgreSQL) | `NodeEffect` |

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| **Directory** | `node_{type}_{category}` | `node_pattern_storage_effect` |
| **Class** | `Node{Type}{Category}` | `NodePatternStorageEffect` |
| **Input Model** | `Model{NodeName}Input` | `ModelPatternStorageInput` |
| **Output Model** | `Model{NodeName}Output` | `ModelPatternStorageOutput` |
| **Handler** | `handle_{operation}` or `Handler{Domain}` | `handle_store_pattern` |

**Directory naming is MANDATORY**: All node directories MUST start with `node_` prefix for consistency.

### Complete Node Inventory

**Orchestrators**:
- `NodeIntelligenceOrchestrator` - Main workflow coordination (contract-driven)
- `NodePatternAssemblerOrchestrator` - Pattern assembly from traces

**Reducer**:
- `NodeIntelligenceReducer` - Unified FSM handler (ingestion, pattern_learning, quality_assessment)

**Compute Nodes**:
- `NodeQualityScoringCompute` - Code quality scoring with ONEX compliance
- `NodeSemanticAnalysisCompute` - Semantic code analysis
- `NodePatternExtractionCompute` - Extract patterns from code
- `NodePatternLearningCompute` - ML pattern learning pipeline
- `NodePatternMatchingCompute` - Match patterns against code
- `NodeIntentClassifierCompute` - User prompt intent classification
- `NodeExecutionTraceParserCompute` - Parse execution traces
- `NodeSuccessCriteriaMatcherCompute` - Match success criteria

**Effect Nodes**:
- `NodeClaudeHookEventEffect` - Process Claude Code hook events
- `NodePatternStorageEffect` - Persist patterns to PostgreSQL
- `NodePatternPromotionEffect` - Promote patterns (provisional → validated)
- `NodePatternDemotionEffect` - Demote patterns (validated → deprecated)
- `NodePatternFeedbackEffect` - Record session outcomes and metrics
- `NodePatternLifecycleEffect` - Atomic pattern lifecycle transitions with audit trail

---

## Declarative Node Pattern (CRITICAL)

**All nodes MUST be declarative, not imperative.** The node class is a thin shell (~20-50 lines) that:
1. Declares dependencies via constructor or registry (not setters)
2. Delegates ALL logic to handler functions
3. Contains NO error handling, logging, or validation

### Ideal Pattern: Thin Shell Compute Node

**File**: `nodes/node_quality_scoring_compute/node.py` (~22 lines)

```python
"""Quality Scoring Compute Node - Thin shell delegating to handler."""
from omnibase_core.nodes.node_compute import NodeCompute
from .handlers import handle_quality_scoring_compute
from .models import ModelQualityScoringInput, ModelQualityScoringOutput


class NodeQualityScoringCompute(
    NodeCompute[ModelQualityScoringInput, ModelQualityScoringOutput]
):
    """Pure compute node for scoring code quality.

    This node is a thin shell following the ONEX declarative pattern.
    All computation logic is delegated to the handler function.
    """

    async def compute(
        self, input_data: ModelQualityScoringInput
    ) -> ModelQualityScoringOutput:
        """Score code quality by delegating to handler function."""
        return handle_quality_scoring_compute(input_data)
```

### Effect Node with Handler Injection

**File**: `nodes/node_claude_hook_event_effect/node.py` (~35 lines)

```python
class NodeClaudeHookEventEffect(NodeEffect):
    """Thin shell effect node for Claude Code hook event handling."""

    def __init__(
        self,
        container: ModelONEXContainer,
        handler: HandlerClaudeHookEvent,
    ) -> None:
        super().__init__(container)
        self._handler = handler  # Handler injected, not created

    async def execute(
        self, event: ModelClaudeCodeHookEvent
    ) -> ModelClaudeHookResult:
        """Execute by delegating to handler - single line."""
        return await self._handler.handle(event)
```

### Effect Node with Registry Pattern

**File**: `nodes/node_pattern_promotion_effect/node.py` (~40 lines)

```python
class NodePatternPromotionEffect(NodeEffect):
    """Pattern promotion with registry-wired handlers."""

    def __init__(
        self,
        container: ModelONEXContainer,
        registry: ServiceHandlerRegistry,  # Frozen dataclass
    ) -> None:
        super().__init__(container)
        self._registry = registry

    async def execute(
        self, request: ModelPromotionCheckRequest
    ) -> ModelPromotionCheckResult:
        handler = self._registry.check_and_promote
        return await handler(request)
```

**Registry Creation** (frozen, immutable):
```python
registry = RegistryPatternPromotionEffect.create_registry(
    repository=db_connection,
    producer=kafka_producer,
)
node = NodePatternPromotionEffect(container, registry)
```

### Anti-Patterns to AVOID

| Anti-Pattern | Why Wrong | Correct Approach |
|--------------|-----------|------------------|
| `set_repository()` setters | Mutable state, testing complexity | Constructor/registry injection |
| `try/except` in node | Business logic in wrong place | Handler handles all errors |
| `logger.info()` in node | Cross-cutting concern | Handler logs with context |
| `if self._repo is None` | Validation is business logic | Handler validates |
| `self.container.get(X)` at runtime | Implicit dependencies | Explicit constructor params |
| Nodes > 100 lines | Violates thin shell | Refactor to handler |

### Enforcement (CI/Audit)

These rules are **mechanically enforced**, not just documented:

| Rule | Enforcement | Location |
|------|-------------|----------|
| Node line count < 100 | `tests/audit/test_io_violations.py` | AST analysis |
| No `logging` import in nodes | `tests/audit/test_io_violations.py` | Import audit |
| No `container.get(` in node methods | `tests/audit/test_io_violations.py` | AST pattern match |
| No `try/except` in node.py | `tests/audit/test_io_violations.py` | AST analysis |
| Protocol conformance | `node_tests/conftest.py` | `isinstance()` checks |

Run enforcement: `pytest -m audit`

### Where Logic Belongs

| Component | Responsibility | Typical Lines |
|-----------|----------------|---------------|
| **node.py** | Type declarations, single delegation | 20-50 |
| **handler_compute.py** | Orchestrate, error handling, timing | 100-350 |
| **handler_{domain}.py** | Pure business logic | 200-1000 |
| **protocols.py** | TypedDict, Protocol definitions | 50-150 |
| **exceptions.py** | Domain-specific errors with codes | 30-60 |

---

## Handler System

Handlers contain ALL business logic, error handling, and logging. Three patterns exist:

### Pattern 1: Pure Module-Level Functions (Compute Nodes)

```python
# handlers/handler_quality_scoring.py
def score_code_quality(
    content: str,
    language: str,
    weights: dict[str, float] | None = None,
    onex_threshold: float = 0.7,
) -> QualityScoringResult:
    """Pure function - no I/O, returns TypedDict."""
    # All computation logic here
    ...
```

### Pattern 2: Async Functions with Protocol Deps (Effect Nodes)

```python
# handlers/handler_store_pattern.py
async def handle_store_pattern(
    input_data: ModelPatternStorageInput,
    *,
    pattern_store: ProtocolPatternStore,  # Protocol, not concrete
    conn: AsyncConnection,                 # External transaction control
) -> ModelPatternStoredEvent:
    """Dependencies injected via parameters."""
    ...
```

### Pattern 3: Handler Classes (Complex Workflows)

```python
# handlers/handler_pattern_learning.py
class HandlerPatternLearning:
    """Stateless handler class with execute() interface."""

    def handle(
        self,
        training_data: Sequence[TrainingDataItemDict],
        parameters: LearningParametersDict | None = None,
    ) -> PatternLearningResult:
        return _execute_pipeline(...)
```

### Error Handling Pattern

**Handlers must not raise domain or expected errors** - return structured error output instead.

**Handlers MAY raise** for:
- Invariant violations (data corruption, impossible states)
- Schema violations (Pydantic validation at boundaries)
- Unrecoverable infrastructure faults (connection pool exhausted)

```python
def handle_quality_scoring_compute(
    input_data: ModelQualityScoringInput,
) -> ModelQualityScoringOutput:
    start_time = time.perf_counter()

    try:
        return _execute_scoring(input_data, start_time)

    except QualityScoringValidationError as e:
        # Domain error - return structured response, DO NOT RAISE
        return _create_validation_error_output(str(e), _elapsed(start_time))

    except SchemaCorruptionError:
        # Invariant violation - MUST RAISE to halt orchestration
        raise

    except Exception as e:
        # Unknown error - return structured, log for investigation
        logger.exception("Unhandled exception...")
        return _create_safe_error_output(f"Unhandled: {e}", _elapsed(start_time))
```

**Error Classification**:
| Error Type | Action | Rationale |
|------------|--------|-----------|
| Domain/business errors | Return structured output | Expected, recoverable |
| Validation errors | Return structured output | User/input issue |
| Invariant violations | RAISE | System corruption, must halt |
| Schema corruption | RAISE | Data integrity at risk |
| Infrastructure fatal | RAISE | Cannot continue safely |

### Handler Directory Structure

```
nodes/node_quality_scoring_compute/
├── node.py                     # Thin shell (~20-40 lines)
├── models/
│   ├── model_input.py
│   └── model_output.py
└── handlers/
    ├── __init__.py             # Re-exports
    ├── handler_compute.py      # Main orchestration, error handling
    ├── handler_quality_scoring.py  # Pure scoring logic
    ├── protocols.py            # TypedDict, Protocol definitions
    ├── exceptions.py           # Domain-specific errors
    └── presets.py              # Configuration presets
```

---

## Claude Code Hook System

OmniIntelligence processes Claude Code hooks via `NodeClaudeHookEventEffect`.

### Supported Hook Event Types

| Hook Type | Handler | Status | Purpose |
|-----------|---------|--------|---------|
| `UserPromptSubmit` | `handle_user_prompt_submit()` | **ACTIVE** | Classify user intent, emit to Kafka |
| `SessionStart` | `handle_no_op()` | DEFERRED | Session tracking |
| `SessionEnd` | `handle_no_op()` | DEFERRED | Session summary |
| `PreToolUse` | `handle_no_op()` | DEFERRED | Tool validation |
| `PostToolUse` | `handle_no_op()` | DEFERRED | Result capture |
| `Stop` | `handle_no_op()` | DEFERRED | Completion tracking |
| `Notification` | `handle_no_op()` | IGNORED | No current use case |

**Status Legend**:
- **ACTIVE**: Implemented and emitting events
- **DEFERRED**: Intentionally unimplemented, planned for future
- **IGNORED**: Intentionally no-op, no planned implementation

### Hook Event Flow

```
Claude Code Extension
       │
       ▼
omniclaude (Hook Producer)
  Publishes: onex.cmd.omniintelligence.claude-hook-event.v1
       │
       ▼
NodeClaudeHookEventEffect
  ├── route_hook_event()
  │     ├── UserPromptSubmit → handle_user_prompt_submit()
  │     │     ├── Call NodeIntentClassifierCompute
  │     │     └── Emit to Kafka (intent-classified.v1)
  │     └── Other events → handle_no_op()
       │
       ▼
omnimemory (Graph Storage)
  Consumes: onex.evt.omniintelligence.intent-classified.v1
  Stores intent classifications in knowledge graph
```

---

## Event-Driven Architecture

### Kafka Topics

**Topic Naming**: `{env}.onex.{kind}.{producer}.{event-name}.v{version}`
- `kind=cmd` for commands/inputs
- `kind=evt` for events/outputs

| Topic | Direction | Purpose |
|-------|-----------|---------|
| `onex.cmd.omniintelligence.claude-hook-event.v1` | Input | Claude Code hooks |
| `onex.evt.omniintelligence.intent-classified.v1` | Output | Classified intents |
| `onex.evt.omniintelligence.pattern-stored.v1` | Output | Pattern storage confirmations |
| `onex.evt.omniintelligence.pattern-promoted.v1` | Output | Pattern promotions |
| `onex.evt.omniintelligence.pattern-deprecated.v1` | Output | Pattern demotions |

### DLQ (Dead Letter Queue) Pattern

All effect nodes route failed messages to `{topic}.dlq` with:
- Original envelope preserved
- Error message and timestamp
- Retry count and service metadata
- Secret sanitization via `LogSanitizer`

### Correlation ID Tracing

All operations thread `correlation_id` through:
1. Input model (`correlation_id: UUID`)
2. Handler logging (`extra={"correlation_id": ...}`)
3. Kafka payloads (`"correlation_id": str(correlation_id)`)
4. Output models (preserved for downstream)

---

## Infrastructure Patterns

### Protocol-Based Dependencies

All I/O uses `@runtime_checkable` Protocol classes:

```python
@runtime_checkable
class ProtocolKafkaPublisher(Protocol):
    async def publish(self, topic: str, key: str, value: dict) -> None: ...

@runtime_checkable
class ProtocolPatternRepository(Protocol):
    async def fetch(self, query: str, *args: Any) -> list[Mapping]: ...
    async def execute(self, query: str, *args: Any) -> str: ...
```

### Non-Blocking Kafka Emission

Kafka is **required infrastructure** — but event emission must never block the primary operation. Fire-and-forget: the database write succeeds regardless of Kafka ack timing:

```python
# Emit asynchronously — do not await a Kafka ack before returning
await _emit_promotion_event(producer=producer, ...)
# Primary operation already complete; Kafka delivery is best-effort async
```

### External Transaction Control

Handlers accept `conn` parameter for caller-managed transactions:

```python
async def handle_store_pattern(
    input_data: ModelPatternStorageInput,
    *,
    pattern_store: ProtocolPatternStore,
    conn: AsyncConnection,  # External transaction control
) -> ModelPatternStoredEvent:
    # All operations use the provided connection
    await pattern_store.store_pattern(..., conn=conn)
```

### Protocol Design Guidelines

To prevent protocol explosion and mock fatigue:

| When To | Guidance |
|---------|----------|
| **Create new protocol** | Only when existing protocols don't cover the I/O boundary |
| **Reuse existing** | Prefer `ProtocolPatternRepository` over domain-specific repos |
| **Aggregate protocols** | Combine related operations (e.g., `ProtocolPatternStore` = read + write + query) |
| **Avoid** | Single-method protocols, overlapping responsibilities |

**Protocol Hierarchy**:
```
ProtocolPatternRepository (generic DB ops)
    └── ProtocolPatternStore (pattern-specific: store, query, check_exists)
    └── ProtocolPatternStateManager (lifecycle: promote, demote)

ProtocolKafkaPublisher (single publish method - intentionally minimal)
```

**Rule**: If you're creating a 4th protocol for the same resource, refactor existing ones first.

---

## Contract YAML Structure

Each node has a `contract.yaml` defining behavior declaratively:

```yaml
# =============================================================================
# IDENTIFIERS
# =============================================================================
name: "node_name"
contract_version: {major: 1, minor: 0, patch: 0}
node_version: {major: 1, minor: 0, patch: 0}
node_type: "EFFECT_GENERIC"  # or COMPUTE_GENERIC, REDUCER_GENERIC, ORCHESTRATOR_GENERIC

# =============================================================================
# I/O MODELS
# =============================================================================
input_model:
  name: "ModelNodeInput"
  module: "omniintelligence.nodes.node_name.models"

output_model:
  name: "ModelNodeOutput"
  module: "omniintelligence.nodes.node_name.models"

# =============================================================================
# HANDLER ROUTING (Effect/Orchestrator)
# =============================================================================
handler_routing:
  routing_strategy: "event_type_match"  # or "operation_match"
  handlers:
    - operation: "operation_name"
      handler:
        function: "handle_operation"
        module: "...handlers.handler_operation"
        type: "async"

# =============================================================================
# EVENT BUS (Effect nodes)
# =============================================================================
event_bus:
  event_bus_enabled: true
  subscribe_topics:
    - "onex.cmd.omniintelligence.topic.v1"
  publish_topics:
    - "onex.evt.omniintelligence.topic.v1"

# =============================================================================
# STATE MACHINE (Reducer nodes)
# =============================================================================
state_machine:
  state_machine_name: "fsm_name"
  initial_state: "idle"
  states:
    - state_name: "state"
      is_terminal: false
  transitions:
    - from_state: "a"
      to_state: "b"
      trigger: "action"

# =============================================================================
# DEPENDENCIES
# =============================================================================
dependencies:
  - name: "kafka_producer"
    type: "protocol"
    class_name: "ProtocolKafkaProducer"
    required: false  # Optional = graceful degradation

# =============================================================================
# IDEMPOTENCY
# =============================================================================
idempotency:
  enabled: true
  strategy: "event_id_tracking"
  hash_fields: ["pattern_id", "signature_hash"]
```

---

## Running Nodes

Nodes in this repository are **not standalone executables**. They are discovered and executed by `RuntimeHostProcess` from `omnibase_infra`.

### Why No `__main__.py`?

Nodes are thin shells that delegate to handlers. Infrastructure concerns (Kafka consumption, health checks, graceful shutdown, drain timeout) belong to the **runtime**, not individual nodes.

| Anti-Pattern | Why Wrong | Correct Approach |
|--------------|-----------|------------------|
| `__main__.py` in node directory | Nodes shouldn't own infrastructure | Use `RuntimeHostProcess` |
| Ad-hoc Kafka consumer loops | Duplicates runtime logic | Declare topics in `contract.yaml` |
| Manual health check endpoints | Cross-cutting concern | `RuntimeHostProcess` handles |
| Custom shutdown handlers | Inconsistent drain behavior | Runtime manages gracefully |

### Correct Pattern: RuntimeHostProcess

`RuntimeHostProcess` from `omnibase_infra.runtime` is the correct way to run effect nodes:

```python
import asyncio
import signal

from omnibase_infra.runtime import RuntimeHostProcess
from omnibase_infra.event_bus.event_bus_kafka import EventBusKafka

shutdown_event = asyncio.Event()


def handle_shutdown(sig, frame):
    """Signal handler to trigger graceful shutdown."""
    shutdown_event.set()


signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)


async def main():
    # RuntimeHostProcess discovers nodes and wires them automatically
    process = RuntimeHostProcess(
        event_bus=EventBusKafka.default(),
        contract_paths=["src/omniintelligence/nodes/"],
    )
    await process.start()

    # RuntimeHostProcess handles:
    #   - Kafka subscription from contract.yaml event_bus config
    #   - Handler routing based on handler_routing config
    #   - Health checks at /health endpoint
    #   - Graceful shutdown with configurable drain timeout
    #   - DLQ routing for failed messages

    await shutdown_event.wait()
    await process.stop()
```

### Contract Configuration for Event Bus

Each node's `contract.yaml` declares its event bus configuration (see Contract YAML Structure above):

```yaml
event_bus:
  event_bus_enabled: true
  subscribe_topics:
    - "onex.cmd.omniintelligence.claude-hook-event.v1"
  publish_topics:
    - "onex.evt.omniintelligence.intent-classified.v1"

handler_routing:
  routing_strategy: "event_type_match"
  handlers:
    - operation: "UserPromptSubmit"
      handler:
        function: "handle_user_prompt_submit"
        module: "omniintelligence.nodes.node_claude_hook_event_effect.handlers"
        type: "async"
```

`RuntimeHostProcess` reads this configuration to:
1. Subscribe to declared `subscribe_topics`
2. Route incoming messages to handlers based on `handler_routing`
3. Publish output events to `publish_topics`

### Node Discovery

`RuntimeHostProcess` discovers nodes by scanning `contract_paths` for `contract.yaml` files:

```
src/omniintelligence/nodes/
├── node_claude_hook_event_effect/
│   ├── contract.yaml          # Discovered by RuntimeHostProcess
│   ├── node.py                # Thin shell
│   └── handlers/              # Business logic
├── node_pattern_feedback_effect/
│   ├── contract.yaml          # Discovered by RuntimeHostProcess
│   └── ...
```

Only nodes with `event_bus.event_bus_enabled: true` are wired to Kafka.

### Testing Without RuntimeHostProcess

For unit tests, instantiate nodes directly with mock dependencies:

```python
# Unit test - no RuntimeHostProcess needed
async def test_handler():
    handler = HandlerClaudeHookEvent(
        intent_classifier=mock_classifier,
        kafka_producer=mock_producer,
    )
    result = await handler.handle(sample_event)
    assert result.success
```

For integration tests that need Kafka, use `EventBusInmemory` or the full `RuntimeHostProcess`:

```python
# Integration test with in-memory event bus
process = RuntimeHostProcess(
    event_bus=EventBusInmemory(),
    contract_paths=["src/omniintelligence/nodes/"],
)
```

---

## Models and Enums

### Intelligence Operations

Defined in `EnumIntelligenceOperationType`:

| Category | Operations |
|----------|------------|
| **Quality** | `assess_code_quality`, `analyze_document_quality`, `get_quality_patterns`, `check_architectural_compliance` |
| **Pattern Learning** | `pattern_match`, `hybrid_score`, `semantic_analyze`, `get_pattern_metrics`, `get_cache_stats`, `clear_pattern_cache`, `get_pattern_health` |
| **Performance** | `establish_performance_baseline`, `identify_optimization_opportunities`, `apply_performance_optimization`, `get_optimization_report`, `monitor_performance_trends` |
| **Document Freshness** | `analyze_document_freshness`, `get_stale_documents`, `refresh_documents`, `get_freshness_stats`, `get_document_freshness`, `cleanup_freshness_data` |
| **Vector** | `advanced_vector_search`, `quality_weighted_search`, `batch_index_documents`, `get_vector_stats`, `optimize_vector_index` |
| **Traceability** | `track_pattern_lineage`, `get_pattern_lineage`, `get_execution_logs`, `get_execution_summary` |
| **Autonomous** | `ingest_patterns`, `record_success_pattern`, `predict_agent`, `predict_execution_time`, `calculate_safety_score`, `get_autonomous_stats`, `get_autonomous_health` |

### FSM Types

| FSM Type | State Flow |
|----------|-----------|
| `INGESTION` | `idle → received → processing → indexed` |
| `PATTERN_LEARNING` | `idle → foundation → matching → validation → traceability → completed` |
| `QUALITY_ASSESSMENT` | `idle → raw → assessing → scored → stored` |

### Pattern Lifecycle States

`EnumPatternLifecycleStatus`: `CANDIDATE → PROVISIONAL → VALIDATED → DEPRECATED`

### Model Naming Conventions

- **Input**: `Model{NodeName}Input`
- **Output**: `Model{NodeName}Output`
- **Event**: `Model{Event}Event` (e.g., `ModelPatternStoredEvent`)
- **Payload**: `Model{FSM}Payload` (e.g., `ModelIngestionPayload`)

---

## Testing

### Test Organization

```
tests/
├── conftest.py              # Root fixtures
├── fixtures/                # Shared test data
├── audit/                   # I/O purity audit tests
│   └── fixtures/io/         # AST test fixtures
├── unit/                    # Unit tests (no infrastructure)
│   └── nodes/               # Node-specific unit tests
│       └── {node}/handlers/ # Handler tests
└── integration/             # Integration tests
    └── nodes/               # Node integration tests

src/omniintelligence/nodes/
└── {node}/node_tests/       # Co-located node tests
    ├── conftest.py          # Mock protocol implementations
    └── test_*.py            # Behavior tests
```

### Key Fixtures

| Fixture | Purpose |
|---------|---------|
| `correlation_id` | Fixed UUID for tracing tests |
| `sample_code` | Python code snippet for analysis |
| `mock_kafka_producer` | AsyncMock Kafka producer |
| `mock_onex_container` | Mock ONEX container |
| `db_conn` | asyncpg connection (auto-skip if unavailable) |
| `sample_execution_trace` | JSON execution trace |

### pytest Markers

```bash
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests
pytest -m slow          # Slow tests
pytest -m audit         # I/O audit enforcement
pytest -m performance   # Performance benchmarks
```

### Protocol Mock Pattern

```python
class MockPatternStore:
    """Mock implementation of ProtocolPatternStore."""
    def __init__(self) -> None:
        self.patterns: dict[UUID, dict] = {}

    async def store_pattern(self, ...) -> UUID:
        self.patterns[pattern_id] = {...}
        return pattern_id

# Verify mock conforms to protocol
assert isinstance(MockPatternStore(), ProtocolPatternStore)
```

---

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `omnibase_core` | ONEX node base classes, protocols, validation |
| `omnibase_spi` | Service Provider Interface protocols |
| `omnibase_infra` | Kafka, PostgreSQL infrastructure |
| `asyncpg` | PostgreSQL async driver |
