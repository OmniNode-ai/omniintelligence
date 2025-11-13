# ONEX Architecture Patterns - Complete Reference

**Version**: 1.0.0
**Generated**: 2025-10-01
**Purpose**: Comprehensive ONEX patterns for AI-assisted development with hooks integration

---

## Core Architecture

### 4-Node Architecture Pattern

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   EFFECT    │───▶│   COMPUTE   │───▶│   REDUCER   │───▶│ORCHESTRATOR │
│   (Input)   │    │ (Process)   │    │(Aggregate)  │    │(Coordinate) │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

**Unidirectional Data Flow**: EFFECT → COMPUTE → REDUCER → ORCHESTRATOR

---

## 1. Node Types

### NodeEffect
**Purpose**: Side effect management and external interactions
**File Pattern**: `node_*_effect.py`
**Contract**: `ModelContractEffect`

**Responsibilities**:
- I/O operations (file, database, API)
- Transaction management with rollback
- Retry policies and circuit breakers
- Event emission
- Metrics collection

**Method Signature**:
```python
async def execute_effect(self, contract: ModelContractEffect) -> Any:
    """Execute side effect with transaction support."""
    pass
```

**Example Use Cases**:
- Database writes
- File operations
- API calls
- Event publishing

---

### NodeCompute
**Purpose**: Pure computational operations
**File Pattern**: `node_*_compute.py`
**Contract**: `ModelContractCompute`

**Responsibilities**:
- Data transformations
- Calculations and computations
- Caching and memoization
- Parallel processing
- Pure functions (no side effects)

**Method Signature**:
```python
async def execute_compute(self, contract: ModelContractCompute) -> Any:
    """Execute computation with caching support."""
    pass
```

**Example Use Cases**:
- Data transformations
- Calculations
- Filtering/mapping
- Validation logic

---

### NodeReducer
**Purpose**: Data aggregation and state reduction
**File Pattern**: `node_*_reducer.py`
**Contract**: `ModelContractReducer`

**Responsibilities**:
- Data aggregation
- State reduction
- Conflict resolution
- Streaming support
- Statistical operations

**Method Signature**:
```python
async def execute_reduction(self, contract: ModelContractReducer) -> Any:
    """Execute reduction with streaming support."""
    pass
```

**Example Use Cases**:
- Data aggregation
- Statistics calculation
- State merging
- Report generation

---

### NodeOrchestrator
**Purpose**: Workflow coordination
**File Pattern**: `node_*_orchestrator.py`
**Contract**: `ModelContractOrchestrator`

**Responsibilities**:
- Workflow coordination
- Thunk emission
- Dependency management
- Pipeline orchestration
- Error recovery

**Method Signature**:
```python
async def execute_orchestration(self, contract: ModelContractOrchestrator) -> Any:
    """Execute orchestration with dependency management."""
    pass
```

**Example Use Cases**:
- Multi-step workflows
- Pipeline coordination
- Dependency resolution
- Error recovery flows

---

## 2. Contract System

### Base Contract
**Class**: `ModelContractBase`
**File Pattern**: `model_contract_base.py`

**Core Fields**:
- `name: str` - Contract identifier
- `version: str` - Semantic version
- `description: str` - Human-readable description
- `node_type: EnumNodeType` - Node type (EFFECT/COMPUTE/REDUCER/ORCHESTRATOR)

### Specialized Contracts

1. **ModelContractEffect** - For EFFECT nodes
2. **ModelContractCompute** - For COMPUTE nodes
3. **ModelContractReducer** - For REDUCER nodes
4. **ModelContractOrchestrator** - For ORCHESTRATOR nodes

---

## 3. Subcontract System

**Pattern**: `Model<Type>Subcontract`
**File Pattern**: `model_*_subcontract.py`

### 6 Core Subcontract Types

1. **ModelFSMSubcontract** - Finite State Machine functionality
   - State transitions
   - Event-driven state changes
   - Guards and actions

2. **ModelEventTypeSubcontract** - Event-driven architecture
   - Event definitions
   - Event handlers
   - Pub/sub patterns

3. **ModelAggregationSubcontract** - Data aggregation
   - Aggregation strategies
   - Statistical operations
   - Group by operations

4. **ModelStateManagementSubcontract** - State persistence
   - State storage
   - State synchronization
   - State recovery

5. **ModelRoutingSubcontract** - Request routing
   - Load balancing
   - Request routing
   - Endpoint selection

6. **ModelCachingSubcontract** - Performance optimization
   - Cache strategies
   - TTL management
   - Cache invalidation

---

## 4. Naming Conventions

### File Naming

| Type | Pattern | Example |
|------|---------|---------|
| Models | `model_<name>.py` | `model_task_data.py` |
| Enums | `enum_<name>.py` | `enum_task_status.py` |
| TypedDicts | `typed_dict_<name>.py` | `typed_dict_result_kwargs.py` |
| Nodes | `node_<type>_<name>.py` | `node_effect_database.py` |
| Contracts | `model_contract_<type>.py` | `model_contract_effect.py` |
| Subcontracts | `model_<type>_subcontract.py` | `model_fsm_subcontract.py` |
| Protocols | `protocol_<name>.py` | `protocol_event_bus.py` |

### Class Naming

| Type | Pattern | Example |
|------|---------|---------|
| Pydantic Models | `Model<Name>` | `ModelTaskData` |
| Enums | `Enum<Name>` | `EnumTaskStatus` |
| TypedDicts | `TypedDict<Name>` | `TypedDictResultKwargs` |
| Protocols | `Protocol<Name>` | `ProtocolEventBus` |
| Nodes | `Node<Name><Type>` | `NodeDatabaseWriterEffect` |

---

## 5. Architecture Principles

### Zero Tolerance for Any Types
```python
# ✅ Correct - Strongly typed
def process_data(data: ModelTaskData) -> ModelResult:
    pass

# ❌ Incorrect - Using Any
def process_data(data: Any) -> Any:
    pass
```

### Contract-Driven Development
```python
# ✅ Correct - Contract defines behavior
class NodeDatabaseWriterEffect:
    async def execute_effect(self, contract: ModelContractEffect) -> ModelResult:
        # Implementation follows contract spec
        pass
```

### Composition Over Inheritance
```python
# ✅ Correct - Subcontract composition
contract = ModelContractEffect(
    name="database_write",
    state_transitions=ModelFSMSubcontract(...),  # Compose FSM
    caching=ModelCachingSubcontract(...)  # Compose caching
)
```

### Unidirectional Data Flow
```python
# ✅ Correct - Left to right flow
effect_result = await effect_node.execute_effect(effect_contract)
compute_result = await compute_node.execute_compute(compute_contract)
reducer_result = await reducer_node.execute_reduction(reducer_contract)
final_result = await orchestrator.execute_orchestration(orch_contract)
```

---

## 6. Quick Reference Templates

### Creating an Effect Node
```python
from omnibase.core.models.contracts import ModelContractEffect
from omnibase.core.nodes import NodeEffect

class NodeMyOperationEffect(NodeEffect):
    """My custom effect node."""

    async def execute_effect(self, contract: ModelContractEffect) -> ModelResult:
        # Transaction management
        async with self.transaction_manager.begin():
            # Your side effect logic here
            result = await self._perform_operation(contract)
            return ModelResult(success=True, data=result)
```

### Creating a Compute Node
```python
from omnibase.core.models.contracts import ModelContractCompute
from omnibase.core.nodes import NodeCompute

class NodeMyTransformCompute(NodeCompute):
    """My custom compute node."""

    async def execute_compute(self, contract: ModelContractCompute) -> ModelResult:
        # Pure computation with caching
        cached = self.cache.get(contract.cache_key)
        if cached:
            return cached

        result = self._transform_data(contract.input_data)
        self.cache.set(contract.cache_key, result)
        return ModelResult(success=True, data=result)
```

### Contract YAML Template
```yaml
name: my_operation
version: 1.0.0
description: "My operation description"
node_type: EFFECT  # or COMPUTE, REDUCER, ORCHESTRATOR

# Optional subcontracts
state_transitions:
  initial_state: PENDING
  transitions:
    - from: PENDING
      to: PROCESSING
      event: START
    - from: PROCESSING
      to: COMPLETED
      event: FINISH

caching:
  strategy: LRU
  ttl_seconds: 3600
  max_entries: 1000
```

---

## 7. Best Practices

### DO ✅
- Use unidirectional data flow (EFFECT → COMPUTE → REDUCER → ORCHESTRATOR)
- Apply contract-driven development
- Compose subcontracts for reusable functionality
- Use strong typing (zero `Any` types)
- Follow naming conventions consistently
- Implement proper error handling and logging
- Use UUID correlation IDs for tracing

### DON'T ❌
- Skip contract validation
- Use `Any` types in models
- Create side effects in compute nodes
- Break unidirectional flow
- Mix responsibilities across node types
- Hardcode configuration (use contracts)
- Ignore transaction management in effects

---

## 8. Integration Checklist

When creating new nodes:

- [ ] Choose correct node type (Effect/Compute/Reducer/Orchestrator)
- [ ] Follow file naming convention (`node_<type>_<name>.py`)
- [ ] Follow class naming convention (`Node<Type><Name>`)
- [ ] Create contract YAML with all required fields
- [ ] Implement correct method signature (`execute_effect/compute/reduction/orchestration`)
- [ ] Use appropriate subcontracts (FSM, caching, etc.)
- [ ] Add proper error handling and logging
- [ ] Include UUID correlation tracking
- [ ] Write comprehensive tests
- [ ] Document in contract YAML

---

**References**:
- omnibase_core: Node implementations
- omnibase_3: Contract and subcontract models
- omnibase_infra: Production examples (PostgreSQL, Kafka adapters)
