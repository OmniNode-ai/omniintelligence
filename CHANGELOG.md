# Changelog

All notable changes to OmniIntelligence will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2026-02-27

### Changed
- Version bump as part of coordinated OmniNode platform release (release-20260227-eceed7)

### Dependencies
- omnibase-spi pinned to 0.14.0
- omnibase-core pinned to 0.21.0

## [0.6.0] - 2026-02-24

### Added
- MIT LICENSE and SPDX copyright headers (migrated from Apache-2.0)
- CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md
- GitHub issue templates and PR template
- `.github/dependabot.yml`
- `no-internal-ips` pre-commit hook

### Changed
- Bumped `omnibase-core` to 0.19.0, `omnibase-spi` to 0.12.0, `omnibase-infra` to 0.10.0
- License changed from Apache-2.0 to MIT
- Updated test registries to include new nodes: `node_document_parser_compute`, `node_doc_staleness_detector_effect`, `node_context_item_writer_effect`, `node_doc_promotion_reducer`

### Fixed
- Documentation cleanup: removed internal IP references, added Quick Start
- All Apache-2.0 SPDX headers migrated to MIT

## [0.5.0] - 2026-02-20

### Added

- **NodePatternProjectionEffect** — publishes a pattern snapshot event on
  every lifecycle change, enabling downstream projection consumers to stay
  in sync without polling the database. (OMN-2424, #135)
- **Integration tests for `handle_intent_classification` langextract seam** —
  covers the full path from raw hook payload through intent classification
  to Kafka emission. (OMN-2377, #133)

### Fixed

- **Dispatch handlers reshape crash** — NACK loop on every omniclaude hook
  event caused by missing payload reshaping before dispatch. (OMN-2423, #132)
- **Routing feedback orphan topic** — add `routing.feedback` consumer to
  prevent unrouted messages from building up on the orphan topic.
  (OMN-2366, #130)
- **session_id propagation** — thread `session_id` through the compliance
  evaluate command and corresponding event. (OMN-2368, #131)
- **Multi-class file split** — split files containing multiple classes to
  satisfy the architecture validator. (OMN-2206, #126)
- **Rename `ServiceHandlerRegistry` → `RegistryLifecycleHandlers`** — align
  with ONEX naming conventions. (OMN-2200, #127)
- **Tech debt from OMN-2221 review cycle** — address deferred architectural
  items flagged during the OMN-2221 PR review. (OMN-2321, #134)

### Changed

- **Bump omnibase_core** ^0.18.0 → ^0.18.1
- **Bump omnibase_infra** ^0.8.0 → ^0.9.0
- **omnibase_spi** remains ^0.10.0

### Documentation

- Migrated documentation to `omnibase_core` format. (#128)

## [0.4.0] - 2026-02-19

### Added

- **Compliance evaluation effect** (`NodeComplianceEvaluateEffect`) — consumes
  `compliance-evaluate` events and processes ONEX compliance evaluation
  results. (OMN-2339, #124)
- **Gated intelligence introspection publishing** — intelligence introspection
  events are now published only to the designated container, preventing
  unintended broadcast to other consumers. (OMN-2342, #123)

### Changed

- **Bump omnibase_core** ^0.17.0 → ^0.18.0
- **Bump omnibase_infra** ^0.7.0 → ^0.8.0
- **Bump omnibase_spi** ^0.8.0 → ^0.10.0

## [0.3.0] - 2026-02-18

### Added

- **Enforcement feedback loop** (`NodeEnforcementFeedbackEffect`) — consumes
  `onex.evt.omniclaude.pattern-enforcement.v1` events and applies conservative
  `-0.01` quality score adjustments per confirmed violation (requires both
  `was_advised=True` and `was_corrected=True`). 50 confirmed violations to drop
  from 1.0 to 0.5. Per-violation error isolation prevents one DB failure from
  blocking others. (OMN-2270, #120)

### Fixed

- **Remove hardcoded `topic_env_prefix`** from promotion and demotion effect
  nodes — all Kafka topics now use canonical constants directly
  (`TOPIC_PATTERN_LIFECYCLE_CMD_V1`) instead of runtime f-string concatenation
  with a hardcoded `"dev"` prefix. Fixes broken constant reference where
  `TOPIC_SUFFIX_PATTERN_LIFECYCLE_CMD_V1` was renamed but usages were not
  updated. (#121)

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

[0.6.0]: https://github.com/OmniNode-ai/omniintelligence/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/OmniNode-ai/omniintelligence/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/OmniNode-ai/omniintelligence/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/OmniNode-ai/omniintelligence/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/OmniNode-ai/omniintelligence/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/OmniNode-ai/omniintelligence/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/OmniNode-ai/omniintelligence/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/OmniNode-ai/omniintelligence/releases/tag/v0.1.0
