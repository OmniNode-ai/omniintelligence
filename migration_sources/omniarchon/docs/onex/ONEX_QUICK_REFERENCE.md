# ONEX Quick Reference

**Version**: 2.0.0
**Last Verified**: 2025-10-07 (against omnibase_core v2.0.0)
**Purpose**: Fast lookup for patterns, naming, and templates
**For comprehensive guide**: See [ONEX_GUIDE.md](ONEX_GUIDE.md)

> **✅ VERIFIED**: All imports and patterns verified against actual omnibase_core implementations.

---

## 🏗️ 4-Node Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   EFFECT    │───▶│   COMPUTE   │───▶│   REDUCER   │───▶│ORCHESTRATOR │
│   (Input)   │    │ (Process)   │    │(Aggregate)  │    │(Coordinate) │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

**Unidirectional Data Flow**: EFFECT → COMPUTE → REDUCER → ORCHESTRATOR

---

## 📝 Naming Conventions (SUFFIX-based)

### Files
- Nodes: `node_<name>_<type>.py` → `node_database_writer_effect.py`
- Models: `model_<name>.py` → `model_task_data.py`
- Enums: `enum_<name>.py` → `enum_task_status.py`
- Protocols: `protocol_<name>.py` → `protocol_event_bus.py`

### Classes
- Nodes: `Node<Name><Type>` → `NodeDatabaseWriterEffect`
- Models: `Model<Name>` → `ModelTaskData`
- Enums: `Enum<Name>` → `EnumTaskStatus`
- Protocols: `Protocol<Name>` → `ProtocolEventBus`

**Key**: Type comes LAST (suffix-based), not first!

---

## 🎨 Node Types Quick Reference

### NodeEffect
**Purpose**: Side effects (I/O, database, API calls)
**Method**: `async def execute_effect(self, contract: ModelContractEffect) -> Any`
**Import**: `from omnibase_core.infrastructure.node_effect import NodeEffect`
**Use for**: Database writes, file operations, API calls, event publishing

### NodeCompute
**Purpose**: Pure computations (no side effects)
**Method**: `async def execute_compute(self, contract: ModelContractCompute) -> Any`
**Import**: `from omnibase_core.infrastructure.node_compute import NodeCompute`
**Use for**: Data transformations, calculations, filtering, validation

### NodeReducer
**Purpose**: Data aggregation and state reduction
**Method**: `async def execute_reduction(self, contract: ModelContractReducer) -> Any`
**Import**: `from omnibase_core.infrastructure.node_reducer import NodeReducer`
**Use for**: Aggregation, statistics, state merging, report generation

### NodeOrchestrator
**Purpose**: Workflow coordination
**Method**: `async def execute_orchestration(self, contract: ModelContractOrchestrator) -> Any`
**Import**: `from omnibase_core.infrastructure.node_orchestrator import NodeOrchestrator`
**Use for**: Multi-step workflows, pipeline coordination, dependency resolution

---

## 🚀 Quick Start Templates

### Effect Node (Standard) ⭐

```python
#!/usr/bin/env python3
"""My Effect Node."""

from pathlib import Path
from omnibase_core.constants.contract_constants import CONTRACT_FILENAME
from omnibase_core.infrastructure.node_base import NodeBase
from omnibase_core.infrastructure.node_effect import NodeEffect
from omnibase_core.models.container.model_onex_container import ModelONEXContainer
from omnibase_core.models.contracts import ModelContractEffect

from .models.model_input_state import ModelMyInputState
from .models.model_output_state import ModelMyOutputState


class NodeMyProcessor(NodeEffect):
    """
    My Effect node with standard operational patterns.

    Includes: service resolution, health check, performance monitoring,
    configuration, request/response patterns.
    """

    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)

    async def execute_effect(
        self, contract: ModelContractEffect
    ) -> ModelMyOutputState:
        """Execute side effect with transaction support."""
        async with self.transaction_manager.begin():
            result = await self._perform_operation(contract)
            return ModelMyOutputState(success=True, data=result)


def main():
    return NodeBase(Path(__file__).parent / CONTRACT_FILENAME)


if __name__ == "__main__":
    main()
```

### Compute Node (Standard)

```python
#!/usr/bin/env python3
"""My Compute Node."""

from omnibase_core.infrastructure.node_compute import NodeCompute
from omnibase_core.models.container.model_onex_container import ModelONEXContainer
from omnibase_core.models.contracts import ModelContractCompute

from .models.model_input_state import ModelMyInputState
from .models.model_output_state import ModelMyOutputState


class NodeMyTransform(NodeCompute):
    """
    My Compute node with caching and performance monitoring.

    Includes: caching, performance monitoring, configuration, health check.
    """

    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)

    async def execute_compute(
        self, contract: ModelContractCompute
    ) -> ModelMyOutputState:
        """Execute computation with caching."""
        # Check cache
        cached = self.cache.get(contract.cache_key)
        if cached:
            return cached

        # Compute
        result = self._transform_data(contract.input_data)

        # Cache result
        self.cache.set(contract.cache_key, result)
        return ModelMyOutputState(success=True, data=result)


def main():
    return NodeBase(Path(__file__).parent / CONTRACT_FILENAME)


if __name__ == "__main__":
    main()
```

### Reducer Node (Standard)

```python
#!/usr/bin/env python3
"""My Reducer Node."""

from omnibase_core.infrastructure.node_reducer import NodeReducer
from omnibase_core.models.container.model_onex_container import ModelONEXContainer
from omnibase_core.models.contracts import ModelContractReducer

from .models.model_input_state import ModelMyInputState
from .models.model_output_state import ModelMyOutputState


class NodeMyAggregator(NodeReducer):
    """
    My Reducer node with aggregation patterns.

    Includes: aggregation, state management, caching, performance monitoring.
    """

    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)

    async def execute_reduction(
        self, contract: ModelContractReducer
    ) -> ModelMyOutputState:
        """Execute reduction with aggregation."""
        aggregated_data = []

        # Process stream
        async for item in contract.input_stream:
            aggregated_data.append(self._process_item(item))

        # Aggregate
        result = self._aggregate(aggregated_data)
        return ModelMyOutputState(success=True, data=result)


def main():
    return NodeBase(Path(__file__).parent / CONTRACT_FILENAME)


if __name__ == "__main__":
    main()
```

### Orchestrator Node (Standard)

```python
#!/usr/bin/env python3
"""My Orchestrator Node."""

from omnibase_core.infrastructure.node_orchestrator import NodeOrchestrator
from omnibase_core.models.container.model_onex_container import ModelONEXContainer
from omnibase_core.models.contracts import ModelContractOrchestrator

from .models.model_input_state import ModelMyInputState
from .models.model_output_state import ModelMyOutputState


class NodeMyCoordinator(NodeOrchestrator):
    """
    My Orchestrator node with workflow coordination.

    Includes: workflow coordination, routing, service resolution,
    event handling, health monitoring.
    """

    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)

    async def execute_orchestration(
        self, contract: ModelContractOrchestrator
    ) -> ModelMyOutputState:
        """Execute orchestration with workflow coordination."""
        # Coordinate workflow
        results = await self._coordinate_workflow(contract)
        return ModelMyOutputState(success=True, data=results)


def main():
    return NodeBase(Path(__file__).parent / CONTRACT_FILENAME)


if __name__ == "__main__":
    main()
```

---

## 📦 Contract Architecture

### Base Contracts (One Per Node Type)

```python
# Use the appropriate base contract for your node type
from omnibase_core.models.contracts import ModelContractEffect
from omnibase_core.models.contracts import ModelContractCompute
from omnibase_core.models.contracts import ModelContractReducer
from omnibase_core.models.contracts import ModelContractOrchestrator
```

### Composing Functionality via Subcontracts

Add functionality by including subcontracts in your contract.yaml:

| Subcontract | Purpose | Use For |
|-------------|---------|---------|
| **Caching** | Response caching | Compute nodes with expensive operations |
| **EventType** | Event handling | Effect nodes that emit/receive events |
| **Routing** | Request routing | Orchestrator nodes with multiple paths |
| **FSM** | State machines | Complex workflow state management |
| **Aggregation** | Data aggregation | Reducer nodes collecting data streams |
| **StateManagement** | Persistent state | Nodes requiring state persistence |

---

## 📄 Contract YAML Template

### Basic Contract
```yaml
name: my_operation
version: 1.0.0
description: "My operation description"
node_type: EFFECT  # or COMPUTE, REDUCER, ORCHESTRATOR

io_operations:
  - operation_type: "file_write"
    path: "/data/output.json"
```

### Contract with Subcontracts
```yaml
name: my_operation
version: 1.0.0
description: "My operation with caching and events"
node_type: COMPUTE

# Compose functionality via subcontracts
caching:
  enabled: true
  ttl_seconds: 300
  cache_key_pattern: "${operation}:${input_hash}"

event_type:
  event_name: "computation_completed"
  event_schema_version: "1.0.0"

io_operations:
  - operation_type: "api_call"
    endpoint: "${SERVICE_URL}/api/data"
```

### Complex Orchestrator Contract
```yaml
name: my_workflow
version: 1.0.0
description: "Complex workflow with routing and FSM"
node_type: ORCHESTRATOR

# Compose multiple capabilities
routing:
  strategy: "round_robin"
  load_balancing: true
  max_retries: 3

fsm:
  initial_state: "pending"
  states:
    - name: "pending"
      transitions: ["processing"]
    - name: "processing"
      transitions: ["completed", "failed"]

workflow_coordination:
  max_concurrent_workflows: 100
  execution_timeout_seconds: 300
```

---

## 🎯 Decision Trees

### Which Subcontracts Should I Use?

```
Need side effects (I/O, database, API)?
  YES → Use ModelContractEffect + appropriate subcontracts
  NO  → ↓

Pure computation with no side effects?
  YES → Use ModelContractCompute + Caching subcontract if needed
  NO  → ↓

Aggregating data from multiple sources?
  YES → Use ModelContractReducer + Aggregation subcontract
  NO  → ↓

Coordinating multiple workflows?
  YES → Use ModelContractOrchestrator + Routing/FSM subcontracts
```

### Where Should This Resource Live?

```
Is it a MODEL or PROTOCOL?
  ↓
Used by 2+ nodes?
  NO  → Keep in node/v1_0_0/models/ or protocols/
  YES → Same semantic meaning?
          NO  → Keep separate
          YES → ↓

Used by nodes in SAME group?
  YES → Promote to shared/models/v1/ or protocols/v1/
  NO  → Used by nodes in DIFFERENT groups?
          YES → Promote to project/shared/models/v1/
```

### Protocol Location?

```
Node-specific? → node/v1_0_0/protocols/
Shared (2+ nodes)? → shared/protocols/v1/
Framework-wide? → omnibase_spi/protocols/
```

---

## ✅ Best Practices Checklist

### Creating a New Node

- [ ] Choose correct node type (Effect/Compute/Reducer/Orchestrator)
- [ ] Use appropriate base contract (ModelContractEffect/Compute/Reducer/Orchestrator)
- [ ] Use `ModelONEXContainer` (capital ONEX)
- [ ] Follow SUFFIX-based naming (`Node<Name><Type>`)
- [ ] One class per node.py (no enums, no helpers)
- [ ] Create contract.yaml with required subcontracts
- [ ] Keep models node-local initially (lazy promotion)
- [ ] Keep protocols node-local initially (lazy promotion)
- [ ] Implement proper error handling and logging
- [ ] Add UUID correlation tracking
- [ ] Write comprehensive tests

### Before Promoting to Shared

- [ ] Resource used by 2+ nodes (not "might be")
- [ ] Same semantic meaning across consumers
- [ ] Duplication detected by tooling
- [ ] Use `shared/models/v1/` or `shared/protocols/v1/`
- [ ] Update imports in all consuming nodes
- [ ] Add tests for shared resource

### Contract YAML

- [ ] Include `name`, `version`, `description`, `node_type`
- [ ] Define required subcontracts for functionality composition
- [ ] Specify io_operations or workflow_coordination as appropriate
- [ ] Use environment variables for config (`${VAR_NAME}`)
- [ ] Add validation rules if needed
- [ ] Document expected inputs/outputs

---

## 🚫 Common Mistakes

### ❌ Don't
- Import from `omnibase.core` (use `omnibase_core.infrastructure`)
- Use `ModelOnexContainer` (use `ModelONEXContainer` with capital ONEX)
- Reference non-existent Standard/Full contract variants
- Put multiple classes in node.py
- Create shared/ upfront
- Use semantic versioning for shared resources (v1_0_0 → use v1, v2)
- Promote resources prematurely
- Break unidirectional flow
- Skip contract validation

### ✅ Do
- Use correct import paths: `omnibase_core.infrastructure.*`
- Use `ModelONEXContainer` (capital ONEX)
- Use base contracts with subcontract composition
- One class per node.py
- Lazy promotion to shared/
- Major versioning for shared (v1, v2, v3)
- Promote when 2+ nodes actually need it
- Follow unidirectional data flow
- Validate contracts

---

## 📚 Quick Imports Reference

### Essential Node Imports ⭐
```python
# Node bases (CORRECT paths)
from omnibase_core.infrastructure.node_effect import NodeEffect
from omnibase_core.infrastructure.node_compute import NodeCompute
from omnibase_core.infrastructure.node_reducer import NodeReducer
from omnibase_core.infrastructure.node_orchestrator import NodeOrchestrator

# Base contracts (one per node type)
from omnibase_core.models.contracts import ModelContractEffect
from omnibase_core.models.contracts import ModelContractCompute
from omnibase_core.models.contracts import ModelContractReducer
from omnibase_core.models.contracts import ModelContractOrchestrator

# Container (CORRECT name with capital ONEX)
from omnibase_core.models.container.model_onex_container import ModelONEXContainer

# Node base for main()
from omnibase_core.infrastructure.node_base import NodeBase
from omnibase_core.constants.contract_constants import CONTRACT_FILENAME
```

### Subcontract Imports (For Custom Composition)
```python
# Individual subcontracts for advanced use cases
from omnibase_core.models.contracts.subcontracts import (
    ModelFSMSubcontract,
    ModelEventTypeSubcontract,
    ModelCachingSubcontract,
    ModelRoutingSubcontract,
    ModelAggregationSubcontract,
    ModelStateManagementSubcontract,
)
```

---

## 🔗 Related Documentation

- **[ONEX_GUIDE.md](ONEX_GUIDE.md)** - Comprehensive implementation guide
- **[SHARED_RESOURCE_VERSIONING.md](SHARED_RESOURCE_VERSIONING.md)** - Versioning strategy
- **[examples/](examples/)** - Real implementation examples

---

**Status**: ✅ Quick Reference
**Version**: 2.0.0
**Last Updated**: 2025-10-01
