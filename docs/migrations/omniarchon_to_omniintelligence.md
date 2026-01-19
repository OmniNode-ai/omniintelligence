# OmniArchon → OmniIntelligence Migration Guide

## 1. Objective
- Rebuild `omniarchon` intelligence, indexing, and pattern services as first-class Omninode nodes located in `omniintelligence`.
- Preserve contract-driven ingestion, vector search, and intelligence APIs while aligning with canonical node standards (`node_cli` pattern, linked documents, enum-backed tooling).
- Provide a repeatable process Claude Code Web can execute with copied source trees only.

## 2. Source Staging
```bash
export SOURCE_ROOT="/Volumes/PRO-G40/Code/omninode/repos"
export MIGRATION_ROOT="/tmp/omniarchon_migration"
mkdir -p "${MIGRATION_ROOT}"
rsync -a --delete "${SOURCE_ROOT}/omniarchon/" "${MIGRATION_ROOT}/omniarchon/"
git -C "${SOURCE_ROOT}/omniarchon" rev-parse HEAD > "${MIGRATION_ROOT}/REVISION.txt"
```
- Never push the staged copy; it exists solely for migration diffing.
- Capture supporting assets (docker-compose, SQL migrations) required for integration tests.

## 3. Target Repository Setup (`omniintelligence`)
- Clone or update `/Volumes/PRO-G40/Code/omninode/repos/omniintelligence` (create repo if absent).
- Ensure `poetry install` and baseline `pytest` succeed.
- Add migration docs directory `docs/migrations/`.
- Review canonical references from `omnibase_core`:
  - `docs/guides/node-building/`
  - `docs/guides/templates/ORCHESTRATOR_NODE_TEMPLATE.md`
  - `docs/guides/templates/REDUCER_NODE_TEMPLATE.md`
  - `docs/guides/templates/COMPUTE_NODE_TEMPLATE.md`
  - `docs/guides/templates/EFFECT_NODE_TEMPLATE.md`

## 4. Service Decomposition

| Legacy Area (`omniarchon`) | Target Node(s) (`omniintelligence`) | Notes |
|----------------------------|--------------------------------------|-------|
| `services/intelligence_request_service.py` orchestrating ingestion & intelligence routing | `nodes/intelligence_orchestrator` | Drive ingestion, analysis, and response workflows; integrate with event bus topics from `docs/architecture/INTELLIGENCE_SYSTEM_INTEGRATION.md`. |
| `services/ingestion_pipeline/` (Kafka consumers, retry logic) | `nodes/ingestion_reducer` + `nodes/ingestion_effect` | Reducer manages FSM, Effect handles Kafka/Qdrant/PostgreSQL side effects. |
| `services/vectorization/`, `test_vectorization_integration.py` | `nodes/vectorization_compute` | Encapsulate embedding generation, scoring, fallback models. |
| `services/pattern_learning/`, `docs/pattern_learning_engine/*` | `nodes/pattern_learning_compute` + optional orchestrator workflow steps | Align with ONEX compute patterns; maintain contract for pattern enrichment. |
| `services/search/api.py`, `docs/api/PATTERN_LEARNING_API_FOR_OMNICLAUDE.md` | `nodes/intelligence_api_effect` | Provide HTTP or Kafka façade; ensure contracts align with shared schemas. |
| `monitoring/`, `STRUCTURED_LOGGING_IMPLEMENTATION.md` | Observability mixins integrated into each node; share `tools/tool_structured_logging.py`. |

## 5. Node Stack Blueprint
1. **Orchestrator** (`intelligence_orchestrator`)
   - Coordinates ingestion, enrichment, vectorization, persistence pipelines.
   - Incorporates dependency resolver logic described in `docs/architecture/CORE_MIGRATION_ARCHITECTURE.md`.
2. **Reducer** (`ingestion_reducer`, `pattern_state_reducer`)
   - Converts manual state machines (`PIPELINE_TRACEABILITY.md`) to canonical reducer transitions with lease management.
3. **Compute** (`vectorization_compute`, `scoring_compute`, `pattern_quality_compute`)
   - Pure operations: embed text, compute hybrid scores, evaluate QoS metrics.
4. **Effect** (`ingestion_effect`, `search_gateway_effect`)
   - Handle Kafka topics, PostgreSQL, Qdrant, Memgraph interactions.

- Ensure each node follows versioned directory structure, contracts referencing subcontracts, and generated Pydantic models.

## 6. Migration Steps
1. **Generate scaffolds**
   ```bash
   cd /Volumes/PRO-G40/Code/omninode/repos/omniintelligence
   poetry run python -m omnibase_core.scripts.generate_node \
     --node-type orchestrator \
     --node-name intelligence_orchestrator \
     --domain intelligence \
     --output src/omniintelligence/nodes
   # Repeat for reducer/compute/effect nodes
   ```
2. **Port contracts and schemas**
   - Start from `MIGRATION_ROOT/omniarchon/contracts/`.
   - Convert HTTP payload schemas to YAML contracts referencing shared definitions (`omnibase_core/docs/reference/api`).
   - Include optional documents (e.g., `contract_capabilities.yaml`) for SLA metadata.
3. **Move business logic**
   - Translate pipeline classes to compute node services.
   - Inject dependencies via node config; drop global singletons.
   - Move asynchronous Kafka consumers into effect nodes using canonical `NodeEffectService`.
4. **Event Bus Alignment**
   - Map topics from `docs/KAFKA_LISTENER_ISSUE.md`, `docs/integration/*` to enumerations.
   - Document event schemas in `scenarios/` YAML files for integration tests.
5. **State & persistence**
   - Reducers own ingestion queue state, dedupe caches, and retries (see `ORPHAN_PREVENTION_IMPLEMENTATION.md`).
   - Persist state via `deployment_config.yaml` linking to infrastructure secrets.
6. **API migration**
   - For HTTP endpoints, implement effect node that interfaces with FastAPI or whichever adapter remains. Place HTTP adapter in `src/omniintelligence/adapters/http/`.
   - Document required deployment adjustments in repo-level `docs/`.
7. **Docs & tickets**
   - Update architecture docs referencing new nodes.
   - Create work tickets for follow-up tasks (archival of legacy code, rollout plan).

## 7. Testing & Validation
- **Unit tests**
  - **Note**: Current implementation uses flat structure (no `v1_0_0` subdirectories)
  - Tests are located directly under node directories (e.g., `src/omniintelligence/nodes/*/node_tests/`) or in the central `tests/` directory
  - Update fixtures from `tests/fixtures/` to canonical structure (`tests/fixtures/intelligence`).
  - Ensure each node has state, contract, and tool coverage.
- **Integration tests**
  - Recreate ingestion pipeline integration: spin up local Kafka/Qdrant using docker-compose file from `deployment/TREE_STAMPING_ADAPTER.md`.
  - Provide `tests/integration/intelligence/test_ingestion_pipeline.py` verifying event flow orchestrator→effect→compute→reducer.
- **Contract validation**
  - Add `tests/contracts/test_intelligence_contracts.py` running `omnibase_core` validator.
- **Performance baseline**
  - Use data from `performance_test_results_1762181933.json` to define thresholds; add pytest markers `@pytest.mark.performance`.
- **CI integration**
  - Update pipeline to run `pytest -m "not slow"`, and separate job for `pytest -m performance`.

## 8. Automation Assets
- `scripts/generate_intelligence_nodes.py`: orchestrates scaffold generation for all node types with consistent naming, optional `--dry-run`.
- `scripts/import_archon_contracts.py`: converts Python dataclasses to YAML contracts via AST inspection.
- `scripts/run_intelligence_migration_tests.sh`:
  ```bash
  #!/usr/bin/env bash
  set -euo pipefail
  # Note: Current implementation uses flat structure (no v1_0_0 subdirectories)
  # Tests are located directly under node directories or in tests/
  poetry run pytest src/omniintelligence/nodes/intelligence_orchestrator/
  poetry run pytest src/omniintelligence/nodes/intelligence_reducer/
  poetry run pytest tests/integration/intelligence
  poetry run pytest -m performance --maxfail=1
  ```
- Document each script in `docs/migrations/README.md` (create if missing).

## 9. Validation Checklist

### Required Node Artifacts

All ONEX nodes must follow the canonical directory structure. Two patterns are supported:

**Pattern A: Flat Structure** (current implementation)
```
nodes/
└── node_name/
    ├── __init__.py              # Module initialization (REQUIRED)
    ├── __main__.py              # CLI entry point (REQUIRED for executable nodes)
    ├── contract.yaml            # Main node contract definition (REQUIRED)
    ├── models/                  # Pydantic models directory (REQUIRED)
    │   ├── __init__.py          # Model exports
    │   ├── model_*.py           # Input/output model classes
    │   └── enum_*.py            # Enumeration definitions
    └── node.py                  # Main node implementation (REQUIRED)
```

**Pattern B: Versioned Structure** (canonical reference)
```
nodes/
└── node_name/
    ├── __init__.py
    └── v1_0_0/
        ├── __init__.py
        ├── __main__.py
        ├── contract.yaml
        ├── contracts/           # Subcontracts directory
        ├── models/
        ├── node.py
        ├── introspection.py
        ├── scenarios/
        └── node_tests/
```

**Required Artifacts Checklist**:

- [ ] `__init__.py` - Module initialization with exports
- [ ] `__main__.py` - CLI entry point (for executable nodes)
- [ ] `contract.yaml` - Main node contract (see below for required fields)
- [ ] `contracts/` - Subcontracts directory containing:
  - `fsm_contract.yaml` - FSM definitions (for reducers)
  - `event_type_contract.yaml` - Event schemas (for effect nodes)
  - `contract_models.yaml` - Shared model definitions
  - `contract_cli.yaml` - CLI parameter definitions
- [ ] `node.py` - Main node implementation
- [ ] `models/` - Pydantic models directory (see below)
- [ ] `introspection.py` - Runtime introspection support
- [ ] `scenarios/` - YAML integration test scenarios
- [ ] `node_tests/` - Node-specific unit tests

**Contract.yaml Required Fields**:
- `contract_version` (semver)
- `node_version` (semver)
- `name`, `node_type`, `description`
- `input_model` and `output_model` references
- `operations` list with input/output field mappings
- `error_handling` configuration
- `health_check` settings
- `metadata` (author, dates, tags)

**Models Directory Contents**:
- `__init__.py` with model exports
- `model_<name>_input.py` - Input Pydantic model
- `model_<name>_output.py` - Output Pydantic model
- `enum_*.py` - Enumeration types (operation types, states, etc.)

**Node.py Requirements**:
- Node class following naming convention (`Node<Name><Type>`)
- Async execution method (`execute_compute`, `execute_effect`, etc.)
- Proper error handling and logging
- ARCHITECTURE_DECISIONS.md - Design rationale documenting architectural choices

**Optional Artifacts** (recommended for production nodes):

- [ ] `infrastructure/` - Supporting infrastructure code (for effect nodes)

### Linked Document Contracts

ONEX uses a linked-doc architecture where contracts reference external configuration files.

**Configuration Contracts**:

- [ ] `node_config.yaml` - Node-specific configuration schema:
  - Performance settings (timeouts, memory limits, concurrency)
  - Resource requirements (CPU, memory, disk, network)
  - Runtime configuration (environment variables, startup/shutdown)
  - Monitoring configuration (metrics, health checks, alerts)
  - Security configuration (input sanitization, access controls)
  - Feature flags

- [ ] `deployment_config.yaml` - Deployment and infrastructure configuration:
  - Container settings (image, resources, replicas)
  - Environment-specific overrides
  - Secret references (never hardcoded values)
  - Network configuration
  - Scaling policies

**Subcontract Types** (6 canonical types):

- [ ] `contracts/fsm_contract.yaml` - Finite State Machine definition:
  - State enumeration
  - Transition rules
  - Guard conditions
  - Entry/exit actions

- [ ] `contracts/event_type_contract.yaml` - Event type definitions:
  - Event schemas
  - Topic mappings
  - Payload validation rules

- [ ] `contracts/aggregation_contract.yaml` - Aggregation patterns:
  - Aggregation strategies
  - Windowing configuration
  - Merge operations

- [ ] `contracts/state_management_contract.yaml` - State persistence:
  - State schema
  - Persistence strategy
  - Recovery procedures
  - Snapshot configuration

- [ ] `contracts/routing_contract.yaml` - Message routing:
  - Routing rules
  - Filter expressions
  - Destination mappings

- [ ] `contracts/caching_contract.yaml` - Cache configuration:
  - Cache strategy (LRU, TTL, etc.)
  - Key patterns
  - Invalidation rules
  - Size limits

**Linked Document Reference Patterns**:

In `contract.yaml`, use `$ref` for external references:
```yaml
# Schema references
input_state:
  full_schema: {$ref: "contracts/contract_models.yaml#/input_state"}

output_state:
  full_schema: {$ref: "contracts/contract_models.yaml#/output_state"}

# CLI parameter references
cli_parameters: {$ref: "contracts/contract_cli.yaml#/cli_parameters"}

# Subcontract references
subcontracts:
  models: {$ref: "contracts/contract_models.yaml"}
  cli: {$ref: "contracts/contract_cli.yaml"}
  actions: {$ref: "contracts/contract_actions.yaml"}
  validation: {$ref: "contracts/contract_validation.yaml"}
  fsm: {$ref: "contracts/fsm_contract.yaml"}
```

Alternative explicit linked_contracts format:
```yaml
linked_contracts:
  - type: "node_config"
    path: "./node_config.yaml"
    description: "Node-specific configuration"
  - type: "deployment_config"
    path: "./deployment_config.yaml"
    description: "Deployment configuration"
  - type: "subcontract"
    path: "./contracts/fsm_contract.yaml"
    description: "FSM state transitions"
  - type: "subcontract"
    path: "./contracts/event_type_contract.yaml"
    description: "Event type definitions"
```

### Code Quality

**Required Node Artifacts** (all nodes must have):
- [ ] `__init__.py` - Module initialization with exports
- [ ] `__main__.py` - CLI entry point (for executable nodes)
- [ ] `contract.yaml` - Main node contract definition
- [ ] `contracts/` - Subcontracts directory (fsm, event_type, models, cli, etc.)
- [ ] `models/` - Pydantic models directory
- [ ] `node.py` - Main node implementation following `Node<Name><Type>` naming
- [ ] `introspection.py` - Runtime introspection support
- [ ] `scenarios/` - YAML integration test scenarios
- [ ] `node_tests/` - Node-specific unit tests
- [ ] `ARCHITECTURE_DECISIONS.md` - Design rationale and architectural choices

**Linked-Doc Contracts** (properly configured):
- [ ] `node_config.yaml` - Node-specific configuration schema
- [ ] `deployment_config.yaml` - Deployment and infrastructure configuration
- [ ] Subcontracts using `$ref` pattern:
  - `contracts/fsm_contract.yaml` - FSM definitions (for reducers)
  - `contracts/event_type_contract.yaml` - Event schemas (for effect nodes)
  - `contracts/contract_models.yaml` - Shared model definitions
  - `contracts/contract_cli.yaml` - CLI parameter definitions
  - `contracts/aggregation_contract.yaml` - Aggregation patterns (if applicable)
  - `contracts/state_management_contract.yaml` - State persistence (for reducers)
  - `contracts/routing_contract.yaml` - Message routing (if applicable)
  - `contracts/caching_contract.yaml` - Cache configuration (if applicable)

**Validation Checks**:

*Node Artifact Verification* (required for all nodes):
- [ ] Each node has `__init__.py` with proper exports
- [ ] Each node has `contract.yaml` with required fields (contract_version, node_version, name, node_type, description, input_model, output_model)
- [ ] Each node has `node.py` with class following `Node<Name><Type>` naming convention
- [ ] Each node has `models/` directory with input/output Pydantic models
- [ ] Each node has `introspection.py` for runtime introspection support

*Production Readiness Checks* (recommended for production nodes):
- [ ] `contracts/` subdirectory for subcontracts (FSM, event types, etc.)
- [ ] `scenarios/` for YAML integration test scenarios
- [ ] `node_tests/` or tests in `tests/` for node-specific tests
- [ ] `ARCHITECTURE_DECISIONS.md` documenting design rationale
- [ ] Linked-doc contracts (`node_config.yaml`, `deployment_config.yaml`) properly configured

*Code Quality*:
- [ ] Enumerations replace string literals for tool names, topics, and status codes.
- [ ] Contract validator passes with zero warnings.
- [ ] Event replay integration test validates ingestion → intelligence → response.
- [ ] Observability hooks emit logs/metrics consistent with `STRUCTURED_LOGGING_IMPLEMENTATION.md`.
- [ ] Deployment manifests updated for new node entrypoints and containers.

## 10. Risks & Mitigation
- **Kafka Topic Drift**: Document topic mappings; add regression test verifying expected topics exist.
- **Vector Model Differences**: Keep fallback model configuration in `node_config.yaml`, add fixtures covering both GPU and CPU paths.
- **Stateful Reducer Bugs**: Provide snapshot tests comparing reducer state before/after replays.
- **Migration Downtime**: plan blue/green rollout, run orchestrator in shadow mode before cutover.

## 11. Documentation Updates
- Update `docs/architecture/INTELLIGENCE_SYSTEM_INTEGRATION.md` to describe node architecture.
- Cross-reference `docs/planning/AUTOMATED_CORE_MIGRATION_SYSTEM.md`.
- Archive legacy documentation in `docs/archive/migrations/` with note pointing to this guide.
- Review active prep work:
  - Branch `feature/file-tree-graph-implementation` (currently ahead of `main` by two commits) contains file graph ingestion updates that may inform reducer scope.
  - Coordinate with open PRs (#27 `feature/file-tree-graph-implementation`, #26 Redpanda migration, #25 Haystack demo) to avoid rework or duplicate migration steps.

## 12. Pending Implementation TODOs

The following items are marked as TODO in contract files and require implementation:

### Intent/State Model TODOs

| Location | TODO ID | Description | Priority | Notes |
|----------|---------|-------------|----------|-------|
| `nodes/intelligence_reducer/contract.yaml:307` | - | Intent emission models not implemented | Medium | Create `ModelWorkflowTriggerPayload` and `ModelEventPublishPayload` when implementing intent-based workflow triggering |
| `nodes/intelligence_reducer/contract.yaml:327` | - | State model not implemented | Medium | Create `ModelIntelligenceState` for pure reducer pattern with immutable state |

### Protocol Module TODOs

| Location | TODO ID | Description | Priority | Notes |
|----------|---------|-------------|----------|-------|
| `nodes/vectorization_compute/contract.yaml:52` | ONEX-EMBED-001 | Embedding model protocol not created | Low | Create `EmbeddingModelProtocol` in `omniintelligence.protocols` |
| `nodes/intent_classifier_compute/contract.yaml:38` | ONEX-PROTO-002 | Intent classifier protocol not created | Low | Create `IntentClassifierProtocol` in `omniintelligence.protocols` |
| `nodes/quality_scoring_compute/contract.yaml:38` | ONEX-PROTO-003 | Quality analyzer protocol not created | Low | Create `QualityAnalyzerProtocol` in `omniintelligence.protocols` |

### Resolution Plan

1. **Phase 1 (v0.2.0)**: Implement `ModelIntelligenceState` for pure reducer pattern
2. **Phase 2 (v0.3.0)**: Add intent emission infrastructure with `ModelWorkflowTriggerPayload`
3. **Phase 3 (v0.4.0)**: Create protocols module and formalize all protocol interfaces:
   - `EmbeddingModelProtocol` - Interface for embedding generation
   - `IntentClassifierProtocol` - Interface for intent classification
   - `QualityAnalyzerProtocol` - Interface for quality analysis

These TODOs are tracked in the contract files themselves with inline comments explaining the intended implementation. Each TODO includes a reference back to this document for traceability.
