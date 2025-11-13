# ONEX Node Group Structure - Final Consensus Design

**Version**: 2.0.0 (Final Consensus)
**Status**: ✅ Validated Against Production Canary Implementation
**Last Updated**: 2025-10-01
**Review**: See FINAL_DESIGN_REVIEW_ONEX_STRUCTURE.md

---

## Overview

A **Node Group** is a collection of related ONEX nodes that work together as a cohesive suite. This document describes the **FINAL CONSENSUS DESIGN** reconciling:
- ✅ Current working patterns (canary implementation)
- ✅ Future ideal state (migration targets)
- ✅ Hybrid/lazy/pragmatic approaches

**Reference Implementation**: `canary` group in omnibase_3

---

## Directory Structure (Consensus)

### Minimum Viable Structure

**USE THIS** for new nodes (works now, production-ready):

```
<node_group>/                           # e.g., "canary"
├── __init__.py                         # Group package initialization
├── README.md                           # Main documentation
│
├── deployment/                         # Deployment configs
│   ├── docker-compose.<group>.yml
│   └── *.env files
│
└── <node_name>/                        # e.g., "canary_impure_tool"
    ├── __init__.py
    └── v1_0_0/
        ├── __init__.py
        ├── node.py                     # ONLY node class + main()
        │
        ├── contract.yaml               # Main interface
        ├── node_config.yaml            # Runtime config
        ├── deployment_config.yaml      # Deployment config
        │
        ├── contracts/                  # YAML subcontracts
        │   ├── contract_actions.yaml
        │   ├── contract_cli.yaml
        │   ├── contract_examples.yaml
        │   └── contract_models.yaml
        │
        └── models/                     # Node-specific models
            ├── __init__.py
            ├── model_input_state.py
            └── model_output_state.py
```

### Maximum Recommended Structure

**EVOLVE TO THIS** as needs arise (best practices):

```
<node_group>/                           # e.g., "canary"
│
├── __init__.py
├── README.md
├── API_REFERENCE.md
├── compatibility.yaml                  # 🆕 Version compatibility matrix
│
├── shared/                             # 🆕 LAZY: Only when 2+ nodes share
│   ├── models/                         # Independent versioning
│   │   ├── v1/                         # Major version 1 (stable)
│   │   │   ├── __init__.py
│   │   │   └── model_*.py
│   │   └── v2/                         # Major version 2 (breaking changes)
│   │       ├── __init__.py
│   │       └── model_*.py
│   └── protocols/                      # Shared protocols (if needed)
│       ├── v1/
│       │   ├── __init__.py
│       │   └── protocol_*.py
│       └── v2/
│           ├── __init__.py
│           └── protocol_*.py
│
├── tests/                              # 🆕 Group-level integration tests
│   ├── integration/
│   │   └── test_node_interactions.py
│   └── fixtures/
│
├── deployment/
│   ├── docker-compose.<group>.yml
│   └── *.env files
│
└── <node_name>/                        # e.g., "canary_impure_tool"
    ├── __init__.py
    └── v1_0_0/
        ├── README.md                   # 🆕 Node documentation
        ├── CHANGELOG.md                # 🆕 Version history
        ├── node.py                     # ONLY node class + main()
        │
        ├── contract.yaml               # Main interface
        ├── node_config.yaml
        ├── deployment_config.yaml
        ├── state_transitions.yaml      # State machine (if needed)
        ├── workflow_testing.yaml       # Testing workflows (if needed)
        ├── security_config.yaml        # Security (Effect nodes only)
        │
        ├── contracts/                  # YAML subcontracts
        │   ├── contract_actions.yaml
        │   ├── contract_cli.yaml
        │   ├── contract_examples.yaml
        │   ├── contract_models.yaml
        │   └── contract_validation.yaml
        │
        ├── models/                     # Node-specific models
        │   ├── __init__.py
        │   ├── model_input_state.py
        │   ├── model_output_state.py
        │   └── enum_*.py
        │
        ├── protocols/                  # ⚠️ HYBRID: Node-specific protocols
        │   ├── __init__.py             # (or use omnibase_spi for shared)
        │   └── protocol_<node>.py
        │
        ├── tests/                      # 🆕 Node unit tests
        │   ├── unit/
        │   │   └── test_node.py
        │   └── fixtures/
        │
        └── mock_configurations/        # Testing mocks (optional)
            ├── event_bus_mock_behaviors.yaml
            ├── llm_mock_responses.yaml
            └── uuid_mock_behaviors.yaml
```

---

## Key Principles (Final Consensus)

### 1. Node Group = Collection of Siblings

✅ All nodes are siblings under the group
✅ No parent-child relationship between nodes
✅ Each node is independently versioned (v1_0_0, v2_0_0, etc.)
✅ Group provides documentation and deployment coordination

### 2. Shared Resources: LAZY PROMOTION with INDEPENDENT VERSIONING ⭐

**CONSENSUS**: Do NOT create `group/shared/` upfront. Use lazy promotion with independent versioning.

**Strategy**:
```
Phase 1 (initial):
node_1/v1_0_0/models/model_data.py    # Node-specific

Phase 2 (when 2nd node needs it):
group/shared/models/v1/model_data.py   # Promoted to shared v1

Phase 3 (breaking change needed):
group/shared/models/v1/model_data.py   # Stable version (frozen)
group/shared/models/v2/model_data.py   # New version (breaking changes)
node_1/v1_0_0/  # still uses v1
node_2/v2_0_0/  # uses v2

Phase 4 (when 2nd group needs it):
project/shared/models/v1/model_data.py # Promoted to project level
```

**Promotion Criteria** (ALL must be true):
1. ✅ Actually used by 2+ consumers (not "might be")
2. ✅ Same semantic meaning
3. ✅ Same version lifecycle
4. ✅ Detected by duplication analysis

**Versioning Strategy**:
- Use **major versions only** (v1, v2, v3) not semantic (v1_0_0)
- Non-breaking changes allowed within version
- Breaking changes require new major version
- Old versions remain until all nodes migrate
- See `SHARED_RESOURCE_VERSIONING.md` for complete details

**Anti-Pattern**: Creating `group/shared/` "just in case" → YAGNI violation

### 3. Protocols: HYBRID APPROACH ⭐

**CONSENSUS**: Both node-local AND omnibase_spi locations are valid.

**Decision Rule**:

| Protocol Scope | Location | Example |
|----------------|----------|---------|
| Node-specific, versions with node | `node/v1_0_0/protocols/` | `protocol_canary_impure.py` |
| Framework-wide, stable interface | `omnibase_spi/protocols/` | `ProtocolOnexNode` |
| Shared across 2+ groups | `omnibase_spi/protocols/` | `ProtocolFileSystem` |

**Example**:
```python
# Node-Local Protocol (node-specific)
from .protocols.protocol_canary_impure import ProtocolCanaryImpure

# omnibase_spi Protocol (framework-wide)
from omnibase_spi.protocols import ProtocolOnexNode
```

**Justification**:
- Node-local protocols version with node implementation
- Prevents breaking other nodes during experimentation
- Can promote to omnibase_spi when stable and shared

### 4. Node.py Purity - ONLY the Node Class ✅

**RULE**: `node.py` contains ONLY:
- ✅ One node class (Effect/Compute/Reducer/Orchestrator)
- ✅ main() function (one-liner)
- ✅ Class-level constants (if needed)
- ❌ NO other classes
- ❌ NO enums
- ❌ NO helper functions (use separate modules)

**Example**:
```python
#!/usr/bin/env python3
"""Canary Impure Tool - Node Implementation"""

from pathlib import Path
from omnibase.constants.contract_constants import CONTRACT_FILENAME
from omnibase.core.node_base import NodeBase
from omnibase.core.node_effect import NodeEffect
from omnibase_core.models.core import ModelOnexContainer

from .models.model_input_state import ModelCanaryImpureInputState
from .models.model_output_state import ModelCanaryImpureOutputState
from .protocols.protocol_canary_impure import ProtocolCanaryImpure


class ToolCanaryImpureProcessor(NodeEffect, ProtocolCanaryImpure):
    """Node implementation - business logic only."""

    def __init__(self, container: ModelOnexContainer) -> None:
        super().__init__(container)
        # Business logic initialization only

    def process(self, input_state: ModelCanaryImpureInputState) -> ModelCanaryImpureOutputState:
        """Main processing method."""
        # Implementation
        pass


def main():
    """One-line main function - NodeBase handles everything."""
    return NodeBase(Path(__file__).parent / CONTRACT_FILENAME)


if __name__ == "__main__":
    main()
```

### 5. Container Type: ModelOnexContainer ✅

**DECISION**: Use ModelOnexContainer ONLY. No technical debt.

**Correct Pattern** (use this):
```python
from omnibase_core.models.core import ModelOnexContainer

class MyNode(NodeEffect):
    """Node implementation using proper container type."""

    def __init__(self, container: ModelOnexContainer) -> None:
        super().__init__(container)
```

**Why ModelOnexContainer**:
- ✅ Proper Pydantic model-based container
- ✅ Strong typing and validation
- ✅ No legacy code patterns
- ✅ Future-proof design

**Note**: ModelOnexContainer will be unarchived in omnibase_core in next PR.

**Anti-Pattern** (DO NOT USE):
```python
# ❌ WRONG - Legacy container (technical debt)
from omnibase.core.onex_container import ONEXContainer
```

### 6. contracts/ Contains YAML, Not Python ✅

✅ YAML specifications for actions, CLI, examples
✅ Python contract models imported from omnibase_core
✅ Separation of interface (YAML) and implementation (Python)

**DO NOT DUPLICATE** framework contracts:
```python
# ✅ CORRECT - Import from framework
from omnibase_core.models.contracts import (
    ModelContractBase,
    ModelContractEffect,
    ModelContractCompute,
)

# ❌ WRONG - Don't duplicate in contracts/
class ModelContractBase(BaseModel):  # Framework component!
    pass
```

### 7. Versioning Per Node ✅

✅ Each node has `v1_0_0/`, `v2_0_0/`, etc.
✅ Nodes evolve independently
✅ Use `compatibility.yaml` to track which versions work together
❌ NO group-level versioning (breaks independence)

---

## Framework Components

### DO NOT DUPLICATE

These are imported from `omnibase_core`:

**Base Contracts** (Pydantic models):
```python
from omnibase_core.models.contracts import (
    ModelContractBase,
    ModelContractEffect,
    ModelContractCompute,
    ModelContractReducer,
    ModelContractOrchestrator,
)
```

**Subcontracts** (Pydantic models):
```python
from omnibase_core.models.contracts.subcontracts import (
    ModelFsmSubcontract,
    ModelEventTypeSubcontract,
    ModelAggregationSubcontract,
    ModelStateManagementSubcontract,
    ModelRoutingSubcontract,
    ModelCachingSubcontract,
)
```

**Location**: `/omnibase_core/src/omnibase_core/models/contracts/`

---

## Anti-Patterns (DO NOT DO)

### ❌ Premature Shared Resources

```
# ❌ WRONG - Creating group/shared/ upfront
node_group/
├── shared/
│   └── models/
│       └── v1/      # Created "just in case"
│           └── model_*.py   # No nodes use it yet
└── node_1/
    └── v1_0_0/
        └── models/

# ✅ CORRECT - Start with node-level models
node_group/
└── node_1/
    └── v1_0_0/
        └── models/
            └── model_*.py  # Only promote when 2+ nodes need it
```

### ❌ Multiple Classes in node.py

```python
# ❌ WRONG - node.py with multiple classes
class MyDataModel(BaseModel):      # Should be in models/
    pass

class MyEnum(Enum):                 # Should be in models/
    pass

class MyNode(NodeEffect):           # Only this should be in node.py
    pass
```

### ❌ Premature Protocol Promotion

```
# ❌ WRONG - Moving protocol to omnibase_spi prematurely
omnibase_spi/protocols/
└── protocol_experimental.py  # Only one node uses it!

# ✅ CORRECT - Keep in node until actually shared
node/v1_0_0/protocols/
└── protocol_experimental.py  # Promote when 2+ nodes need it
```

### ❌ Group-Level Versioning

```
# ❌ WRONG - Version at group level
node_group/
└── v1_0_0/         # Breaks independent node evolution
    ├── node_1/
    └── node_2/

# ✅ CORRECT - Version per node
node_group/
├── node_1/
│   └── v1_0_0/    # Independent versioning
└── node_2/
    └── v2_0_0/    # Can be different version
```

---

## Model Hierarchy with Independent Versioning

```
┌─────────────────────────────────────────────┐
│ Framework Models (omnibase_core)            │ ← Import, don't duplicate
│ - ModelContractBase, ModelOnexContainer     │
└─────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────┐
│ Project Shared (across ALL groups)          │ ← Rare, only when needed
│ - project/shared/models/v1/, v2/            │ ← Independent versioning
└─────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────┐
│ Group Shared (shared in THIS group)         │ ← LAZY: Promote when 2+ nodes
│ - group/shared/models/v1/, v2/              │ ← Independent versioning
│ - group/shared/protocols/v1/, v2/           │
└─────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────┐
│ Node Models (specific to ONE node)          │ ← Start here
│ - node/v1_0_0/models/model_*.py             │ ← Node versioning
└─────────────────────────────────────────────┘
```

**Promotion Decision Tree**:
```
Is model used by 2+ nodes in SAME group?
  NO  → Keep in node/v1_0_0/models/
  YES → Same semantic meaning?
          NO  → Keep separate (similar ≠ same)
          YES → Promote to group/shared/models/v1/

Does shared model need breaking change?
  NO  → Add non-breaking changes to existing v1/
  YES → Create group/shared/models/v2/
        (v1 remains for nodes that haven't migrated)

Is model used by 2+ groups?
  NO  → Keep in group/shared/models/
  YES → Same semantic meaning?
          NO  → Keep separate
          YES → Promote to project/shared/models/v1/
```

---

## New Additions (vs Current Canary)

### 🆕 1. Compatibility Matrix

**Create**: `<node_group>/compatibility.yaml`

```yaml
# compatibility.yaml - Version Compatibility Matrix
version: 1.0.0
description: "Compatible version sets for canary node group"

compatible_sets:
  - set_id: "stable-2024-08"
    description: "Production stable release"
    canary_impure_tool: "v1_0_0"
    canary_pure_tool: "v1_0_0"
    canary_reducer_tool: "v1_0_0"
    canary_orchestrator_tool: "v1_0_0"
    tested_together: true
    test_date: "2024-08-15"

  - set_id: "experimental-2024-09"
    description: "Beta features"
    canary_impure_tool: "v2_0_0"
    canary_pure_tool: "v1_0_0"
    canary_reducer_tool: "v1_1_0"
    canary_orchestrator_tool: "v1_0_0"
    tested_together: false
    status: "experimental"

validation_script: "scripts/validate_compatibility.py"
```

### 🆕 2. Node-Level Documentation

**Create**: `<node>/v1_0_0/README.md`

```markdown
# Canary Impure Tool v1.0.0

## Quick Start
Brief overview and usage examples

## What Changed (from v0.x.x)
Version-specific changes

## When to Use
Decision criteria for using this node

## Examples
Concrete usage examples
```

**Create**: `<node>/v1_0_0/CHANGELOG.md`

```markdown
# Changelog - Canary Impure Tool

## [1.0.0] - 2024-08-15

### Added
- Security assessment for file operations
- Rollback instruction generation

### Changed
- Updated input validation

### Fixed
- Path traversal vulnerability
```

### 🆕 3. Explicit Test Structure

**Group-level tests**: `<node_group>/tests/integration/`
```
canary/tests/
├── integration/
│   ├── test_impure_pure_interaction.py
│   └── test_orchestration_flow.py
└── fixtures/
    └── shared_test_data.yaml
```

**Node-level tests**: `<node>/v1_0_0/tests/unit/`
```
canary_impure_tool/v1_0_0/tests/
├── unit/
│   ├── test_node.py
│   ├── test_validation.py
│   └── test_security.py
└── fixtures/
    └── test_input_states.yaml
```

### 🆕 4. Migration Annotations

Add comments documenting evolution paths:

```python
# CURRENT (working):
from omnibase.core.onex_container import ONEXContainer
# FUTURE (after migration):
# from omnibase_core.models.core import ModelOnexContainer

# CURRENT (node-specific):
from .protocols.protocol_canary_impure import ProtocolCanaryImpure
# FUTURE (if promoted):
# from omnibase_spi.protocols import ProtocolCanaryImpure
```

---

## Canonical Example: Canary Group

```
canary/                                     # Node group
├── __init__.py
├── README.md
├── API_REFERENCE.md
├── compatibility.yaml                      # 🆕
│
├── tests/                                  # 🆕 Group-level tests
│   └── integration/
│
├── deployment/
│   └── docker-compose.canary.yml
│
├── canary_impure_tool/                     # Effect node
│   └── v1_0_0/
│       ├── README.md                       # 🆕
│       ├── CHANGELOG.md                    # 🆕
│       ├── node.py
│       ├── contract.yaml
│       ├── node_config.yaml
│       ├── deployment_config.yaml
│       ├── state_transitions.yaml
│       ├── workflow_testing.yaml
│       ├── security_config.yaml
│       ├── contracts/
│       │   ├── contract_actions.yaml
│       │   ├── contract_cli.yaml
│       │   ├── contract_examples.yaml
│       │   └── contract_models.yaml
│       ├── models/
│       │   ├── model_input_state.py
│       │   └── model_output_state.py
│       ├── protocols/                      # ⚠️ Node-specific
│       │   └── protocol_canary_impure.py
│       ├── tests/                          # 🆕
│       │   └── unit/
│       └── mock_configurations/
│
├── canary_pure_tool/                       # Compute node
│   └── v1_0_0/
│       └── ...
│
├── canary_reducer_tool/                    # Reducer node
│   └── v1_0_0/
│       └── ...
│
└── canary_orchestrator_tool/               # Orchestrator node
    └── v1_0_0/
        └── ...
```

---

## Pattern Summary

### ✅ DO

- ✅ Start with minimum viable structure
- ✅ Use ModelOnexContainer (proper Pydantic container)
- ✅ Keep protocols node-local initially (promote when shared)
- ✅ Keep models node-local initially (lazy promotion)
- ✅ Use shared/models/v1/ when promoting (independent versioning)
- ✅ Add compatibility.yaml for version coordination
- ✅ Add node-level README.md + CHANGELOG.md
- ✅ Add explicit tests/ directories
- ✅ Import framework components from omnibase_core
- ✅ Version per node, not per group

### ❌ DON'T

- ❌ Create group/shared/ upfront (lazy promotion only)
- ❌ Use ONEXContainer (legacy, technical debt)
- ❌ Put ALL protocols in omnibase_spi (hybrid approach)
- ❌ Use semantic versioning for shared resources (v1_0_0 → use v1, v2, v3)
- ❌ Add multiple classes to node.py
- ❌ Duplicate framework components
- ❌ Create group-level versioning
- ❌ Promote models/protocols prematurely

---

## Migration Strategy

**From**: Current production canary
**To**: Maximum recommended structure

**Steps**:
1. ✅ Keep current structure (it works!)
2. 🆕 Add `compatibility.yaml` at group level
3. 🆕 Add `README.md` + `CHANGELOG.md` per node
4. 🆕 Add `tests/` directories (explicit structure)
5. ✅ Migrate to ModelOnexContainer (will be unarchived in next PR)
6. ⏸️ Don't create `group/shared/` yet (wait for need)

**Future When Needed**:
- Create `group/shared/models/v1/` when 2nd node needs shared model
- Create `group/shared/models/v2/` when breaking changes needed
- Promote protocols to omnibase_spi when truly shared

---

## Tooling Support

### Required Scripts

**1. Duplication Detection**: `scripts/detect_duplicate_models.py`
- Find models/protocols that should be promoted
- Similarity analysis across nodes
- Promotion recommendations

**2. Compatibility Validation**: `scripts/validate_compatibility.py`
- Validate version compatibility matrix
- Test compatible sets
- Report conflicts

**3. Documentation Generation**: `scripts/generate_docs.py`
- Auto-generate API_REFERENCE.md from contracts
- Keep documentation synchronized

**4. Container Migration**: `scripts/migrate_container.py`
- Migrate from ONEXContainer to ModelOnexContainer
- Run when ModelOnexContainer available
- Automated refactoring

---

## References

- **Innovation Analysis**: `INNOVATION_ANALYSIS_ONEX_STRUCTURE.md`
- **Final Design Review**: `FINAL_DESIGN_REVIEW_ONEX_STRUCTURE.md`
- **Migration Guide**: `MIGRATION_GUIDE.md`
- **Shared Resource Versioning**: `SHARED_RESOURCE_VERSIONING.md` ⭐ New
- **Reference Implementation**: `omnibase_3/src/omnibase/tools/canary/`

---

**Status**: ✅ Final Consensus Design
**Validation**: ✅ Updated with Corrected Decisions
**Review Date**: 2025-10-01
**Version**: 2.1.0 (Updated with ModelOnexContainer + shared/ versioning)
**Key Changes**:
- ✅ ModelOnexContainer (not ONEXContainer) - no technical debt
- ✅ shared/models/v1/, v2/ - independent major versioning for shared resources
