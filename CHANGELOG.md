## v0.24.0 (2026-05-21)

### Features
- feat: port change-aware test selection to omniintelligence (#645)
- feat: record dispatch feedback outcomes (#634)
- feat: accept dispatch worker cost payload (#630)
- feat: subscribe pattern feedback to dispatch outcomes (#628)
- feat: wire dispatch outcome quality scoring (#627)
- feat: use shared usage source enum (#629)
- feat: scaffold dispatch outcome eval effect (#626)
- feat: wire docs-validate as required CI gate (#623)
- feat: migrate runner selector to vars.OMNI_TRUSTED_CI_RUNS_ON_JSON (#649)
- feat: remove ANTHROPIC_API_KEY hard requirement from Claude API fallback (#632)

### Bug Fixes
- fix: remove LOCAL_LLM_SHARED_SECRET source synthesis in adapter (#651)
- fix: wire skip-token rejection CI gate (#650)
- fix: route merge queue off self-hosted runner (#652)
- fix: consolidate env fallback validator (#647)
- fix: resolve fallback validator review threads (#646)
- fix: replace 4 silent env fallbacks with os.environ[] (#644)
- fix: wire Kafka producer into crawl scheduler registry (#639)

### Tests
- test: verify seed_patterns_from_families dry-run pipeline (#641)
- test: verify AST crawl yields >500 entities across 4 repos (#640)
- test: add integration tests for node family grouping (#633)

### Pin Updates (2026-05-21 release wave 2)
- omnibase-core: `>=0.40.1,<0.41.0` → `>=0.42.0,<0.43.0`
- omnibase-infra: `==0.34.2` → `==0.36.1`
- omnibase-spi: `==0.20.6` → `==0.21.0`

### Other Changes
- chore(deps): bump urllib3 from 2.6.3 to 2.7.0 (#648)
- chore(deps-dev): bump python-multipart 0.0.26 → 0.0.27 (#643)
- chore(deps): bump mako 1.3.11 → 1.3.12 (#642)
- chore(deps-dev): update aiokafka requirement (#638)
- chore(deps): bump actions/checkout from 4 to 6 (#637)

## v0.23.0 (2026-04-03)

### Features
- feat: wire ChangeFrame data from STOP payload into objective evaluation (#536)
- feat(intelligence): embed source content in crawl events (#532)
- feat(review): add Qwen3-Next-80B-A3B to model registry (#528)
- feat: add NodeFamily to learned_patterns bridge (#527)
- feat: add NodeFamily grouping for subsystem pattern instances (#526)
- feat: add match_pattern_role function for role detection (#522)
- feat: add ModelPatternDefinition and ModelPatternRole (#521)
- feat: add directory scanner for role occurrences (#523)
- feat: add cross-repo pattern baseline scanner (#524)
- feat: add contract declarations for 7 orphan dispatch routes (#516)
- feat: wire dispatch handlers for 7 command topics (#515)
- feat: replace hardcoded INTELLIGENCE_NODES with contract-driven discovery (#512)
- feat: intelligence contract packages — auto-wiring migration (#510)
- feat: add projection handler registration tests and pattern seed script (#508)

### Bug Fixes
- fix: update is_current test assertions after PR #535 removal (#537)
- fix: remove is_current filter from pattern read queries (#535)
- fix: set is_current=TRUE for version-1 patterns and lifecycle transitions (#534)
- fix(api): use correct column name 'status' in retention cleanup SQL (#533)
- fix(intelligence): disable old behavioral pattern extractors (#531)
- fix(intelligence): remove all localhost fallbacks, require env vars (#530)
- fix: update test fixtures to match ModelCodeEntity/ModelCodeRelationship schema (#529)
- fix: update test fixtures to match ModelCodeEntity/ModelCodeRelationship schema (#517)
- fix(ci): auto-tag workflow matches chore: release PR titles (#513)
- fix: add MIN_CLASSIFIABLE_LENGTH guard and clean up TODO (#507)

### Other Changes
- chore(deps): bump omnibase_core to 0.37.0 (#538)
- test: verify role detection on real compute node file (#520)
- test: verify AST extraction on all four ONEX base node classes (#519)
- test: verify AST extraction on NodeCompute base class (#518)
- test: document AST extraction quality baseline and known gaps (#525)
- test: add dispatch parity contract test (#514)
- chore: bump version to 0.22.0 for release (#511)
- test: add CI pattern pipeline health checks and trigger verification (#509)

## v0.21.1 (2026-03-31)

### Changed
- chore(deps): bump omnibase_core to 0.36.0, omnibase_infra to 0.30.1
- ci: add onex compliance check to CI (#505)

## v0.21.0 (2026-03-30)

### Changed
- chore(deps): bump omnibase_infra to 0.30.0 (#504)

## v0.20.0 (2026-03-28)

### Added
- ci: add CodeQL security scanning workflow (#491)
- feat(ci): add auto-merge-on-open workflow (#490)
- feat(ci): add handler contract compliance check (#488)
- feat(topics): centralize omnidash projection topics + emission regression tests (#487)

### Fixed
- fix(types): resolve 32 mypy strict errors across 15 files (#486)
- fix: pass event_publisher to UtilizationLLMClient for LLM cost emission (#483)

### Changed
- chore(deps): bump omnibase-core to 0.34.0

### Dependencies
- omnibase-core 0.33.1 -> 0.34.0

## v0.19.1 (2026-03-27)

### Fixed
- fix: add tiktoken to dev dependencies (#480)

### Changed
- chore(lint): remove 17 stale noqa directives for globally-ignored rules (#481)
- chore(deps): bump omnibase_core to 0.33.1, omnibase_spi to 0.20.2, omnibase_infra to 0.28.0

## v0.19.0 (2026-03-26)

### Added
- feat: wire CI intelligence nodes into dispatch engine (#469)
- feat(crawl): add Postgres persistence to sync crawl pipeline (#474)

### Changed
- chore: standardize TODO markers with ticket references (#475)
- chore: bump omnibase-spi to 0.20.1 (#476)
- chore(deps): bump omnibase_core to 0.33.0
- chore(deps-dev): bump requests from 2.32.5 to 2.33.0 (#473)

### Dependencies
- omnibase-core 0.32.0 -> 0.33.0
- omnibase-spi 0.20.0 -> 0.20.1
- omnibase-infra 0.27.0 -> 0.27.1

## v0.18.0 (2026-03-25)

### Added
- feat: wire model_selector DecisionEmitter into dispatch engine (#467)
- feat: register review_pairing node package for topic discovery (#466)
- feat(runtime): wire orchestrator, reducer, and CI nodes into dispatch engine (#470)
- feat: add review_pairing PairingEngine to intelligence handler specs (#464)

### Fixed
- fix: add code_entities and code_relationships to schema manifest (#468)
- fix: add relevance filters to file access pattern extraction (#465)
- fix: correct stale DATABASE_URL default to omniintelligence database (#463)

### Changed
- feat(projection): truncate pattern_signature to 512 chars in projection snapshots (#461)
- chore(deps): bump omnibase-core to 0.32.0, omnibase-infra to 0.27.0 (coordinated release)
- chore(deps): bump omnibase_core to 0.31.0 (#462)

## v0.17.0 (2026-03-24)

### Added
- feat(calibration): add documentation and wiring for calibration system (#455)
- feat(calibration): add CLI entry point for calibration (#453)
- feat(calibration): add prompt writer for few-shot injection (#452)
- feat(calibration): add calibration run orchestrator (#451)
- feat(calibration): add few-shot extractor (#450)
- feat(review-pairing): add calibration Kafka topic (#449)
- feat(review-pairing): add calibration persistence layer (#448)
- feat(review-pairing): add calibration scorer (#447)
- feat(review-pairing): add finding alignment engine (#445)
- feat(review-pairing): add R1-R6 finding serializer (#444)
- feat(review-pairing): add calibration data models (#442)
- feat(db): add calibration runs migration (#443)
- feat: wire omniintelligence event emissions for omnidash upstream (#446)

### Tests
- test(calibration): add calibration integration tests (#454)

### Changed
- fix(deps): update stale omnibase-infra and spi version pins (#438)
- chore(deps): bump omnibase-infra from 0.22.0 to 0.24.1 (#439)
- chore(deps): bump actions/checkout from 4 to 6 (#440)
- chore(deps-dev): bump omnibase-spi from 0.18.0 to 0.19.1 (#441)

## v0.16.0 (2026-03-20)

### Added
- feat(rl): policy-to-Bifrost config exporter with fidelity check (#405)
- feat(rl): routing observation builder + offline training pipeline (#404)
- feat: add periodic promotion-check scheduler to plugin lifecycle (#395)
- feat(rl): add episode replay buffer and data sources (#403)
- feat(rl): observation, action, and reward contracts (#400)
- feat: add promotion-check dispatch handler (#392)
- feat: add one-time bootstrap promotion sweep script (#396)
- feat(rl): add reward shaping module with calibration gate (#399)
- feat: wire utilization scoring handler into dispatch engine (#394)

### Tests
- test: add E2E verification script for pattern lifecycle pipeline (#397)

## v0.15.0 (2026-03-19)

### Added
- feat(ci): deploy CodeQL security scanning to omniintelligence (#382)
- feat(audit): add NodeContextAuditAggregatorCompute node (#373)
- feat(telemetry): add LLM call completion event for Cost Trends page (#371)

### Changed
- ci(omniintelligence): add ruff UP007 standards compliance workflow (#381)
- chore(standards): fix PEP 604 type-unions and mypy errors (#380)
- refactor: deduplicate topic constants to single source in omniintelligence (#372)
- chore(deps): bump omnibase-core to 0.29.0, omnibase-spi to 0.18.0, omnibase-infra to 0.22.0

### Fixed
- fix: remove {env}. prefix from contract YAML and fix port defaults (#370)

## v0.13.2 (2026-03-13)

### Other Changes
- chore(deps): bump omnibase_core to 0.27.0, omnibase_infra to 0.20.0 (#351)

## v0.13.1 (2026-03-13)

### Other Changes
- chore(deps): bump omnibase_infra to 0.18.0 (#349)

## v0.13.0 (2026-03-12)

### Features
- feat(spdx): add validate-spdx-headers pre-commit hook and stamp all Python files (#348)

### Other Changes
- chore(deps): bump omnibase_infra to 0.17.0 (#346)

# Changelog

All notable changes to OmniIntelligence will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.10.0] - 2026-03-07

### Added
- Protocol handlers for declarative effect nodes (#314)
- NodeStorageRouterEffect for storage coordination (#313)
- LOCAL_OPENAI embedding provider for MLX server (#312)
- `project_scope` field to learned patterns (#303)

### Fixed
- Pin actions/checkout@v4 and actions/setup-python@v5 (#311)
- Remove `{env}.` topic prefix from CLAUDE.md, make correlation_id required (#309)
- Remove boilerplate_docstring AI-slop violations across 100 files (#305)
- Convert all :named SQL placeholders to $N positional syntax (#302)
- Convert upsert_pattern SQL to asyncpg positional syntax (#301)

### Changed
- CI resilience fixes (#304)
- Relax ONEX version bounds, raise core lower bound to >=0.23.0 (#308)
- Add cloud bus guard pre-commit hook (#310)
- Add no-env-file pre-commit hook (#307)
- Add no-planning-docs pre-commit hook (#300)

### Dependencies
- `omnibase-core` pinned to `0.24.0`
- `omnibase-spi` pinned to `0.15.1`
- `omnibase-infra` pinned to `0.16.0`

## [0.9.2] - 2026-03-03

### Dependencies
- `omnibase-infra` bumped to `>=0.14.0,<0.15.0` (was `>=0.13.0,<0.14.0`) to resolve dependency conflict with `omnibase-infra 0.14.0` release

## [0.8.0] - 2026-02-28

### Added
- Bifrost feedback loop consumer for routing-feedback events (#240)
- `emitted_at` field to intent-classified.v1 event payload (#236)
- Import canonical `ModelRewardAssignedEvent` from omnibase_core (#237)
- AI-slop checker Phase 2 rollout (#243)
- Migration 019 for `agent_actions` and `workflow_steps` tables (#245)

### Fixed
- Wire PostToolUse write path to `omniintelligence.agent_actions` (#246)
- Switch routing-feedback consumer from `routing-outcome-raw.v1` to `routing-feedback.v1` (#242)
- Wire intent output topics to downstream consumers (#239)
- Remove internal IP references from `.env.example` (#241)
- Replace Step N narration with intent comments in handler docs (#244)
- Tune AI-slop checker v1.0 — scope `step_narration` to markdown only (#248)
- Add code fence tracking to AI-slop checker follow-up (#249)

### Dependencies
- `omnibase-core` bumped to >=0.22.0,<0.23.0 (was ==0.21.0)
- `omnibase-spi` bumped to >=0.15.0,<0.16.0 (was ==0.14.0)
- `omnibase-infra` bumped to >=0.13.0,<0.14.0 (was >=0.12.0,<0.13.0)

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
  in sync without polling the database. (#135)
- **Integration tests for `handle_intent_classification` langextract seam** —
  covers the full path from raw hook payload through intent classification
  to Kafka emission. (#133)

### Fixed

- **Dispatch handlers reshape crash** — NACK loop on every omniclaude hook
  event caused by missing payload reshaping before dispatch. (#132)
- **Routing feedback orphan topic** — add `routing.feedback` consumer to
  prevent unrouted messages from building up on the orphan topic. (#130)
- **session_id propagation** — thread `session_id` through the compliance
  evaluate command and corresponding event. (#131)
- **Multi-class file split** — split files containing multiple classes to
  satisfy the architecture validator. (#126)
- **Rename `ServiceHandlerRegistry` → `RegistryLifecycleHandlers`** — align
  with ONEX naming conventions. (#127)
- **Tech debt from an earlier review cycle** — address deferred architectural
  items flagged during that PR review. (#134)

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
  results. (#124)
- **Gated intelligence introspection publishing** — intelligence introspection
  events are now published only to the designated container, preventing
  unintended broadcast to other consumers. (#123)

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
  blocking others. (#120)

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
  tool-content consumer for end-to-end pipeline execution (#107)
- **CI compliance gates** — automated compliance checks for omniintelligence
  repository (#108)
- **Node registration + pattern extraction** — wired intelligence nodes into
  registration system with pattern extraction support (#105)
- **omnibase_core Python validators** — wired all validators and fixed
  violations (#103)

### Fixed

- **Missing pattern_learning_compute node** — added missing node and updated
  stale topic documentation (#106)

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

[0.10.0]: https://github.com/OmniNode-ai/omniintelligence/compare/v0.9.4...v0.10.0
[0.6.0]: https://github.com/OmniNode-ai/omniintelligence/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/OmniNode-ai/omniintelligence/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/OmniNode-ai/omniintelligence/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/OmniNode-ai/omniintelligence/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/OmniNode-ai/omniintelligence/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/OmniNode-ai/omniintelligence/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/OmniNode-ai/omniintelligence/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/OmniNode-ai/omniintelligence/releases/tag/v0.1.0
