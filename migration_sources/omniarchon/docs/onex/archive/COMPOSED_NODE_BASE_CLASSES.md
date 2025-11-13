# ONEX Composed Node Base Classes - Design Specification

**Version**: 1.0.0
**Status**: 🚧 Proposed Design
**Last Updated**: 2025-10-01
**Related**: NODE_GROUP_STRUCTURE.md, SHARED_RESOURCE_VERSIONING.md

---

## Problem Statement

Currently, **each node manually composes the subcontracts it needs**, leading to:
- ❌ Boilerplate repetition across similar nodes
- ❌ Inconsistent subcontract usage patterns
- ❌ Difficult to enforce best practices
- ❌ No clear templates for new nodes

**Current State** (ModelContractEffect):
```python
class ModelContractEffect(ModelContractBase):
    # Only 3 subcontracts out of 14 available!
    event_type: ModelEventTypeSubcontract | None = None
    caching: ModelCachingSubcontract | None = None
    routing: ModelRoutingSubcontract | None = None
```

**Missing Subcontracts** not in base contracts:
1. ModelConfigurationSubcontract
2. ModelWorkflowCoordinationSubcontract
3. ModelServiceResolutionSubcontract ⭐
4. ModelExternalDependenciesSubcontract
5. ModelHealthCheckSubcontract
6. ModelIntrospectionSubcontract
7. ModelPerformanceMonitoringSubcontract
8. ModelRequestResponseSubcontract
9. ModelAggregationSubcontract (Reducer only?)
10. ModelFSMSubcontract (in base, but not mentioned)
11. ModelStateManagementSubcontract (in base, but not mentioned)

---

## Solution: Composed Base Classes

Create **pre-composed base contract classes** that aggregate common subcontract patterns for typical use cases.

### Design Principles

1. **Layered Composition**: Multiple levels of composition for flexibility
2. **Progressive Enhancement**: Start minimal, add features as needed
3. **Clear Naming**: Names indicate included subcontracts
4. **Backward Compatible**: Existing contracts still work
5. **Zero Duplication**: DRY principle for subcontract aggregation

---

## Proposed Hierarchy

```
ModelContractBase (foundation)
    ↓
ModelContract{Type} (current: minimal)
    ↓
ModelContract{Type}Standard (common patterns)
    ↓
ModelContract{Type}Full (all applicable subcontracts)
```

---

## Composed Base Classes Design

### 1. Effect Node Compositions

#### ModelContractEffectStandard
**Common patterns for typical Effect nodes**

```python
class ModelContractEffectStandard(ModelContractEffect):
    """
    Standard Effect node with common operational patterns.

    Includes:
    - Service resolution (dependency injection)
    - Health monitoring
    - Performance tracking
    - Configuration management
    - Request/response patterns

    Use for: Most production Effect nodes
    """

    # === OPERATIONAL SUBCONTRACTS ===
    service_resolution: ModelServiceResolutionSubcontract = Field(
        default_factory=ModelServiceResolutionSubcontract,
        description="Service discovery and dependency injection",
    )

    health_check: ModelHealthCheckSubcontract = Field(
        default_factory=ModelHealthCheckSubcontract,
        description="Health monitoring and readiness checks",
    )

    performance_monitoring: ModelPerformanceMonitoringSubcontract = Field(
        default_factory=ModelPerformanceMonitoringSubcontract,
        description="Performance metrics and monitoring",
    )

    configuration: ModelConfigurationSubcontract = Field(
        default_factory=ModelConfigurationSubcontract,
        description="Configuration management",
    )

    request_response: ModelRequestResponseSubcontract = Field(
        default_factory=ModelRequestResponseSubcontract,
        description="Request/response pattern support",
    )

    # Inherit from parent: event_type, caching, routing
```

#### ModelContractEffectFull
**All applicable Effect subcontracts**

```python
class ModelContractEffectFull(ModelContractEffectStandard):
    """
    Full-featured Effect node with all operational capabilities.

    Adds to Standard:
    - External dependencies tracking
    - Runtime introspection
    - Advanced state management
    - FSM patterns

    Use for: Complex infrastructure nodes, critical services
    """

    # === ADVANCED SUBCONTRACTS ===
    external_dependencies: ModelExternalDependenciesSubcontract = Field(
        default_factory=ModelExternalDependenciesSubcontract,
        description="External dependency management",
    )

    introspection: ModelIntrospectionSubcontract = Field(
        default_factory=ModelIntrospectionSubcontract,
        description="Runtime introspection capabilities",
    )

    state_management: ModelStateManagementSubcontract | None = Field(
        default=None,
        description="Advanced state management (optional)",
    )

    fsm: ModelFSMSubcontract | None = Field(
        default=None,
        description="Finite state machine patterns (optional)",
    )
```

---

### 2. Compute Node Compositions

#### ModelContractComputeStandard
**Common patterns for typical Compute nodes**

```python
class ModelContractComputeStandard(ModelContractCompute):
    """
    Standard Compute node with performance optimization patterns.

    Includes:
    - Caching (critical for pure functions)
    - Performance monitoring
    - Configuration management
    - Health checks

    Use for: Most Compute nodes with caching needs
    """

    # === PERFORMANCE SUBCONTRACTS ===
    caching: ModelCachingSubcontract = Field(
        default_factory=ModelCachingSubcontract,
        description="Result caching for pure computations",
    )

    performance_monitoring: ModelPerformanceMonitoringSubcontract = Field(
        default_factory=ModelPerformanceMonitoringSubcontract,
        description="Computation performance tracking",
    )

    configuration: ModelConfigurationSubcontract = Field(
        default_factory=ModelConfigurationSubcontract,
        description="Algorithm configuration",
    )

    health_check: ModelHealthCheckSubcontract = Field(
        default_factory=ModelHealthCheckSubcontract,
        description="Computation health monitoring",
    )
```

#### ModelContractComputeFull
**All applicable Compute subcontracts**

```python
class ModelContractComputeFull(ModelContractComputeStandard):
    """
    Full-featured Compute node for complex computations.

    Adds to Standard:
    - Service resolution (for external data sources)
    - Request/response patterns
    - Introspection capabilities

    Use for: Complex algorithmic nodes, ML inference nodes
    """

    service_resolution: ModelServiceResolutionSubcontract | None = Field(
        default=None,
        description="External data source resolution (optional)",
    )

    request_response: ModelRequestResponseSubcontractt | None = Field(
        default=None,
        description="Request/response patterns (optional)",
    )

    introspection: ModelIntrospectionSubcontract | None = Field(
        default=None,
        description="Runtime introspection (optional)",
    )
```

---

### 3. Reducer Node Compositions

#### ModelContractReducerStandard
**Common patterns for typical Reducer nodes**

```python
class ModelContractReducerStandard(ModelContractReducer):
    """
    Standard Reducer node with aggregation patterns.

    Includes:
    - Aggregation (core reducer functionality)
    - State management
    - Caching
    - Performance monitoring

    Use for: Most Reducer nodes
    """

    # === AGGREGATION SUBCONTRACTS ===
    aggregation: ModelAggregationSubcontract = Field(
        default_factory=ModelAggregationSubcontract,
        description="Data aggregation strategies",
    )

    state_management: ModelStateManagementSubcontract = Field(
        default_factory=ModelStateManagementSubcontract,
        description="Aggregation state management",
    )

    caching: ModelCachingSubcontract = Field(
        default_factory=ModelCachingSubcontract,
        description="Aggregation result caching",
    )

    performance_monitoring: ModelPerformanceMonitoringSubcontract = Field(
        default_factory=ModelPerformanceMonitoringSubcontract,
        description="Aggregation performance tracking",
    )
```

---

### 4. Orchestrator Node Compositions

#### ModelContractOrchestratorStandard
**Common patterns for typical Orchestrator nodes**

```python
class ModelContractOrchestratorStandard(ModelContractOrchestrator):
    """
    Standard Orchestrator node with workflow coordination.

    Includes:
    - Workflow coordination (core orchestrator functionality)
    - Routing
    - Service resolution
    - Health monitoring
    - Event coordination

    Use for: Most Orchestrator nodes
    """

    # === ORCHESTRATION SUBCONTRACTS ===
    workflow_coordination: ModelWorkflowCoordinationSubcontract = Field(
        default_factory=ModelWorkflowCoordinationSubcontract,
        description="Multi-node workflow coordination",
    )

    routing: ModelRoutingSubcontract = Field(
        default_factory=ModelRoutingSubcontract,
        description="Node routing and load balancing",
    )

    service_resolution: ModelServiceResolutionSubcontract = Field(
        default_factory=ModelServiceResolutionSubcontract,
        description="Node and service discovery",
    )

    event_type: ModelEventTypeSubcontract = Field(
        default_factory=ModelEventTypeSubcontract,
        description="Event-driven orchestration",
    )

    health_check: ModelHealthCheckSubcontract = Field(
        default_factory=ModelHealthCheckSubcontract,
        description="Orchestration health monitoring",
    )
```

#### ModelContractOrchestratorFull
**All applicable Orchestrator subcontracts**

```python
class ModelContractOrchestratorFull(ModelContractOrchestratorStandard):
    """
    Full-featured Orchestrator with advanced capabilities.

    Adds to Standard:
    - FSM patterns for complex workflows
    - State management
    - Performance monitoring
    - Configuration management

    Use for: Complex multi-stage workflows, critical orchestration
    """

    fsm: ModelFSMSubcontract = Field(
        default_factory=ModelFSMSubcontract,
        description="State machine-based workflow control",
    )

    state_management: ModelStateManagementSubcontract = Field(
        default_factory=ModelStateManagementSubcontract,
        description="Workflow state management",
    )

    performance_monitoring: ModelPerformanceMonitoringSubcontract = Field(
        default_factory=ModelPerformanceMonitoringSubcontract,
        description="Orchestration performance tracking",
    )

    configuration: ModelConfigurationSubcontract = Field(
        default_factory=ModelConfigurationSubcontract,
        description="Workflow configuration management",
    )
```

---

## Subcontract-to-Node Type Matrix

| Subcontract | Effect | Compute | Reducer | Orchestrator | Notes |
|------------|--------|---------|---------|--------------|-------|
| **ServiceResolution** | ✅ Standard | Optional | Optional | ✅ Standard | DI pattern |
| **HealthCheck** | ✅ Standard | ✅ Standard | ✅ Standard | ✅ Standard | Universal |
| **PerformanceMonitoring** | ✅ Standard | ✅ Standard | ✅ Standard | Optional | Universal |
| **Configuration** | ✅ Standard | ✅ Standard | Optional | Optional | Common |
| **RequestResponse** | ✅ Standard | Optional | ❌ | ❌ | Effect/Compute only |
| **Caching** | Optional | ✅ Standard | ✅ Standard | ❌ | Performance |
| **EventType** | Optional | ❌ | ❌ | ✅ Standard | Event-driven |
| **Routing** | Optional | ❌ | ❌ | ✅ Standard | Orchestration |
| **WorkflowCoordination** | ❌ | ❌ | ❌ | ✅ Standard | Orchestrator only |
| **Aggregation** | ❌ | ❌ | ✅ Standard | ❌ | Reducer only |
| **StateManagement** | Optional | ❌ | ✅ Standard | Optional | Stateful nodes |
| **FSM** | Optional | ❌ | ❌ | Optional | Complex workflows |
| **ExternalDependencies** | Optional | Optional | ❌ | ❌ | Integration nodes |
| **Introspection** | Optional | Optional | ❌ | ❌ | Debugging/monitoring |

**Legend**:
- ✅ Standard: Included in `{Type}Standard` composition
- Optional: Available in `{Type}Full` or can be added manually
- ❌: Not applicable to this node type

---

## Usage Examples

### Example 1: Simple Effect Node (Minimal)

```python
# Use base contract - minimal subcontracts
from omnibase_core.models.contracts import ModelContractEffect

class ToolSimpleFileWriter(NodeEffect):
    """Minimal Effect node - just the essentials."""

    def __init__(self, container: ModelOnexContainer) -> None:
        super().__init__(container)
        # Contract: ModelContractEffect with basic I/O only
```

### Example 2: Production Effect Node (Standard)

```python
# Use Standard composition - common operational patterns
from omnibase_core.models.contracts import ModelContractEffectStandard

class ToolProductionAPIClient(NodeEffect):
    """
    Production Effect node with standard operational patterns.

    Automatically includes:
    - Service resolution
    - Health monitoring
    - Performance tracking
    - Configuration management
    - Request/response patterns
    """

    def __init__(self, container: ModelOnexContainer) -> None:
        super().__init__(container)
        # Contract: ModelContractEffectStandard
        # All standard subcontracts available automatically
```

### Example 3: Complex Infrastructure Node (Full)

```python
# Use Full composition - all capabilities
from omnibase_core.models.contracts import ModelContractEffectFull

class ToolDatabaseConnector(NodeEffect):
    """
    Complex infrastructure node with all operational capabilities.

    Includes all Standard features PLUS:
    - External dependencies tracking
    - Runtime introspection
    - State management
    - FSM patterns
    """

    def __init__(self, container: ModelOnexContainer) -> None:
        super().__init__(container)
        # Contract: ModelContractEffectFull
        # Maximum operational capabilities
```

### Example 4: Custom Composition

```python
# Start with Standard, customize as needed
from omnibase_core.models.contracts import ModelContractEffectStandard
from omnibase_core.models.contracts.subcontracts import ModelFSMSubcontract

class ToolCustomProcessor(NodeEffect):
    """Custom composition: Standard + FSM, no caching."""

    def __init__(self, container: ModelOnexContainer) -> None:
        super().__init__(container)
        # Contract in YAML can specify custom subcontracts
        # Inherits Standard patterns, adds FSM, removes caching
```

---

## Contract YAML Examples

### Minimal Effect (base)
```yaml
contract_version: "2.0.0"
node_type: "effect"
# Uses: ModelContractEffect
# Subcontracts: event_type, caching, routing (all optional)

io_operations:
  - operation_type: "file_write"
    path: "/data/output.json"
```

### Standard Effect
```yaml
contract_version: "2.0.0"
node_type: "effect"
composed_type: "standard"  # 🆕 Triggers ModelContractEffectStandard
# Automatically includes: service_resolution, health_check,
# performance_monitoring, configuration, request_response

io_operations:
  - operation_type: "api_call"
    endpoint: "${SERVICE_URL}/api/data"

service_resolution:
  service_name: "data_api"
  discovery_method: "dns"

health_check:
  endpoint: "/health"
  interval_seconds: 30

performance_monitoring:
  enable_metrics: true
  sample_rate: 1.0
```

### Full Orchestrator
```yaml
contract_version: "2.0.0"
node_type: "orchestrator"
composed_type: "full"  # 🆕 Triggers ModelContractOrchestratorFull
# All orchestration capabilities enabled

workflow_coordination:
  max_concurrent_workflows: 100
  execution_timeout_seconds: 300

routing:
  strategy: "round_robin"
  load_balancing: true

fsm:
  initial_state: "pending"
  states:
    - name: "pending"
      transitions: ["processing"]
    - name: "processing"
      transitions: ["completed", "failed"]
```

---

## Migration Strategy

### Phase 1: Create Composed Base Classes (omnibase_core)
1. ✅ Audit all 14 subcontracts
2. 🆕 Create `model_contract_{type}_standard.py` for each node type
3. 🆕 Create `model_contract_{type}_full.py` for each node type
4. ✅ Update `__init__.py` exports

### Phase 2: Update Documentation
1. 🆕 Update NODE_GROUP_STRUCTURE.md with composed classes
2. 🆕 Create this document (COMPOSED_NODE_BASE_CLASSES.md)
3. 🆕 Update ONEX examples to show all three levels
4. 🆕 Create migration guide for existing nodes

### Phase 3: Gradual Adoption
1. ✅ Keep existing base contracts (backward compatible)
2. 🆕 New nodes use `Standard` by default
3. 🆕 Complex nodes use `Full` when needed
4. ⏸️ Migrate existing nodes gradually (optional)

### Phase 4: Tooling Support
1. 🆕 CLI: `onex create node --template standard|full|minimal`
2. 🆕 Validator: Check subcontract usage against patterns
3. 🆕 Generator: Auto-generate composed contracts from specs

---

## Benefits

### ✅ Developer Experience
- **Faster Development**: Pre-composed patterns reduce boilerplate
- **Best Practices**: Standard patterns enforce good architecture
- **Clear Templates**: Three levels (minimal/standard/full) guide choices
- **Gradual Complexity**: Start minimal, add features as needed

### ✅ Consistency
- **Uniform Patterns**: Same operational patterns across similar nodes
- **Predictable Behavior**: Standard nodes behave consistently
- **Easier Onboarding**: Clear examples of typical compositions

### ✅ Maintainability
- **DRY Principle**: Subcontract aggregation in one place
- **Centralized Updates**: Update composed class, all nodes benefit
- **Clear Dependencies**: Explicit subcontract requirements

### ✅ Flexibility
- **Progressive Enhancement**: Start small, grow as needed
- **Custom Compositions**: Can still compose manually
- **Backward Compatible**: Existing nodes unchanged

---

## Implementation Checklist

### omnibase_core Updates
- [ ] Create `model_contract_effect_standard.py`
- [ ] Create `model_contract_effect_full.py`
- [ ] Create `model_contract_compute_standard.py`
- [ ] Create `model_contract_compute_full.py`
- [ ] Create `model_contract_reducer_standard.py`
- [ ] Create `model_contract_orchestrator_standard.py`
- [ ] Create `model_contract_orchestrator_full.py`
- [ ] Update `__init__.py` exports
- [ ] Add validation for `composed_type` field
- [ ] Unit tests for all composed classes

### Documentation Updates
- [ ] Update NODE_GROUP_STRUCTURE.md
- [ ] Create examples for all 14 subcontracts
- [ ] Update ONEX examples (docs/onex/examples/)
- [ ] Create migration guide
- [ ] Update CLAUDE.md

### Tooling
- [ ] CLI: Node creation with templates
- [ ] Validator: Pattern compliance checking
- [ ] Generator: Auto-generate from specs

---

## References

- **Node Structure**: NODE_GROUP_STRUCTURE.md
- **Subcontracts**: omnibase_core/models/contracts/subcontracts/
- **Base Contracts**: omnibase_core/models/contracts/model_contract_*.py
- **Versioning**: SHARED_RESOURCE_VERSIONING.md

---

**Status**: 🚧 Proposed Design - Ready for Review
**Version**: 1.0.0
**Last Updated**: 2025-10-01
**Next Steps**: Review → Implement in omnibase_core → Update documentation
