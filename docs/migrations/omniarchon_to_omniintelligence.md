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
  - Relocate tests under `src/omniintelligence/nodes/*/v1_0_0/node_tests/`.
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
  poetry run pytest src/omniintelligence/nodes/intelligence_orchestrator/v1_0_0/node_tests
  poetry run pytest src/omniintelligence/nodes/ingestion_reducer/v1_0_0/node_tests
  poetry run pytest tests/integration/intelligence
  poetry run pytest -m performance --maxfail=1
  ```
- Document each script in `docs/migrations/README.md` (create if missing).

## 9. Validation Checklist
- [ ] All node directories include `contract.yaml`, `contracts/`, `models/`, `node.py`, `introspection.py`, and scenario/tests.
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
