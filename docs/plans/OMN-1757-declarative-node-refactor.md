# OMN-1757: Refactor omniintelligence Nodes to Declarative Pattern

## Executive Summary

Refactor all omniintelligence nodes to follow the **fully declarative pattern** used in omnibase_infra, where nodes are thin shells with **ZERO implementation methods**. All behavior is driven by `contract.yaml` and wired by `RuntimeHostProcess`.

## Key Insight from Research

In omnibase_infra, nodes do NOT have `execute()`, `compute()`, or `process()` methods. The base classes (`NodeEffect`, `NodeCompute`, `NodeReducer`) handle dispatching to handlers based on contract configuration.

### Pattern Comparison

| Aspect | Current (Imperative) | Target (Declarative) |
|--------|---------------------|---------------------|
| Node body | Has execute/compute/process methods | Empty (0 methods) |
| Handler import | Imports handler in node.py | None in node.py |
| Handler call | Direct method call in node | Via contract routing |
| Node lines | ~40-307 lines | ~20-50 lines |
| Dependencies | In `__init__()` or setters | In contract.yaml `dependencies` |

---

## Reference Patterns (from omnibase_infra)

### COMPUTE Node Pattern

```python
# src/omnibase_infra/nodes/node_ledger_projection_compute/node.py (~48 lines)
from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute


class NodeLedgerProjectionCompute(NodeCompute):
    """Declarative COMPUTE node for ledger projection.

    All behavior is defined in contract.yaml and delegated to
    HandlerLedgerProjection. This node contains no custom logic.
    """
    # Declarative node - all behavior defined in contract.yaml


__all__ = ["NodeLedgerProjectionCompute"]
```

### EFFECT Node Pattern

```python
# src/omnibase_infra/nodes/node_slack_alerter_effect/node.py (~106 lines)
from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodeSlackAlerterEffect(NodeEffect):
    """Declarative effect node for Slack webhook alerting.

    This effect node is a lightweight shell that defines the I/O contract
    for Slack alert operations. All routing and execution logic is driven
    by contract.yaml - this class contains NO custom routing code.
    """
    # Pure declarative shell - all behavior defined in contract.yaml


__all__ = ["NodeSlackAlerterEffect"]
```

### REDUCER Node Pattern

```python
# src/omnibase_infra/nodes/contract_registry_reducer/node.py (~121 lines)
from __future__ import annotations

from omnibase_core.nodes.node_reducer import NodeReducer


class NodeContractRegistryReducer(NodeReducer):
    """Contract registry reducer - FSM state transitions driven by contract.yaml.

    This is a purely declarative reducer. All behavior is defined in contract.yaml.
    No custom Python logic is required - the base NodeReducer class handles all
    FSM-driven state transitions via the contract configuration.
    """


__all__ = ["NodeContractRegistryReducer"]
```

---

## Nodes Requiring Migration

### Phase 1: Compute Nodes (8 nodes)

| Node | Current Lines | Has compute() | Priority |
|------|---------------|---------------|----------|
| `node_quality_scoring_compute` | 42 | Yes | High |
| `node_semantic_analysis_compute` | 56 | Yes | High |
| `node_pattern_extraction_compute` | 49 | Yes | High |
| `node_intent_classifier_compute` | ~60 | Yes | High |
| `node_pattern_learning_compute` | ~80 | Yes | Medium |
| `node_pattern_matching_compute` | ~50 | Yes (stub) | Low |
| `node_execution_trace_parser_compute` | ~50 | Yes (stub) | Low |
| `node_success_criteria_matcher_compute` | ~50 | Yes (stub) | Low |

### Phase 2: Effect Nodes (6 nodes)

| Node | Current Lines | Has execute() | Priority |
|------|---------------|---------------|----------|
| `node_pattern_storage_effect` | **307** | Yes + setters + properties | **Critical** |
| `node_claude_hook_event_effect` | ~72 | Yes | High |
| `node_pattern_promotion_effect` | ~99 | Yes | Medium |
| `node_pattern_demotion_effect` | ~80 | Yes | Medium |
| `node_pattern_feedback_effect` | ~70 | Yes | Medium |
| `node_pattern_lifecycle_effect` | ~81 | Yes | Medium |

### Phase 3: Reducer Nodes (1 node)

| Node | Current Lines | Has process() | Priority |
|------|---------------|---------------|----------|
| `node_intelligence_reducer` | ~100 | Yes | High |

### Phase 4: Orchestrator Nodes (2 nodes)

| Node | Current Lines | Has orchestrate() | Priority |
|------|---------------|-------------------|----------|
| `node_intelligence_orchestrator` | ~48 | Minimal | Low |
| `node_pattern_assembler_orchestrator` | ~50 | Yes (stub) | Low |

---

## Migration Steps Per Node

### For COMPUTE Nodes:

1. **Remove `compute()` method** from node.py
2. **Remove handler imports** from node.py
3. **Add handler_routing to contract.yaml**:
   ```yaml
   handler_routing:
     routing_strategy: "operation_match"
     handlers:
       - operation: "score_quality"
         handler:
           name: "handle_quality_scoring_compute"
           module: "omniintelligence.nodes.node_quality_scoring_compute.handlers"
         input_model:
           name: "ModelQualityScoringInput"
           module: "omniintelligence.nodes.node_quality_scoring_compute.models"
   ```
4. **Add declarative comment** to node body
5. **Verify handler has correct signature** for contract-driven dispatch

### For EFFECT Nodes:

1. **Remove `execute()` method** from node.py
2. **Remove `__init__()` override** (unless truly needed for non-DI reasons)
3. **Remove setter methods** (`set_pattern_store()`, etc.)
4. **Remove property accessors**
5. **Add handler_routing to contract.yaml**
6. **Move dependencies to contract.yaml `dependencies` section**
7. **Verify RuntimeHostProcess can resolve dependencies**

### For REDUCER Nodes:

1. **Remove `process()` method** from node.py
2. **Ensure `state_machine` section in contract.yaml is complete**
3. **Verify FSM transitions work via base class**

---

## Contract YAML Updates

Each node's contract.yaml needs a `handler_routing` section. Example for effect node:

```yaml
# =============================================================================
# HANDLER ROUTING (Declarative Handler Dispatch)
# =============================================================================
handler_routing:
  routing_strategy: "operation_match"
  handlers:
    - operation: "store_pattern"
      handler:
        name: "handle_store_pattern"
        module: "omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_store_pattern"
        type: "async"
      description: "Store a learned pattern with governance validation"
      input_model:
        name: "ModelPatternStorageInput"
        module: "omniintelligence.nodes.node_pattern_storage_effect.models"
    - operation: "check_exists"
      handler:
        name: "handle_check_pattern_exists"
        module: "omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_check_exists"
        type: "async"
      description: "Check if pattern with signature already exists"
  execution_mode: "sequential"
  aggregation_strategy: "first_match"
```

---

## Test Updates

### Remove from purity_exempt_nodes

After refactoring, remove nodes from the exemption list in `tests/unit/test_node_purity.py`:

```python
# BEFORE: All these nodes are exempted
purity_exempt_nodes = {
    "node_pattern_storage_effect",
    "node_pattern_demotion_effect",
    "node_pattern_feedback_effect",
    "node_pattern_promotion_effect",
    "node_pattern_lifecycle_effect",
    "node_claude_hook_event_effect",
    "node_quality_scoring_compute",
    "node_semantic_analysis_compute",
    "node_intent_classifier_compute",
    "node_pattern_extraction_compute",
    "node_intelligence_reducer",
}

# AFTER: Empty set - all nodes pass purity checks
purity_exempt_nodes = set()
```

### Update purity checker

The purity checker may need updates to recognize that nodes with NO methods (only docstring) are valid.

---

## Execution Order

### Wave 1: Quick Wins (Compute nodes already thin)
1. `node_quality_scoring_compute` - Remove compute(), add handler_routing
2. `node_semantic_analysis_compute` - Remove compute(), add handler_routing
3. `node_pattern_extraction_compute` - Remove compute(), add handler_routing
4. `node_intent_classifier_compute` - Remove compute(), add handler_routing

### Wave 2: Effect Nodes (Medium complexity)
5. `node_pattern_promotion_effect` - Remove execute(), already has registry
6. `node_pattern_lifecycle_effect` - Remove execute(), already has registry
7. `node_pattern_demotion_effect` - Remove execute()
8. `node_pattern_feedback_effect` - Remove execute()
9. `node_claude_hook_event_effect` - Remove execute(), remove handler injection

### Wave 3: Complex Refactor
10. `node_pattern_storage_effect` - **Major refactor**: Remove 307 lines → ~30 lines

### Wave 4: Reducer/Orchestrator
11. `node_intelligence_reducer` - Remove process(), verify FSM works
12. `node_intelligence_orchestrator` - Verify declarative
13. `node_pattern_assembler_orchestrator` - Stub, verify pattern

### Wave 5: Cleanup
14. Remove all nodes from `purity_exempt_nodes`
15. Run `pytest tests/unit/test_node_purity.py` - all should pass
16. Run full test suite

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| RuntimeHostProcess may not support all routing strategies | High | Verify handler routing works before mass refactor |
| Base class `process()`/`compute()` may not call handlers correctly | High | Test one node end-to-end first |
| Handler signatures may need changes | Medium | Document required signature pattern |
| Tests may break due to different execution flow | Medium | Update test fixtures for contract-driven dispatch |

---

## Validation Checklist

After refactoring each node:

- [ ] node.py is <50 lines
- [ ] node.py has NO methods (except optional `__init__` with only `super().__init__()`)
- [ ] contract.yaml has `handler_routing` section
- [ ] Handler is importable from specified module
- [ ] `pytest tests/unit/test_node_purity.py` passes for this node
- [ ] Node's own unit tests pass
- [ ] Integration test passes (if applicable)

---

## Definition of Done (from OMN-1757)

- [ ] `node_quality_scoring_compute` - Declarative (no compute method)
- [ ] `node_semantic_analysis_compute` - Declarative (no compute method)
- [ ] `node_pattern_extraction_compute` - Declarative (no compute method)
- [ ] `node_pattern_storage_effect` - Declarative (no execute, setters, properties)
- [ ] All 20+ violations resolved
- [ ] `purity_exempt_nodes` set is empty
- [ ] `uv run pytest tests/unit/test_node_purity.py` passes
- [ ] Unit tests updated/passing
