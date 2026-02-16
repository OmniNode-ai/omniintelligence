# Changelog

All notable changes to OmniIntelligence will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2026-02-16

### Changed

- **Bump omnibase_core** ^0.16.0 → ^0.18.0
- **Bump omnibase_infra** ^0.6.0 → ^0.7.0
- **Bump omnibase_spi** ^0.7.0 → ^0.9.0

### Fixed

- **Flat daemon hook payload reshaping** — reshape flat daemon hook payloads
  before Pydantic validation (#110)

## [0.2.0] - 2026-02-15

### Added

- **Intelligence pipeline wiring** — storage handler, node registration, and
  tool-content consumer for end-to-end pipeline execution (OMN-2222, #107)
- **CI compliance gates** — automated compliance checks for omniintelligence
  repository (OMN-2227, #108)
- **Node registration + pattern extraction** — wired intelligence nodes into
  registration system with pattern extraction support (OMN-2210, #105)
- **omnibase_core Python validators** — wired all validators and fixed
  violations (#103)

### Fixed

- **Missing pattern_learning_compute node** — added missing node and updated
  stale topic documentation (OMN-2221, #106)

## [0.1.1] - 2026-02-13

### Fixed

- **Orchestrator contract topic naming** — migrated all consumed/published
  topics from legacy `{env}.archon-intelligence.*` format to proper ONEX
  conventions (`onex.cmd.omniintelligence.*` / `onex.evt.omniintelligence.*`)
- **Command vs event channel semantics** — request topics now use `cmd`
  channel, outcome topics use `evt` channel
- **Event grammar normalization** — replaced irregular past-tense event names
  (`pattern-learned`, `quality-assessed`, `document-ingested`) with symmetric
  `-completed` suffix for fingerprint-safe registry pairing

### Added

- **pattern_extraction_compute** added to orchestrator `available_compute_nodes`
  and `dependencies`
- **Required status checks** on main branch protection (#100)

## [0.1.0] - 2026-02-13

Initial release of the OmniIntelligence platform — 15 ONEX nodes providing
code quality analysis, pattern learning, semantic analysis, and Claude Code
hook processing as a kernel domain plugin.

### Added

#### Domain Plugin Runtime

- **PluginIntelligence** domain plugin with full kernel lifecycle
  (`should_activate` / `initialize` / `wire_handlers` / `wire_dispatchers` /
  `start_consumers` / `shutdown`)
- Entry point registration (`onex.domain_plugins`) for automatic kernel
  discovery via `importlib.metadata`
- **MessageDispatchEngine** wiring with 4 handlers and 5 routes for
  topic-based event routing
- Contract-driven topic discovery from `contract.yaml` declarations —
  no hardcoded topic lists
- Message type registration via `RegistryMessageType`
- Protocol adapters for PostgreSQL, Kafka, intent classification, and
  idempotency tracking

#### Compute Nodes (Pure Functions)

- **NodeQualityScoringCompute** — code quality scoring with ONEX compliance
  checking, configurable weights, and recommendation generation
- **NodeSemanticAnalysisCompute** — semantic code analysis
- **NodeIntentClassifierCompute** — user prompt intent classification with
  keyword extraction for Claude Code hook events
- **NodePatternExtractionCompute** — extract patterns from code with tool
  failure detection
- **NodePatternLearningCompute** — ML pattern learning pipeline with feature
  extraction, clustering, confidence scoring, deduplication, and orchestration
- **NodePatternMatchingCompute** — match patterns against code
- **NodeSuccessCriteriaMatcherCompute** — match success criteria against
  execution outcomes
- **NodeExecutionTraceParserCompute** — parse execution traces into
  structured data

#### Effect Nodes (I/O)

- **NodeClaudeHookEventEffect** — process Claude Code hook events, route to
  intent classification, emit to Kafka
- **NodePatternStorageEffect** — persist patterns to PostgreSQL with
  governance checks and idempotency
- **NodePatternFeedbackEffect** — record session outcomes with rolling-window
  effectiveness scoring and contribution heuristics
- **NodePatternPromotionEffect** — promote patterns
  (provisional -> validated) with evidence tier gating
- **NodePatternDemotionEffect** — demote patterns
  (validated -> deprecated) based on feedback signals
- **NodePatternLifecycleEffect** — atomic pattern lifecycle transitions with
  audit trail and idempotency

#### Orchestrator Nodes

- **NodePatternAssemblerOrchestrator** — assemble patterns from execution
  traces

#### Reducer Nodes

- **NodeIntelligenceReducer** — unified FSM handler for ingestion,
  pattern_learning, and quality_assessment state machines

#### Pattern Learning Pipeline

- Feature extraction with strict output contracts
- Deterministic pattern clustering
- Decomposed confidence scoring with component breakdown
- Versioned signature-based deduplication
- Pattern compilation with safety validation
- L1 attribution binder and L2 lifecycle controller with evidence tier gating
- Pattern lifecycle state machine
  (`CANDIDATE` -> `PROVISIONAL` -> `VALIDATED` -> `DEPRECATED`)
- Learned patterns repository contract and ownership model

#### Database Schema

- Pattern storage schema with domain taxonomy
- Pattern injections table with A/B experiment support
- Pattern disable events table for runtime kill switch
- Disabled patterns current materialized view
- FSM state and history tables
- Constraint enhancements and lifecycle state transition validation
- FK scan report verifying all references are intra-service
- Schema migration freeze (`.migration_freeze`)

#### Event Bus Integration

- Kafka topic naming: `{env}.onex.{kind}.{producer}.{event-name}.v{version}`
- Subscribe topics: `claude-hook-event.v1`, `session-outcome.v1`,
  `pattern-lifecycle-transition.v1`, `pattern-learned.v1`,
  `pattern.discovered.v1`
- Publish topics: `intent-classified.v1`, `pattern-stored.v1`,
  `pattern-promoted.v1`, `pattern-deprecated.v1`
- Dead letter queue routing for failed messages
- Optional Kafka with graceful degradation — database operations succeed
  without Kafka

#### Architectural Enforcement

- I/O purity audit via AST analysis — nodes enforced as thin shells (<100
  lines, no logging, no try/except, no runtime container access)
- AST-based transport import validator (ARCH-002) — no Kafka imports in
  non-transport modules
- Contract linter with Pydantic validation for all 15 node contracts
- Pre-commit hooks for ruff, mypy strict, contract linting, and audit tests

#### Testing

- Unit tests for all handlers and compute nodes
- Integration tests: kernel boots with PluginIntelligence
- Integration tests: entry point discovery validation
- Integration tests: pattern matching compute with pattern storage effect
- E2E: Claude hook -> intent classification pipeline
- E2E: full pattern learning pipeline
- Golden path integration tests for pattern feedback verification

#### Docker Deployment

- Multi-stage Dockerfiles for orchestrator, reducer, compute, and effect
  nodes
- `docker-compose.yml` for local infrastructure (PostgreSQL, Qdrant,
  Memgraph, Valkey, Redpanda)
- `docker-compose.nodes.yml` for ONEX node services
- Stub launcher with health check endpoints pending RuntimeHostProcess
  integration

### Dependencies

- `omnibase_core` ^0.18.0
- `omnibase_infra` ^0.7.0
- `omnibase_spi` ^0.9.0
- Python >=3.12

[0.2.1]: https://github.com/OmniNode-ai/omniintelligence/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/OmniNode-ai/omniintelligence/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/OmniNode-ai/omniintelligence/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/OmniNode-ai/omniintelligence/releases/tag/v0.1.0
