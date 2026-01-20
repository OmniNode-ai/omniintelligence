# Node State Policy

**Purpose**: Define node implementation states, enforcement mechanisms, and orchestrator dependency rules
**Audience**: Contributors, AI agents, infrastructure engineers
**Last Updated**: 2026-01-20

---

## Overview

OmniIntelligence nodes follow a progressive implementation model with three distinct states. This policy defines what each state means, how compliance is enforced, and what guarantees orchestrators can depend on.

---

## Node States

### 1. Implemented

**Definition**: A fully functional node with business logic delegated to handler modules.

**Characteristics**:
- Has `handlers/` directory containing operation-specific handler modules
- Pure shell `node.py` that delegates to handlers via contract routing
- Contract defines `handler_routing` section mapping operations to handlers
- All handler modules follow `handler_{operation}.py` naming convention
- Zero business logic in `node.py` itself

**Example Structure**:
```
nodes/my_node/
    __init__.py
    node.py                      # Pure shell (~50 lines)
    contract.yaml                # Includes handler_routing section
    models.py                    # Input/output models
    handlers/
        __init__.py
        handler_operation_a.py   # Handler for operation A
        handler_operation_b.py   # Handler for operation B
```

**Contract Pattern**:
```yaml
handler_routing:
  operation_a:
    handler_module: "handlers.handler_operation_a"
    handler_class: "HandlerOperationA"
  operation_b:
    handler_module: "handlers.handler_operation_b"
    handler_class: "HandlerOperationB"
```

**Guarantees**:
- Full functionality available
- Testable in isolation via handler unit tests
- Contract-driven operation routing
- Suitable for production orchestrator dependencies

---

### 2. Shell

**Definition**: A pure delegating node with no embedded business logic, awaiting handler implementation.

**Characteristics**:
- Pure shell `node.py` that extends base class with zero custom methods
- No business logic - relies entirely on base class + contract
- May have empty `handlers/` directory (prepared for handler extraction)
- Contract fully defines operations, inputs, outputs
- Does NOT have `is_stub: ClassVar[bool] = True`

**Example Structure**:
```
nodes/my_shell_node/
    __init__.py
    node.py                      # Pure shell (~30-50 lines)
    contract.yaml                # Full operation definitions
    models.py                    # Input/output models (optional)
    handlers/                    # May be empty or absent
```

**Example node.py**:
```python
"""Example Compute - Pure compute node following ONEX declarative pattern.

This node follows the ONEX declarative pattern:
    - DECLARATIVE compute driven by contract.yaml
    - Pure function: input -> output, no side effects
    - Lightweight shell that delegates to NodeCompute base class
"""
from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute


class NodeExampleCompute(NodeCompute):
    """Pure compute node - all operation logic driven by contract.yaml."""

    # No custom __init__ needed - uses base class default initialization


__all__ = ["NodeExampleCompute"]
```

**Guarantees**:
- Stable interface defined by contract
- Safe to instantiate and include in workflows
- Base class provides default behavior
- Ready for handler extraction when business logic is implemented

---

### 3. Stub

**Definition**: A placeholder node that emits warnings and returns empty results.

**Characteristics**:
- Has `is_stub: ClassVar[bool] = True` class attribute
- Emits `RuntimeWarning` on instantiation or operation calls
- Returns empty/placeholder results with tracking URL
- Comment header: `# STUB: This node is a stub implementation...`
- Includes `_STUB_TRACKING_URL` constant linking to implementation issue

**Example Structure**:
```
nodes/my_stub_node/
    __init__.py
    node.py                      # Stub with warnings (~70-100 lines)
    contract.yaml                # Interface definition
    models.py                    # Output models for typed stubs
```

**Required Stub Pattern**:
```python
# STUB: This node is a stub implementation. Full functionality is not yet available.
# Tracking: https://github.com/OmniNode-ai/omniintelligence/issues/XX
# Status: Interface defined, implementation pending
"""Node Description - STUB implementation."""
from __future__ import annotations

import warnings
from typing import ClassVar

from omnibase_core.nodes.node_compute import NodeCompute

_STUB_TRACKING_URL = "https://github.com/OmniNode-ai/omniintelligence/issues/XX"


class NodeExampleCompute(NodeCompute):
    """STUB: Description of expected functionality.

    Attributes:
        is_stub: Class attribute indicating this is a stub implementation.

    WARNING: This is a stub implementation that does not provide full functionality.
    """

    is_stub: ClassVar[bool] = True

    async def compute(self, _input_data: dict) -> dict:
        """Compute operation (STUB - returns empty result)."""
        warnings.warn(
            f"NodeExampleCompute.compute() is a stub. See {_STUB_TRACKING_URL}",
            category=RuntimeWarning,
            stacklevel=2,
        )
        return {"status": "stub", "tracking_url": _STUB_TRACKING_URL}
```

**Guarantees**:
- Interface is defined and importable
- Will emit warnings if accidentally used
- Returns predictable empty results
- Traceable via issue tracking URL

---

## Enforcement Mechanisms

### 1. AST Purity Validator (I/O Audit)

**Purpose**: Enforce shell compliance by detecting I/O violations in pure nodes.

**Location**: `tests/audit/test_io_violations.py`

**Rules Enforced**:

| Rule ID | Description | Detection |
|---------|-------------|-----------|
| `net-client` | Forbidden network/DB client imports | `confluent_kafka`, `qdrant_client`, `neo4j`, `asyncpg`, `httpx`, `aiofiles` |
| `env-access` | Environment variable access | `os.environ`, `os.getenv`, `os.putenv` |
| `file-io` | File I/O operations | `open()`, `pathlib` I/O, `logging.FileHandler` |

**Shell Compliance**: Pure shell nodes MUST pass the I/O audit with zero violations. Effect nodes may whitelist specific violations via `io_audit_whitelist.yaml`.

**Running the Audit**:
```bash
pytest tests/audit/test_io_violations.py -v
```

### 2. Contract Validation

**Purpose**: Ensure contracts define required fields and valid structure.

**Location**: Contract linter (see `docs/CONTRACT_VALIDATION_GUIDE.md`)

**Stub Detection**:
- Contract may include `is_stub: true` field (mirrors class attribute)
- Linter warns if node.py has `is_stub` but contract does not declare it

**Required Contract Fields** (all node types):
```yaml
name: node_name
version:
  major: 1
  minor: 0
  patch: 0
node_type: compute|effect|reducer|orchestrator
```

### 3. Handler Directory Checks

**Purpose**: Verify implemented nodes have proper handler structure.

**Checks**:
- `handlers/` directory exists for implemented nodes
- Handler modules follow `handler_{operation}.py` naming
- Handler classes are importable
- Contract `handler_routing` references valid modules

**Future Automation**: CI check to verify handler routing consistency.

### 4. Stub Marker Detection

**Purpose**: Identify stub nodes programmatically.

**Detection Methods**:
```python
# Runtime check
if getattr(node_class, 'is_stub', False):
    print(f"{node_class.__name__} is a stub")

# AST check (for static analysis)
# grep -r "is_stub: ClassVar\[bool\] = True" src/
```

---

## Orchestrator Dependency Rules

### Production Graph Rules

| Rule | Enforcement |
|------|-------------|
| Orchestrators MUST NOT depend on stub nodes in production graphs | CI validation, runtime check |
| Orchestrators MAY reference stubs with graceful degradation | Must catch `RuntimeWarning`, handle empty results |
| All non-stub dependencies must be implemented or shell | Contract validation |
| Effect nodes in production must have whitelisted I/O only | I/O audit gate |

### Graceful Degradation Pattern

When an orchestrator may encounter stubs (e.g., during migration):

```python
import warnings

async def execute_workflow(self, operation: str) -> dict:
    """Execute workflow with stub-safe handling."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always", RuntimeWarning)

        result = await self._invoke_node(operation)

        # Check for stub warnings
        stub_warnings = [x for x in w if "stub" in str(x.message).lower()]
        if stub_warnings:
            self.logger.warning(
                f"Workflow {operation} invoked stub node(s). "
                f"Results may be incomplete."
            )
            return {"status": "degraded", "result": result}

    return {"status": "complete", "result": result}
```

### Dependency Declaration

Orchestrators should declare node dependencies in their contracts:

```yaml
# orchestrator_contract.yaml
workflow_coordination:
  document_ingestion:
    nodes:
      - node: vectorization_compute
        required: true
        stub_allowed: false
      - node: entity_extraction_compute
        required: false
        stub_allowed: true  # Graceful degradation
```

---

## Current Node Inventory

**Total Nodes**: 21

### Pure Shell Nodes (3)

| Node | Type | Status | Notes |
|------|------|--------|-------|
| `vectorization_compute` | Compute | Shell | Ready for handler extraction |
| `intelligence_orchestrator` | Orchestrator | Shell | Workflow routing via contract |
| `intelligence_reducer` | Reducer | Shell | FSM via contract |

### Stub Nodes (16)

| Node | Type | Tracking Issue | Notes |
|------|------|----------------|-------|
| `entity_extraction_compute` | Compute | [#4](https://github.com/OmniNode-ai/omniintelligence/issues/4) | Entity extraction from code |
| `context_keyword_extractor_compute` | Compute | - | Keyword extraction |
| `execution_trace_parser_compute` | Compute | - | Parse execution traces |
| `intent_classifier_compute` | Compute | - | Classify user intents |
| `pattern_learning_compute` | Compute | - | Pattern learning pipeline |
| `pattern_matching_compute` | Compute | - | Pattern matching |
| `quality_scoring_compute` | Compute | - | Code quality scoring |
| `relationship_detection_compute` | Compute | - | Relationship detection |
| `semantic_analysis_compute` | Compute | - | Semantic analysis |
| `success_criteria_matcher_compute` | Compute | - | Match success criteria |
| `ingestion_effect` | Effect | [#1](https://github.com/OmniNode-ai/omniintelligence/issues/1) | Document ingestion |
| `intelligence_api_effect` | Effect | - | Intelligence API calls |
| `memgraph_graph_effect` | Effect | - | Memgraph operations |
| `postgres_pattern_effect` | Effect | - | PostgreSQL pattern storage |
| `qdrant_vector_effect` | Effect | [#12](https://github.com/OmniNode-ai/omniintelligence/issues/12) | Qdrant vector operations |
| `pattern_assembler_orchestrator` | Orchestrator | - | Pattern assembly workflow |

### Needs Handler Extraction (1)

| Node | Type | Lines | Notes |
|------|------|-------|-------|
| `intelligence_adapter` | Effect | 2,205 | Large monolithic node, partial handler extraction started |

### Contract-Only (No node.py) (1)

| Node | Type | Notes |
|------|------|-------|
| `pattern_assembler_compute` | Compute | Has contract.yaml and models.py, no node implementation |

---

## State Transitions

### Stub -> Shell

1. Remove `is_stub: ClassVar[bool] = True`
2. Remove warning emissions from methods
3. Ensure pure delegation to base class
4. Remove `# STUB:` header comment
5. Pass I/O audit

### Shell -> Implemented

1. Create `handlers/` directory
2. Extract operation logic to handler modules
3. Add `handler_routing` to contract
4. Verify handler imports work
5. Add handler unit tests

### Monolith -> Implemented

For large nodes like `intelligence_adapter`:

1. Identify discrete operations in monolithic code
2. Create handler module per operation
3. Move business logic to handlers
4. Reduce node.py to pure shell
5. Update contract with handler routing
6. Pass I/O audit (node.py only)

---

## Validation Checklist

### For Shell Nodes

- [ ] `node.py` extends base class only
- [ ] No custom `__init__` beyond `super().__init__()`
- [ ] No method overrides with business logic
- [ ] Passes I/O audit with zero violations
- [ ] Contract defines all operations
- [ ] Does NOT have `is_stub` class attribute

### For Stub Nodes

- [ ] Has `is_stub: ClassVar[bool] = True`
- [ ] Header comment with `# STUB:`
- [ ] `_STUB_TRACKING_URL` constant defined
- [ ] Emits `RuntimeWarning` on operations
- [ ] Returns typed stub output with tracking URL
- [ ] Contract interface complete

### For Implemented Nodes

- [ ] `handlers/` directory exists
- [ ] Handler modules follow naming convention
- [ ] Contract includes `handler_routing`
- [ ] `node.py` is pure shell
- [ ] Handler unit tests exist
- [ ] Passes I/O audit

---

## References

- [I/O Audit Test](../tests/audit/test_io_violations.py) - Purity enforcement
- [Contract Validation Guide](./CONTRACT_VALIDATION_GUIDE.md) - Contract requirements
- [Declarative Effect Nodes Spec](./specs/DECLARATIVE_EFFECT_NODES_SPEC.md) - Architecture
- [Naming Conventions](./conventions/NAMING_CONVENTIONS.md) - File/class naming

---

**Version**: 1.0
**Maintained By**: OmniIntelligence Team
