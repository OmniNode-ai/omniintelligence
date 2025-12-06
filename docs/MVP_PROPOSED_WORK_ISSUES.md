# MVP Proposed Work Issues - omniintelligence

**Repository**: omniintelligence
**Version Target**: v0.5.0 (Runtime Host Integration)
**Generated**: 2025-12-03
**Last Updated**: 2025-12-03
**Linear Project**: MVP - OmniIntelligence Runtime Host

---

## Overview

This document outlines proposed issues for migrating OmniIntelligence from the 1-container-per-node architecture to the Runtime Host architecture, derived from the architecture refactoring planning documents.

**Reference Documents**:
- `docs/RUNTIME_HOST_REFACTORING_PLAN.md`
- `omnibase_core/docs/MINIMAL_RUNTIME_PHASED_PLAN.md`
- `omnibase_spi/docs/PROTOCOL_INTERFACES_PLAN.md`
- `omnibase_infra/docs/DECLARATIVE_EFFECT_NODES_PLAN.md`

---

## Performance Regression Budget

> **HARD LIMITS**: The new architecture MUST NOT exceed:
> - **500ms** message latency (p99)
> - **400MB** RAM per runtime host container
> - **15%** CPU at idle
>
> Changes that violate these limits are **rejected**.
>
> **Note**: Performance regression tests should be marked `xfail` until routing and event bus integration are stable. Enforce hard limits only after Beta.

---

## Milestone Classification

All issues are classified by milestone to avoid over-specification:

| Milestone | Definition | Stability Requirement |
|-----------|------------|----------------------|
| **MVP** | Minimum viable runtime host with basic node execution | Architecture stable enough to route envelopes |
| **Beta** | Production-ready with monitoring, chaos testing, full validation | Handlers and contracts frozen |
| **GA** | Full feature set with performance guarantees | All metrics enforced |

> **CRITICAL**: Do not implement Beta/GA items during MVP phase. This prevents architecture bloat.

---

## Platform vs Application Concerns

Several components defined here should ultimately live in platform repos, not omniintelligence:

| Component | Current Location | Correct Location | Reason |
|-----------|-----------------|------------------|--------|
| Dependency graph validator | omniintelligence | omnibase_core/validators | Reusable platform concern |
| Envelope validator | omniintelligence | omnibase_core/validators | Single source of truth |
| Health/Lifecycle enums | omniintelligence | omnibase_core/runtime | Platform-level concern |
| RuntimeProfileDefinition | omniintelligence | omnibase_core/runtime | Needs formal contract |
| NodeMeta model | omniintelligence | omnibase_core/runtime | Required by NodeRuntime |
| Error taxonomy | omniintelligence | omnibase_core/errors | Unified error model |

> **Action**: For MVP, implement in omniintelligence with clear `# TODO: Move to omnibase_core` markers. Migrate during Beta.

---

## Summary Statistics

| Phase | Issue Count | MVP | Beta | GA | Status |
|-------|-------------|-----|------|-----|--------|
| Phase 0: External Dependencies | 0 | - | - | - | BLOCKED |
| Phase 1: Tooling & Validators | 8 | 3 | 3 | 2 | Can start immediately |
| Phase 2: Contract Reconciliation | 6 | 4 | 2 | 0 | Ready when Phase 0 complete |
| Phase 3: Compute Node Refactoring | 4 | 4 | 0 | 0 | Ready when Phase 2 complete |
| Phase 4: Effect Node Refactoring | 7 | 7 | 0 | 0 | Ready when Phase 2 complete |
| Phase 5: Orchestrator & Reducer Refactoring | 4 | 4 | 0 | 0 | Ready when Phase 4 complete |
| Phase 6: Runtime Host Integration | 8 | 5 | 2 | 1 | Ready when Phase 5 complete |
| Phase 7: Docker Consolidation | 6 | 4 | 2 | 0 | Ready when Phase 6 complete |
| Phase 8: Testing & Validation | 10 | 4 | 4 | 2 | Ready when Phase 7 complete |
| Phase 9: Cleanup | 3 | 0 | 3 | 0 | Ready when Phase 8 validated |
| **Total** | **56** | **35** | **16** | **5** | - |

> **MVP Scope**: 35 issues required for minimum viable runtime host
> **Beta Scope**: +16 issues for production readiness
> **GA Scope**: +5 issues for full performance guarantees

---

## External Dependencies (Blocking)

> **CRITICAL**: OmniIntelligence is BLOCKED until the following work is completed in other repositories. No OmniIntelligence work should begin until these are available.

### omnibase_core Dependencies

| Issue | Repository | Status |
|-------|------------|--------|
| Fix Core→SPI dependency inversion | omnibase_core | Pending |
| Implement `NodeRuntime` class | omnibase_core | Pending |
| Implement `NodeInstance` class | omnibase_core | Pending |
| Declarative `NodeCompute` base class | omnibase_core | Pending |
| Declarative `NodeEffect` base class | omnibase_core | Pending |

### omnibase_spi Dependencies

> **IMPORTANT**: All protocols use the `Protocol*` naming convention per SPI standards.

| Protocol | File | Status |
|----------|------|--------|
| `ProtocolVectorStoreHandler` | `omnibase_spi/protocols/handlers/vector_store_handler.py` | Pending (Future F.7) |
| `ProtocolGraphDatabaseHandler` | `omnibase_spi/protocols/handlers/graph_database_handler.py` | Pending (Future F.8) |
| `ProtocolRelationalDatabaseHandler` | `omnibase_spi/protocols/handlers/relational_database_handler.py` | Pending (Future F.9) |
| `ProtocolEmbeddingHandler` | `omnibase_spi/protocols/handlers/embedding_handler.py` | Pending (Future F.10) |
| `ProtocolKafkaProducerHandler` | `omnibase_spi/protocols/handlers/kafka_producer_handler.py` | Pending (Future F.11) |
| `ProtocolEventBus` | `omnibase_spi/protocols/event_bus.py` | Pending |

### omnibase_infra Dependencies

| Handler | Implements | Status |
|---------|------------|--------|
| `QdrantVectorHandler` | `ProtocolVectorStoreHandler` | Pending |
| `MemgraphGraphHandler` | `ProtocolGraphDatabaseHandler` | Pending |
| `AsyncpgDatabaseHandler` | `ProtocolRelationalDatabaseHandler` | Pending |
| `OpenAProtocolEmbeddingHandler` | `ProtocolEmbeddingHandler` | Pending |
| `LocalEmbeddingHandler` | `ProtocolEmbeddingHandler` | Pending |
| `KafkaProducerHandler` | `ProtocolKafkaProducerHandler` | Pending |
| `KafkaEventBus` | `ProtocolEventBus` | Pending |
| `BaseRuntimeHostProcess` | - | Pending |

---

## Phase 1: Tooling & Validators

**Priority**: HIGH
**Dependencies**: None (can start immediately)
**Purpose**: Build validation infrastructure before node refactoring begins

### Epic: Build Validation Tools

These tools ensure the implementation proceeds correctly and catch issues early.

#### Issue 1.1: Create Contract Linter CLI Tool

**Title**: Create contract linter CLI tool for YAML contract validation
**Type**: Feature
**Priority**: High
**Milestone**: **MVP** (Phase 1 only)
**Labels**: `tooling`, `contracts`, `cli`

**Description**:
Create a CLI tool to validate all node contracts against `BaseNodeContract` schema and ONEX contract requirements. The linter is implemented in phases to avoid over-specification.

**Phased Implementation**:

| Phase | Milestone | Scope | Validation |
|-------|-----------|-------|------------|
| Phase 1 | MVP | Basic parsing | Contract parses as valid YAML + required Pydantic fields exist |
| Phase 2 | Beta | Handler validation | Validate handler dependencies match SPI protocol names |
| Phase 3 | GA | Full validation | Validate topic names, workflow references, dependency graph completeness |

**Location**: `scripts/validate_contracts.py`

**Phase 1 Implementation (MVP)**:
```python
#!/usr/bin/env python
"""Contract linter CLI for OmniIntelligence nodes (Phase 1: MVP)."""
import argparse
from pathlib import Path
import yaml
from pydantic import ValidationError

# Phase 1 (MVP): Only check required fields exist
REQUIRED_FIELDS = ["kind", "version", "node_id", "subscriptions", "dependencies"]

def lint_contract(contract_path: Path) -> list[str]:
    """Lint a single contract file (Phase 1: parsing + required fields)."""
    errors = []

    # Phase 1: Verify YAML parses
    try:
        with open(contract_path) as f:
            contract = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return [f"YAML parse error: {e}"]

    # Phase 1: Verify required fields exist

    for field in REQUIRED_FIELDS:
        if field not in contract:
            errors.append(f"Missing required field: {field}")

    # Phase 1: Basic version format check
    if "version" in contract and not re.match(r"^\d+\.\d+\.\d+$", contract["version"]):
        errors.append(f"Invalid version format: {contract['version']}")

    return errors

def main():
    parser = argparse.ArgumentParser(description="Lint OmniIntelligence contracts")
    parser.add_argument("--path", default="src/omniintelligence/nodes")
    args = parser.parse_args()

    # Find and lint all contracts
    ...
```

**CLI Usage**:
```bash
python scripts/validate_contracts.py --path src/omniintelligence/nodes
# or
omniintelligence-lint-contracts
```

**Acceptance Criteria (Phase 1 - MVP)**:
- [ ] CLI tool validates all contracts in specified path
- [ ] Verifies contracts parse as valid YAML
- [ ] Checks for required fields: `kind`, `version`, `node_id`, `subscriptions`, `dependencies`
- [ ] Validates version format (semver)
- [ ] Returns non-zero exit code on validation failure
- [ ] CI integration ready

**Deferred to Phase 2 (Beta)**:
- Validates handler dependencies exist in omnibase_spi

**Deferred to Phase 3 (GA)**:
- Validates topic names match schema
- Validates workflow identifiers for orchestrators
- Validates state transitions for reducers
- Full dependency graph validation

---

#### Issue 1.2: Create Runtime Envelope Shape Audit Test

**Title**: Create envelope shape audit to verify consistent envelope usage
**Type**: Feature
**Priority**: High
**Milestone**: **MVP**
**Labels**: `tooling`, `testing`, `audit`

> **Platform Concern**: The envelope validator should ultimately be the single source of truth in `omnibase_core/validators`. For MVP, implement in omniintelligence with a `# TODO: Move to omnibase_core` marker.

**Description**:
Create an automated test that scans all OmniIntelligence nodes to verify they use the standard `ModelOnexEnvelope` shape.

**Location**: `tests/unit/test_envelope_audit.py`

**Implementation**:
```python
"""Audit test for consistent envelope shape usage."""
import ast
from pathlib import Path
import pytest

REQUIRED_ENVELOPE_FIELDS = {
    "node_id",
    "correlation_id",
    "payload",
    "timestamp",
}

OPTIONAL_ENVELOPE_FIELDS = {
    "metadata",
    "trace_id",
}

NODES_PATH = Path("src/omniintelligence/nodes")


def test_nodes_use_standard_envelope_shape():
    """Verify all nodes use ModelOnexEnvelope, not custom shapes."""
    violations = []

    for py_file in NODES_PATH.rglob("*.py"):
        tree = ast.parse(py_file.read_text())
        # Check for bare dict usage in input/output type hints
        # Check for custom envelope classes
        # Verify ModelOnexEnvelope import where envelope is used
        ...

    assert not violations, f"Envelope shape violations:\n" + "\n".join(violations)


def test_workflows_use_envelope_not_bare_dicts():
    """Verify workflows pass envelopes, not bare dicts or Pydantic models."""
    ...
```

**Acceptance Criteria**:
- [ ] Scans all node files for envelope usage
- [ ] Verifies consistent use of: `node_id`, `correlation_id`, `payload`, `timestamp`
- [ ] Flags nodes using custom input shapes
- [ ] Flags workflows passing bare dicts instead of envelopes
- [ ] Clear violation messages with file paths
- [ ] Integrated into pytest suite

---

#### Issue 1.3: Create Cross-Node Dependency Graph Validator

**Title**: Create dependency graph validator to detect circular dependencies
**Type**: Feature
**Priority**: High
**Milestone**: **Beta**
**Labels**: `tooling`, `validation`, `architecture`

> **Platform Concern**: The dependency graph validator should ultimately live in `omnibase_core/validators` as a reusable platform concern. For MVP, implement in omniintelligence with a `# TODO: Move to omnibase_core` marker.

**Description**:
Create a script that builds and validates the node dependency graph to prevent circular dependencies.

**Location**: `scripts/validate_dependency_graph.py`

**Implementation**:
```python
#!/usr/bin/env python
"""Validate node dependency graph for cycles."""
import argparse
from pathlib import Path
from collections import defaultdict
import yaml

def build_dependency_graph(nodes_path: Path) -> dict[str, list[str]]:
    """Build dependency graph from node contracts."""
    graph = defaultdict(list)

    for contract_file in nodes_path.rglob("**/contract.yaml"):
        with open(contract_file) as f:
            contract = yaml.safe_load(f)

        node_id = contract.get("node_id", "")
        deps = contract.get("dependencies", {})

        # Add handler dependencies
        for handler in deps.get("handlers", []):
            graph[node_id].append(f"handler:{handler['handler_type']}")

        # Add workflow dependencies
        for workflow in deps.get("contracts", []):
            graph[node_id].append(f"workflow:{workflow['contract_type']}")

    return graph


def detect_cycles(graph: dict) -> list[list[str]]:
    """Detect cycles using DFS."""
    ...


def generate_dot_output(graph: dict) -> str:
    """Generate DOT format for visualization."""
    lines = ["digraph G {"]
    for node, deps in graph.items():
        for dep in deps:
            lines.append(f'  "{node}" -> "{dep}";')
    lines.append("}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dot", help="Output DOT file for visualization")
    args = parser.parse_args()

    graph = build_dependency_graph(Path("src/omniintelligence/nodes"))
    cycles = detect_cycles(graph)

    if cycles:
        print("CIRCULAR DEPENDENCIES DETECTED:")
        for cycle in cycles:
            print(f"  {' -> '.join(cycle)}")
        exit(1)

    if args.output_dot:
        with open(args.output_dot, "w") as f:
            f.write(generate_dot_output(graph))
```

**CLI Usage**:
```bash
python scripts/validate_dependency_graph.py --output-dot deps.dot
dot -Tpng deps.dot -o deps.png  # Generate visualization
```

**Acceptance Criteria**:
- [ ] Builds dependency graph from all node contracts
- [ ] Detects circular dependencies
- [ ] Fails with non-zero exit code if cycles found
- [ ] Generates DOT output for visualization
- [ ] CI integration ready

---

#### Issue 1.4: Create Node Contract Coverage Report Generator

**Title**: Create node contract coverage report generator
**Type**: Feature
**Priority**: Medium
**Milestone**: **Beta**
**Labels**: `tooling`, `reporting`, `contracts`

**Description**:
Create a script that generates a coverage report showing the contract status of all nodes.

**Location**: `scripts/generate_contract_coverage_report.py`

**Output**: `reports/node_contract_coverage.md`

**Report Format**:
```markdown
# Node Contract Coverage Report

Generated: 2025-12-03

| Node | Has Contract | Version | Has Handler Deps | Has Workflow Deps | Profile Membership |
|------|--------------|---------|------------------|-------------------|-------------------|
| vectorization_compute | ✅ | v1.1.0 | ✅ ProtocolEmbeddingHandler | ❌ | main, all |
| qdrant_vector_effect | ✅ | v2.0.0 | ✅ ProtocolVectorStoreHandler | ❌ | effects, all |
| intelligence_orchestrator | ✅ | v1.5.0 | ❌ | ✅ 5 workflows | main, all |
| quality_scoring_compute | ✅ | v1.0.0 | ❌ (pure) | ❌ | main, all |
| ... | ... | ... | ... | ... | ... |

## Summary
- Total nodes: 17
- With contracts: 17/17 (100%)
- With v1.1+ upgrade: 12/17 (71%)
- Missing handler declarations: 3
```

**Acceptance Criteria**:
- [ ] Scans all node directories
- [ ] Generates markdown report with coverage table
- [ ] Shows contract presence/absence
- [ ] Shows version status
- [ ] Shows handler dependency declarations
- [ ] Shows workflow dependency declarations
- [ ] Shows runtime profile membership
- [ ] Summary statistics at bottom
- [ ] CI can fail if coverage below threshold

---

#### Issue 1.5: Create Topic Naming Schema Validator

**Title**: Create topic naming schema validator
**Type**: Feature
**Priority**: Medium
**Milestone**: **GA**
**Labels**: `tooling`, `validation`, `kafka`

> **Note**: GA implementation should include multi-version topic support validation (e.g., simultaneous v1 and v2 topic handling).

**Description**:
Create a validator that enforces the topic naming schema across all contracts.

**Topic Naming Schema**:
```
onex.<domain>.<signal>.<version>

Where:
- domain: intelligence, archon, bridge, etc.
- signal: cmd, evt, state, log, error
- version: v1, v2, etc.

Examples:
- onex.intelligence.cmd.v1
- onex.intelligence.evt.v1
- onex.intelligence.error.v1
```

**Location**: `scripts/validate_topic_names.py`

**Implementation**:
```python
import re

TOPIC_PATTERN = r"^onex\.[a-z]+\.(cmd|evt|state|log|error)\.v\d+$"

def validate_topic_name(topic: str) -> bool:
    """Validate topic follows naming schema."""
    return bool(re.match(TOPIC_PATTERN, topic))
```

**Acceptance Criteria**:
- [ ] Validates all topic names in contracts
- [ ] Enforces schema: `onex.<domain>.<signal>.<version>`
- [ ] Validates domain is `intelligence`
- [ ] Validates signal is one of: `cmd`, `evt`, `state`, `log`, `error`
- [ ] Validates version format: `v1`, `v2`, etc.
- [ ] Reports violations with contract file paths
- [ ] CI integration ready

---

#### Issue 1.6: Create Handler-to-Node Binding Map Generator

**Title**: Create handler-to-node binding map generator
**Type**: Feature
**Priority**: Medium
**Milestone**: **Beta**
**Labels**: `tooling`, `documentation`, `runtime`

**Description**:
Create a script that generates a machine-readable and human-readable map of handler bindings.

**Location**: `scripts/generate_handler_binding_map.py`

**Output**: `docs/runtime/handler_binding_matrix.md`

**Report Format**:
```markdown
# Handler Binding Matrix

| Handler Type | Protocol | Required By | Optional For |
|--------------|----------|-------------|--------------|
| vector_store | ProtocolVectorStoreHandler | qdrant_vector_effect | - |
| graph_database | ProtocolGraphDatabaseHandler | memgraph_graph_effect | - |
| relational_database | ProtocolRelationalDatabaseHandler | postgres_pattern_effect, intelligence_reducer | - |
| embedding | ProtocolEmbeddingHandler | vectorization_compute | - |
| kafka_producer | ProtocolKafkaProducerHandler | kafka_event_effect | intelligence_adapter |

## Runtime Profile Requirements

### Profile: main
Required handlers: embedding, relational_database
Optional handlers: kafka_producer

### Profile: effects
Required handlers: vector_store, graph_database, relational_database, kafka_producer
Optional handlers: -

### Profile: all
Required handlers: ALL
Optional handlers: -
```

**Acceptance Criteria**:
- [ ] Scans all contracts for handler dependencies
- [ ] Generates markdown matrix
- [ ] Shows required vs optional handlers per node
- [ ] Shows handler requirements per runtime profile
- [ ] Machine-readable JSON output option
- [ ] Auto-generated (script, not manual)

---

#### Issue 1.7: Create Runtime Host Dry Run Mode

**Title**: Implement runtime host dry run mode for validation
**Type**: Feature
**Priority**: High
**Milestone**: **MVP**
**Labels**: `runtime`, `tooling`, `validation`

**Description**:
Add a `--dry-run` flag to the runtime host that validates configuration without connecting to services.

**CLI Usage**:
```bash
omniintelligence-runtime --dry-run
```

**Dry Run Behavior**:
1. Load all node contracts
2. Validate contract schema
3. Validate handler bindings
4. Perform dependency graph check
5. Validate topic naming
6. Report any issues
7. Exit WITHOUT starting event loop or connecting to Kafka/Postgres/etc.

**Implementation** (in `runtime/main.py`):
```python
async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate configuration without running")
    args = parser.parse_args()

    config = IntelligenceRuntimeConfig.from_environment()
    registry = IntelligenceNodeRegistry()

    if args.dry_run:
        errors = validate_runtime_configuration(config, registry)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            sys.exit(1)
        print("Dry run successful: all validations passed")
        sys.exit(0)

    # Normal startup...
```

**Acceptance Criteria**:
- [ ] `--dry-run` flag added to CLI
- [ ] Loads all nodes and contracts
- [ ] Validates handler bindings
- [ ] Validates dependency graph
- [ ] Validates topic names
- [ ] Reports all errors
- [ ] Exits with appropriate code (0 = success, 1 = errors)
- [ ] Does NOT connect to Kafka, Postgres, Qdrant, etc.

---

#### Issue 1.8: Create Workflow Simulation CLI Tool

**Title**: Create workflow simulation CLI for orchestrator testing
**Type**: Feature
**Priority**: Medium
**Milestone**: **GA**
**Labels**: `tooling`, `testing`, `orchestrator`

**Description**:
Create a CLI tool to simulate orchestrator workflow execution without running real nodes.

**Location**: `scripts/simulate_workflow.py` or CLI entry point

**CLI Usage**:
```bash
omnilab simulate-workflow DOCUMENT_INGESTION --input '{"document_id": "doc-123"}'
omnilab simulate-workflow PATTERN_LEARNING --input @input.json
```

**Output**:
```
Workflow: DOCUMENT_INGESTION
Input: {"document_id": "doc-123"}

Step 1: vectorization_compute
  Input: {"texts": [...]}
  Output: {"embeddings": [...]}
  Status: SUCCESS

Step 2: entity_extraction_compute
  Input: {"text": "..."}
  Output: {"entities": [...]}
  Status: SUCCESS

Step 3: qdrant_vector_effect
  Input: {"embeddings": [...], "metadata": {...}}
  Output: {"success": true}
  Status: SUCCESS

Workflow completed: 3/3 steps successful
```

**Acceptance Criteria**:
- [ ] CLI entry point: `omnilab simulate-workflow`
- [ ] Loads workflow contract
- [ ] Simulates step-by-step execution
- [ ] Shows input/output for each step
- [ ] Reports success/failure status
- [ ] Accepts JSON input from file or stdin
- [ ] Useful for debugging multi-step workflows

---

## Phase 2: Contract Reconciliation

**Priority**: HIGH
**Dependencies**: Phase 0 complete (omnibase_core schemas available)
**Purpose**: Align all contracts with Runtime Host requirements before node refactoring

### Epic: Reconcile Contracts with Runtime Host Architecture

Before node refactoring begins, all contracts must be updated to match the new SPI-based architecture.

#### Issue 2.1: Validate all contracts against BaseNodeContract

**Title**: Validate all node contracts against BaseNodeContract schema
**Type**: Task
**Priority**: High
**Labels**: `contracts`, `validation`
**Milestone**: MVP

**Description**:
Run the contract linter (Issue 1.1) against all OmniIntelligence contracts and fix any schema violations.

**Required Contract Fields**:
```yaml
kind: COMPUTE | EFFECT | REDUCER | ORCHESTRATOR
version: "1.0.0"  # semver
node_id: "vectorization_compute"
subscriptions:
  topics: []
dependencies:
  handlers: []
  contracts: []
```

**Acceptance Criteria**:
- [ ] All 17 node contracts pass schema validation
- [ ] All contracts have `kind` field
- [ ] All contracts have `version` field (semver format)
- [ ] All contracts have `node_id` field
- [ ] All contracts have `subscriptions` section
- [ ] All contracts have `dependencies` section
- [ ] All contracts have `fingerprint` field (see Issue 2.7)
- [ ] Contract linter (Issue 1.1) passes with zero errors

---

#### Issue 2.2: Upgrade compute node contracts to v1.1.0

**Title**: Upgrade compute node contracts to v1.1.0 with handler references
**Type**: Task
**Priority**: High
**Labels**: `contracts`, `compute`
**Milestone**: MVP

**Description**:
Upgrade all compute node contracts from v1.0.0 to v1.1.0, adding handler dependencies where applicable.

**Version Changes**:
| Node | Old Version | New Version | Change |
|------|-------------|-------------|--------|
| vectorization_compute | v1.0.0 | v1.1.0 | Add ProtocolEmbeddingHandler dependency |
| quality_scoring_compute | v1.0.0 | v1.0.0 | No change (pure) |
| entity_extraction_compute | v1.0.0 | v1.0.0 | No change (pure) |
| relationship_detection_compute | v1.0.0 | v1.0.0 | No change (pure) |
| intent_classifier_compute | v1.0.0 | v1.0.0 | No change (pure) |
| context_keyword_extractor_compute | v1.0.0 | v1.0.0 | No change (pure) |
| success_criteria_matcher_compute | v1.0.0 | v1.0.0 | No change (pure) |
| execution_trace_parser_compute | v1.0.0 | v1.0.0 | No change (pure) |

**Acceptance Criteria**:
- [ ] `vectorization_compute` upgraded to v1.1.0 with handler dependency
- [ ] Pure compute nodes remain at v1.0.0 (no handler changes needed)
- [ ] All contracts validated

---

#### Issue 2.3: Upgrade effect node contracts to v2.0.0

**Title**: Upgrade effect node contracts to v2.0.0 with mandatory handler injection
**Type**: Task
**Priority**: High
**Labels**: `contracts`, `effect`
**Milestone**: MVP

**Description**:
Upgrade all effect node contracts from v1.0.0 to v2.0.0 with mandatory handler dependencies.

**Version Changes**:
| Node | Old Version | New Version | Handler Dependency |
|------|-------------|-------------|-------------------|
| kafka_event_effect | v1.0.0 | v2.0.0 | ProtocolKafkaProducerHandler (required) |
| qdrant_vector_effect | v1.0.0 | v2.0.0 | ProtocolVectorStoreHandler (required) |
| memgraph_graph_effect | v1.0.0 | v2.0.0 | ProtocolGraphDatabaseHandler (required) |
| postgres_pattern_effect | v1.0.0 | v2.0.0 | ProtocolRelationalDatabaseHandler (required) |
| intelligence_adapter | v1.0.0 | v2.0.0 | ProtocolKafkaProducerHandler (optional) |

**Contract Example**:
```yaml
kind: EFFECT
version: "2.0.0"
node_id: "qdrant_vector_effect"
dependencies:
  handlers:
    - handler_type: vector_store
      protocol: ProtocolVectorStoreHandler
      required: true
```

**Acceptance Criteria**:
- [ ] All 5 effect node contracts upgraded to v2.0.0
- [ ] All handler dependencies declared
- [ ] Required vs optional correctly specified
- [ ] Contract schema validation passes

---

#### Issue 2.4: Upgrade orchestrator/reducer contracts to v1.5.0

**Title**: Upgrade orchestrator and reducer contracts to v1.5.0 with contract injection
**Type**: Task
**Priority**: High
**Labels**: `contracts`, `orchestrator`, `reducer`
**Milestone**: MVP

**Description**:
Upgrade orchestrator and reducer contracts to v1.5.0 with workflow/contract dependencies.

**Version Changes**:
| Node | Old Version | New Version | Dependencies |
|------|-------------|-------------|--------------|
| intelligence_orchestrator | v1.0.0 | v1.5.0 | Workflow contracts (5 workflows) |
| pattern_assembler_orchestrator | v1.0.0 | v1.5.0 | Pattern assembly contracts (4 phases) |
| intelligence_reducer | v1.0.0 | v1.5.0 | ProtocolRelationalDatabaseHandler + FSM contracts |

**Contract Example**:
```yaml
kind: ORCHESTRATOR
version: "1.5.0"
node_id: "intelligence_orchestrator"
dependencies:
  contracts:
    - contract_type: workflow
      required: true
      identifiers:
        - DOCUMENT_INGESTION
        - PATTERN_LEARNING
        - QUALITY_ASSESSMENT
        - SEMANTIC_ANALYSIS
        - RELATIONSHIP_DETECTION
```

**Acceptance Criteria**:
- [ ] All 3 coordination node contracts upgraded to v1.5.0
- [ ] Workflow identifiers validated (orchestrators)
- [ ] FSM state transitions validated (reducer)
- [ ] Handler dependencies declared (reducer)
- [ ] Contract schema validation passes

---

#### Issue 2.5: Create mandatory contract test fixtures

**Title**: Create test fixtures for all node contracts
**Type**: Task
**Priority**: Medium
**Labels**: `testing`, `contracts`, `fixtures`
**Milestone**: Beta

**Description**:
Create pytest fixtures that load and validate each node contract, plus snapshot tests to detect accidental changes.

**Location**: `tests/contracts/`

**Implementation**:
```python
# tests/contracts/conftest.py
import pytest
from pathlib import Path
import yaml

@pytest.fixture
def vectorization_compute_contract():
    """Load vectorization_compute contract."""
    path = Path("src/omniintelligence/nodes/vectorization_compute/v1_0_0/contracts/contract.yaml")
    with open(path) as f:
        return yaml.safe_load(f)

# ... fixtures for all 17 nodes


# tests/contracts/test_contract_snapshots.py
def test_vectorization_compute_contract_snapshot(vectorization_compute_contract, snapshot):
    """Snapshot test to detect accidental contract changes."""
    assert vectorization_compute_contract == snapshot
```

**Acceptance Criteria**:
- [ ] Fixtures for all 17 node contracts
- [ ] Automated schema validation in fixtures
- [ ] Snapshot tests for all contracts
- [ ] CI fails on unexpected contract changes
- [ ] Contract change requires explicit snapshot update

---

#### Issue 2.6: Document node versioning strategy

**Title**: Document node versioning strategy
**Type**: Documentation
**Priority**: Medium
**Labels**: `documentation`, `contracts`, `versioning`
**Milestone**: Beta

**Description**:
Create documentation explaining the versioning strategy for node contracts.

**Location**: `docs/NODE_VERSIONING_STRATEGY.md`

**Content**:
```markdown
# Node Versioning Strategy

## Version Bump Rules

| Change Type | Version Bump | Example |
|-------------|--------------|---------|
| Runtime host integration | Major (v2.0.0) | Effect nodes with handler injection |
| Handler injection (breaking) | Major (v2.0.0) | I/O removal from nodes |
| Handler injection (additive) | Minor (v1.1.0) | Compute nodes adding handler param |
| Contract injection | Minor (v1.5.0) | Orchestrators accepting workflow contracts |
| Pure contract fixes | Patch (v1.0.1) | Typo fixes, doc updates |

## Node Version Table

| Node | Current Version | Change Type |
|------|-----------------|-------------|
| vectorization_compute | v1.1.0 | Handler injection (additive) |
| qdrant_vector_effect | v2.0.0 | Handler injection (breaking) |
| intelligence_orchestrator | v1.5.0 | Contract injection |
| ... | ... | ... |
```

**Acceptance Criteria**:
- [ ] Versioning strategy documented
- [ ] Version bump rules clear
- [ ] All 17 nodes listed with pre/post versions
- [ ] Change type explained for each node

---

#### Issue 2.7: Contract Fingerprint Implementation

**Title**: Add fingerprint field to all node contracts
**Type**: Task
**Priority**: High
**Labels**: `contracts`, `validation`
**Milestone**: MVP

**Description**:
Add a fingerprint field to all node contracts that combines the semver version with a structural hash. This enables contract integrity verification and change detection during runtime host initialization.

**Fingerprint Format**:
```
fingerprint: "<semver>:<hash>"
```

**Example**:
```yaml
kind: EFFECT
version: "2.0.0"
fingerprint: "2.0.0:sha256:abc123def456..."
node_id: "qdrant_vector_effect"
dependencies:
  handlers:
    - handler_type: vector_store
      protocol: ProtocolVectorStoreHandler
      required: true
```

**Hash Computation**:
The hash is computed from:
1. Contract structure (all fields except `fingerprint` itself)
2. Type definitions referenced by the contract
3. Handler protocol signatures (for effect nodes)
4. Workflow identifiers (for orchestrator nodes)

**Implementation Steps**:
1. Create fingerprint computation utility in `omnibase_core`
2. Add `fingerprint` field to `BaseNodeContract` schema
3. Update contract linter to validate fingerprint format
4. Generate fingerprints for all 17 OmniIntelligence contracts
5. Add fingerprint verification to runtime host contract loading

**Contract Changes Required**:
| Node Type | Count | Fingerprint Pattern |
|-----------|-------|---------------------|
| Compute | 8 | `v1.x.0:sha256:...` |
| Effect | 5 | `v2.0.0:sha256:...` |
| Orchestrator | 2 | `v1.5.0:sha256:...` |
| Reducer | 1 | `v1.5.0:sha256:...` |

**Acceptance Criteria**:
- [ ] All 17 contracts have `fingerprint` field
- [ ] Fingerprint includes version and structural hash
- [ ] Hash computed from contract structure + type definitions
- [ ] Contract linter validates fingerprint format (`<semver>:sha256:<hex>`)
- [ ] Fingerprint utility available in `omnibase_core.contracts`
- [ ] Documentation updated with fingerprint specification

---

## Phase 3: Compute Node Refactoring

**Priority**: HIGH
**Dependencies**: Phase 2 complete (contracts reconciled)
**Node Count**: 8 compute nodes (7 pure, 1 needs handler injection)

### Epic: Refactor Compute Nodes for Handler Injection

Pure compute nodes (7 of 8) require no changes. Only `NodeVectorizationCompute` needs handler injection.

#### Issue 3.1: Refactor NodeVectorizationCompute for ProtocolEmbeddingHandler

**Title**: Refactor NodeVectorizationCompute to use ProtocolEmbeddingHandler
**Type**: Feature
**Priority**: High
**Labels**: `architecture`, `refactoring`, `compute`

**Description**:
Refactor `NodeVectorizationCompute` to accept `ProtocolEmbeddingHandler` via dependency injection instead of direct embedding library imports.

**Current State**:
```python
# WRONG - direct library import
from openai import OpenAI  # or sentence_transformers
```

**Target State**:
```python
from omnibase_spi.protocols.handlers import ProtocolEmbeddingHandler

class NodeVectorizationCompute(NodeCompute[VectorizationInput, VectorizationOutput]):
    def __init__(
        self,
        config: VectorizationConfig,
        embedding_handler: ProtocolEmbeddingHandler,  # Injected
    ):
        self._config = config
        self._embedding_handler = embedding_handler

    async def compute(self, input: VectorizationInput) -> VectorizationOutput:
        embeddings = await self._embedding_handler.embed_texts(
            texts=input.texts,
            model_name=self._config.model_name,
        )
        return VectorizationOutput(embeddings=embeddings)
```

**Files to Modify**:
- `src/omniintelligence/nodes/vectorization_compute/v1_0_0/compute.py`
- `src/omniintelligence/nodes/vectorization_compute/v1_0_0/models/config.py`

**Acceptance Criteria**:
- [ ] `ProtocolEmbeddingHandler` injected via constructor
- [ ] No direct imports of `openai`, `sentence_transformers`, or `httpx`
- [ ] Config model updated to remove embedding-specific connection details
- [ ] Unit tests updated with mock `ProtocolEmbeddingHandler`
- [ ] mypy passes
- [ ] Existing functionality preserved

---

#### Issue 3.2: Audit pure compute nodes for I/O violations

**Title**: Audit pure compute nodes to ensure no I/O imports
**Type**: Task
**Priority**: High
**Labels**: `architecture`, `audit`, `compute`

**Description**:
Audit all 7 pure compute nodes to ensure they have no direct I/O library imports.

**Nodes to Audit**:
1. `NodeQualityScoringCompute` - Expected: Pure ✓
2. `NodeEntityExtractionCompute` - Expected: Pure ✓
3. `NodeRelationshipDetectionCompute` - Expected: Pure ✓
4. `NodeIntentClassifierCompute` - Expected: Pure ✓
5. `NodeContextKeywordExtractorCompute` - Expected: Pure ✓
6. `NodeSuccessCriteriaMatcherCompute` - Expected: Pure ✓
7. `NodeExecutionTraceParserCompute` - Expected: Pure ✓

**Forbidden Imports** (must not appear in any compute node):
```python
# None of these should appear in pure compute nodes
import confluent_kafka
import qdrant_client
import neo4j
import asyncpg
import httpx
import openai
import sentence_transformers
```

**Acceptance Criteria**:
- [ ] All 7 pure compute nodes verified as I/O-free
- [ ] Report generated listing any violations found
- [ ] Violations fixed before marking complete
- [ ] `grep -r "confluent_kafka\|qdrant_client\|neo4j\|asyncpg\|httpx" nodes/*compute*/` returns no results

---

#### Issue 3.3: Update compute node contracts for v1.1.0

**Title**: Update compute node contracts with handler dependencies
**Type**: Task
**Priority**: Medium
**Labels**: `contracts`, `compute`

**Description**:
Update YAML contracts for compute nodes to declare handler dependencies where applicable.

**Files to Update**:
- `src/omniintelligence/nodes/vectorization_compute/v1_0_0/contracts/contract.yaml`

**Contract Changes**:
```yaml
# Add to vectorization_compute contract
dependencies:
  handlers:
    - handler_type: embedding
      required: true
      protocol: ProtocolEmbeddingHandler
```

**Acceptance Criteria**:
- [ ] `vectorization_compute` contract declares `ProtocolEmbeddingHandler` dependency
- [ ] Pure compute node contracts have no handler dependencies
- [ ] Contract schema validation passes
- [ ] Contract version bumped to v1.1.0 where applicable

---

#### Issue 3.4: Create compute node unit tests with mocked handlers

**Title**: Create comprehensive unit tests for compute nodes with mocked handlers
**Type**: Task
**Priority**: Medium
**Labels**: `testing`, `compute`

**Description**:
Create/update unit tests for all compute nodes using mocked handlers instead of real services.

**Test Coverage Requirements**:
- [ ] `NodeVectorizationCompute` tests with `MockEmbeddingHandler`
- [ ] All pure compute nodes have unit tests
- [ ] Edge cases covered (empty input, large batches, error handling)
- [ ] >80% code coverage for compute nodes

**Acceptance Criteria**:
- [ ] Test file: `tests/unit/nodes/test_vectorization_compute.py`
- [ ] Mock handler fixtures in `tests/conftest.py`
- [ ] All compute node tests pass
- [ ] Coverage report shows >80% for compute nodes

---

## Phase 4: Effect Node Refactoring

**Priority**: HIGH
**Dependencies**: Phase 0 complete (omnibase_spi protocols available)
**Node Count**: 5 effect nodes

### Epic: Extract I/O from Effect Nodes

Remove all direct I/O library imports from effect nodes, replacing with injected SPI handlers.

#### Issue 4.1: Refactor NodeKafkaEventEffect to use ProtocolKafkaProducerHandler

**Title**: Refactor NodeKafkaEventEffect to use ProtocolKafkaProducerHandler
**Type**: Feature
**Priority**: High
**Labels**: `architecture`, `refactoring`, `effect`

**Description**:
Remove direct `confluent_kafka.Producer` usage from `NodeKafkaEventEffect`, replace with injected `ProtocolKafkaProducerHandler`.

**Current State**:
```python
from confluent_kafka import Producer  # WRONG
```

**Target State**:
```python
from omnibase_spi.protocols.handlers import ProtocolKafkaProducerHandler

class NodeKafkaEventEffect(NodeEffect[KafkaEventInput, KafkaEventOutput]):
    def __init__(
        self,
        config: KafkaEventConfig,
        kafka_handler: ProtocolKafkaProducerHandler,  # Injected
    ):
        self._config = config
        self._kafka_handler = kafka_handler

    async def execute(self, input: KafkaEventInput) -> KafkaEventOutput:
        await self._kafka_handler.produce(
            topic=input.topic,
            key=input.key,
            value=input.payload,
            headers=input.headers,
        )
        return KafkaEventOutput(success=True)
```

**Files to Modify**:
- `src/omniintelligence/nodes/kafka_event_effect/v1_0_0/effect.py`
- `src/omniintelligence/nodes/kafka_event_effect/v1_0_0/models/config.py`

**Acceptance Criteria**:
- [ ] No `from confluent_kafka import` statements
- [ ] `ProtocolKafkaProducerHandler` injected via constructor
- [ ] Circuit breaker logic retained (now delegates to handler)
- [ ] Envelope serialization retained (pure logic)
- [ ] Unit tests with mock handler
- [ ] mypy passes

---

#### Issue 4.2: Refactor NodeQdrantVectorEffect to use ProtocolVectorStoreHandler

**Title**: Refactor NodeQdrantVectorEffect to use ProtocolVectorStoreHandler
**Type**: Feature
**Priority**: High
**Labels**: `architecture`, `refactoring`, `effect`

**Description**:
Remove direct `qdrant_client.AsyncQdrantClient` usage from `NodeQdrantVectorEffect`, replace with injected `ProtocolVectorStoreHandler`.

**Current State**:
```python
from qdrant_client import AsyncQdrantClient  # WRONG
```

**Target State**:
```python
from omnibase_spi.protocols.handlers import ProtocolVectorStoreHandler

class NodeQdrantVectorEffect(NodeEffect[VectorInput, VectorOutput]):
    def __init__(
        self,
        config: VectorConfig,
        vector_handler: ProtocolVectorStoreHandler,  # Injected
    ):
        self._config = config
        self._vector_handler = vector_handler

    async def execute(self, input: VectorInput) -> VectorOutput:
        self._validate_dimensions(input.embeddings)  # Pure logic retained
        result = await self._vector_handler.upsert(
            collection=self._config.collection,
            id=input.id,
            vector=input.embeddings,
            metadata=input.metadata,
        )
        return VectorOutput(success=result.success)
```

**Files to Modify**:
- `src/omniintelligence/nodes/qdrant_vector_effect/v1_0_0/effect.py`
- `src/omniintelligence/nodes/qdrant_vector_effect/v1_0_0/models/config.py`

**Acceptance Criteria**:
- [ ] No `from qdrant_client import` statements
- [ ] `ProtocolVectorStoreHandler` injected via constructor
- [ ] Dimension validation retained (pure logic)
- [ ] Collection/index logic retained (pure logic)
- [ ] Unit tests with mock handler
- [ ] mypy passes

---

#### Issue 4.3: Refactor NodeMemgraphGraphEffect to use ProtocolGraphDatabaseHandler

**Title**: Refactor NodeMemgraphGraphEffect to use ProtocolGraphDatabaseHandler
**Type**: Feature
**Priority**: High
**Labels**: `architecture`, `refactoring`, `effect`

**Description**:
Remove direct `neo4j.AsyncGraphDatabase` usage from `NodeMemgraphGraphEffect`, replace with injected `ProtocolGraphDatabaseHandler`.

**Current State**:
```python
from neo4j import AsyncGraphDatabase  # WRONG
```

**Target State**:
```python
from omnibase_spi.protocols.handlers import ProtocolGraphDatabaseHandler

class NodeMemgraphGraphEffect(NodeEffect[GraphInput, GraphOutput]):
    def __init__(
        self,
        config: GraphConfig,
        graph_handler: ProtocolGraphDatabaseHandler,  # Injected
    ):
        self._config = config
        self._graph_handler = graph_handler

    async def execute(self, input: GraphInput) -> GraphOutput:
        cypher_query = self._build_cypher(input)  # Pure logic retained
        result = await self._graph_handler.execute(
            query=cypher_query,
            parameters=input.parameters,
        )
        return GraphOutput(nodes_affected=result.nodes_affected)
```

**Files to Modify**:
- `src/omniintelligence/nodes/memgraph_graph_effect/v1_0_0/effect.py`
- `src/omniintelligence/nodes/memgraph_graph_effect/v1_0_0/models/config.py`

**Acceptance Criteria**:
- [ ] No `from neo4j import` statements
- [ ] `ProtocolGraphDatabaseHandler` injected via constructor
- [ ] Cypher query construction retained (pure logic)
- [ ] Entity/relationship model mapping retained (pure logic)
- [ ] Unit tests with mock handler
- [ ] mypy passes

---

#### Issue 4.4: Refactor NodePostgresPatternEffect to use ProtocolRelationalDatabaseHandler

**Title**: Refactor NodePostgresPatternEffect to use ProtocolRelationalDatabaseHandler
**Type**: Feature
**Priority**: High
**Labels**: `architecture`, `refactoring`, `effect`

**Description**:
Remove direct `asyncpg` usage from `NodePostgresPatternEffect`, replace with injected `ProtocolRelationalDatabaseHandler`.

**Current State**:
```python
import asyncpg  # WRONG
```

**Target State**:
```python
from omnibase_spi.protocols.handlers import ProtocolRelationalDatabaseHandler

class NodePostgresPatternEffect(NodeEffect[PatternInput, PatternOutput]):
    def __init__(
        self,
        config: PatternConfig,
        db_handler: ProtocolRelationalDatabaseHandler,  # Injected
    ):
        self._config = config
        self._db_handler = db_handler

    async def execute(self, input: PatternInput) -> PatternOutput:
        sql_query = self._build_sql(input)  # Pure logic retained
        pattern_hash = self._compute_hash(input)  # Pure logic retained
        result = await self._db_handler.execute(
            query=sql_query,
            parameters={"hash": pattern_hash, **input.parameters},
        )
        return PatternOutput(pattern_id=result.last_insert_id)
```

**Files to Modify**:
- `src/omniintelligence/nodes/postgres_pattern_effect/v1_0_0/effect.py`
- `src/omniintelligence/nodes/postgres_pattern_effect/v1_0_0/models/config.py`

**Acceptance Criteria**:
- [ ] No `import asyncpg` statements
- [ ] `ProtocolRelationalDatabaseHandler` injected via constructor
- [ ] SQL query construction retained (pure logic)
- [ ] Pattern hashing retained (pure logic)
- [ ] Unit tests with mock handler
- [ ] mypy passes

---

#### Issue 4.5: Refactor NodeIntelligenceAdapterEffect - REMOVE Kafka consumer

**Title**: Remove Kafka consumer logic from NodeIntelligenceAdapterEffect (CRITICAL)
**Type**: Feature
**Priority**: Urgent
**Labels**: `architecture`, `refactoring`, `effect`, `critical`

**Description**:
**CRITICAL**: Remove ALL Kafka consumer logic from `NodeIntelligenceAdapterEffect`. This node MUST NOT poll Kafka, subscribe to topics, or commit offsets. All event consumption is handled by `BaseRuntimeHostProcess` via `ProtocolEventBus`.

**What to REMOVE**:
```python
# ALL of this must be removed:
from confluent_kafka import Consumer, Producer  # ❌
self._consumer = Consumer(...)  # ❌
async def _consume_loop(self):  # ❌ ENTIRE METHOD
    while True:
        msg = self._consumer.poll(1.0)  # ❌
        ...
        self._consumer.commit()  # ❌
```

**What to KEEP/TRANSFORM**:
```python
from omnibase_spi.protocols.handlers import ProtocolKafkaProducerHandler
from omnibase_spi.protocols.handlers import ProtocolEmbeddingHandler  # if needed

class NodeIntelligenceAdapterEffect(NodeEffect[AdapterInput, AdapterOutput]):
    """Application-level adapter for intelligence operations.

    NOTE: This node does NOT poll Kafka. It receives envelopes from
    BaseRuntimeHostProcess and transforms/routes them. All event consumption
    is handled by the runtime host.
    """

    def __init__(
        self,
        config: AdapterConfig,
        kafka_producer: ProtocolKafkaProducerHandler | None = None,  # For explicit publish
    ):
        self._config = config
        self._kafka_producer = kafka_producer

    async def execute(self, input: AdapterInput) -> AdapterOutput:
        # Pure transformation logic only
        result = self._transform_payload(input)
        if self._kafka_producer and result.requires_publish:
            await self._kafka_producer.produce(...)
        return AdapterOutput(...)
```

**Files to Modify**:
- `src/omniintelligence/nodes/intelligence_adapter/node_intelligence_adapter_effect.py`
- All related files in `intelligence_adapter/` directory

**Acceptance Criteria**:
- [ ] **ZERO** Kafka consumer imports (`from confluent_kafka import Consumer`)
- [ ] **ZERO** Kafka consumer instantiation (`Consumer(...)`)
- [ ] **ZERO** polling loops (`while True: poll()`)
- [ ] **ZERO** offset commits (`consumer.commit()`)
- [ ] **ZERO** topic subscriptions (`consumer.subscribe()`)
- [ ] Optional `ProtocolKafkaProducerHandler` injection for explicit publish
- [ ] Node receives envelopes via `execute()` method (called by runtime)
- [ ] Pure payload transformation logic retained
- [ ] Unit tests with mock handlers
- [ ] mypy passes
- [ ] Integration test demonstrates runtime host calling this node

---

#### Issue 4.6: Update effect node contracts with handler dependencies

**Title**: Update effect node contracts with handler dependencies
**Type**: Task
**Priority**: Medium
**Labels**: `contracts`, `effect`

**Description**:
Update YAML contracts for all effect nodes to declare handler dependencies.

**Contract Changes**:

```yaml
# kafka_event_effect
dependencies:
  handlers:
    - handler_type: kafka_producer
      required: true
      protocol: ProtocolKafkaProducerHandler

# qdrant_vector_effect
dependencies:
  handlers:
    - handler_type: vector_store
      required: true
      protocol: ProtocolVectorStoreHandler

# memgraph_graph_effect
dependencies:
  handlers:
    - handler_type: graph_database
      required: true
      protocol: ProtocolGraphDatabaseHandler

# postgres_pattern_effect
dependencies:
  handlers:
    - handler_type: relational_database
      required: true
      protocol: ProtocolRelationalDatabaseHandler

# intelligence_adapter
dependencies:
  handlers:
    - handler_type: kafka_producer
      required: false  # Optional for explicit publish
      protocol: ProtocolKafkaProducerHandler
```

**Files to Update**:
- `src/omniintelligence/nodes/kafka_event_effect/v1_0_0/contracts/contract.yaml`
- `src/omniintelligence/nodes/qdrant_vector_effect/v1_0_0/contracts/contract.yaml`
- `src/omniintelligence/nodes/memgraph_graph_effect/v1_0_0/contracts/contract.yaml`
- `src/omniintelligence/nodes/postgres_pattern_effect/v1_0_0/contracts/contract.yaml`
- `src/omniintelligence/nodes/intelligence_adapter/contracts/contract.yaml`

**Acceptance Criteria**:
- [ ] All 5 effect node contracts declare handler dependencies
- [ ] Required vs optional handlers correctly specified
- [ ] Contract schema validation passes
- [ ] Contract versions bumped

---

#### Issue 4.7: Create effect node unit tests with mocked handlers

**Title**: Create comprehensive unit tests for effect nodes with mocked handlers
**Type**: Task
**Priority**: Medium
**Labels**: `testing`, `effect`

**Description**:
Create/update unit tests for all effect nodes using mocked handlers instead of real services.

**Test Coverage Requirements**:
- [ ] `NodeKafkaEventEffect` tests with `MockKafkaProducerHandler`
- [ ] `NodeQdrantVectorEffect` tests with `MockVectorStoreHandler`
- [ ] `NodeMemgraphGraphEffect` tests with `MockGraphDatabaseHandler`
- [ ] `NodePostgresPatternEffect` tests with `MockRelationalDatabaseHandler`
- [ ] `NodeIntelligenceAdapterEffect` tests demonstrating NO consumer behavior
- [ ] Error handling tests (handler failures, timeouts)
- [ ] >80% code coverage for effect nodes

**Acceptance Criteria**:
- [ ] Test files created in `tests/unit/nodes/`
- [ ] Mock handler fixtures in `tests/conftest.py`
- [ ] All effect node tests pass
- [ ] Specific test: `test_intelligence_adapter_has_no_consumer()`
- [ ] Coverage report shows >80% for effect nodes

---

## Phase 5: Orchestrator & Reducer Refactoring

**Priority**: HIGH
**Dependencies**: Phase 4 complete
**Node Count**: 2 orchestrator, 1 reducer

### Epic: Refactor Coordination Nodes

#### Issue 5.1: Refactor NodeIntelligenceReducer to use ProtocolRelationalDatabaseHandler

**Title**: Refactor NodeIntelligenceReducer to use ProtocolRelationalDatabaseHandler
**Type**: Feature
**Priority**: High
**Labels**: `architecture`, `refactoring`, `reducer`

**Description**:
Remove direct PostgreSQL access from `NodeIntelligenceReducer`, replace with injected `ProtocolRelationalDatabaseHandler`.

**Files to Modify**:
- `src/omniintelligence/nodes/intelligence_reducer/v1_0_0/reducer.py`
- `src/omniintelligence/nodes/intelligence_reducer/v1_0_0/models/config.py`

**Acceptance Criteria**:
- [ ] No `import asyncpg` statements
- [ ] `ProtocolRelationalDatabaseHandler` injected via constructor
- [ ] FSM transition logic retained (pure logic)
- [ ] Intent emission logic retained (uses handler for storage)
- [ ] Unit tests with mock handler
- [ ] mypy passes

---

#### Issue 5.2: Refactor NodeIntelligenceOrchestrator for contract injection

**Title**: Refactor NodeIntelligenceOrchestrator to accept workflow contracts via injection
**Type**: Feature
**Priority**: High
**Labels**: `architecture`, `refactoring`, `orchestrator`

**Description**:
Refactor `NodeIntelligenceOrchestrator` to receive workflow contracts via injection instead of loading YAML from disk.

**Current State**:
```python
# WRONG - direct file I/O
with open("workflows/document_ingestion.yaml") as f:
    workflow = yaml.safe_load(f)
```

**Target State**:
```python
class NodeIntelligenceOrchestrator(NodeOrchestrator[OrchestratorInput, OrchestratorOutput]):
    def __init__(
        self,
        config: OrchestratorConfig,
        workflow_contracts: dict[str, WorkflowContract],  # Injected
    ):
        self._config = config
        self._workflows = workflow_contracts

    async def orchestrate(self, input: OrchestratorInput) -> OrchestratorOutput:
        workflow = self._workflows[input.workflow_type]
        # Execute workflow steps...
```

**Files to Modify**:
- `src/omniintelligence/nodes/intelligence_orchestrator/v1_0_0/orchestrator.py`
- `src/omniintelligence/nodes/intelligence_orchestrator/v1_0_0/models/config.py`

**Acceptance Criteria**:
- [ ] No direct file I/O in orchestrator
- [ ] Workflow contracts injected via constructor
- [ ] Workflow execution logic retained (pure logic)
- [ ] Step coordination retained (pure logic)
- [ ] Unit tests with injected workflow contracts
- [ ] mypy passes

---

#### Issue 5.3: Refactor NodePatternAssemblerOrchestrator for contract injection

**Title**: Refactor NodePatternAssemblerOrchestrator for contract injection
**Type**: Feature
**Priority**: High
**Labels**: `architecture`, `refactoring`, `orchestrator`

**Description**:
Apply same contract injection pattern to `NodePatternAssemblerOrchestrator`.

**Files to Modify**:
- `src/omniintelligence/nodes/pattern_assembler_orchestrator/v1_0_0/orchestrator.py`

**Acceptance Criteria**:
- [ ] No direct file I/O in orchestrator
- [ ] Pattern assembly contracts injected via constructor
- [ ] 4-phase pattern learning logic retained (Foundation → Matching → Validation → Traceability)
- [ ] Unit tests with injected contracts
- [ ] mypy passes

---

#### Issue 5.4: Update orchestrator/reducer contracts with dependencies

**Title**: Update orchestrator and reducer contracts with handler/contract dependencies
**Type**: Task
**Priority**: Medium
**Labels**: `contracts`, `orchestrator`, `reducer`

**Description**:
Update YAML contracts for orchestrators and reducer to declare dependencies.

**Contract Changes**:
```yaml
# intelligence_reducer
dependencies:
  handlers:
    - handler_type: relational_database
      required: true
      protocol: ProtocolRelationalDatabaseHandler

# intelligence_orchestrator
dependencies:
  contracts:
    - contract_type: workflow
      required: true
      patterns:
        - DOCUMENT_INGESTION
        - PATTERN_LEARNING
        - QUALITY_ASSESSMENT
        - SEMANTIC_ANALYSIS
        - RELATIONSHIP_DETECTION

# pattern_assembler_orchestrator
dependencies:
  contracts:
    - contract_type: pattern_assembly
      required: true
      phases:
        - foundation
        - matching
        - validation
        - traceability
```

**Acceptance Criteria**:
- [ ] All 3 contracts updated with dependencies
- [ ] Contract schema validation passes
- [ ] Contract versions bumped

---

## Phase 6: Runtime Host Integration

**Priority**: HIGH
**Dependencies**: Phase 5 complete, `BaseRuntimeHostProcess` available in omnibase_infra

### Epic: Wire OmniIntelligence into Runtime Host

Create the application-specific runtime wiring that connects OmniIntelligence nodes to the shared Runtime Host infrastructure.

#### Issue 6.1: Create IntelligenceNodeRegistry

**Title**: Implement IntelligenceNodeRegistry class
**Type**: Feature
**Priority**: High
**Labels**: `architecture`, `runtime`, `new-feature`
**Milestone**: MVP

**Description**:
Create `IntelligenceNodeRegistry` class that declares which NodeInstances exist in OmniIntelligence. The registry must also provide version awareness for contract validation and diagnostics.

**Location**: `src/omniintelligence/runtime/node_registry.py`

**Implementation**:
```python
from omnibase_core.runtime import NodeRegistry, NodeInstance
from omniintelligence.nodes import (
    NodeVectorizationCompute,
    NodeQualityScoringCompute,
    NodeEntityExtractionCompute,
    NodeRelationshipDetectionCompute,
    NodeIntentClassifierCompute,
    NodeContextKeywordExtractorCompute,
    NodeSuccessCriteriaMatcherCompute,
    NodeExecutionTraceParserCompute,
    NodeKafkaEventEffect,
    NodeQdrantVectorEffect,
    NodeMemgraphGraphEffect,
    NodePostgresPatternEffect,
    NodeIntelligenceAdapterEffect,
    NodeIntelligenceOrchestrator,
    NodePatternAssemblerOrchestrator,
    NodeIntelligenceReducer,
)

class IntelligenceNodeRegistry(NodeRegistry):
    """Registry of all OmniIntelligence nodes."""

    def get_compute_nodes(self) -> list[type]:
        return [
            NodeVectorizationCompute,
            NodeQualityScoringCompute,
            NodeEntityExtractionCompute,
            NodeRelationshipDetectionCompute,
            NodeIntentClassifierCompute,
            NodeContextKeywordExtractorCompute,
            NodeSuccessCriteriaMatcherCompute,
            NodeExecutionTraceParserCompute,
        ]

    def get_effect_nodes(self) -> list[type]:
        return [
            NodeKafkaEventEffect,
            NodeQdrantVectorEffect,
            NodeMemgraphGraphEffect,
            NodePostgresPatternEffect,
            NodeIntelligenceAdapterEffect,
        ]

    def get_orchestrator_nodes(self) -> list[type]:
        return [
            NodeIntelligenceOrchestrator,
            NodePatternAssemblerOrchestrator,
        ]

    def get_reducer_nodes(self) -> list[type]:
        return [
            NodeIntelligenceReducer,
        ]

    def get_all_nodes(self) -> list[type]:
        return (
            self.get_compute_nodes()
            + self.get_effect_nodes()
            + self.get_orchestrator_nodes()
            + self.get_reducer_nodes()
        )

    def get_node_versions(self) -> dict[str, str]:
        """Return version info for all registered nodes.

        Used by RuntimeHost for contract validation and diagnostics.
        """
        versions = {}
        for node_cls in self.get_all_nodes():
            # Each node must expose metadata via NodeMeta (see Issue 6.9)
            if hasattr(node_cls, 'node_meta'):
                meta = node_cls.node_meta
                versions[node_cls.__name__] = meta.version
            else:
                versions[node_cls.__name__] = "unknown"
        return versions
```

**Acceptance Criteria**:
- [ ] `IntelligenceNodeRegistry` class implemented
- [ ] All 17 nodes registered (8 compute, 5 effect, 2 orchestrator, 1 reducer)
- [ ] Inherits from `omnibase_core.runtime.NodeRegistry`
- [ ] `get_node_versions()` method returns dict[str, str] of node versions
- [ ] Version info used by RuntimeHost for contract validation
- [ ] Unit tests verify all nodes registered
- [ ] mypy passes

---

#### Issue 6.2: Create IntelligenceRuntimeConfig

**Title**: Implement IntelligenceRuntimeConfig class
**Type**: Feature
**Priority**: High
**Labels**: `architecture`, `runtime`, `new-feature`
**Milestone**: MVP

**Description**:
Create `IntelligenceRuntimeConfig` class that configures handler bindings, topics, and contracts for the runtime host. Handler configurations must include production-ready fields for connection pooling, timeouts, retries, circuit breakers, and SSL.

**Location**: `src/omniintelligence/runtime/runtime_config.py`

**Implementation**:
```python
from pydantic import BaseModel, Field
from omnibase_core.runtime import RuntimeConfig

class EventBusConfig(BaseModel):
    """Event bus (ProtocolEventBus/KafkaEventBus) configuration."""
    enabled: bool = True
    bootstrap_servers: str = Field(default="${KAFKA_BOOTSTRAP_SERVERS}")
    consumer_group: str = "intelligence-runtime"
    topics: TopicConfig = Field(default_factory=TopicConfig)

class TopicConfig(BaseModel):
    """Topic configuration for event bus."""
    commands: str = "onex.intelligence.cmd.v1"
    events: str = "onex.intelligence.evt.v1"

class BaseHandlerConfig(BaseModel):
    """Base configuration for all handlers with production-ready fields."""
    connection_pool_size: int = Field(default=10, description="Size of connection pool")
    timeout_ms: int = Field(default=30000, description="Operation timeout in milliseconds")
    retry_max_attempts: int = Field(default=3, description="Maximum retry attempts")
    retry_backoff_ms: int = Field(default=1000, description="Backoff between retries in ms")
    circuit_breaker_enabled: bool = Field(default=True, description="Enable circuit breaker")
    circuit_breaker_threshold: int = Field(default=5, description="Failures before circuit opens")
    ssl_enabled: bool = Field(default=False, description="Enable SSL/TLS for connections")

class VectorStoreHandlerConfig(BaseHandlerConfig):
    """Qdrant-specific handler configuration."""
    host: str = Field(default="${QDRANT_HOST}")
    port: int = Field(default=6333)
    grpc_port: int = Field(default=6334)

class GraphDatabaseHandlerConfig(BaseHandlerConfig):
    """Memgraph-specific handler configuration."""
    host: str = Field(default="${MEMGRAPH_HOST}")
    port: int = Field(default=7687)

class RelationalDatabaseHandlerConfig(BaseHandlerConfig):
    """Postgres-specific handler configuration."""
    host: str = Field(default="${POSTGRES_HOST}")
    port: int = Field(default=5432)
    database: str = Field(default="${POSTGRES_DB}")

class EmbeddingHandlerConfig(BaseHandlerConfig):
    """Embedding service handler configuration."""
    model: str = Field(default="text-embedding-3-small")

class KafkaProducerHandlerConfig(BaseHandlerConfig):
    """Kafka producer handler configuration."""
    bootstrap_servers: str = Field(default="${KAFKA_BOOTSTRAP_SERVERS}")
    acks: str = Field(default="all")

class HandlerConfig(BaseModel):
    """Handler binding configuration."""
    vector_store: VectorStoreHandlerConfig | None = None
    graph_database: GraphDatabaseHandlerConfig | None = None
    relational_database: RelationalDatabaseHandlerConfig | None = None
    embedding: EmbeddingHandlerConfig | None = None
    kafka_producer: KafkaProducerHandlerConfig | None = None

class IntelligenceRuntimeConfig(RuntimeConfig):
    """Configuration for OmniIntelligence runtime host."""

    runtime_node_id: str = "intelligence-runtime"
    event_bus: EventBusConfig = Field(default_factory=EventBusConfig)
    handlers: HandlerConfig = Field(default_factory=HandlerConfig)

    @classmethod
    def from_environment(cls) -> "IntelligenceRuntimeConfig":
        """Load configuration from environment variables."""
        ...
```

**Acceptance Criteria**:
- [ ] `IntelligenceRuntimeConfig` class implemented
- [ ] Event bus configuration for topics and consumer group
- [ ] Handler configurations for all 5 handler types
- [ ] `BaseHandlerConfig` with production fields:
  - [ ] `connection_pool_size: int`
  - [ ] `timeout_ms: int`
  - [ ] `retry_max_attempts: int`
  - [ ] `retry_backoff_ms: int`
  - [ ] `circuit_breaker_enabled: bool`
  - [ ] `circuit_breaker_threshold: int`
  - [ ] `ssl_enabled: bool`
- [ ] Environment variable loading with sensible defaults
- [ ] YAML serialization/deserialization
- [ ] Unit tests for config loading
- [ ] mypy passes

---

#### Issue 6.3: Create runtime host entrypoint main.py

**Title**: Create thin runtime host entrypoint
**Type**: Feature
**Priority**: High
**Labels**: `architecture`, `runtime`, `entrypoint`
**Milestone**: MVP

**Description**:
Create thin `main.py` entrypoint that calls `BaseRuntimeHostProcess` from `omnibase_infra`.

**Location**: `src/omniintelligence/runtime/main.py`

**IMPORTANT NOTE**: Event loop creation should be handled in `BaseRuntimeHostProcess`, not in `main.py`. This ensures all runtime hosts behave identically, supports uvloop replacement, and enables test embedding. The `main.py` entrypoint should simply call into `BaseRuntimeHostProcess` which owns the event loop lifecycle.

**Implementation**:
```python
"""OmniIntelligence Runtime Host entrypoint.

This is a THIN entrypoint that delegates to BaseRuntimeHostProcess.
All heavy lifting is done by omnibase_infra - we just provide config and registry.

NOTE: Event loop creation is handled by BaseRuntimeHostProcess to ensure:
- All runtime hosts behave identically
- Supports uvloop replacement
- Enables test embedding
"""
import asyncio
import signal
from omnibase_infra.runtime import BaseRuntimeHostProcess

from omniintelligence.runtime.node_registry import IntelligenceNodeRegistry
from omniintelligence.runtime.runtime_config import IntelligenceRuntimeConfig


async def main() -> None:
    """Start the OmniIntelligence runtime host."""
    config = IntelligenceRuntimeConfig.from_environment()
    registry = IntelligenceNodeRegistry()

    runtime_host = BaseRuntimeHostProcess(
        config=config,
        registry=registry,
    )

    # Graceful shutdown
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, runtime_host.request_shutdown)

    await runtime_host.run()


if __name__ == "__main__":
    asyncio.run(main())
```

**Acceptance Criteria**:
- [ ] `main.py` is thin (<50 lines)
- [ ] Uses `BaseRuntimeHostProcess` from `omnibase_infra`
- [ ] Provides `IntelligenceRuntimeConfig` and `IntelligenceNodeRegistry`
- [ ] Graceful shutdown on SIGTERM/SIGINT
- [ ] No direct Kafka/DB code in this file
- [ ] Event loop creation delegated to BaseRuntimeHostProcess (not main.py)
- [ ] mypy passes

---

#### Issue 6.4: Create runtime/__init__.py with exports

**Title**: Create runtime module exports
**Type**: Task
**Priority**: Medium
**Labels**: `architecture`, `runtime`
**Milestone**: MVP

**Description**:
Create `runtime/__init__.py` with proper exports.

**Location**: `src/omniintelligence/runtime/__init__.py`

**Implementation**:
```python
"""OmniIntelligence Runtime Host module.

This module provides the application-specific runtime configuration
for OmniIntelligence. The actual runtime host implementation is in
omnibase_infra.
"""
from omniintelligence.runtime.node_registry import IntelligenceNodeRegistry
from omniintelligence.runtime.runtime_config import IntelligenceRuntimeConfig

__all__ = [
    "IntelligenceNodeRegistry",
    "IntelligenceRuntimeConfig",
]
```

**Acceptance Criteria**:
- [ ] `__init__.py` created with exports
- [ ] Module docstring explains purpose
- [ ] `__all__` defined
- [ ] Imports work correctly

---

#### Issue 6.5: Add runtime entry point to pyproject.toml

**Title**: Add omniintelligence-runtime CLI entry point
**Type**: Task
**Priority**: Medium
**Labels**: `cli`, `configuration`
**Milestone**: MVP

**Description**:
Add CLI entry point for starting the runtime host.

**Location**: `pyproject.toml`

**Changes**:
```toml
[project.scripts]
omniintelligence-runtime = "omniintelligence.runtime.main:main"
```

**Usage**:
```bash
omniintelligence-runtime
# or with explicit config
KAFKA_BOOTSTRAP_SERVERS=192.168.86.200:29092 omniintelligence-runtime
```

**Acceptance Criteria**:
- [ ] Entry point added to `pyproject.toml`
- [ ] Command works: `omniintelligence-runtime --help`
- [ ] Environment variable configuration works
- [ ] Integration test verifies startup

---

#### Issue 6.6: Create Node Health & Lifecycle Integration

**Title**: Implement node health and lifecycle integration with runtime host
**Type**: Feature
**Priority**: High
**Labels**: `runtime`, `health`, `lifecycle`
**Milestone**: Beta

**Description**:
Define and implement health/lifecycle integration between nodes and the runtime host.

**Health Definition by Node Type**:

| Node Type | Health Indicators |
|-----------|-------------------|
| Compute | Always healthy if loaded (no external dependencies) |
| Effect | Handler connection status, last successful operation time |
| Orchestrator | Workflow contract loaded, dependency nodes available |
| Reducer | FSM contract loaded, database handler connected |

**Lifecycle Events**:
```python
class NodeLifecycleEvent(Enum):
    INITIALIZING = "initializing"
    READY = "ready"
    PROCESSING = "processing"
    DEGRADED = "degraded"  # Handler failure but recoverable
    FAILED = "failed"      # Unrecoverable failure
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"
```

**Implementation**:
```python
# In each node
class NodeQdrantVectorEffect(NodeEffect):
    async def health_check(self) -> HealthStatus:
        """Report health status to runtime host."""
        try:
            await self._vector_handler.ping()
            return HealthStatus(
                status="healthy",
                last_success=self._last_success_time,
                handler_connected=True,
            )
        except Exception as e:
            return HealthStatus(
                status="degraded",
                error=str(e),
                handler_connected=False,
            )

    def emit_lifecycle_event(self, event: NodeLifecycleEvent) -> None:
        """Emit lifecycle event to runtime host."""
        ...
```

**Acceptance Criteria**:
- [ ] Health status defined for all node types
- [ ] Lifecycle events defined and emitted
- [ ] Effect nodes report handler connection status
- [ ] Orchestrators report dependency availability
- [ ] Runtime host aggregates node health
- [ ] Health endpoint exposes aggregated status
- [ ] Degraded state triggers alerts (not shutdown)

---

#### Issue 6.7: Create Local Development Mode Profile

**Title**: Implement local-dev runtime profile with mock handlers
**Type**: Feature
**Priority**: Medium
**Labels**: `runtime`, `development`, `testing`
**Milestone**: Beta

**Description**:
Create a `local-dev` runtime profile that uses mock handlers for rapid local development without requiring Kafka, Qdrant, Memgraph, or Postgres.

**Profile Configuration**:
```yaml
profile: local-dev

event_bus:
  type: mock  # MockEventBus instead of KafkaEventBus

handlers:
  vector_store:
    type: mock  # In-memory vector store
  graph_database:
    type: mock  # Stub graph handler
  relational_database:
    type: sqlite  # SQLite for local persistence (optional)
  embedding:
    type: mock  # Returns random embeddings
  kafka_producer:
    type: mock  # No-op producer
```

**Mock Handler Implementation**:
```python
class MockVectorStoreHandler(ProtocolVectorStoreHandler):
    """In-memory vector store for local development."""

    def __init__(self):
        self._store: dict[str, list[float]] = {}

    async def upsert(self, collection: str, id: str, vector: list[float], metadata: dict) -> Result:
        self._store[f"{collection}:{id}"] = vector
        return Result(success=True)

    async def search(self, collection: str, vector: list[float], limit: int) -> list[SearchResult]:
        # Simple cosine similarity search
        ...
```

**Usage**:
```bash
RUNTIME_PROFILE=local-dev omniintelligence-runtime
```

**Acceptance Criteria**:
- [ ] `local-dev` profile implemented
- [ ] MockEventBus for event consumption
- [ ] In-memory vector store handler
- [ ] Stub graph handler
- [ ] Optional SQLite for relational DB
- [ ] Mock embedding handler (random or fixed)
- [ ] No-op Kafka producer
- [ ] Startup time <5s with mocks
- [ ] All nodes can be exercised locally

---

#### Issue 6.8: Create Runtime Host Boot Diagram Documentation

**Title**: Create runtime host boot sequence diagram
**Type**: Documentation
**Priority**: Medium
**Labels**: `documentation`, `architecture`, `runtime`
**Milestone**: MVP

**Description**:
Create a visual diagram showing the runtime host boot sequence and envelope flow.

**Location**: `docs/architecture/RUNTIME_HOST_BOOT_SEQUENCE.md`

**Content**:
```markdown
# Runtime Host Boot Sequence

## Boot Sequence Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        RUNTIME HOST BOOT SEQUENCE                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. Load Configuration                                                        │
│     ├── Read environment variables                                           │
│     ├── Load IntelligenceRuntimeConfig                                       │
│     └── Validate configuration (dry-run checks)                              │
│                                                                              │
│  2. Initialize Handlers (omnibase_infra)                                     │
│     ├── Create handler pool                                                  │
│     ├── Connect to Qdrant (ProtocolVectorStoreHandler)                              │
│     ├── Connect to Memgraph (ProtocolGraphDatabaseHandler)                          │
│     ├── Connect to Postgres (ProtocolRelationalDatabaseHandler)                     │
│     ├── Initialize Embedding service (ProtocolEmbeddingHandler)                     │
│     └── Connect to Kafka producer (ProtocolKafkaProducerHandler)                    │
│                                                                              │
│  3. Load Node Contracts                                                       │
│     ├── Scan IntelligenceNodeRegistry                                        │
│     ├── Load YAML contracts for each node                                    │
│     ├── Validate contract schema                                             │
│     └── Build dependency graph                                               │
│                                                                              │
│  4. Create NodeInstances                                                      │
│     ├── For each registered node:                                            │
│     │   ├── Resolve handler dependencies                                     │
│     │   ├── Inject handlers into node constructor                            │
│     │   └── Register with NodeRuntime                                        │
│     └── Verify all dependencies satisfied                                    │
│                                                                              │
│  5. Start Event Bus (KafkaEventBus)                                          │
│     ├── Subscribe to command topics                                          │
│     ├── Subscribe to event topics                                            │
│     └── Begin polling loop                                                   │
│                                                                              │
│  6. Enter Run Loop                                                            │
│     └── See Envelope Flow Diagram below                                      │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Envelope Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           ENVELOPE FLOW                                       │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Kafka Topic                                                                  │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────┐                                 │
│  │         KafkaEventBus (infra)           │                                 │
│  │  - poll() → raw message                 │                                 │
│  │  - deserialize → payload                │                                 │
│  │  - wrap → ModelOnexEnvelope             │                                 │
│  └─────────────────────────────────────────┘                                 │
│       │                                                                      │
│       ▼ envelope                                                             │
│  ┌─────────────────────────────────────────┐                                 │
│  │        BaseRuntimeHostProcess (infra)   │                                 │
│  │  - route_envelope(envelope)             │                                 │
│  └─────────────────────────────────────────┘                                 │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────┐                                 │
│  │          NodeRuntime (core)             │                                 │
│  │  - lookup target node by envelope.type  │                                 │
│  │  - get NodeInstance                     │                                 │
│  └─────────────────────────────────────────┘                                 │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────┐                                 │
│  │     NodeInstance (omniintelligence)     │                                 │
│  │  - node.execute(envelope.payload)       │                                 │
│  │  - (calls injected handlers as needed)  │                                 │
│  │  - return result envelope               │                                 │
│  └─────────────────────────────────────────┘                                 │
│       │                                                                      │
│       ▼ result envelope                                                      │
│  ┌─────────────────────────────────────────┐                                 │
│  │         KafkaEventBus (infra)           │                                 │
│  │  - publish result to output topic       │                                 │
│  │  - commit offset                        │                                 │
│  └─────────────────────────────────────────┘                                 │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```
```

**Acceptance Criteria**:
- [ ] Boot sequence diagram created
- [ ] Envelope flow diagram created
- [ ] All 6 boot phases documented
- [ ] Handler initialization order clear
- [ ] Node loading process clear
- [ ] Envelope routing path clear
- [ ] Reviewed before Phase 6 implementation begins

---

#### Issue 6.9: Implement NodeMeta Model for Node-Level Metadata

**Title**: Implement NodeMeta model for node-level metadata
**Type**: Feature
**Priority**: High
**Labels**: `architecture`, `runtime`, `new-feature`
**Milestone**: MVP

**Description**:
Every node must emit standardized metadata that the runtime host can query. This enables contract validation, version tracking, dependency analysis, and diagnostics.

> **TODO**: NodeMeta should ultimately live in `omnibase_core/runtime` to be reusable across all applications. Initially implement in `omniintelligence` and migrate later.

**Location**: `src/omniintelligence/runtime/node_meta.py` (temporary, migrate to omnibase_core later)

**Implementation**:
```python
from pydantic import BaseModel, Field
from enum import Enum


class NodeKind(str, Enum):
    """Node type classification."""
    COMPUTE = "compute"
    EFFECT = "effect"
    REDUCER = "reducer"
    ORCHESTRATOR = "orchestrator"


class NodeMeta(BaseModel):
    """Standardized metadata that every node must expose.

    This enables runtime host to:
    - Validate node contracts
    - Track node versions across the system
    - Analyze handler dependencies
    - Generate diagnostics and health reports
    """

    version: str = Field(
        ...,
        description="Semantic version of the node (e.g., '1.0.0')"
    )
    fingerprint: str = Field(
        ...,
        description="Content hash of node implementation for cache invalidation"
    )
    kind: NodeKind = Field(
        ...,
        description="Node type classification"
    )
    contract_path: str = Field(
        ...,
        description="Relative path to YAML contract file"
    )
    handlers_required: list[str] = Field(
        default_factory=list,
        description="List of handler types this node requires (e.g., ['vector_store', 'embedding'])"
    )
    handlers_optional: list[str] = Field(
        default_factory=list,
        description="List of handler types this node can optionally use"
    )
    topics_subscribe: list[str] = Field(
        default_factory=list,
        description="Kafka topics this node subscribes to"
    )
    topics_publish: list[str] = Field(
        default_factory=list,
        description="Kafka topics this node publishes to"
    )


# Example usage in a node class
class NodeVectorizationCompute:
    """Example node with NodeMeta."""

    node_meta = NodeMeta(
        version="1.0.0",
        fingerprint="abc123def456",
        kind=NodeKind.COMPUTE,
        contract_path="nodes/vectorization_compute/v1_0_0/contracts/contract.yaml",
        handlers_required=["embedding"],
        handlers_optional=[],
        topics_subscribe=[],
        topics_publish=[],
    )
```

**Usage by NodeRuntime**:
```python
class NodeRuntime:
    def validate_node(self, node_cls: type) -> ValidationResult:
        """Validate node against its contract using NodeMeta."""
        meta = node_cls.node_meta
        contract = self.load_contract(meta.contract_path)

        # Validate version matches contract
        if meta.version != contract.version:
            return ValidationResult(
                valid=False,
                error=f"Version mismatch: node={meta.version}, contract={contract.version}"
            )

        # Validate required handlers are available
        for handler in meta.handlers_required:
            if handler not in self.available_handlers:
                return ValidationResult(
                    valid=False,
                    error=f"Missing required handler: {handler}"
                )

        return ValidationResult(valid=True)
```

**Acceptance Criteria**:
- [ ] `NodeMeta` model defined with all fields
- [ ] `NodeKind` enum defined (compute, effect, reducer, orchestrator)
- [ ] All 17 OmniIntelligence nodes expose `node_meta` class property
- [ ] `NodeRuntime` can query `node_meta` for any registered node
- [ ] Metadata validated against YAML contract during startup
- [ ] Handler dependencies declared in metadata
- [ ] Topic subscriptions declared in metadata
- [ ] TODO marker added for move to omnibase_core
- [ ] Unit tests for NodeMeta validation
- [ ] mypy passes

---

## Phase 7: Docker Consolidation

**Priority**: MEDIUM
**Dependencies**: Phase 6 complete

### Epic: Consolidate to 2-3 Runtime Host Containers

Replace 10+ per-node containers with 2-3 runtime host containers.

#### Issue 7.1: Create unified runtime host Dockerfile

**Title**: Create single Dockerfile.runtime-host
**Type**: Task
**Priority**: Medium
**Labels**: `docker`, `infrastructure`
**Milestone**: **MVP** (basic single-stage), **Beta** (multistage optimization)

**Description**:
Create single Dockerfile that can run any configuration of nodes via the runtime host.

**Location**: `deployment/docker/Dockerfile.runtime-host`

**Implementation (MVP - Single Stage)**:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen

# Copy application
COPY src/ ./src/

# Set entrypoint
ENTRYPOINT ["python", "-m", "omniintelligence.runtime.main"]
```

**Implementation (Beta - Multistage Build)**:

Multistage builds can reduce image size by ~70% by separating build dependencies from runtime.

```dockerfile
# Stage 1: Builder
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev

# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app

# Copy only the virtual environment from builder
COPY --from=builder /build/.venv /app/.venv

# Copy application source
COPY src/ ./src/

# Set path to use venv
ENV PATH="/app/.venv/bin:$PATH"

# Set entrypoint
ENTRYPOINT ["python", "-m", "omniintelligence.runtime.main"]
```

**Benefits of Multistage**:
- Eliminates build-essential (~200MB) from final image
- No pip/uv in runtime image
- Smaller attack surface
- Faster container pulls

**Acceptance Criteria**:
- [ ] Single Dockerfile for all runtime configurations
- [ ] Uses uv for dependency installation
- [ ] Slim base image for minimal footprint
- [ ] Health check endpoint configured
- [ ] Build succeeds: `docker build -f Dockerfile.runtime-host -t omniintelligence-runtime .`
- [ ] (Beta) Multistage build implemented
- [ ] (Beta) Image size reduced by >50%

---

#### Issue 7.2: Create docker-compose.runtime.yml

**Title**: Create docker-compose for runtime host deployment
**Type**: Task
**Priority**: Medium
**Labels**: `docker`, `infrastructure`
**Milestone**: **MVP**

**Description**:
Create docker-compose with 2 services: main runtime and effects runtime.

**Rationale for Resource Limits**:
Without resource limits, container consolidation risks OOM kills and CPU throttling when multiple nodes compete for resources. Resource limits ensure predictable behavior and prevent cascade failures.

**Location**: `deployment/docker/docker-compose.runtime.yml`

**Implementation**:
```yaml
version: "3.9"

services:
  intelligence-runtime-main:
    build:
      context: ../..
      dockerfile: deployment/docker/Dockerfile.runtime-host
    environment:
      KAFKA_BOOTSTRAP_SERVERS: "${KAFKA_BOOTSTRAP_SERVERS:-omninode-bridge-redpanda:9092}"
      RUNTIME_NODE_ID: "intelligence-runtime-main"
      RUNTIME_PROFILE: "main"  # orchestrator, reducer, compute nodes
    depends_on:
      - redpanda
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 512m
          cpus: "0.5"
        reservations:
          memory: 256m
          cpus: "0.25"

  intelligence-runtime-effects:
    build:
      context: ../..
      dockerfile: deployment/docker/Dockerfile.runtime-host
    environment:
      KAFKA_BOOTSTRAP_SERVERS: "${KAFKA_BOOTSTRAP_SERVERS:-omninode-bridge-redpanda:9092}"
      QDRANT_HOST: "${QDRANT_HOST:-qdrant}"
      MEMGRAPH_HOST: "${MEMGRAPH_HOST:-memgraph}"
      POSTGRES_HOST: "${POSTGRES_HOST:-postgres}"
      RUNTIME_NODE_ID: "intelligence-runtime-effects"
      RUNTIME_PROFILE: "effects"  # effect nodes only
    depends_on:
      - redpanda
      - qdrant
      - memgraph
      - postgres
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 512m
          cpus: "0.5"
        reservations:
          memory: 256m
          cpus: "0.25"

# External networks/volumes reference shared infrastructure
networks:
  default:
    external: true
    name: omninode-bridge_default
```

**Resource Limit Guidelines**:
| Profile | Memory Limit | CPU Limit | Rationale |
|---------|-------------|-----------|-----------|
| `main` | 512m | 0.5 | Compute nodes are CPU-bound, moderate memory |
| `effects` | 512m | 0.5 | I/O-bound, moderate resources |
| `all` | 1024m | 1.0 | Full stack for development |

**Acceptance Criteria**:
- [ ] 2 services defined (main + effects)
- [ ] Environment variable configuration
- [ ] Resource limits configured for each service
- [ ] Resource reservations ensure minimum guaranteed resources
- [ ] Health checks configured
- [ ] References external shared infrastructure network
- [ ] Services start successfully: `docker compose -f docker-compose.runtime.yml up`

---

#### Issue 7.3: Create runtime profiles for node selection

**Title**: Implement runtime profiles for selective node loading
**Type**: Feature
**Priority**: Medium
**Labels**: `runtime`, `configuration`
**Milestone**: **MVP**

**Description**:
Implement runtime profiles that determine which nodes are loaded in each container.

**Profiles**:
- `main`: Orchestrators, reducer, compute nodes
- `effects`: Effect nodes only
- `all`: All nodes (for development/testing)

**Implementation** (in `IntelligenceRuntimeConfig`):
```python
class RuntimeProfile(str, Enum):
    MAIN = "main"
    EFFECTS = "effects"
    ALL = "all"

class IntelligenceRuntimeConfig(RuntimeConfig):
    profile: RuntimeProfile = RuntimeProfile.ALL

    def get_enabled_nodes(self, registry: IntelligenceNodeRegistry) -> list[type]:
        if self.profile == RuntimeProfile.MAIN:
            return (
                registry.get_compute_nodes()
                + registry.get_orchestrator_nodes()
                + registry.get_reducer_nodes()
            )
        elif self.profile == RuntimeProfile.EFFECTS:
            return registry.get_effect_nodes()
        else:
            return registry.get_all_nodes()
```

**Acceptance Criteria**:
- [ ] `RuntimeProfile` enum defined
- [ ] Profile selection via `RUNTIME_PROFILE` environment variable
- [ ] `main` profile loads 11 nodes (8 compute, 2 orchestrator, 1 reducer)
- [ ] `effects` profile loads 5 nodes (5 effect)
- [ ] `all` profile loads all 16 nodes
- [ ] Unit tests verify correct node selection

---

#### Issue 7.4: Archive per-node Dockerfiles

**Title**: Archive per-node Docker configuration
**Type**: Task
**Priority**: Low
**Labels**: `docker`, `cleanup`
**Milestone**: **Beta**

**Description**:
Move per-node Docker files to `deployment/docker/archived/` for reference.

**Files to Move**:
- `Dockerfile.compute` -> `archived/Dockerfile.compute`
- `Dockerfile.effect` -> `archived/Dockerfile.effect`
- `Dockerfile.orchestrator` -> `archived/Dockerfile.orchestrator`
- `Dockerfile.reducer` -> `archived/Dockerfile.reducer`
- `docker-compose.nodes.yml` -> `archived/docker-compose.nodes.yml`

**Acceptance Criteria**:
- [ ] All per-node files moved to `archived/` directory
- [ ] `archived/README.md` created explaining these are no longer used
- [ ] `.dockerignore` updated if needed
- [ ] CI/CD pipelines updated to use new files

---

#### Issue 7.5: Create Runtime Profile Compatibility Matrix

**Title**: Create runtime profile compatibility matrix documentation
**Type**: Documentation
**Priority**: Medium
**Labels**: `documentation`, `runtime`, `configuration`
**Milestone**: **MVP**

**Description**:
Create comprehensive documentation of runtime profile compatibility, handler requirements, and failure behaviors.

**Location**: `docs/runtime/PROFILE_COMPATIBILITY_MATRIX.md`

**Content**:
```markdown
# Runtime Profile Compatibility Matrix

## Profile Overview

| Profile | Description | Node Count | Use Case |
|---------|-------------|------------|----------|
| `main` | Orchestrators, reducer, compute | 11 | Core processing |
| `effects` | Effect nodes only | 5 | I/O-heavy operations |
| `all` | All nodes | 16 | Development/testing |
| `local-dev` | All nodes + mock handlers | 16 | Local development |

## Node-to-Profile Mapping

| Node | main | effects | all | local-dev |
|------|------|---------|-----|-----------|
| vectorization_compute | ✅ | ❌ | ✅ | ✅ |
| quality_scoring_compute | ✅ | ❌ | ✅ | ✅ |
| entity_extraction_compute | ✅ | ❌ | ✅ | ✅ |
| relationship_detection_compute | ✅ | ❌ | ✅ | ✅ |
| intent_classifier_compute | ✅ | ❌ | ✅ | ✅ |
| context_keyword_extractor_compute | ✅ | ❌ | ✅ | ✅ |
| success_criteria_matcher_compute | ✅ | ❌ | ✅ | ✅ |
| execution_trace_parser_compute | ✅ | ❌ | ✅ | ✅ |
| kafka_event_effect | ❌ | ✅ | ✅ | ✅ |
| qdrant_vector_effect | ❌ | ✅ | ✅ | ✅ |
| memgraph_graph_effect | ❌ | ✅ | ✅ | ✅ |
| postgres_pattern_effect | ❌ | ✅ | ✅ | ✅ |
| intelligence_adapter | ❌ | ✅ | ✅ | ✅ |
| intelligence_orchestrator | ✅ | ❌ | ✅ | ✅ |
| pattern_assembler_orchestrator | ✅ | ❌ | ✅ | ✅ |
| intelligence_reducer | ✅ | ❌ | ✅ | ✅ |

## Handler Requirements by Profile

| Handler | main | effects | all |
|---------|------|---------|-----|
| ProtocolEmbeddingHandler | **REQUIRED** | ❌ | **REQUIRED** |
| ProtocolVectorStoreHandler | ❌ | **REQUIRED** | **REQUIRED** |
| ProtocolGraphDatabaseHandler | ❌ | **REQUIRED** | **REQUIRED** |
| ProtocolRelationalDatabaseHandler | **REQUIRED** | **REQUIRED** | **REQUIRED** |
| ProtocolKafkaProducerHandler | optional | **REQUIRED** | **REQUIRED** |

## Failure Behavior

| Scenario | Behavior |
|----------|----------|
| Required handler not configured | Runtime fails to start with error |
| Required handler connection fails | Runtime starts in DEGRADED state |
| Optional handler not configured | Node skips optional operations |
| Handler becomes unavailable at runtime | Node transitions to DEGRADED, retries |
```

**Acceptance Criteria**:
- [ ] All profiles documented
- [ ] Node-to-profile mapping complete
- [ ] Handler requirements clear per profile
- [ ] Failure behavior documented
- [ ] Machine-readable JSON version available

---

#### Issue 7.6: Docker Compose Autogeneration from Registry

**Title**: Add docker-compose autogeneration from registry
**Type**: Feature
**Priority**: Medium
**Labels**: `docker`, `tooling`, `automation`
**Milestone**: **Beta**

**Description**:
Hardcoding node lists into docker-compose is fragile and error-prone. When nodes are added, removed, or renamed, the docker-compose files must be manually updated. This issue adds a CLI command that reads the runtime profiles and node registry to automatically generate valid docker-compose configurations.

**Rationale**:
- Reduces human error when adding/removing nodes
- Ensures docker-compose always matches the registry
- Simplifies maintenance and CI/CD integration
- Single source of truth (registry) for node configuration

**CLI Command**:
```bash
# Generate docker-compose for main profile
omniintelligence-runtime generate-docker-compose --profile main --output docker-compose.runtime.yml

# Generate for specific profiles
omniintelligence-runtime generate-docker-compose --profile effects --output docker-compose.effects.yml

# Generate all profiles in separate files
omniintelligence-runtime generate-docker-compose --profile all --output docker-compose.all.yml

# Generate for local development
omniintelligence-runtime generate-docker-compose --profile local-dev --output docker-compose.local.yml
```

**Implementation**:
```python
# In omniintelligence/runtime/cli.py
import click
import yaml
from omniintelligence.runtime.config import RuntimeProfile
from omniintelligence.runtime.registry import IntelligenceNodeRegistry

@click.command()
@click.option('--profile', type=click.Choice(['main', 'effects', 'all', 'local-dev']), required=True)
@click.option('--output', type=click.Path(), default='docker-compose.runtime.yml')
def generate_docker_compose(profile: str, output: str):
    """Generate docker-compose.yml from node registry and profile."""
    registry = IntelligenceNodeRegistry()
    config = generate_compose_config(profile, registry)

    with open(output, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)

    click.echo(f"Generated {output} with {len(config['services'])} services")

def generate_compose_config(profile: str, registry: IntelligenceNodeRegistry) -> dict:
    """Generate docker-compose config dict from registry."""
    nodes = registry.get_nodes_for_profile(RuntimeProfile(profile))

    return {
        'version': '3.9',
        'services': {
            f'intelligence-runtime-{profile}': {
                'build': {
                    'context': '../..',
                    'dockerfile': 'deployment/docker/Dockerfile.runtime-host'
                },
                'environment': {
                    'RUNTIME_PROFILE': profile,
                    'RUNTIME_NODE_ID': f'intelligence-runtime-{profile}',
                    # ... other env vars
                },
                'deploy': {
                    'resources': {
                        'limits': {'memory': '512m', 'cpus': '0.5'},
                        'reservations': {'memory': '256m', 'cpus': '0.25'}
                    }
                }
            }
        },
        'networks': {
            'default': {
                'external': True,
                'name': 'omninode-bridge_default'
            }
        }
    }
```

**Acceptance Criteria**:
- [ ] CLI command `generate-docker-compose` implemented
- [ ] Generates valid docker-compose YAML from registry
- [ ] Supports all profiles: `main`, `effects`, `all`, `local-dev`
- [ ] Includes resource limits in generated config
- [ ] Includes health checks in generated config
- [ ] Output file path configurable via `--output` flag
- [ ] Updates automatically when nodes added/removed from registry
- [ ] Integration with CI/CD to validate docker-compose matches registry

---

## Phase 8: Testing & Validation

**Priority**: MEDIUM
**Dependencies**: Phase 7 complete

> **MVP Scope Reduction**: For MVP, Phase 8 is limited to:
> - Unit tests for each node (8.1 mock fixtures, basic coverage)
> - 1-2 integration tests (Qdrant + Postgres only)
> - Envelope routing test in runtime host
>
> Advanced testing (chaos, replay, full compliance) deferred to Beta/GA.

### Epic: Comprehensive Testing

#### Issue 8.1: Create handler mock fixtures

**Title**: Create comprehensive handler mock fixtures for testing
**Type**: Task
**Priority**: High
**Labels**: `testing`, `fixtures`
**Milestone**: **MVP**

**Description**:
Create reusable mock handler fixtures for all SPI handler types.

**Location**: `tests/conftest.py`

**Fixtures to Create**:
```python
@pytest.fixture
def mock_embedding_handler() -> MockEmbeddingHandler:
    """Mock ProtocolEmbeddingHandler for testing."""
    ...

@pytest.fixture
def mock_vector_store_handler() -> MockVectorStoreHandler:
    """Mock ProtocolVectorStoreHandler for testing."""
    ...

@pytest.fixture
def mock_graph_database_handler() -> MockGraphDatabaseHandler:
    """Mock ProtocolGraphDatabaseHandler for testing."""
    ...

@pytest.fixture
def mock_relational_database_handler() -> MockRelationalDatabaseHandler:
    """Mock ProtocolRelationalDatabaseHandler for testing."""
    ...

@pytest.fixture
def mock_kafka_producer_handler() -> MockKafkaProducerHandler:
    """Mock ProtocolKafkaProducerHandler for testing."""
    ...
```

**Acceptance Criteria**:
- [ ] All 5 mock handler fixtures created
- [ ] Mocks implement full SPI protocol interface
- [ ] Mocks support configurable responses
- [ ] Mocks support assertion on calls made
- [ ] Documentation in fixture docstrings

---

#### Issue 8.2: Create integration tests with testcontainers

**Title**: Create integration tests using testcontainers
**Type**: Task
**Priority**: Medium
**Labels**: `testing`, `integration`
**Milestone**: **MVP** (limited to Qdrant + Postgres only)

**Description**:
Create integration tests that use testcontainers for real service testing.

> **MVP Scope**: For MVP, only Qdrant and Postgres integration tests are required. Memgraph, Redpanda, and full runtime host integration tests are deferred to Beta.

**Location**: `tests/integration/`

**Tests to Create (MVP)**:
- `test_qdrant_integration.py` - Real Qdrant container
- `test_postgres_integration.py` - Real PostgreSQL container

**Tests to Create (Beta)**:
- `test_memgraph_integration.py` - Real Memgraph container
- `test_redpanda_integration.py` - Real Redpanda container
- `test_runtime_host_integration.py` - Full runtime host with real services

**Acceptance Criteria (MVP)**:
- [ ] testcontainers dependency added
- [ ] Qdrant integration test file created
- [ ] Postgres integration test file created
- [ ] Tests start containers, run operations, verify results
- [ ] Tests clean up containers after completion
- [ ] CI marker: `@pytest.mark.integration`

**Acceptance Criteria (Beta)**:
- [ ] All 5 integration test files created
- [ ] Full runtime host integration test passing

---

#### Issue 8.3: Create I/O audit test

**Title**: Create automated I/O import audit test
**Type**: Task
**Priority**: High
**Labels**: `testing`, `audit`
**Milestone**: **MVP**

**Description**:
Create automated test that verifies no OmniIntelligence nodes import forbidden I/O libraries.

**Location**: `tests/unit/test_io_audit.py`

**Implementation**:
```python
import ast
from pathlib import Path
import pytest

FORBIDDEN_IMPORTS = {
    "confluent_kafka",
    "qdrant_client",
    "neo4j",
    "asyncpg",
    "httpx",
    "openai",
    "sentence_transformers",
}

NODES_PATH = Path("src/omniintelligence/nodes")


def test_nodes_have_no_forbidden_imports():
    """Verify no OmniIntelligence node imports forbidden I/O libraries."""
    violations = []

    for py_file in NODES_PATH.rglob("*.py"):
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in FORBIDDEN_IMPORTS:
                        violations.append(f"{py_file}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in FORBIDDEN_IMPORTS:
                    violations.append(f"{py_file}: from {node.module} import ...")

    assert not violations, f"Found forbidden imports:\n" + "\n".join(violations)
```

**Acceptance Criteria**:
- [ ] Test file created
- [ ] Tests all Python files in `nodes/` directory
- [ ] Catches all forbidden import patterns
- [ ] Clear error messages on failure
- [ ] Test passes (after node refactoring complete)

---

#### Issue 8.4: Create performance benchmark tests

**Title**: Create before/after performance benchmarks
**Type**: Task
**Priority**: Medium
**Labels**: `testing`, `performance`
**Milestone**: **GA**

> **Note**: Mark tests with `@pytest.mark.xfail` until architecture is stable. Performance benchmarks are informational during MVP/Beta and only become hard requirements at GA.

**Description**:
Create performance benchmark tests to measure improvement from architecture change.

**Metrics to Measure**:
- Container count (target: ≤3)
- Memory footprint (target: ≤400MB)
- Startup time
- Message throughput
- Kafka connection count (target: 1-3)

**Location**: `tests/performance/`

**Acceptance Criteria**:
- [ ] Benchmark test framework set up
- [ ] Memory measurement utilities
- [ ] Before/after comparison script
- [ ] Results documented in report
- [ ] Tests marked `@pytest.mark.xfail` until GA

---

#### Issue 8.5: Achieve >80% test coverage

**Title**: Achieve >80% test coverage for refactored code
**Type**: Task
**Priority**: High
**Labels**: `testing`, `coverage`
**Milestone**: **Beta**

**Description**:
Ensure all refactored code has >80% test coverage.

**Coverage Requirements**:
- [ ] `nodes/` directory: >80%
- [ ] `runtime/` directory: >80%
- [ ] Overall project: >80%

**Acceptance Criteria**:
- [ ] Coverage report generated: `pytest --cov=src/omniintelligence --cov-report=html`
- [ ] All directories meet 80% threshold
- [ ] Coverage report committed to `reports/`
- [ ] CI fails if coverage drops below 80%

---

#### Issue 8.6: Create Handler Compliance Tests

**Title**: Create handler protocol compliance tests for all SPI handlers
**Type**: Task
**Priority**: High
**Labels**: `testing`, `handlers`, `compliance`
**Milestone**: **Beta**

**Description**:
Create tests that verify each handler implementation fully complies with its SPI protocol.

**Location**: `tests/unit/handlers/test_handler_compliance.py`

**Implementation**:
```python
"""Handler compliance tests - verify handlers implement SPI exactly."""
import inspect
from typing import get_type_hints
import pytest

from omnibase_spi.protocols.handlers import ProtocolVectorStoreHandler
from omnibase_spi.protocols.handlers import ProtocolGraphDatabaseHandler
from omnibase_spi.protocols.handlers import ProtocolRelationalDatabaseHandler
from omnibase_spi.protocols.handlers import ProtocolEmbeddingHandler
from omnibase_spi.protocols.handlers import ProtocolKafkaProducerHandler


class TestHandlerCompliance:
    """Verify handlers implement all protocol methods."""

    @pytest.mark.parametrize("protocol,handler_class", [
        (ProtocolVectorStoreHandler, "QdrantVectorHandler"),
        (ProtocolGraphDatabaseHandler, "MemgraphGraphHandler"),
        (ProtocolRelationalDatabaseHandler, "AsyncpgDatabaseHandler"),
        (ProtocolEmbeddingHandler, "OpenAProtocolEmbeddingHandler"),
        (ProtocolKafkaProducerHandler, "KafkaProducerHandler"),
    ])
    def test_handler_implements_all_methods(self, protocol, handler_class):
        """Verify handler implements every protocol method."""
        protocol_methods = {
            name for name, _ in inspect.getmembers(protocol, predicate=inspect.isfunction)
            if not name.startswith("_")
        }
        handler_methods = {
            name for name, _ in inspect.getmembers(handler_class, predicate=inspect.isfunction)
            if not name.startswith("_")
        }

        missing = protocol_methods - handler_methods
        assert not missing, f"{handler_class} missing methods: {missing}"

    def test_handler_parameter_names_match_protocol(self):
        """Verify parameter names match SPI protocols."""
        ...

    def test_handler_return_types_match_protocol(self):
        """Verify return types are Pydantic models from SPI."""
        ...
```

**Acceptance Criteria**:
- [ ] Tests for all 5 handler types
- [ ] Verifies every method is implemented
- [ ] Verifies parameter names match
- [ ] Verifies return types match Pydantic models
- [ ] CI fails if handler doesn't comply with SPI

---

#### Issue 8.7: Create Runtime Host State Replay Tests

**Title**: Create state replay tests for runtime host
**Type**: Task
**Priority**: Medium
**Labels**: `testing`, `runtime`, `integration`
**Milestone**: **Beta**

> **Deferred Rationale**: State replay tests require stable envelope schemas and finalized orchestrator behavior. These tests are meaningful only after the core envelope routing and orchestrator patterns are locked down in MVP.

**Description**:
Create tests that replay recorded envelope sequences to verify correct orchestrator/reducer behavior.

**Location**: `tests/integration/test_state_replay.py`

**Implementation**:
```python
"""State replay tests for runtime host."""
import pytest
from pathlib import Path
import json


class TestStateReplay:
    """Test envelope replay for idempotency and correctness."""

    @pytest.fixture
    def recorded_envelopes(self) -> list[dict]:
        """Load recorded envelope sequence."""
        with open(Path("tests/fixtures/envelope_sequence.json")) as f:
            return json.load(f)

    def test_orchestrator_handles_replay_idempotently(self, recorded_envelopes):
        """Orchestrators should handle replayed envelopes idempotently."""
        # Replay envelopes in order
        # Verify same output each time
        # Verify no duplicate side effects
        ...

    def test_reducer_applies_fsm_transitions_correctly(self, recorded_envelopes):
        """Reducer should apply correct FSM transitions on replay."""
        # Replay state-changing envelopes
        # Verify FSM reaches correct final state
        # Verify invalid transitions are rejected
        ...

    def test_replay_with_out_of_order_envelopes(self):
        """Handle out-of-order envelope delivery gracefully."""
        ...
```

**Acceptance Criteria**:
- [ ] Recorded envelope fixtures created
- [ ] Orchestrator idempotency tested
- [ ] Reducer FSM transitions tested
- [ ] Out-of-order handling tested
- [ ] Replay produces deterministic results

---

#### Issue 8.8: Create Stress & Chaos Tests for Effect Nodes

**Title**: Create stress and chaos tests for effect nodes
**Type**: Task
**Priority**: Medium
**Labels**: `testing`, `chaos`, `effect`
**Milestone**: **GA**

**Description**:
Create stress and chaos tests to verify effect node resilience under failure conditions.

**Location**: `tests/chaos/`

**Test Scenarios**:
```python
"""Chaos tests for effect nodes."""
import pytest
from unittest.mock import AsyncMock


class TestEffectNodeChaos:
    """Chaos tests for effect node resilience."""

    @pytest.mark.chaos
    async def test_handler_timeout(self, mock_vector_handler):
        """Effect node handles handler timeout gracefully."""
        mock_vector_handler.upsert = AsyncMock(side_effect=asyncio.TimeoutError())

        node = NodeQdrantVectorEffect(config, mock_vector_handler)
        result = await node.execute(input_data)

        assert result.status == "error"
        assert "timeout" in result.error.lower()

    @pytest.mark.chaos
    async def test_handler_slowdown(self, mock_vector_handler):
        """Effect node handles slow handler responses."""
        async def slow_response(*args, **kwargs):
            await asyncio.sleep(5)  # 5 second delay
            return Result(success=True)

        mock_vector_handler.upsert = slow_response
        # Test with configurable timeout
        ...

    @pytest.mark.chaos
    async def test_handler_unavailable(self, mock_vector_handler):
        """Effect node handles handler unavailability."""
        mock_vector_handler.upsert = AsyncMock(
            side_effect=ConnectionError("Handler unavailable")
        )
        # Verify graceful degradation
        ...

    @pytest.mark.chaos
    async def test_partial_failure(self, mock_vector_handler):
        """Effect node handles partial success scenarios."""
        mock_vector_handler.upsert = AsyncMock(
            return_value=Result(success=False, partial=True, succeeded=5, failed=2)
        )
        # Verify partial results handled
        ...
```

**Acceptance Criteria**:
- [ ] Handler timeout tests
- [ ] Handler slowdown tests
- [ ] Handler unavailable tests
- [ ] Partial failure tests
- [ ] Circuit breaker behavior verified
- [ ] Retry logic verified
- [ ] pytest marker: `@pytest.mark.chaos`

---

#### Issue 8.9: Create Node Runtime Compliance Checklist

**Title**: Create node runtime compliance checklist for validation
**Type**: Documentation
**Priority**: High
**Labels**: `documentation`, `compliance`, `checklist`
**Milestone**: **MVP**

**Description**:
Create a compliance checklist that must be completed for each node before the implementation is considered done.

**Location**: `docs/NODE_RUNTIME_COMPLIANCE_CHECKLIST.md`

**Content**:
```markdown
# Node Runtime Compliance Checklist

Every node must pass this checklist before implementation is complete.

## Checklist

For each of the 17 nodes, verify:

| # | Requirement | Verification Method |
|---|-------------|---------------------|
| 1 | No direct I/O imports | `grep -r "confluent_kafka\|qdrant_client\|neo4j\|asyncpg\|httpx" <node_path>` returns empty |
| 2 | Contract validated | Contract linter passes (Issue 1.1) |
| 3 | Uses injected handlers only | Code review: all I/O via `self._*_handler` |
| 4 | Envelope shape correct | Envelope audit test passes (Issue 1.2) |
| 5 | Logging uses unified logger | Uses `omnibase_core.logging`, not `print()` or bare `logging` |
| 6 | Unit tests ≥ 80% coverage | Coverage report shows ≥80% for node directory |
| 7 | Has runtime profile entry | Listed in IntelligenceNodeRegistry |
| 8 | Contract version updated | Version matches version table (Issue 2.6) |
| 9 | Documented in registry | Export present in nodes/__init__.py |

## Node Compliance Status

| Node | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | Status |
|------|---|---|---|---|---|---|---|---|---|--------|
| vectorization_compute | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Pending |
| quality_scoring_compute | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Pending |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

Legend: ✅ Pass | ❌ Fail | ⬜ Not checked
```

**Acceptance Criteria**:
- [ ] Checklist document created
- [ ] All 9 requirements documented
- [ ] Verification method for each requirement
- [ ] Status table for all 17 nodes
- [ ] Checklist reviewed before Phase 9 begins

---

#### Issue 8.10: Create Performance Regression Tests

**Title**: Create automated performance regression tests
**Type**: Task
**Priority**: High
**Labels**: `testing`, `performance`, `regression`
**Milestone**: **GA**

> **Note**: Performance regression tests should be marked with `@pytest.mark.xfail` until routing and infrastructure are stable (post-Beta). Hard limits are only enforced at GA. During MVP/Beta, these tests provide informational metrics only.

**Description**:
Create automated tests that enforce the performance regression budget defined in the document header.

**Location**: `tests/performance/test_performance_regression.py`

**Implementation**:
```python
"""Performance regression tests - enforce budget limits."""
import pytest
import psutil
import time
import asyncio

# Performance budget from document
MAX_LATENCY_MS = 500
MAX_MEMORY_MB = 400
MAX_IDLE_CPU_PERCENT = 15


class TestPerformanceRegression:
    """Enforce performance regression budget."""

    @pytest.mark.performance
    async def test_message_latency_under_budget(self, runtime_host):
        """Message latency must be under 500ms p99."""
        latencies = []

        for _ in range(100):
            start = time.perf_counter()
            await runtime_host.process_envelope(test_envelope)
            latencies.append((time.perf_counter() - start) * 1000)

        p99 = sorted(latencies)[99]
        assert p99 < MAX_LATENCY_MS, f"p99 latency {p99}ms exceeds budget {MAX_LATENCY_MS}ms"

    @pytest.mark.performance
    def test_memory_under_budget(self, running_runtime_host):
        """Memory usage must be under 400MB."""
        process = psutil.Process(running_runtime_host.pid)
        memory_mb = process.memory_info().rss / 1024 / 1024

        assert memory_mb < MAX_MEMORY_MB, f"Memory {memory_mb}MB exceeds budget {MAX_MEMORY_MB}MB"

    @pytest.mark.performance
    def test_idle_cpu_under_budget(self, running_runtime_host):
        """Idle CPU must be under 15%."""
        process = psutil.Process(running_runtime_host.pid)
        cpu_percent = process.cpu_percent(interval=5)  # 5 second sample

        assert cpu_percent < MAX_IDLE_CPU_PERCENT, f"Idle CPU {cpu_percent}% exceeds budget {MAX_IDLE_CPU_PERCENT}%"
```

**Acceptance Criteria**:
- [ ] Latency test (p99 < 500ms)
- [ ] Memory test (< 400MB)
- [ ] Idle CPU test (< 15%)
- [ ] Tests run in CI
- [ ] Tests marked `@pytest.mark.xfail` until GA
- [ ] Budget violations fail the build (GA only - informational during MVP/Beta)
- [ ] Results logged for trending

---

#### Issue 8.11: Define Unified Error Taxonomy for Runtime Host

**Title**: Define unified error taxonomy for runtime host
**Type**: Feature
**Priority**: Medium
**Labels**: `architecture`, `errors`, `runtime`
**Milestone**: **Beta**

**Description**:
Runtime host errors are currently free-form strings with inconsistent structure. Define a unified error taxonomy that provides machine-readable error codes with consistent categorization.

> **TODO**: Error taxonomy enum should ultimately live in `omnibase_core/errors/` for cross-project reuse. For Beta, can be defined in OmniIntelligence and migrated later.

**Error Categories**:

| Code | Category | Description |
|------|----------|-------------|
| `HANDLER_FAILURE` | Handler connection or operation failed | Handler unavailable, timeout, or returned error |
| `ENVELOPE_ROUTING_FAILURE` | Could not route envelope to node | Unknown node type, invalid envelope schema |
| `CONTRACT_MISMATCH` | Contract validation failed | Input/output schema mismatch, version incompatibility |
| `PROFILE_VIOLATION` | Node not in current profile | Node requested but not enabled in active profile |
| `DEPENDENCY_MISSING` | Required dependency not available | Handler or service dependency not injected |

**Error Model**:
```python
from enum import Enum
from pydantic import BaseModel
from typing import Any, Optional


class EnumRuntimeErrorCode(str, Enum):
    """Unified error codes for runtime host."""
    HANDLER_FAILURE = "HANDLER_FAILURE"
    ENVELOPE_ROUTING_FAILURE = "ENVELOPE_ROUTING_FAILURE"
    CONTRACT_MISMATCH = "CONTRACT_MISMATCH"
    PROFILE_VIOLATION = "PROFILE_VIOLATION"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"


class ModelRuntimeError(BaseModel):
    """Structured runtime error with machine-readable code."""
    code: EnumRuntimeErrorCode
    message: str
    context: Optional[dict[str, Any]] = None
    correlation_id: Optional[str] = None
    node_id: Optional[str] = None
    recoverable: bool = False
```

**Acceptance Criteria**:
- [ ] Error taxonomy enum defined with all 5 categories
- [ ] All runtime host errors use taxonomy
- [ ] Error includes code, message, and context
- [ ] Errors are machine-readable (JSON serializable)
- [ ] Documentation for each error code
- [ ] TODO marker for move to omnibase_core

---

#### Issue 8.12: Define Optional Handler Behavior Semantics

**Title**: Define optional handler behavior semantics
**Type**: Documentation
**Priority**: Medium
**Labels**: `documentation`, `handlers`, `semantics`
**Milestone**: **Beta**

**Description**:
Define what "optional" means for handlers in the runtime host. When a handler is marked optional but unavailable, the system needs clear semantics for how to proceed.

**Behavior Semantics**:

| Semantic | Description | Use Case |
|----------|-------------|----------|
| `skip_silently` | Operation skipped, no log entry | Telemetry handlers, non-critical enrichment |
| `warn_and_skip` | Log warning, skip operation | Optional caching, secondary storage |
| `degrade` | Mark node as degraded, continue execution | Partial functionality acceptable |
| `error` | Fail the operation | Handler is required despite optional flag |

**Default Behavior**: `warn_and_skip`

**Contract Configuration**:
```yaml
# In node contract YAML
handlers:
  embedding:
    protocol: ProtocolEmbeddingHandler
    required: true
  vector_store:
    protocol: ProtocolVectorStoreHandler
    required: false
    on_missing: warn_and_skip  # Optional: skip_silently | warn_and_skip | degrade | error
  telemetry:
    protocol: ProtocolTelemetryHandler
    required: false
    on_missing: skip_silently
```

**Runtime Behavior**:
```python
class HandlerMissingBehavior(str, Enum):
    """Behavior when optional handler is missing."""
    SKIP_SILENTLY = "skip_silently"
    WARN_AND_SKIP = "warn_and_skip"
    DEGRADE = "degrade"
    ERROR = "error"
```

**Acceptance Criteria**:
- [ ] All 4 behavior semantics documented
- [ ] Default behavior defined (`warn_and_skip`)
- [ ] Per-handler configuration supported in contracts
- [ ] Runtime host implements all behavior modes
- [ ] Degraded node state properly tracked
- [ ] Examples in contract documentation

---

#### Issue 8.13: Add Protocol Lockfile Snapshot Tests

**Title**: Add protocol lockfile snapshot tests
**Type**: Task
**Priority**: Medium
**Labels**: `testing`, `protocols`, `compatibility`
**Milestone**: **Beta**

**Description**:
Ensure SPI handler interfaces don't change unexpectedly by implementing protocol snapshot tests. These tests capture the current interface signatures and fail if they change without explicit approval.

**Implementation**:

**Location**: `tests/unit/protocols/test_protocol_snapshots.py`

```python
"""Protocol lockfile snapshot tests.

These tests ensure SPI handler interfaces don't change unexpectedly.
If a test fails, either:
1. The change was unintentional - revert it
2. The change was intentional - update the snapshot and document the breaking change
"""
import inspect
from typing import get_type_hints
import pytest

from omnibase_spi.protocols.handlers import ProtocolVectorStoreHandler
from omnibase_spi.protocols.handlers import ProtocolGraphDatabaseHandler
from omnibase_spi.protocols.handlers import ProtocolRelationalDatabaseHandler
from omnibase_spi.protocols.handlers import ProtocolEmbeddingHandler
from omnibase_spi.protocols.handlers import ProtocolKafkaProducerHandler


def get_protocol_signature(protocol_class) -> dict:
    """Extract method signatures from protocol class."""
    methods = {}
    for name, method in inspect.getmembers(protocol_class, predicate=inspect.isfunction):
        if not name.startswith("_"):
            sig = inspect.signature(method)
            hints = get_type_hints(method)
            methods[name] = {
                "parameters": [p.name for p in sig.parameters.values()],
                "return_type": str(hints.get("return", "None")),
            }
    return methods


class TestProtocolSnapshots:
    """Snapshot tests for protocol stability."""

    @pytest.mark.parametrize("protocol,snapshot_file", [
        (ProtocolVectorStoreHandler, "vector_store_protocol.json"),
        (ProtocolGraphDatabaseHandler, "graph_database_protocol.json"),
        (ProtocolRelationalDatabaseHandler, "relational_database_protocol.json"),
        (ProtocolEmbeddingHandler, "embedding_protocol.json"),
        (ProtocolKafkaProducerHandler, "kafka_producer_protocol.json"),
    ])
    def test_protocol_matches_snapshot(self, protocol, snapshot_file, snapshot):
        """Protocol interface must match recorded snapshot."""
        current = get_protocol_signature(protocol)
        assert current == snapshot(name=snapshot_file)
```

**Snapshot Files Location**: `tests/fixtures/protocol_snapshots/`

**CI Integration**:
- Snapshots committed to version control
- CI fails on unexpected protocol changes
- Snapshot update requires explicit approval (PR review)

**Acceptance Criteria**:
- [ ] Protocol snapshot tests for all 5 handler types
- [ ] Snapshot files generated and committed
- [ ] CI fails on unexpected protocol changes
- [ ] Documentation for updating snapshots
- [ ] Protocol stability enforced by default
- [ ] Breaking change process documented

---

## Phase 9: Cleanup

**Priority**: LOW
**Dependencies**: Phase 8 validated, 2 weeks production validation

### Epic: Remove Deprecated Code

#### Issue 9.1: Remove per-node Dockerfiles

**Title**: Delete per-node Docker files
**Type**: Task
**Priority**: Low
**Labels**: `cleanup`, `docker`

**Description**:
After production validation, delete Docker files from `deployment/docker/archived/`.

**Files to Delete**:
- `deployment/docker/archived/` (entire directory)

**Acceptance Criteria**:
- [ ] 2 weeks of production validation complete
- [ ] No issues reported with new architecture
- [ ] Legacy directory deleted
- [ ] CI/CD fully migrated to new files

---

#### Issue 9.2: Remove any remaining direct I/O code

**Title**: Final audit and removal of any remaining I/O code
**Type**: Task
**Priority**: Low
**Labels**: `cleanup`, `audit`

**Description**:
Final audit to remove any remaining direct I/O code that may have been missed.

**Acceptance Criteria**:
- [ ] `grep -r "confluent_kafka" src/omniintelligence/nodes/` returns empty
- [ ] `grep -r "qdrant_client" src/omniintelligence/nodes/` returns empty
- [ ] `grep -r "neo4j" src/omniintelligence/nodes/` returns empty
- [ ] `grep -r "asyncpg" src/omniintelligence/nodes/` returns empty
- [ ] `grep -r "httpx" src/omniintelligence/nodes/` returns empty
- [ ] All I/O audit tests pass

---

#### Issue 9.3: Update documentation for v0.5.0

**Title**: Update all documentation for v0.5.0 release
**Type**: Documentation
**Priority**: Low
**Labels**: `documentation`

**Description**:
Update all documentation to reflect the new Runtime Host architecture.

**Files to Update**:
- `CLAUDE.md` - Update node execution model
- `README.md` - Update deployment instructions
- `docs/MVP_PLAN.md` - Mark runtime host implementation complete
- `docs/RUNTIME_HOST_REFACTORING_PLAN.md` - Mark all phases complete

**Acceptance Criteria**:
- [ ] All documentation reflects new architecture
- [ ] Deployment instructions use new Docker configuration
- [ ] Upgrade guide added for consumers
- [ ] Version changelog updated

---

## Issue Creation Guidelines

When creating these issues in Linear:

1. **Team**: Omninode
2. **Project**: MVP - OmniIntelligence Runtime Host
3. **Labels**: Apply as indicated
4. **Priority**:
   - 1 = Urgent (Issue 4.5 - Remove Kafka consumer)
   - 2 = High (Phases 3-6)
   - 3 = Normal (Phases 7-8)
   - 4 = Low (Phase 9)
5. **Dependencies**: Link related issues and external blockers

---

## Execution Order

```
Phase 1 (Tooling & Validators) ←─── Can start immediately
    |
    v
BLOCKED: External Dependencies (omnibase_core, omnibase_spi, omnibase_infra)
    |
    v (when unblocked)
Phase 2 (Contract Reconciliation)
    |
    ├─────────────────────────┐
    v                         v
Phase 3 (Compute Nodes)   Phase 4 (Effect Nodes)  [parallel]
    |                         |
    └──────────┬──────────────┘
               v
Phase 5 (Orchestrator/Reducer)
    |
    v
Phase 6 (Runtime Host Integration)
    |
    v
Phase 7 (Docker Consolidation)
    |
    v
Phase 8 (Testing & Validation)
    |
    v
v0.5.0 Release
    |
    v (after 2 weeks validation)
Phase 9 (Legacy Cleanup)
```

---

## Success Criteria Summary

| Metric | Current | Target | Issue |
|--------|---------|--------|-------|
| Container count | 10+ | ≤3 | 7.2 |
| Memory footprint | ~1.5GB | ≤400MB | 8.4, 8.10 |
| Message latency (p99) | TBD | ≤500ms | 8.10 |
| Idle CPU | TBD | ≤15% | 8.10 |
| Test coverage | TBD | ≥80% | 8.5 |
| Zero I/O in nodes | No | Yes | 8.3 |
| No forbidden imports | No | Yes | 8.3 |
| No Kafka consumer in nodes | No | Yes | 4.5 |
| All contracts validated | No | Yes | 1.1, 2.1 |
| Dependency graph acyclic | TBD | Yes | 1.3 |
| Envelope shape consistent | TBD | Yes | 1.2 |
| Handler compliance | TBD | 100% | 8.6 |
| Node compliance checklist | 0/17 | 17/17 | 8.9 |

---

## Issue Index by Type

### Tooling Issues
- 1.1: Contract Linter CLI
- 1.2: Envelope Shape Audit
- 1.3: Dependency Graph Validator
- 1.4: Contract Coverage Report
- 1.5: Topic Naming Validator
- 1.6: Handler Binding Map Generator
- 1.7: Dry Run Mode
- 1.8: Workflow Simulation CLI

### Contract Issues
- 2.1-2.4: Contract upgrades
- 2.5: Contract test fixtures
- 2.6: Versioning strategy docs

### Node Refactoring Issues
- 3.1-3.4: Compute nodes
- 4.1-4.7: Effect nodes
- 5.1-5.4: Orchestrator/Reducer

### Runtime Integration Issues
- 6.1-6.5: Core runtime wiring
- 6.6: Health & Lifecycle
- 6.7: Local-dev profile
- 6.8: Boot diagram docs

### Docker Issues
- 7.1-7.4: Container consolidation
- 7.5: Profile compatibility matrix

### Testing Issues
- 8.1-8.5: Core testing
- 8.6: Handler compliance
- 8.7: State replay
- 8.8: Chaos testing
- 8.9: Compliance checklist
- 8.10: Performance regression

### Cleanup Issues
- 9.1-9.3: Legacy removal

---

**Last Updated**: 2025-12-03
**Document Owner**: OmniNode Architecture Team
**Linear Project URL**: TBD
