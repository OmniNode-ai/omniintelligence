# CLAUDE.md - OmniIntelligence

> **Python**: 3.12+ | **Framework**: ONEX Intelligence | **Package Manager**: uv | **Shared Standards**: See **`~/.claude/CLAUDE.md`** for shared development standards (Python, Git, testing, architecture principles) and infrastructure configuration (PostgreSQL, Kafka/Redpanda, Docker networking, environment variables).

---

## Table of Contents

1. [Repo Invariants](#repo-invariants)
2. [Non-Goals](#non-goals)
3. [Quick Reference](#quick-reference)
4. [Handler Output Constraints](#handler-output-constraints)
5. [Forbidden Data Flow Patterns](#forbidden-data-flow-patterns)
6. [Dependency Injection](#dependency-injection)
7. [Error Handling](#error-handling)
8. [Project Structure](#project-structure)
9. [Node Inventory](#node-inventory)
10. [Event-Driven Architecture](#event-driven-architecture)
11. [Runtime Module](#runtime-module)
12. [API Module](#api-module)
13. [Repositories Module](#repositories-module)
14. [Pydantic Model Standards](#pydantic-model-standards)
15. [Code Quality](#code-quality)
16. [Common Pitfalls](#common-pitfalls)
17. [Documentation](#documentation)

---

## Repo Invariants

These are non-negotiable architectural truths. Violations cause production issues or architectural drift.

| Invariant | Rationale |
|-----------|-----------|
| **No backwards compatibility** — schemas, APIs, and interfaces may change without deprecation periods | This repo has no external consumers |
| Node classes must be **thin shells** (<100 lines) | Declarative pattern; logic belongs in handlers |
| Effect nodes must **never block** on Kafka | Async-only — never await synchronously in the calling thread; nodes must remain non-blocking |
| All event schemas are **frozen** (`frozen=True`) | Events are immutable after emission |
| Handlers must **return structured errors**, not raise | Domain errors are data, not exceptions |
| `correlation_id` must be **threaded through all operations** | End-to-end tracing is required |
| **No hardcoded environment variables** | All config via `.env` or Pydantic Settings |
| Subscribe topics declared in `contract.yaml`, not in `plugin.py` | `collect_subscribe_topics_from_contracts()` is the single source |
| `PluginIntelligence.wire_dispatchers()` must run before `start_consumers()` | No dispatch engine = no consumers (hard gate) |
| `AdapterPatternStore` ignores the `conn` parameter — each method is an independent transaction | External transaction control is not supported by this adapter |

**Mechanically enforced** (run `uv run pytest -m audit`):

| Rule | Enforcement |
|------|-------------|
| Node line count < 100 | `tests/audit/test_io_violations.py` — AST analysis |
| No `logging` import in `node.py` | `tests/audit/test_io_violations.py` — import audit |
| No `container.get(` in node methods | `tests/audit/test_io_violations.py` — AST pattern match |
| No `try/except` in `node.py` | `tests/audit/test_io_violations.py` — AST analysis |
| Protocol conformance | `nodes/*/node_tests/conftest.py` — `isinstance()` checks |

---

## Non-Goals

This system explicitly does NOT optimize for:

- **Developer convenience** — Strictness over ergonomics. Boilerplate is acceptable if it enforces boundaries.
- **Framework agnosticism** — ONEX-native only. No abstraction layers for hypothetical portability.
- **Flexibility** — Determinism over configurability. One way to do things.
- **Minimal code** — Explicit is better than clever. Verbose handlers over magic.
- **Backwards compatibility** — No deprecation periods, no shims, no `_deprecated` suffixes.
- **Business logic in nodes** — Nodes coordinate; handlers compute.

---

## Quick Reference

```bash
# Setup
uv sync --group all && pre-commit install

# Testing
uv run pytest tests/                          # All tests
uv run pytest tests/unit                      # Unit tests only
uv run pytest tests/integration               # Integration tests (requires infrastructure)
uv run pytest -m audit                        # I/O purity audit enforcement
uv run pytest -m unit -xvs                    # Debug mode
uv run pytest tests/ --cov=src/omniintelligence # With coverage

# Code Quality
uv run mypy src/                              # Type checking (strict, 0 errors required)
uv run ruff check src tests                   # Linting
uv run ruff check --fix src tests             # Auto-fix lint issues
uv run ruff format src tests                  # Format code
pre-commit run --all-files                    # All hooks
```

**Test markers**: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow`, `@pytest.mark.audit`, `@pytest.mark.performance`

---

## Handler Output Constraints

| Node Kind | Allowed | Forbidden |
|-----------|---------|-----------|
| **ORCHESTRATOR** | `events[]`, `intents[]` | `projections[]`, `result` |
| **REDUCER** | `projections[]` | `events[]`, `intents[]`, `result` |
| **EFFECT** | `events[]` | `intents[]`, `projections[]`, `result` |
| **COMPUTE** | `result` (required) | `events[]`, `intents[]`, `projections[]` |

**Where logic belongs**:

| Component | Responsibility | Typical Lines |
|-----------|----------------|---------------|
| `node.py` | Type declarations, single delegation | 20–50 |
| `handler_compute.py` | Orchestrate, error handling, timing | 100–350 |
| `handler_{domain}.py` | Pure business logic | 200–1000 |
| `protocols.py` | TypedDict, Protocol definitions | 50–150 |
| `exceptions.py` | Domain-specific errors with codes | 30–60 |

---

## Forbidden Data Flow Patterns

- Command → Reducer (bypasses orchestration)
- Reducer → I/O (violates purity)
- Orchestrator → Typed Result (only COMPUTE returns results)
- Effect node blocking on Kafka (async-only — never await synchronously in the calling thread; use non-blocking publish patterns)
- `set_repository()` setters in nodes (use constructor/registry injection)
- `try/except` in `node.py` (error handling belongs in handlers)
- `logger.info()` in `node.py` (logging belongs in handlers)
- `self.container.get(X)` at runtime in nodes (use explicit constructor params)
- Hardcoded topic lists in `plugin.py` (declare in `contract.yaml`, collect via `collect_subscribe_topics_from_contracts()`)

---

## Dependency Injection

| Type | Purpose | In Node `__init__` |
|------|---------|-------------------|
| `ModelContainer[T]` | Value wrapper | **NEVER** |
| `ModelONEXContainer` | Dependency injection | **ALWAYS** |

All I/O dependencies use `@runtime_checkable` Protocol classes:

| Protocol | Used By |
|----------|---------|
| `ProtocolKafkaPublisher` | Effect nodes publishing events |
| `ProtocolPatternRepository` | Generic DB fetch/execute |
| `ProtocolPatternStore` | Pattern-specific: store, query, check_exists |
| `ProtocolPatternStateManager` | Lifecycle: promote, demote |
| `ProtocolIdempotencyStore` | Idempotency checks (pattern lifecycle) |

**Protocol design rule**: If you are creating a 4th protocol for the same resource, refactor existing ones first. Prefer aggregated protocols (`ProtocolPatternStore` = read + write + query) over single-method protocols.

**Registry pattern** (frozen, immutable wiring):

```python
registry = RegistryPatternPromotionEffect.create_registry(
    repository=db_connection,
    producer=kafka_producer,
)
node = NodePatternPromotionEffect(container, registry)
```

---

## Error Handling

| Error Type | Action | Rationale |
|------------|--------|-----------|
| Domain / business errors | Return structured output | Expected, recoverable |
| Validation errors | Return structured output | User / input issue |
| Invariant violations | RAISE | System corruption — must halt |
| Schema corruption | RAISE | Data integrity at risk |
| Infrastructure fatal | RAISE | Cannot continue safely |

**Comment markers** (required when suppressing or accepting errors):

- `# fallback-ok:` — Graceful degradation (e.g., optional telemetry service down)
- `# boundary-ok:` — API boundary exception handling
- `# cleanup-resilience-ok:` — Cleanup must complete even on error

---

## Project Structure

```
src/omniintelligence/
├── nodes/              # ONEX node shells (thin, <100 lines each)
├── runtime/            # PluginIntelligence, MessageDispatchEngine wiring
├── api/                # FastAPI pattern store query API (OMN-2253)
├── repositories/       # omnibase_infra effect boundary adapter
├── handlers/           # Shared handler functions (non-node-specific)
├── models/             # Shared Pydantic models
├── enums/              # Enum definitions
├── protocols/          # Shared Protocol definitions
├── utils/              # Utilities (log sanitizer, db_url, etc.)
├── testing/            # Shared test helpers and fixtures
├── tools/              # Internal tooling and scripts
├── audit/              # Audit and compliance utilities
├── _legacy/            # Legacy code (do not import)
└── constants.py        # Module-level constants
```

**File naming conventions**:

| Directory | Required Prefix | Example |
|-----------|----------------|---------|
| `nodes/` | `node_` | `node_quality_scoring_compute/` |
| `models/` | `model_` | `model_pattern_lifecycle.py` |
| `enums/` | `enum_` | `enum_intelligence_operation_type.py` |
| `protocols/` | `protocol_` | `protocol_pattern_store.py` |
| `handlers/` | `handler_` | `handler_pattern_learning.py` |
| `runtime/` | `plugin_`, `wiring_`, `dispatch_`, `adapter_` | `dispatch_handler_pattern_learning.py` |
| `repositories/` | `adapter_` | `adapter_pattern_store.py` |
| `api/` | `router_`, `handler_`, `models_` | `router_patterns.py` |

**Node directory naming is MANDATORY**: All node directories MUST start with `node_` prefix.

---

## Node Inventory

**Orchestrators** (2):

| Class | Directory | Purpose |
|-------|-----------|---------|
| `NodeIntelligenceOrchestrator` | `node_intelligence_orchestrator` | Main workflow coordination (contract-driven) |
| `NodePatternAssemblerOrchestrator` | `node_pattern_assembler_orchestrator` | Pattern assembly from execution traces |

**Reducer** (1):

| Class | Directory | Purpose |
|-------|-----------|---------|
| `NodeIntelligenceReducer` | `node_intelligence_reducer` | Unified FSM handler (ingestion, pattern_learning, quality_assessment) |

**Compute Nodes** (8):

| Class | Directory | Purpose |
|-------|-----------|---------|
| `NodeQualityScoringCompute` | `node_quality_scoring_compute` | Code quality scoring with ONEX compliance |
| `NodeSemanticAnalysisCompute` | `node_semantic_analysis_compute` | Semantic code analysis |
| `NodePatternExtractionCompute` | `node_pattern_extraction_compute` | Extract patterns from code |
| `NodePatternLearningCompute` | `node_pattern_learning_compute` | ML pattern learning pipeline |
| `NodePatternMatchingCompute` | `node_pattern_matching_compute` | Match patterns against code |
| `NodeIntentClassifierCompute` | `node_intent_classifier_compute` | User prompt intent classification |
| `NodeExecutionTraceParserCompute` | `node_execution_trace_parser_compute` | Parse execution traces |
| `NodeSuccessCriteriaMatcherCompute` | `node_success_criteria_matcher_compute` | Match success criteria |

**Effect Nodes** (7):

| Class | Directory | Purpose | Has `node.py` |
|-------|-----------|---------|---------------|
| `NodeClaudeHookEventEffect` | `node_claude_hook_event_effect` | Process Claude Code hook events | Yes |
| `NodePatternStorageEffect` | `node_pattern_storage_effect` | Persist patterns to PostgreSQL | Yes |
| `NodePatternPromotionEffect` | `node_pattern_promotion_effect` | Promote patterns (provisional → validated) | Yes |
| `NodePatternDemotionEffect` | `node_pattern_demotion_effect` | Demote patterns (validated → deprecated) | Yes |
| `NodePatternFeedbackEffect` | `node_pattern_feedback_effect` | Record session outcomes and metrics | Yes |
| `NodePatternLifecycleEffect` | `node_pattern_lifecycle_effect` | Atomic lifecycle transitions with audit trail | Yes |
| `NodePatternLearningEffect` | `node_pattern_learning_effect` | Pattern extraction pipeline (contract-only node) | **No** |

**Note on `NodePatternLearningEffect`**: This is a **contract-only node** — it has a `contract.yaml` but no `node.py`. It is runtime-wired by `PluginIntelligence` via `MessageDispatchEngine`. The dispatch handler lives at `runtime/dispatch_handler_pattern_learning.py`.

**FSM States** (`NodeIntelligenceReducer`):

| FSM Type | State Flow |
|----------|-----------|
| `INGESTION` | `idle → received → processing → indexed` |
| `PATTERN_LEARNING` | `idle → foundation → matching → validation → traceability → completed` |
| `QUALITY_ASSESSMENT` | `idle → raw → assessing → scored → stored` |

**Pattern Lifecycle**: `CANDIDATE → PROVISIONAL → VALIDATED → DEPRECATED`

---

## Event-Driven Architecture

**Topic naming**: `{env}.onex.{kind}.{producer}.{event-name}.v{version}` where `kind=cmd` (inputs) or `kind=evt` (outputs).

### Subscribed Topics (inputs)

| Topic | Consumed By |
|-------|-------------|
| `{env}.onex.cmd.omniintelligence.claude-hook-event.v1` | `NodeClaudeHookEventEffect` |
| `{env}.onex.cmd.omniintelligence.tool-content.v1` | `NodeClaudeHookEventEffect` |
| `{env}.onex.cmd.omniintelligence.code-analysis.v1` | `NodeIntelligenceOrchestrator` |
| `{env}.onex.cmd.omniintelligence.document-ingestion.v1` | `NodeIntelligenceOrchestrator` |
| `{env}.onex.cmd.omniintelligence.pattern-learning.v1` | `NodeIntelligenceOrchestrator`, `NodePatternLearningEffect` |
| `{env}.onex.cmd.omniintelligence.quality-assessment.v1` | `NodeIntelligenceOrchestrator` |
| `{env}.onex.cmd.omniintelligence.session-outcome.v1` | `NodePatternFeedbackEffect` |
| `{env}.onex.cmd.omniintelligence.pattern-lifecycle-transition.v1` | `NodePatternLifecycleEffect` |
| `{env}.onex.evt.omniintelligence.pattern-learned.v1` | `NodePatternStorageEffect` |
| `{env}.onex.evt.pattern.discovered.v1` | `NodePatternStorageEffect` |

### Published Topics (outputs)

| Topic | Published By |
|-------|-------------|
| `{env}.onex.evt.omniintelligence.intent-classified.v1` | `NodeClaudeHookEventEffect` |
| `{env}.onex.evt.omniintelligence.pattern-learned.v1` | `NodePatternLearningEffect` |
| `{env}.onex.evt.omniintelligence.pattern-stored.v1` | `NodePatternStorageEffect` |
| `{env}.onex.evt.omniintelligence.pattern-promoted.v1` | `NodePatternStorageEffect` |
| `{env}.onex.evt.omniintelligence.pattern-deprecated.v1` | `NodePatternDemotionEffect` |
| `{env}.onex.evt.omniintelligence.pattern-lifecycle-transitioned.v1` | `NodePatternLifecycleEffect` |
| `{env}.onex.evt.omniintelligence.code-analysis-completed.v1` | `NodeIntelligenceOrchestrator` |
| `{env}.onex.evt.omniintelligence.code-analysis-failed.v1` | `NodeIntelligenceOrchestrator` |
| `{env}.onex.evt.omniintelligence.document-ingestion-completed.v1` | `NodeIntelligenceOrchestrator` |
| `{env}.onex.evt.omniintelligence.document-ingestion-failed.v1` | `NodeIntelligenceOrchestrator` |
| `{env}.onex.evt.omniintelligence.pattern-learning-completed.v1` | `NodeIntelligenceOrchestrator` |
| `{env}.onex.evt.omniintelligence.pattern-learning-failed.v1` | `NodeIntelligenceOrchestrator` |
| `{env}.onex.evt.omniintelligence.quality-assessment-completed.v1` | `NodeIntelligenceOrchestrator` |
| `{env}.onex.evt.omniintelligence.quality-assessment-failed.v1` | `NodeIntelligenceOrchestrator` |
| `{env}.onex.cmd.omniintelligence.pattern-lifecycle-transition.v1` | `NodePatternPromotionEffect`, `NodePatternDemotionEffect` |

**DLQ pattern**: All effect nodes route failed messages to `{topic}.dlq` with original envelope, error message, timestamp, retry count, and secrets sanitized via `LogSanitizer`.

**Correlation ID**: Thread `correlation_id: UUID` through all input models, handler logging (`extra={"correlation_id": ...}`), Kafka payloads, and output models.

### Claude Code Hook Event Types

| Hook Type | Handler | Status |
|-----------|---------|--------|
| `UserPromptSubmit` | `handle_user_prompt_submit()` | **ACTIVE** — classifies intent, emits to Kafka |
| `SessionStart` | `handle_no_op()` | DEFERRED |
| `SessionEnd` | `handle_no_op()` | DEFERRED |
| `PreToolUse` | `handle_no_op()` | DEFERRED |
| `PostToolUse` | `handle_no_op()` | DEFERRED |
| `Stop` | `handle_no_op()` | DEFERRED |
| `Notification` | `handle_no_op()` | IGNORED |

---

## Runtime Module

**Location**: `src/omniintelligence/runtime/`

| File | Purpose |
|------|---------|
| `plugin.py` | `PluginIntelligence` — implements `ProtocolDomainPlugin` for kernel bootstrap |
| `wiring.py` | `wire_intelligence_handlers()` — registers handlers with container |
| `dispatch_handlers.py` | `create_intelligence_dispatch_engine()` — builds `MessageDispatchEngine` with 5 handlers / 7 routes |
| `dispatch_handler_pattern_learning.py` | Dispatch handler for `node_pattern_learning_effect` (contract-only node) |
| `adapters.py` | Protocol adapters: `AdapterPatternRepositoryRuntime`, `AdapterKafkaPublisher`, `AdapterIntentClassifier`, `AdapterIdempotencyStoreInfra` |
| `contract_topics.py` | `collect_subscribe_topics_from_contracts()`, `collect_publish_topics_for_dispatch()` |
| `introspection.py` | Node introspection proxy publishing for observability |
| `message_type_registration.py` | `register_intelligence_message_types()` for `RegistryMessageType` |

**`PluginIntelligence` kernel lifecycle** (called sequentially by kernel bootstrap):

| Method | What It Does | Activation Gate |
|--------|-------------|-----------------|
| `should_activate(config)` | Returns `True` if `OMNIINTELLIGENCE_DB_URL` is set | Always called |
| `initialize(config)` | Creates `StoreIdempotencyPostgres` (owns pool), `PostgresRepositoryRuntime`, `RegistryMessageType` | Requires `OMNIINTELLIGENCE_DB_URL` |
| `wire_handlers(config)` | Delegates to `wire_intelligence_handlers()` | Requires pool from `initialize()` |
| `wire_dispatchers(config)` | Builds `MessageDispatchEngine` with real adapters; publishes introspection events | Requires pool + pattern runtime |
| `start_consumers(config)` | Subscribes to all contract-declared topics via dispatch engine | Requires dispatch engine from `wire_dispatchers()` |
| `shutdown(config)` | Unsubscribes topics, closes idempotency store (releases shared pool), clears state | Guard against concurrent calls |

---

## API Module

**Location**: `src/omniintelligence/api/`

| File | Purpose |
|------|---------|
| `app.py` | `create_app()` — FastAPI application factory with lifespan pool management |
| `router_patterns.py` | `GET /api/v1/patterns` — query validated/provisional patterns |
| `handler_pattern_query.py` | Business logic for pattern query handler |
| `models_pattern_query.py` | `ModelPatternQueryPage` — paginated response model |

**Purpose** (OMN-2253): REST API for enforcement nodes to query the pattern store. Replaces direct DB access disabled in OMN-2058.

**Endpoint**: `GET /api/v1/patterns` — filters by `domain`, `language`, `min_confidence`, `limit`, `offset`.

**Key constraints**:
- Internal service-to-service only — no authentication, access restricted by network topology
- Connection pool lifecycle managed by FastAPI lifespan (startup before requests, teardown after drain)
- Health probe at `GET /health` (not versioned) — returns 503 if pool not initialized or DB unreachable
- `DatabaseSettings` reads from `POSTGRES_*` environment variables

---

## Repositories Module

**Location**: `src/omniintelligence/repositories/`

| File | Purpose |
|------|---------|
| `adapter_pattern_store.py` | `AdapterPatternStore` — implements `ProtocolPatternStore` via `PostgresRepositoryRuntime` |
| `learned_patterns.repository.yaml` | Contract YAML declaring all SQL operations for the pattern store |

**`AdapterPatternStore`** bridges `ProtocolPatternStore` (used by handlers) to `PostgresRepositoryRuntime` (contract-driven execution via `omnibase_infra`).

**Transaction semantics**: Each method call is an **independent transaction**. The `conn` parameter is accepted for interface compatibility only and is not used. External transaction control is not supported. Use `store_with_version_transition()` for atomic version transitions instead of calling `set_previous_not_current()` + `store_pattern()` separately.

**Key operations** declared in `learned_patterns.repository.yaml`:

| Operation | Purpose |
|-----------|---------|
| `store_pattern` | Insert new pattern (first version) |
| `store_with_version_transition` | Atomic UPDATE previous + INSERT new (preferred for version > 1) |
| `upsert_pattern` | `ON CONFLICT DO NOTHING` — idempotent insert for dispatch bridge |
| `check_exists` | Check by domain + signature_hash + version |
| `check_exists_by_id` | Check by pattern_id + signature_hash (idempotency key) |
| `set_not_current` | Mark previous versions non-current |
| `get_latest_version` | Get max version for a lineage |
| `query_patterns` | Filter validated/provisional patterns (API layer only) |

---

## Pydantic Model Standards

| Model Type | Required ConfigDict |
|------------|---------------------|
| **Immutable / event** | `ConfigDict(frozen=True, extra="forbid", from_attributes=True)` |
| **Mutable internal** | `ConfigDict(extra="forbid", from_attributes=True)` |
| **Contract / external** | `ConfigDict(extra="ignore", ...)` |

**`from_attributes=True`** is required on frozen models for pytest-xdist compatibility.

**Mutable defaults**: Always use `default_factory` — e.g. `items: list[str] = Field(default_factory=list)`

**Naming conventions**:

| Kind | Pattern | Example |
|------|---------|---------|
| Input | `Model{NodeName}Input` | `ModelPatternStorageInput` |
| Output | `Model{NodeName}Output` | `ModelPatternStoredEvent` |
| Event | `Model{Event}Event` | `ModelPatternStoredEvent` |
| FSM Payload | `Model{FSM}Payload` | `ModelIngestionPayload` |

---

## Code Quality

### TODO Policy

```python
# Correct — with Linear ticket
# TODO(OMN-1234): Add validation for edge case

# Wrong — missing ticket
# TODO: Fix this later
```

### Type Ignore Policy

```python
# Correct — specific code + explanation
# NOTE(OMN-1234): mypy false-positive due to Protocol-based DI.
value = container.get_service("ProtocolLogger")  # type: ignore[arg-type]

# Wrong — generic ignore
value = some_call()  # type: ignore
```

### Docstring Guidelines

- **Write** for: complex logic, non-obvious behavior, public APIs, edge cases
- **Skip** for: simple getters, obvious signatures, private helpers
- **Never tautological**: `def get_name(): """Get the name."""` adds no value

### Enum vs Literal Policy

| Context | Use |
|---------|-----|
| External contract surface | Enums |
| Internal parsing glue | Literals allowed |
| Cross-process boundaries | Enums only |

---

## Common Pitfalls

### Don't

1. **Put logic in node.py**
   ```python
   # WRONG — node.py should be a single delegation call
   async def execute(self, event):
       if event.type == "A":
           return await self._handler_a.handle(event)
       return await self._handler_b.handle(event)
   ```

2. **Use setter injection**
   ```python
   def set_repository(self, repo):  # WRONG — use constructor injection
       self._repo = repo
   ```

3. **Block the calling thread on Kafka**
   ```python
   producer.publish_sync(...)  # WRONG — synchronous/blocking publish
   ```

4. **Pass `conn` expecting transaction control with `AdapterPatternStore`**
   ```python
   # conn is IGNORED — each call is an independent transaction
   await adapter.store_pattern(..., conn=conn)
   ```

5. **Hardcode subscribe topics in plugin.py**
   ```python
   TOPICS = ["onex.cmd.omniintelligence.claude-hook-event.v1"]  # WRONG
   ```

### Do

1. Node `execute()` / `compute()` is a single delegation line
2. Use constructor injection with protocols: `handler: HandlerClaudeHookEvent`
3. Kafka is required — use `await producer.publish(...)` with async/non-blocking patterns
4. Use `store_with_version_transition()` for atomic version upgrades
5. Declare topics in `contract.yaml` under `event_bus.subscribe_topics`
6. Use `uv run` for all Python commands

---

## Documentation

| Topic | Document |
|-------|----------|
| Navigation index | `docs/INDEX.md` |
| Node state transitions | `docs/NODE_STATE_POLICY.md` |
| Contract validation | `docs/CONTRACT_VALIDATION_GUIDE.md` |
| ONEX four-node architecture | `docs/architecture/ONEX_FOUR_NODE_ARCHITECTURE.md` |
| Naming conventions | `docs/conventions/NAMING_CONVENTIONS.md` |
| Standard doc layout | `docs/standards/STANDARD_DOC_LAYOUT.md` |

---

**Python**: 3.12+ | **Ready?** → `uv run pytest -m audit` to verify node purity
