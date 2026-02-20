> **Navigation**: [Home](../INDEX.md) > Conventions > Naming Conventions

# ONEX Naming Conventions

This document defines naming conventions for OmniIntelligence code artifacts, including directories, files, classes, and fields.

---

## Table of Contents

1. [Directory Naming](#directory-naming)
2. [File Naming](#file-naming)
3. [Class Naming](#class-naming)
4. [Field Naming](#field-naming)
5. [Kafka Topic Naming](#kafka-topic-naming)

---

## Directory Naming

All directories use a mandatory prefix matching their role:

| Directory | Required Prefix | Example |
|-----------|----------------|---------|
| `nodes/` | `node_` | `node_quality_scoring_compute/` |
| `models/` | `model_` | `model_pattern_lifecycle.py` |
| `enums/` | `enum_` | `enum_intelligence_operation_type.py` |
| `protocols/` | `protocol_` | `protocol_pattern_store.py` |
| `handlers/` | `handler_` | `handler_pattern_learning.py` |
| `runtime/` | `plugin_`, `wiring_`, `dispatch_`, `adapter_`, `contract_`, `introspection_`, `message_type_`, `model_` | `dispatch_handler_pattern_learning.py` |
| `repositories/` | `adapter_` | `adapter_pattern_store.py` |
| `api/` | `router_`, `handler_`, `models_`, `app` | `router_patterns.py` |
| `testing/` | `mock_` | `mock_pattern_store.py` |
| `utils/` | `util_` or descriptive | `util_token_counter.py` |

**Node directories are MANDATORY `node_` prefixed** — the audit enforces this.

---

## File Naming

### Node Directory Files

| File Type | Convention | Example |
|-----------|------------|---------|
| Node shell | `node.py` | `node.py` |
| Handler (compute orchestration) | `handler_compute.py` | `handler_compute.py` |
| Handler (domain logic) | `handler_{domain}.py` | `handler_quality_scoring.py` |
| Handler (semantic analysis) | `handler_compute_semantic_analysis.py` | `handler_compute_semantic_analysis.py` |
| Protocols (local to node) | `protocols.py` | `protocols.py` |
| Exceptions | `exceptions.py` | `exceptions.py` |
| Presets / config | `presets.py` | `presets.py` |
| Heuristics | `heuristics.py` | `heuristics.py` |
| Introspection | `introspection.py` | `introspection.py` |
| Error codes | `error_codes.py` | `error_codes.py` |
| Constants | `constants.py` | `constants.py` |
| Node model (input) | `model_input.py` or `model_{name}_input.py` | `model_input.py`, `model_quality_scoring_input.py` |
| Node model (output) | `model_output.py` or `model_{name}_output.py` | `model_output.py`, `model_quality_scoring_output.py` |
| Node model (other) | `model_{purpose}.py` | `model_pattern_state.py`, `model_transition_result.py` |
| Registry | `registry_{node_name}.py` or `registry.py` | `registry_pattern_promotion_effect.py` |
| Enum (local to node) | `enum_{name}.py` | `enum_insight_type.py`, `enum_onex_strictness_level.py` |

**Note**: Some nodes use `model_{name}_input.py` (fully qualified, e.g. `model_quality_scoring_input.py`) while others use the shorter `model_input.py`. Both are acceptable within a node's `models/` subdirectory. New nodes should prefer the fully qualified form.

### Top-Level Module Files

| Directory | Convention | Example |
|-----------|------------|---------|
| `enums/` | `enum_{domain}.py` | `enum_code_analysis.py`, `enum_pattern_lifecycle.py` |
| `models/` | `model_{name}.py` | `model_intelligence_input.py`, `model_entity.py` |
| `models/domain/` | `model_{name}.py` | `model_gate_snapshot.py` |
| `models/events/` | `model_{event}.py` | `model_pattern_discovered_event.py`, `model_code_analysis_request.py` |
| `models/repository/` | `model_{name}.py` | `model_learned_pattern_row.py`, `model_pattern_for_injection.py` |
| `repositories/` | `adapter_{name}.py` | `adapter_pattern_store.py` |
| `runtime/` | `dispatch_handler_{domain}.py`, `dispatch_handlers.py`, `plugin.py`, `wiring.py`, `contract_topics.py`, `introspection.py`, `message_type_registration.py`, `model_runtime_config.py`, `adapters.py` | `dispatch_handler_pattern_learning.py` |
| `api/` | `router_{domain}.py`, `handler_{domain}.py`, `models_{domain}.py`, `app.py` | `router_patterns.py`, `handler_pattern_query.py` |
| `handlers/` | `handler_{domain}.py` | `handler_compile_pattern.py` |
| `testing/` | `mock_{name}.py` | `mock_pattern_store.py`, `mock_record.py` |
| `utils/` | `util_{name}.py` or descriptive | `util_token_counter.py`, `log_sanitizer.py`, `db_url.py` |
| `protocols/` | `protocol_{name}.py` | `protocol_pattern_store.py` |

**Repository contract files**: `{name}.repository.yaml` (e.g., `learned_patterns.repository.yaml`)

**Doc files**: `UPPER_SNAKE_CASE.md` (e.g., `NAMING_CONVENTIONS.md`)

**Directory indexes**: `README.md`

**Always allowed regardless of directory**: `__init__.py`, `conftest.py`, `py.typed`, `contract.yaml`

---

## Class Naming

### Node Classes

| Element | Convention | Example |
|---------|------------|---------|
| Node class | `Node{Type}{Category}` | `NodeQualityScoringCompute`, `NodePatternStorageEffect`, `NodeIntelligenceReducer`, `NodeIntelligenceOrchestrator` |

**Type suffix** maps to node kind: `Compute`, `Effect`, `Reducer`, `Orchestrator`.

### Handler Classes and Functions

| Element | Convention | Example |
|---------|------------|---------|
| Handler function | `handle_{operation}` | `handle_quality_scoring_compute`, `handle_store_pattern` |
| Handler class | `Handler{Domain}` | `HandlerClaudeHookEvent`, `HandlerPatternLearning` |

### Model Classes

| Element | Convention | Example |
|---------|------------|---------|
| Input model | `Model{NodeName}Input` | `ModelPatternStorageInput`, `ModelQualityScoringInput` |
| Output model | `Model{NodeName}Output` | `ModelPatternStorageOutput`, `ModelQualityScoringOutput` |
| Result model | `Model{Domain}Result` | `ModelTransitionResult`, `ModelDemotionResult`, `ModelPromotionResult` |
| Request model | `Model{Domain}Request` | `ModelDemotionRequest`, `ModelPromotionRequest` |
| Event model | `Model{Event}Event` | `ModelPatternStoredEvent`, `ModelPatternDiscoveredEvent`, `ModelPatternLifecycleEvent` |
| FSM payload | `Model{FSM}Payload` | `ModelIngestionPayload` |
| State model | `Model{Domain}State` | `ModelIntelligenceState`, `ModelPatternState` |
| Config model | `Model{Domain}Config` or `ModelConfig` | `ModelRuntimeConfig` |
| Row model | `Model{Name}Row` | `ModelLearnedPatternRow` |

### Protocol Classes

| Element | Convention | Example |
|---------|------------|---------|
| Protocol | `Protocol{Name}` | `ProtocolPatternStore`, `ProtocolKafkaPublisher` |

### Registry Classes

| Element | Convention | Example |
|---------|------------|---------|
| Registry | `Registry{NodeName}` | `RegistryPatternPromotionEffect`, `RegistryPatternDemotionEffect`, `RegistryPatternFeedbackEffect`, `RegistryClaudeHookEventEffect` |

### Enum Classes

| Element | Convention | Example |
|---------|------------|---------|
| Enum | `Enum{Domain}{Type}` | `EnumIntelligenceOperationType`, `EnumPatternLifecycleStatus`, `EnumCodeAnalysis` |
| Local enum | `Enum{Name}` | `EnumInsightType`, `EnumOnexStrictnessLevel` |

### Adapter Classes

| Element | Convention | Example |
|---------|------------|---------|
| Adapter | `Adapter{Target}` | `AdapterPatternStore` |

---

## Field Naming

### Identifiers

Use `{entity}_id` for all identifier fields:

```python
pattern_id: UUID
correlation_id: UUID
session_id: UUID
```

### Timestamps

Use `*_at` suffix for datetime fields:

```python
created_at: datetime
updated_at: datetime
completed_at: datetime
```

### Durations

Use `*_ms` suffix (always milliseconds):

```python
processing_time_ms: float
latency_ms: float
timeout_ms: int
```

### Counts

Use `*_count` suffix:

```python
retry_count: int
match_count: int
failure_count: int
```

### Scores

Use `*_score` suffix (0.0–1.0 range):

```python
confidence_score: float
quality_score: float
```

### Booleans

| Pattern | Use Case | Example |
|---------|----------|---------|
| `{feature}_enabled` | Feature flags | `cache_enabled`, `kafka_enabled` |
| `is_{condition}` | State checks | `is_success`, `is_terminal`, `is_valid` |
| `has_{thing}` | Presence checks | `has_correlation_id`, `has_dependencies` |

### Limits / Thresholds

```python
max_retries: int
confidence_threshold: float
```

---

## Kafka Topic Naming

Topics follow the pattern: `{env}.onex.{kind}.{producer}.{event-name}.v{version}`

| Component | Values |
|-----------|--------|
| `kind` | `cmd` for commands/inputs, `evt` for events/outputs |
| `env` | `dev`, `staging`, `prod` (omitted in some legacy topics) |

| Topic | Direction | Purpose |
|-------|-----------|---------|
| `{env}.onex.cmd.omniintelligence.claude-hook-event.v1` | Input | Claude Code hooks |
| `{env}.onex.evt.omniintelligence.intent-classified.v1` | Output | Classified intents |
| `{env}.onex.evt.omniintelligence.pattern-stored.v1` | Output | Pattern storage confirmations |
| `{env}.onex.evt.omniintelligence.pattern-promoted.v1` | Output | Pattern promotions |
| `{env}.onex.evt.omniintelligence.pattern-deprecated.v1` | Output | Pattern demotions |

DLQ suffix: `{topic}.dlq`

---

## Known Exceptions

These files exist and deviate from strict prefix rules — document them rather than pretending they don't exist:

| File | Directory | Convention Deviation | Reason |
|------|-----------|---------------------|--------|
| `utils.py` | `node_pattern_extraction_compute/handlers/` | Missing `handler_` or `util_` prefix | Internal utility; local scope only |
| `replay.py` | `node_pattern_learning_compute/handlers/` | Missing `handler_` prefix | Algorithm artifact; local scope |
| `union_find.py` | `node_pattern_learning_compute/handlers/` | Missing `handler_` prefix | Data structure; local scope |
| `_timing.py` | `node_pattern_assembler_orchestrator/handlers/` | Leading underscore (private) | Intentionally private module |
| `heuristics.py` | `node_pattern_feedback_effect/handlers/` | Missing `handler_` prefix | Pure heuristic functions; local scope |
| `models/domain/`, `models/events/`, `models/repository/` | `models/` | Subdirectory names not prefixed with `model_` | Top-level grouping directories, not module files |
| `stub_launcher.py` | `runtime/` | Missing `runtime_` or `dispatch_` prefix | Development/testing stub |
| `constants.py` | `node_pattern_storage_effect/` | No prefix | Flat constants file in node root |
| `contract_loader.py` | `node_pattern_storage_effect/` | Missing prefix | Node-local YAML loading utility |
| `enums.py` | `node_semantic_analysis_compute/models/` | Not `enum_` prefixed | Node-local; predates audit |

---

## Related Documentation

- **omnibase_core Conventions**: `omnibase_core/docs/conventions/NAMING_CONVENTIONS.md`

---

**Last Updated**: 2026-02-19
**Project**: omniintelligence
