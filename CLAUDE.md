# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Shared Infrastructure**: For PostgreSQL, Kafka/Redpanda, server topology, Docker networking, and environment variables, see **`~/.claude/CLAUDE.md`**. Workspace-wide rules (worktrees, PR CI requirements, merge policy, repo layering, canonical handler shape) live in the root **`omni_home/CLAUDE.md`** and are not repeated here. This file covers OmniIntelligence-specific architecture only.

## Overview

OmniIntelligence is the intelligence platform for the ONEX ecosystem: pattern learning, code quality analysis, evaluation, intent classification, document analysis, CI failure tracking, bloom evaluation, and Claude Code hook processing. All nodes follow the ONEX Four-Node Architecture (Effect / Compute / Reducer / Orchestrator) and delegate all business logic to handler modules.

> **Note**: Vector storage and graph operations (Qdrant, Memgraph) are handled by the `omnimemory` repository.

---

## Repository Invariants

These rules are non-negotiable. Violations will cause production issues or architectural drift.

**No backwards compatibility**: This repository has no external consumers. Schemas, APIs, and interfaces may change without deprecation periods. If something needs to change, change it.

| Invariant | Rationale |
|-----------|-----------|
| Node classes must be **thin declarative shells** | Purity is AST-enforced by `tests/unit/test_node_purity.py` (OMN-1140); logic belongs in handlers |
| Effect nodes must **never block** on Kafka | Kafka is optional; accept an optional producer and skip/log events when absent; emit asynchronously |
| All event schemas are **frozen** (`frozen=True`) | Events are immutable after emission |
| Handlers must **return structured errors**, not raise | Domain errors are data, not exceptions |
| `correlation_id` must be **threaded through all operations** | End-to-end tracing is required |
| **No hardcoded environment variables** | All config via `.env` or Pydantic Settings |
| Subscribe topics declared in `contract.yaml`, not in `plugin.py` | `collect_subscribe_topics_from_contracts()` is the single source |
| `PluginIntelligence.wire_dispatchers()` must run before `start_consumers()` | No dispatch engine = no consumers (hard gate: consumers are skipped when the engine is absent) |
| `AdapterPatternStore` ignores the `conn` parameter — each method is an independent transaction | External transaction control is not supported by this adapter |
| **`omnibase_infra` migrations must run before this service starts** | `idempotency_records` is owned and migrated by `omnibase_infra` (not this repo's migrations) but is part of `OMNIINTELLIGENCE_SCHEMA_MANIFEST`. If it is missing at boot, `validate_handshake` fails fast: the B1.5 cross-repo-table pre-check (OMN-3531, `_check_cross_repo_tables` in `runtime/plugin.py`) raises `RuntimeHostError` with the provisioning command, and the B2 first-boot fingerprint auto-stamp additionally aborts when the live table count is below the manifest's — so a missing table can no longer poison the stored fingerprint; the service simply refuses to start until migrations have run |

> **Note on `node_pattern_storage_effect`**: This node does not receive an injected Kafka producer. Handlers return typed event models (`ModelPatternStoredEvent`, `ModelPatternPromotedEvent`) which `RuntimeHostProcess` publishes to the declared `publish_topics`. This is a valid alternative pattern for nodes where the runtime handles event emission transparently.

## Non-Goals

Strictness over ergonomics; ONEX-native (no portability abstraction layers); determinism over configurability; explicit over clever; no backwards compatibility (see above). Boilerplate is acceptable if it enforces boundaries.

---

## Development Commands

```bash
uv sync --group dev            # Development dependencies (also: core, rl, all)

uv run pytest tests/ -v                     # Full suite — required before any PR
uv run pytest tests/ -v -m unit             # Unit tests (includes node purity AST enforcement)
uv run pytest tests/ -v -m integration      # Integration tests (requires Postgres + Kafka on the runtime host)
uv run pytest tests/ -v -m audit            # Audit tests (model type safety, pattern status update paths)
uv run pytest tests/ -v -m "not slow"       # Exclude slow tests

uv run ruff format src/ tests/
uv run ruff check --fix src/ tests/
uv run mypy src/
pre-commit run --all-files

# Review calibration CLI
uv run python -m omniintelligence.review_pairing \
  --file plan.md --ground-truth codex --challenger deepseek-r1
```

Additional pytest markers (`slow`, `performance`, `drift`, `smoke`, `forecast`): see `[tool.pytest.ini_options] markers` in `pyproject.toml`.

---

## Architecture

### Node Types

| Type | Purpose | Base Class |
|------|---------|------------|
| **Orchestrator** | Coordinate workflows, route operations | `NodeOrchestrator` |
| **Reducer** | Manage FSM state transitions | `NodeReducer` |
| **Compute** | Pure data processing, no side effects | `NodeCompute` |
| **Effect** | External I/O (Kafka, PostgreSQL) | `NodeEffect` |

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| **Directory** | `node_{type}_{category}` (the `node_` prefix is MANDATORY) | `node_pattern_storage_effect` |
| **Class** | `Node{Type}{Category}` | `NodePatternStorageEffect` |
| **Input Model** | `Model{NodeName}Input` | `ModelPatternStorageInput` |
| **Output Model** | `Model{NodeName}Output` | `ModelPatternStorageOutput` |
| **Event Model** | `Model{Event}Event` | `ModelPatternStoredEvent` |
| **FSM Payload** | `Model{FSM}Payload` | `ModelIngestionPayload` |
| **Handler** | `handle_{operation}` or `Handler{Domain}` | `handle_store_pattern` |

### Node Inventory

All nodes are registered in `pyproject.toml [project.entry-points."onex.nodes"]` — that section is the source of truth for the count and the list. Curated inventory with per-node purpose: [Node Inventory](https://github.com/OmniNode-ai/knowledge-base/blob/main/reference/omniintelligence-node-inventory.md) (must be updated in the same PR when a node is added or removed).

---

## Declarative Node Pattern (CRITICAL)

**All nodes MUST be declarative, not imperative.** The node class is a thin shell that:
1. Declares dependencies via constructor or registry (not setters)
2. Delegates ALL logic to handler functions
3. Contains NO error handling, logging, validation, or business logic

**Read the real exemplars instead of copying snippets from docs:**
- Thin-shell compute node: `src/omniintelligence/nodes/node_quality_scoring_compute/node.py`
- Effect node with handler injection: `src/omniintelligence/nodes/node_claude_hook_event_effect/node.py`
- Effect node with frozen registry wiring: `src/omniintelligence/nodes/node_pattern_promotion_effect/node.py` (+ its `registry.py`)

### Anti-Patterns to AVOID

| Anti-Pattern | Correct Approach |
|--------------|------------------|
| `set_repository()` setters | Constructor/registry injection |
| `try/except`, `logger.info()`, or validation in node.py | Handler owns errors, logging, validation |
| `self.container.get(X)` at runtime | Explicit constructor params |
| Fat node classes | Refactor logic into handlers |

### Enforcement

Node purity is **mechanically enforced** by `tests/unit/test_node_purity.py` (AST-based, OMN-1140): non-stub `node.py` files may contain only imports, class definitions, docstrings, type annotations, interface methods, and `__init__` limited to `super().__init__()`; business logic in `__init__`, extra methods, I/O, and `os.environ` access all fail the suite. Stub nodes (`is_stub: ClassVar[bool] = True`) are excluded. Run: `uv run pytest tests/unit/test_node_purity.py -v`.

### Where Logic Belongs

| Component | Responsibility |
|-----------|----------------|
| **node.py** | Type declarations, single delegation |
| **handler_compute.py** | Orchestration, error handling, timing |
| **handler_{domain}.py** | Pure business logic |
| **protocols.py** | TypedDict, Protocol definitions |
| **exceptions.py** | Domain-specific errors with codes |

---

## Handler System

Handlers contain ALL business logic, error handling, and logging. Three patterns exist — read a live example of each:

1. **Pure module-level functions** (compute nodes) — `node_quality_scoring_compute/handlers/`
2. **Async functions with protocol deps injected as keyword params** (effect nodes) — `node_pattern_storage_effect/handlers/handler_store_pattern.py`
3. **Handler classes** (complex workflows) — `node_claude_hook_event_effect/handlers/`

### Error Handling Pattern

**Handlers must not raise domain or expected errors** — return structured error output instead.

| Error Type | Action | Rationale |
|------------|--------|-----------|
| Domain/business errors | Return structured output | Expected, recoverable |
| Validation errors | Return structured output | User/input issue |
| Invariant violations | RAISE | System corruption, must halt |
| Schema corruption | RAISE | Data integrity at risk |
| Infrastructure fatal (e.g. pool exhausted) | RAISE | Cannot continue safely |

Unknown exceptions: log with `logger.exception(...)`, return a structured safe-error output.

### Handler Directory Structure

```
src/omniintelligence/nodes/node_{name}/
├── node.py          # Thin shell
├── contract.yaml    # Declarative contract (I/O models, routing, topics)
├── models/          # Input/output models
└── handlers/        # ALL logic: handler_compute.py, handler_{domain}.py,
                     # protocols.py, exceptions.py, presets.py
```

---

## Claude Code Hook System

OmniIntelligence processes Claude Code hooks via `NodeClaudeHookEventEffect`. omniclaude publishes hook events to `onex.cmd.omniintelligence.claude-hook-event.v1`; routing lives in `node_claude_hook_event_effect/handlers/handler_claude_event.py`.

| Hook Type | Handler | Status |
|-----------|---------|--------|
| `UserPromptSubmit` | `handle_user_prompt_submit()` | **ACTIVE** — classifies intent via `NodeIntentClassifierCompute`, emits `intent-classified.v1` |
| `Stop` | `handle_stop()` | **ACTIVE** — triggers pattern extraction, emits to `pattern-learning.v1` (once per session, OMN-7608) |
| `PostToolUse` / `PostToolUseFailure` | `handle_post_tool_use()` | **ACTIVE** — persists to `agent_actions` (OMN-2984); degrades to no-op when no repository is injected |
| `SessionStart` / `SessionEnd` / `PreToolUse` | `handle_no_op()` | DEFERRED — intentionally unimplemented |
| `Notification` | `handle_no_op()` | IGNORED — no planned implementation |

Downstream: `omnimemory` consumes `onex.evt.omniintelligence.intent-classified.v1` into the knowledge graph.

---

## Event-Driven Architecture

**Topic naming**: `onex.{kind}.{producer}.{event-name}.v{version}` — `kind=cmd` for commands/inputs, `kind=evt` for events/outputs.

**Source of truth for all topics**: [Event Surface](https://github.com/OmniNode-ai/knowledge-base/blob/main/reference/omniintelligence-event-surface.md) — generated from the contract YAML files; do not maintain topic lists here. Programmatic collection: `runtime/contract_topics.py` (`collect_subscribe_topics_from_contracts()`, `collect_publish_topics_for_dispatch()`).

**DLQ pattern**: All effect nodes route failed messages to `{topic}.dlq` with the original envelope, error message, timestamp, retry count, and secrets sanitized via `LogSanitizer`.

**Correlation ID**: Thread `correlation_id: UUID` through input models, handler logging (`extra={"correlation_id": ...}`), Kafka payloads, and output models.

---

## Infrastructure Patterns

### Protocol-Based Dependencies

All I/O uses `@runtime_checkable` Protocol classes. Core protocols live in `src/omniintelligence/protocols/__init__.py` (`ProtocolPatternRepository`, `ProtocolKafkaPublisher`); node-specific ones next to their handlers (e.g. `ProtocolPatternStore`, `ProtocolPatternStateManager` in `node_pattern_storage_effect/handlers/`).

### Non-Blocking Kafka Emission

Kafka is optional — event emission must never block the primary operation. Always check `producer is not None` before publishing; fire-and-forget so the primary operation succeeds regardless of Kafka availability. Contract dependencies declare the producer with `required: false`.

### Protocol Design Guidelines

To prevent protocol explosion and mock fatigue: create a new protocol only when existing ones don't cover the I/O boundary; prefer reusing/aggregating (e.g. `ProtocolPatternStore` = read + write + query); avoid single-method protocols with overlapping responsibilities.

**Rule**: If you're creating a 4th protocol for the same resource, refactor existing ones first.

---

## Contract YAML Structure

Each node directory has a `contract.yaml` declaring behavior: identifiers (`name`, versions, `node_type`), `input_model`/`output_model` (name + module), `handler_routing` (strategy + handler function/module per operation), `event_bus` (`subscribe_topics` / `publish_topics`), `state_machine` (reducer nodes), `dependencies` (protocol deps, `required: false` for Kafka), and `idempotency`. Read a real one rather than a doc template — e.g. `src/omniintelligence/nodes/node_claude_hook_event_effect/contract.yaml`.

---

## Running Nodes

Nodes in this repository are **not standalone executables**. They are discovered and executed by `RuntimeHostProcess` (from `omnibase_infra.runtime`), which scans `contract_paths` for `contract.yaml` files, subscribes to declared `subscribe_topics`, routes messages per `handler_routing`, publishes to `publish_topics`, and owns health checks, graceful shutdown/drain, and DLQ routing. Only nodes with `event_bus.event_bus_enabled: true` are wired to Kafka.

Never add: `__main__.py` in a node directory, ad-hoc Kafka consumer loops, manual health endpoints, or custom shutdown handlers — those are runtime concerns. See `omnibase_infra/src/omnibase_infra/runtime/runtime_host_process.py` for the canonical entrypoint.

**Testing**: unit tests instantiate nodes/handlers directly with mock dependencies; integration tests use `EventBusInmemory` (or the full `RuntimeHostProcess`) from `omnibase_infra`.

---

## Models and Enums

- **Operations**: `EnumIntelligenceOperationType` (`src/omniintelligence/enums/enum_intelligence_operation_type.py`) — quality, pattern learning, performance, document freshness, vector, traceability, and autonomous operation names. Read the enum, don't copy lists.
- **FSM types**: `EnumFsmType` in `src/omniintelligence/enums/enum_fsm.py` (`INGESTION`, `PATTERN_LEARNING`, `QUALITY_ASSESSMENT`) with state flows documented in its docstring.
- **Pattern lifecycle**: `EnumPatternLifecycleStatus`: `CANDIDATE → PROVISIONAL → VALIDATED → DEPRECATED`.

### Pydantic Model Standards

| Model Type | Required ConfigDict |
|------------|---------------------|
| **Immutable / event** | `ConfigDict(frozen=True, extra="forbid", from_attributes=True)` |
| **Mutable internal** | `ConfigDict(extra="forbid", from_attributes=True)` |
| **Contract / external** | `ConfigDict(extra="ignore", ...)` |

**`from_attributes=True`** is required on frozen models for pytest-xdist compatibility. Mutable defaults always use `default_factory`.

---

## Runtime Module

**Location**: `src/omniintelligence/runtime/`

| File | Purpose |
|------|---------|
| `plugin.py` | `PluginIntelligence` — implements `ProtocolDomainPlugin` for kernel bootstrap |
| `wiring.py` | `wire_intelligence_handlers()` — registers handlers with container |
| `dispatch_handlers.py` | `create_intelligence_dispatch_engine()` — builds the `MessageDispatchEngine` |
| `dispatch_handler_*.py` | One dispatch handler module per domain (pattern learning, code analysis, crawl scheduling, routing feedback, …) |
| `adapters.py` | Protocol adapters: `AdapterPatternRepositoryRuntime`, `AdapterKafkaPublisher`, `AdapterIntentClassifier`, `AdapterIdempotencyStoreInfra` |
| `contract_topics.py` | Contract-driven topic collection (single source for subscribe topics) |
| `introspection.py` | Node introspection proxy publishing for observability |
| `message_type_registration.py` | `register_intelligence_message_types()` for `RegistryMessageType` |

**`PluginIntelligence` kernel lifecycle** (called sequentially by kernel bootstrap):

| Method | What It Does | Activation Gate |
|--------|-------------|-----------------|
| `should_activate(config)` | Returns `True` if `OMNIINTELLIGENCE_DB_URL` is set | Always called |
| `initialize(config)` | Creates `StoreIdempotencyPostgres` (owns pool), `PostgresRepositoryRuntime`, `RegistryMessageType` | Requires `OMNIINTELLIGENCE_DB_URL` |
| `validate_handshake(config)` | B1: DB ownership (`db_metadata.owner_service`); B1.5: cross-repo tables present (`idempotency_records`, OMN-3531); B2: schema fingerprint matches manifest (auto-stamps on first boot if NULL, aborts if live table count < manifest) | Raises `RuntimeHostError` (pool absent / B1.5), `DbOwnershipMismatchError`/`DbOwnershipMissingError` (B1), `SchemaFingerprintMismatchError` (B2 drift) |
| `wire_handlers(config)` | Delegates to `wire_intelligence_handlers()` | Requires pool from `initialize()` |
| `wire_dispatchers(config)` | Builds `MessageDispatchEngine` with real adapters; publishes introspection events | Requires pool + pattern runtime |
| `start_consumers(config)` | Subscribes to all contract-declared topics via dispatch engine | Raises if handshake not validated; skipped (no consumers) if dispatch engine not wired |
| `shutdown(config)` | Unsubscribes topics, closes idempotency store (releases shared pool), clears state | Guard against concurrent calls |

---

## API Module

**Location**: `src/omniintelligence/api/` — FastAPI app factory (`app.py: create_app()`) exposing `GET /api/v1/patterns` (filters: `domain`, `language`, `min_confidence`, `limit`, `offset`) for enforcement nodes to query the pattern store. Replaces direct DB access.

**Key constraints**:
- Internal service-to-service only — no authentication, access restricted by network topology
- Connection pool lifecycle managed by FastAPI lifespan (startup before requests, teardown after drain)
- Health probe at `GET /health` (not versioned) — returns 503 if pool not initialized or DB unreachable
- `DatabaseSettings` reads `POSTGRES_*` environment variables (`OMNIINTELLIGENCE_DB_URL` takes precedence)

---

## Repositories Module

**Location**: `src/omniintelligence/repositories/`

`AdapterPatternStore` (`adapter_pattern_store.py`) bridges `ProtocolPatternStore` (used by handlers) to `PostgresRepositoryRuntime` (contract-driven SQL execution via `omnibase_infra`). All SQL operations are declared in `learned_patterns.repository.yaml` — read that file for the operation list.

**Transaction semantics**: Each method call is an **independent transaction**. The `conn` parameter is accepted for interface compatibility only and is ignored (a one-time warning is logged). External transaction control is not supported. Use `store_with_version_transition()` for atomic version transitions instead of calling `set_previous_not_current()` + `store_pattern()` separately.

---

## Testing

```
tests/
├── conftest.py              # Root fixtures (correlation_id, sample_code, mock_kafka_producer, mock_onex_container, …)
├── fixtures/                # Shared test data
├── audit/                   # Audit tests (model type safety, pattern status update paths)
├── unit/                    # Unit tests, incl. test_node_purity.py (AST purity enforcement)
└── integration/             # Integration tests (Postgres/Kafka)
```

- Mock protocol dependencies with plain classes and assert conformance: `assert isinstance(MockPatternStore(), ProtocolPatternStore)`.
- Topic lists for test setup: [Event Surface](https://github.com/OmniNode-ai/knowledge-base/blob/main/reference/omniintelligence-event-surface.md).
- TODO comments require a ticket: `# TODO(OMN-123): ...` — never a bare `# TODO`.
