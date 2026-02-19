> **Navigation**: [Home](../INDEX.md) > Architecture > ONEX Four-Node Architecture

# ONEX Four-Node Architecture in OmniIntelligence

> **Scope**: OmniIntelligence-specific node inventory, data flow, and implementation patterns.
> **Framework reference**: For base class definitions, handler output constraints, and FSM/workflow contracts, see `omnibase_core/docs/architecture/ONEX_FOUR_NODE_ARCHITECTURE.md`.

---

## Four Node Types

| Type | Base Class | Allowed Handler Outputs | Count | Example Node |
|------|-----------|------------------------|-------|--------------|
| **Compute** | `NodeCompute` | `result` only | 8 | `NodeQualityScoringCompute` |
| **Effect** | `NodeEffect` | `events[]` only | 7 | `NodeClaudeHookEventEffect` |
| **Reducer** | `NodeReducer` | `projections[]` only | 1 | `NodeIntelligenceReducer` |
| **Orchestrator** | `NodeOrchestrator` | `events[]`, `intents[]` | 2 | `NodeIntelligenceOrchestrator` |

### Full Node Inventory

**Compute** (pure transforms, no I/O):

| Node | Purpose |
|------|---------|
| `NodeQualityScoringCompute` | Code quality scoring with ONEX compliance |
| `NodeSemanticAnalysisCompute` | Semantic code analysis |
| `NodePatternExtractionCompute` | Extract patterns from code |
| `NodePatternLearningCompute` | ML pattern learning pipeline |
| `NodePatternMatchingCompute` | Match patterns against code |
| `NodeIntentClassifierCompute` | User prompt intent classification |
| `NodeExecutionTraceParserCompute` | Parse session execution traces |
| `NodeSuccessCriteriaMatcherCompute` | Match patterns against success criteria |

**Effect** (Kafka, PostgreSQL, external I/O):

| Node | Has node.py | Purpose |
|------|------------|---------|
| `NodeClaudeHookEventEffect` | Yes | Process Claude Code hook events |
| `NodePatternStorageEffect` | Yes | Persist patterns to PostgreSQL |
| `NodePatternPromotionEffect` | Yes | Promote patterns (provisional → validated) |
| `NodePatternDemotionEffect` | Yes | Demote patterns (validated → deprecated) |
| `NodePatternFeedbackEffect` | Yes | Record session outcomes and metrics |
| `NodePatternLifecycleEffect` | Yes | Atomic pattern lifecycle transitions |
| `NodePatternLearningEffect` | **No** | Contract-only; handler wired via dispatch engine |

**Reducer** (FSM state management):

| Node | FSM Types |
|------|-----------|
| `NodeIntelligenceReducer` | `INGESTION`, `PATTERN_LEARNING`, `QUALITY_ASSESSMENT` |

**Orchestrator** (workflow coordination):

| Node | Purpose |
|------|---------|
| `NodeIntelligenceOrchestrator` | Main intelligence workflow coordination |
| `NodePatternAssemblerOrchestrator` | Pattern assembly from execution traces |

---

## Node Topology

### Claude Code Hook Pipeline

```
Claude Code Extension
    |
    v  (omniclaude publishes)
{env}.onex.cmd.omniintelligence.claude-hook-event.v1
    |
    v
NodeClaudeHookEventEffect
    |
    +-- UserPromptSubmit --> NodeIntentClassifierCompute (pure compute, no I/O)
    |                             |
    |                             v
    |                    {env}.onex.evt.omniintelligence.intent-classified.v1
    |                             |
    |                             v
    |                        omnimemory (graph storage, separate service)
    |
    +-- Stop event -----> {env}.onex.cmd.omniintelligence.pattern-learning.v1
    |
    +-- all others -----> handle_no_op() (success, no output)
```

### Pattern Learning Pipeline

```
{env}.onex.cmd.omniintelligence.pattern-learning.v1
    |
    v
NodePatternLearningEffect (contract-only, wired via dispatch engine)
    |  dispatch_handler_pattern_learning.py
    |
    +-- NodePatternExtractionCompute (extract candidates from trace)
    +-- NodePatternLearningCompute (ML learning pipeline)
    |
    v
{env}.onex.evt.omniintelligence.pattern-learned.v1
    |
    v
NodePatternStorageEffect
    |
    v
PostgreSQL (via AdapterPatternStore / PostgresRepositoryRuntime)
```

### Pattern Lifecycle Pipeline

```
{env}.onex.cmd.omniintelligence.pattern-lifecycle-transition.v1
    |
    v
NodePatternLifecycleEffect
    |
    +-- CANDIDATE -> PROVISIONAL
    +-- PROVISIONAL -> VALIDATED  (NodePatternPromotionEffect)
    +-- VALIDATED -> DEPRECATED   (NodePatternDemotionEffect)
    |
    v
PostgreSQL (atomic transition with audit trail)
Kafka (optional: {env}.onex.evt.omniintelligence.pattern-promoted/deprecated.v1)
```

### Intelligence Orchestration Pipeline

```
Kafka (code-analysis / document-ingestion / quality-assessment commands)
    |
    v
NodeIntelligenceOrchestrator
    |
    v
NodeIntelligenceReducer (FSM: INGESTION | PATTERN_LEARNING | QUALITY_ASSESSMENT)
    |
    +-- QUALITY_ASSESSMENT --> NodeQualityScoringCompute
    |                          NodeSemanticAnalysisCompute
    |
    +-- PATTERN_LEARNING   --> NodePatternMatchingCompute
    |                          NodePatternExtractionCompute
    |
    +-- INGESTION          --> NodeExecutionTraceParserCompute
                               NodeSuccessCriteriaMatcherCompute
```

---

## Contract-Only Nodes

`NodePatternLearningEffect` has no `node.py`. Its directory contains only `contract.yaml`.

**Why**: The pattern learning handler coordinates multiple compute nodes (extraction, learning),
reads from PostgreSQL, and publishes to Kafka. The handler logic is complex enough that wrapping
it in a thin-shell `node.py` adds no value — the handler function IS the implementation.

**How it works**: `PluginIntelligence.wire_dispatchers()` calls
`create_intelligence_dispatch_engine()` in `runtime/dispatch_handlers.py`, which reads publish
topics from the node's `contract.yaml` and wires `dispatch_handler_pattern_learning.py` as the
route handler. The `MessageDispatchEngine` routes incoming Kafka messages to the correct handler
without needing a node class as intermediary.

**When to use contract-only**:
- Handler coordinates multiple compute nodes in a non-trivial pipeline
- Handler has real dependencies (repository, Kafka producer) that need explicit wiring
- A node.py shell would be a thin pass-through with no additional structure

**When to use a node.py thin shell**:
- The delegation boundary provides meaningful structure (e.g., injecting a handler class)
- The node participates in protocol-based testing (`isinstance` checks)
- The node type needs to be discoverable for introspection/registration purposes

---

## PluginIntelligence: Node Discovery and Wiring

`PluginIntelligence` (in `runtime/plugin.py`) is the entry point for the ONEX kernel. It
implements `ProtocolDomainPlugin` and runs four sequential bootstrap phases:

```
1. initialize()        — creates PostgreSQL pool + RegistryMessageType
2. wire_handlers()     — registers handlers with the container (legacy path)
3. wire_dispatchers()  — builds MessageDispatchEngine with 5 handlers / 7 routes
4. start_consumers()   — subscribes to all intelligence Kafka topics
```

**Topic Discovery (contract-driven)**:

`collect_subscribe_topics_from_contracts()` in `runtime/contract_topics.py` scans all effect
node `contract.yaml` files at import time and collects `event_bus.subscribe_topics`. This list
drives Kafka subscriptions — there are no hardcoded topic lists in `plugin.py`.

Source contracts scanned:
- `node_claude_hook_event_effect/contract.yaml`
- `node_pattern_feedback_effect/contract.yaml`
- `node_pattern_learning_effect/contract.yaml`
- `node_pattern_lifecycle_effect/contract.yaml`
- `node_pattern_storage_effect/contract.yaml`

**Dispatch engine routes**:

| Route | Handler | Source Topic |
|-------|---------|--------------|
| `claude-hook-event` | `route_hook_event()` | `claude-hook-event.v1` |
| `session-outcome` | `record_session_outcome()` | `session-outcome.v1` |
| `pattern-lifecycle-transition` | `apply_transition()` | `pattern-lifecycle-transition.v1` |
| `pattern-storage` | `store_pattern()` | `pattern-learned.v1`, `pattern.discovered` |
| `pattern-learning-cmd` | `create_pattern_learning_dispatch_handler()` | `pattern-learning.v1` |

**Activation gate**: `PluginIntelligence.should_activate()` returns `True` only if
`OMNIINTELLIGENCE_DB_URL` is set. Without a database URL, no consumers start and all
handlers remain unwired.

---

## Node Implementation Decision Tree

```
Is the operation pure computation with no external I/O?
    YES --> Compute node
        Examples: QualityScoring, SemanticAnalysis, IntentClassifier

Does the node manage FSM state transitions?
    YES --> Reducer node
        Example: IntelligenceReducer (INGESTION / PATTERN_LEARNING / QUALITY_ASSESSMENT FSMs)

Does the node coordinate other nodes without doing I/O itself?
    YES --> Orchestrator node
        Examples: IntelligenceOrchestrator, PatternAssemblerOrchestrator

Does the node read/write external systems (Kafka, PostgreSQL)?
    YES --> Effect node
        Simple delegation? --> node.py thin shell (most effect nodes)
        Complex multi-node pipeline? --> Contract-only effect (NodePatternLearningEffect)
```

**Handler location rule**: All business logic — error handling, retry, logging, validation —
belongs in handler functions or classes under `handlers/`. The `node.py` file contains only
type declarations and a single delegation call.

---

## Kafka Topic Naming

All intelligence topics follow: `{env}.onex.{kind}.omniintelligence.{event-name}.v{n}`

- `kind=cmd` for commands / inputs
- `kind=evt` for events / outputs

| Topic | Direction | Produced By | Consumed By |
|-------|-----------|-------------|-------------|
| `{env}.onex.cmd.omniintelligence.claude-hook-event.v1` | In | omniclaude | `NodeClaudeHookEventEffect` |
| `{env}.onex.cmd.omniintelligence.tool-content.v1` | In | omniclaude | `NodeClaudeHookEventEffect` |
| `{env}.onex.evt.omniintelligence.intent-classified.v1` | Out | `NodeClaudeHookEventEffect` | omnimemory |
| `{env}.onex.cmd.omniintelligence.pattern-learning.v1` | In/Out | `NodeClaudeHookEventEffect` (Stop) | `NodePatternLearningEffect` |
| `{env}.onex.evt.omniintelligence.pattern-learned.v1` | Out | `NodePatternLearningEffect` | `NodePatternStorageEffect` |
| `{env}.onex.evt.omniintelligence.pattern-stored.v1` | Out | `NodePatternStorageEffect` | downstream |
| `{env}.onex.evt.omniintelligence.pattern-promoted.v1` | Out | `NodePatternPromotionEffect` | downstream |
| `{env}.onex.evt.omniintelligence.pattern-deprecated.v1` | Out | `NodePatternDemotionEffect` | downstream |

---

**Last Updated**: 2026-02-19
**See Also**: `omnibase_core/docs/architecture/ONEX_FOUR_NODE_ARCHITECTURE.md` — base class definitions, handler output constraints, and FSM/workflow subcontract reference.
