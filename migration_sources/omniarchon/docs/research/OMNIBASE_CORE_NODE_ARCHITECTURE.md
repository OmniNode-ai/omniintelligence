# Omnibase Core - ONEX 4-Node Architecture Documentation

**Repository**: `/Volumes/PRO-G40/Code/omnibase_core`
**Generated**: October 1, 2025
**Architecture Version**: ONEX Four-Node Architecture v1.0

---

## Table of Contents

1. [Overview](#overview)
2. [4 Main Node Types](#4-main-node-types)
   - [NodeEffect](#nodeeffect)
   - [NodeCompute](#nodecompute)
   - [NodeOrchestrator](#nodeorchestrator)
   - [NodeReducer](#nodereducer)
3. [Node Architecture Patterns](#node-architecture-patterns)
4. [Contract System](#contract-system)
5. [File Organization & Naming Conventions](#file-organization--naming-conventions)
6. [Complete Code Examples](#complete-code-examples)

---

## Overview

The ONEX Four-Node Architecture is a foundational design pattern providing structured, scalable, and maintainable microservice organization. The architecture enforces **unidirectional data flow** with clear separation of concerns.

### Architecture Pattern

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   EFFECT    │───▶│   COMPUTE   │───▶│   REDUCER   │───▶│ORCHESTRATOR │
│   (Input)   │    │ (Process)   │    │(Aggregate)  │    │(Coordinate) │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

**Data Flow**: EFFECT → COMPUTE → REDUCER → ORCHESTRATOR (unidirectional, left to right)

---

## 4 Main Node Types

### NodeEffect

**Location**: `/Volumes/PRO-G40/Code/omnibase_core/archived/src/omnibase_core/core/node_effect.py`

**Primary Responsibility**: Side effect management and external interactions

**Key Capabilities**:
- Side-effect management with external interaction focus
- I/O operation abstraction (file, database, API calls)
- Transaction management for rollback support
- Retry policies and circuit breaker patterns
- RSD Storage Integration (work ticket file operations)
- Directory orchestration and file movement
- Event bus publishing for state changes
- Metrics collection and performance logging

**Core Components**:

```python
class EffectType(Enum):
    """Types of side effects that can be managed."""
    FILE_OPERATION = "file_operation"
    DATABASE_OPERATION = "database_operation"
    API_CALL = "api_call"
    EVENT_EMISSION = "event_emission"
    DIRECTORY_OPERATION = "directory_operation"
    TICKET_STORAGE = "ticket_storage"
    METRICS_COLLECTION = "metrics_collection"

class TransactionState(Enum):
    """Transaction state tracking."""
    PENDING = "pending"
    ACTIVE = "active"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"

class CircuitBreakerState(Enum):
    """Circuit breaker states for failure handling."""
    CLOSED = "closed"          # Normal operation
    OPEN = "open"              # Failing, rejecting requests
    HALF_OPEN = "half_open"    # Testing if service recovered
```

**Input/Output Models**:

```python
class ModelEffectInput(BaseModel):
    """Input model for NodeEffect operations."""
    effect_type: EffectType
    operation_data: dict[str, ModelScalarValue]
    operation_id: str | None = Field(default_factory=lambda: str(uuid4()))
    transaction_enabled: bool = True
    retry_enabled: bool = True
    max_retries: int = 3
    retry_delay_ms: int = 1000
    circuit_breaker_enabled: bool = False
    timeout_ms: int = 30000
    metadata: dict[str, ModelScalarValue] | None = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)

class ModelEffectOutput(BaseModel):
    """Output model for NodeEffect operations."""
    result: str | int | float | bool | dict | list
    operation_id: str
    effect_type: EffectType
    transaction_state: TransactionState
    processing_time_ms: float
    retry_count: int = 0
    side_effects_applied: list[str] | None = Field(default_factory=list)
    rollback_operations: list[str] | None = Field(default_factory=list)
    metadata: dict[str, ModelScalarValue] | None = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
```

**Base Class Pattern**:

```python
class NodeEffect(NodeCoreBase):
    """Side effect management node for external interactions."""

    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)
        # Load contract model for Effect node type
        self.contract_model: ModelContractEffect = self._load_contract_model()

        # Effect-specific configuration
        self.max_retries = 3
        self.circuit_breaker_threshold = 5
        self.transaction_timeout_ms = 30000

        # Initialize circuit breaker and transaction manager
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.circuit_breaker_threshold,
            recovery_timeout_seconds=60
        )
        self.transaction_manager = TransactionManager()
```

**Contract Model**: `/Volumes/PRO-G40/Code/omnibase_core/src/omnibase_core/models/contracts/model_contract_effect.py`

**Contract Fields**:
- `correlation_id: UUID` - UUID for correlation tracking
- `execution_id: UUID` - UUID for individual effect execution instances
- `io_operation_config: ModelIOOperationConfig` - I/O operation specifications
- `transaction_config: ModelTransactionConfig` - Transaction management
- `external_service_config: ModelExternalServiceConfig` - External service integration
- `effect_retry_config: ModelEffectRetryConfig` - Retry policies
- `backup_config: ModelBackupConfig` - Backup configuration

---

### NodeCompute

**Location**: `/Volumes/PRO-G40/Code/omnibase_core/archived/src/omnibase_core/core/node_compute.py`

**Primary Responsibility**: Pure computational operations with deterministic guarantees

**Key Capabilities**:
- Pure function patterns with no side effects
- Deterministic operation guarantees
- Computational pipeline with parallel processing
- Caching layer for expensive computations
- RSD Algorithm Integration (5-factor priority calculations)
- Dependency graph traversal algorithms
- Time decay computation with exponential functions
- Failure surface analysis calculations

**Core Components**:

```python
class ModelComputeInput(BaseModel, Generic[T_Input]):
    """Input model for NodeCompute operations."""
    data: T_Input
    operation_id: str | None = Field(default_factory=lambda: str(uuid4()))
    computation_type: str = "default"
    cache_enabled: bool = True
    parallel_enabled: bool = False
    metadata: dict[str, ModelScalarValue] | None = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)

class ModelComputeOutput(BaseModel, Generic[T_Output]):
    """Output model for NodeCompute operations."""
    result: T_Output
    operation_id: str
    computation_type: str
    processing_time_ms: float
    cache_hit: bool = False
    parallel_execution_used: bool = False
    metadata: dict[str, ModelScalarValue] | None = Field(default_factory=dict)
```

**Caching Layer**:

```python
class ComputationCache:
    """Caching layer for expensive computations with TTL and memory management."""

    def __init__(self, max_size: int = 1000, default_ttl_minutes: int = 30):
        self.max_size = max_size
        self.default_ttl_minutes = default_ttl_minutes
        self._cache: dict[str, tuple[Any, datetime, int]] = {}  # key -> (value, expiry, access_count)

    def get(self, cache_key: str) -> Any | None:
        """Get cached value if valid and not expired."""

    def put(self, cache_key: str, value: Any, ttl_minutes: int | None = None) -> None:
        """Cache value with TTL."""
```

**Base Class Pattern**:

```python
class NodeCompute(NodeCoreBase):
    """Pure computation node for deterministic operations."""

    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)
        # Load contract model for Compute node type
        self.contract_model: ModelContractCompute = self._load_contract_model()

        # Computation-specific configuration
        self.max_parallel_workers = 4
        self.cache_ttl_minutes = 30
        self.performance_threshold_ms = 100.0  # Performance SLA: <100ms

        # Initialize caching layer
        self.computation_cache = ComputationCache(
            max_size=1000,
            default_ttl_minutes=self.cache_ttl_minutes
        )

        # Thread pool for parallel execution
        self.thread_pool: ThreadPoolExecutor | None = None

        # Computation registry for algorithm functions
        self.computation_registry: dict[str, Callable[..., Any]] = {}
```

**Contract Model**: `/Volumes/PRO-G40/Code/omnibase_core/src/omnibase_core/models/contracts/model_contract_compute.py`

**Contract Fields**:
- `algorithm_config: ModelAlgorithmConfig` - Algorithm specifications
- `caching_config: ModelCachingConfig` - Caching configuration
- `parallel_config: ModelParallelConfig` - Parallel processing settings
- `input_validation: ModelInputValidationConfig` - Input validation rules
- `output_transformation: ModelOutputTransformationConfig` - Output transformation specs

---

### NodeOrchestrator

**Location**: `/Volumes/PRO-G40/Code/omnibase_core/archived/src/omnibase_core/core/node_orchestrator.py`

**Primary Responsibility**: Workflow coordination and control flow management

**Key Capabilities**:
- Workflow coordination with control flow
- Thunk emission patterns for deferred execution
- Conditional branching based on runtime state
- Parallel execution coordination
- RSD Workflow Management (ticket lifecycle state transitions)
- Dependency-aware execution ordering
- Batch processing coordination with load balancing
- Error recovery and partial failure handling

**Core Components**:

```python
class WorkflowState(Enum):
    """Workflow execution states."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ExecutionMode(Enum):
    """Execution modes for workflow steps."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    BATCH = "batch"
    STREAMING = "streaming"

class ThunkType(Enum):
    """Types of thunks for deferred execution."""
    COMPUTE = "compute"
    EFFECT = "effect"
    REDUCE = "reduce"
    ORCHESTRATE = "orchestrate"
    CUSTOM = "custom"

class BranchCondition(Enum):
    """Conditional branching types."""
    IF_TRUE = "if_true"
    IF_FALSE = "if_false"
    IF_ERROR = "if_error"
    IF_SUCCESS = "if_success"
    IF_TIMEOUT = "if_timeout"
    CUSTOM = "custom"
```

**Thunk Definition**:

```python
class Thunk(NamedTuple):
    """Deferred execution unit with metadata."""
    thunk_id: str
    thunk_type: ThunkType
    target_node_type: str
    operation_data: dict[str, Any]
    dependencies: list[str]
    priority: int
    timeout_ms: int
    retry_count: int
    metadata: dict[str, Any]
    created_at: datetime
```

**Input/Output Models**:

```python
class ModelOrchestratorInput(BaseModel):
    """Input model for NodeOrchestrator operations."""
    workflow_id: str
    steps: list[dict[str, ModelScalarValue]]
    operation_id: str | None = Field(default_factory=lambda: str(uuid4()))
    execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    max_parallel_steps: int = 5
    global_timeout_ms: int = 300000  # 5 minutes default
    failure_strategy: str = "fail_fast"
    load_balancing_enabled: bool = False
    dependency_resolution_enabled: bool = True
    metadata: dict[str, ModelScalarValue] | None = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)

class ModelOrchestratorOutput:
    """Output model for NodeOrchestrator operations."""
    workflow_id: str
    operation_id: str
    workflow_state: WorkflowState
    steps_completed: int
    steps_failed: int
    thunks_emitted: list[Thunk]
    processing_time_ms: float
    parallel_executions: int = 0
    load_balanced_operations: int = 0
    dependency_violations: int = 0
    results: list[Any] | None = None
    metadata: dict[str, Any] | None = None
```

**Dependency Graph**:

```python
class DependencyGraph:
    """Dependency graph for workflow step ordering."""

    def __init__(self) -> None:
        self.nodes: dict[str, WorkflowStep] = {}
        self.edges: dict[str, list[str]] = {}  # step_id -> [dependent_step_ids]
        self.in_degree: dict[str, int] = {}

    def add_step(self, step: WorkflowStep) -> None:
        """Add step to dependency graph."""

    def add_dependency(self, from_step: str, to_step: str) -> None:
        """Add dependency: to_step depends on from_step."""

    def get_ready_steps(self) -> list[str]:
        """Get steps that are ready to execute (no pending dependencies)."""

    def has_cycles(self) -> bool:
        """Check if dependency graph has cycles using DFS."""
```

**Base Class Pattern**:

```python
class NodeOrchestrator(NodeCoreBase):
    """Workflow coordination node for orchestration."""

    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)
        # Load contract model for Orchestrator node type
        self.contract_model: ModelContractOrchestrator = self._load_contract_model()

        # Orchestrator-specific configuration
        self.max_parallel_workflows = 10
        self.default_step_timeout_ms = 30000
        self.enable_load_balancing = True

        # Workflow management
        self.active_workflows: dict[str, WorkflowExecution] = {}
        self.dependency_graph_cache: dict[str, DependencyGraph] = {}
        self.load_balancer = LoadBalancer(max_concurrent_operations=10)
```

**Contract Model**: `/Volumes/PRO-G40/Code/omnibase_core/src/omnibase_core/models/contracts/model_contract_orchestrator.py`

**Contract Fields**:
- `workflow_config: ModelWorkflowConfig` - Workflow coordination configuration
- `thunk_emission_config: ModelThunkEmissionConfig` - Thunk emission patterns
- `branching_config: ModelBranchingConfig` - Conditional branching
- `event_coordination_config: ModelEventCoordinationConfig` - Event-driven patterns
- `lifecycle_config: ModelLifecycleConfig` - Lifecycle management

---

### NodeReducer

**Location**: `/Volumes/PRO-G40/Code/omnibase_core/archived/src/omnibase_core/core/node_reducer.py`

**Primary Responsibility**: Data aggregation and state reduction operations

**Key Capabilities**:
- State aggregation and data transformation
- Reduce operations (fold, accumulate, merge)
- Streaming support for large datasets
- Conflict resolution strategies
- RSD Data Processing (ticket metadata aggregation)
- Priority score normalization and ranking
- Graph dependency resolution and cycle detection
- Status consolidation across ticket collections

**Core Components**:

```python
class ReductionType(Enum):
    """Types of reduction operations supported."""
    FOLD = "fold"                    # Reduce collection to single value
    ACCUMULATE = "accumulate"        # Build up result incrementally
    MERGE = "merge"                  # Combine multiple datasets
    AGGREGATE = "aggregate"          # Statistical aggregation
    NORMALIZE = "normalize"          # Score normalization and ranking
    DEDUPLICATE = "deduplicate"      # Remove duplicates
    SORT = "sort"                    # Sort and rank operations
    FILTER = "filter"                # Filter with conditions
    GROUP = "group"                  # Group by criteria
    TRANSFORM = "transform"          # Data transformation

class ConflictResolution(Enum):
    """Strategies for resolving conflicts during reduction."""
    FIRST_WINS = "first_wins"        # Keep first encountered value
    LAST_WINS = "last_wins"          # Keep last encountered value
    MERGE = "merge"                  # Attempt to merge values
    ERROR = "error"                  # Raise error on conflict
    CUSTOM = "custom"                # Use custom resolution function

class StreamingMode(Enum):
    """Streaming processing modes."""
    BATCH = "batch"                  # Process all data at once
    INCREMENTAL = "incremental"      # Process data incrementally
    WINDOWED = "windowed"            # Process in time windows
    REAL_TIME = "real_time"          # Process as data arrives
```

**Input/Output Models**:

```python
class ModelReducerInput(BaseModel, Generic[T_Input]):
    """Input model for NodeReducer operations."""
    data: list[T_Input]
    reduction_type: ReductionType
    operation_id: str | None = Field(default_factory=lambda: str(uuid4()))
    conflict_resolution: ConflictResolution = ConflictResolution.LAST_WINS
    streaming_mode: StreamingMode = StreamingMode.BATCH
    batch_size: int = 1000
    window_size_ms: int = 5000
    metadata: dict[str, ModelScalarValue] | None = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)

class ModelReducerOutput(Generic[T_Output]):
    """Output model for NodeReducer operations."""
    result: T_Output
    operation_id: str
    reduction_type: ReductionType
    processing_time_ms: float
    items_processed: int
    conflicts_resolved: int = 0
    streaming_mode: StreamingMode = StreamingMode.BATCH
    batches_processed: int = 1
    metadata: dict[str, str] | None = None
```

**Streaming Window**:

```python
class StreamingWindow:
    """Time-based window for streaming data processing."""

    def __init__(self, window_size_ms: int, overlap_ms: int = 0):
        self.window_size_ms = window_size_ms
        self.overlap_ms = overlap_ms
        self.buffer: deque[Any] = deque()
        self.window_start = datetime.now()

    def add_item(self, item: Any) -> bool:
        """Add item to window, returns True if window is full."""

    def get_window_items(self) -> list[Any]:
        """Get all items in current window."""

    def advance_window(self) -> None:
        """Advance to next window with optional overlap."""
```

**Conflict Resolver**:

```python
class ConflictResolver:
    """Handles conflict resolution during data reduction."""

    def __init__(self, strategy: ConflictResolution, custom_resolver: Callable[..., Any] | None = None):
        self.strategy = strategy
        self.custom_resolver = custom_resolver
        self.conflicts_count = 0

    def resolve(self, existing_value: Any, new_value: Any, key: str | None = None) -> Any:
        """Resolve conflict between existing and new values."""
```

**Base Class Pattern**:

```python
class NodeReducer(NodeCoreBase):
    """Data aggregation and state reduction node."""

    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)
        # Load contract model for Reducer node type
        self.contract_model: ModelContractReducer = self._load_contract_model()

        # Reducer-specific configuration
        self.default_batch_size = 1000
        self.max_memory_usage_mb = 512
        self.streaming_buffer_size = 10000

        # Reduction function registry
        self.reduction_functions: dict[ReductionType, Callable[..., Any]] = {}

        # Performance tracking for reductions
        self.reduction_metrics: dict[str, dict[str, float]] = {}
```

**Contract Model**: `/Volumes/PRO-G40/Code/omnibase_core/src/omnibase_core/models/contracts/model_contract_reducer.py`

**Contract Fields**:
- `reduction_config: ModelReductionConfig` - Reduction operation specifications
- `streaming_config: ModelStreamingConfig` - Streaming processing settings
- `conflict_resolution: ModelConflictResolutionConfig` - Conflict resolution strategy
- `aggregation_subcontract: ModelAggregationSubcontract` - Aggregation patterns
- `memory_management: ModelMemoryManagementConfig` - Memory management settings

---

## Node Architecture Patterns

### Inheritance Hierarchy

All 4 node types inherit from a common base class:

```
NodeCoreBase (Abstract)
    ├── NodeEffect
    ├── NodeCompute
    ├── NodeOrchestrator
    └── NodeReducer
```

**Base Class**: `/Volumes/PRO-G40/Code/omnibase_core/archived/src/omnibase_core/core/node_core_base.py`

**Key Base Class Features**:
- ModelONEXContainer dependency injection
- Contract loading and validation
- Structured logging integration
- Error handling patterns
- Performance monitoring
- UUID correlation tracking

### Common Node Patterns

#### 1. Constructor Pattern

```python
def __init__(self, container: ModelONEXContainer) -> None:
    """Initialize node with ModelONEXContainer dependency injection."""
    super().__init__(container)

    # CANONICAL PATTERN: Load contract model for specific node type
    self.contract_model = self._load_contract_model()

    # Node-specific configuration
    # ...

    # Initialize node-specific components
    # ...
```

#### 2. Contract Loading Pattern

```python
def _load_contract_model(self) -> ModelContract[NodeType]:
    """
    Load and validate contract model for node type.

    CANONICAL PATTERN: Centralized contract loading for all nodes.
    Provides type-safe contract configuration with validation.
    """
    try:
        # Load actual contract from file with subcontract resolution
        contract_path = self._find_contract_path()

        # Load and resolve contract with subcontract support
        yaml_model = load_and_validate_yaml_model(contract_path, ModelGenericYaml)
        contract_data = yaml_model.model_dump()

        # Resolve any $ref references in the contract
        resolved_contract = self._resolve_contract_references(
            contract_data,
            contract_path.parent
        )

        # Create contract model from resolved data
        # Note: Using ModelContract generic with NodeType parameter
        contract_type = ModelContract[NodeType]
        contract_model = contract_type(**resolved_contract)

        # CANONICAL PATTERN: Validate contract model consistency
        contract_model.validate_node_specific_config()

        return contract_model

    except Exception as e:
        raise OnexError(
            code=CoreErrorCode.VALIDATION_ERROR,
            message=f"Contract model loading failed: {e!s}",
            cause=e
        )
```

#### 3. Execution Pattern

```python
async def execute_<node_type>(self, contract: ModelContract[NodeType]) -> ModelOutput[NodeType]:
    """
    Execute <node type> operation based on contract specification.

    Args:
        contract: <Node type> contract with operation specifications

    Returns:
        Model<NodeType>Output: Operation results with metadata

    Raises:
        OnexError: If operation fails
    """
    start_time = time.time()

    try:
        # Validate contract
        self._validate_contract(contract)

        # Execute node-specific operation
        result = await self._execute_operation(contract)

        # Record performance metrics
        execution_time = time.time() - start_time
        self._record_metrics(contract, execution_time)

        # Return typed output
        output_type = ModelOutput[NodeType]
        return output_type(
            correlation_id=contract.correlation_id,
            result=result,
            processing_time_ms=execution_time * 1000,
            metadata=self._generate_metadata(contract)
        )

    except Exception as e:
        execution_time = time.time() - start_time
        self._handle_error(contract, e, execution_time)
        raise OnexError("Operation failed") from e
```

#### 4. Error Handling Pattern

```python
def _handle_error(self, contract: ModelContract, error: Exception, execution_time: float) -> None:
    """Standard error handling with logging and metrics."""
    emit_log_event(
        LogLevel.ERROR,
        f"{self.__class__.__name__} operation failed: {error!s}",
        {
            "correlation_id": str(contract.correlation_id),
            "execution_id": str(contract.execution_id),
            "execution_time_ms": execution_time * 1000,
            "error_type": error.__class__.__name__,
            "node_type": self.__class__.__name__
        }
    )

    # Record error metrics
    self._record_error_metrics(contract, error, execution_time)
```

### Required Methods for Each Node Type

All nodes must implement:

1. `__init__(self, container: ModelONEXContainer)` - Constructor with DI
2. `_load_contract_model(self) -> ModelContract[NodeType]` - Contract loading
3. `execute_<node_type>(self, contract) -> ModelOutput` - Main execution method
4. `_validate_contract(self, contract) -> None` - Contract validation
5. `_execute_operation(self, contract) -> Any` - Core business logic
6. `_record_metrics(self, contract, execution_time) -> None` - Performance tracking

---

## Contract System

### Contract Base Model

**Location**: `/Volumes/PRO-G40/Code/omnibase_core/src/omnibase_core/models/contracts/model_contract_base.py`

All contract models inherit from `ModelContractBase`:

```python
class ModelContractBase(BaseModel, ABC):
    """Abstract base for 4-node architecture contract models."""

    # Core contract identification
    name: str = Field(..., description="Unique contract name")
    version: ModelSemVer = Field(..., description="Semantic version")
    description: str = Field(..., description="Human-readable description")
    node_type: EnumNodeType = Field(..., description="Node type classification")

    # Model specifications
    input_model: str = Field(..., description="Fully qualified input model class name")
    output_model: str = Field(..., description="Fully qualified output model class name")

    # Performance requirements
    performance: ModelPerformanceRequirements = Field(
        default_factory=ModelPerformanceRequirements,
        description="Performance SLA specifications"
    )

    # Lifecycle management
    lifecycle: ModelLifecycleConfig = Field(
        default_factory=ModelLifecycleConfig,
        description="Lifecycle management configuration"
    )

    # Dependencies and protocols
    dependencies: list[ModelDependency] = Field(
        default_factory=list,
        description="Required protocol dependencies"
    )

    protocol_interfaces: list[str] = Field(
        default_factory=list,
        description="Protocol interfaces implemented"
    )

    # Validation and constraints
    validation_rules: ModelValidationRules = Field(
        default_factory=ModelValidationRules,
        description="Contract validation rules"
    )

    @abstractmethod
    def validate_node_specific_config(self) -> None:
        """Validate node-specific configuration requirements."""
```

### Specialized Contract Models

#### 1. ModelContractEffect

**Location**: `/Volumes/PRO-G40/Code/omnibase_core/src/omnibase_core/models/contracts/model_contract_effect.py`

```python
class ModelContractEffect(ModelContractBase):
    """Contract model for NodeEffect implementations."""

    # UUID correlation tracking
    correlation_id: UUID = Field(default_factory=uuid4)
    execution_id: UUID = Field(default_factory=uuid4)

    # Effect-specific configurations
    io_operation_config: ModelIOOperationConfig | None = None
    transaction_config: ModelTransactionConfig | None = None
    external_service_config: ModelExternalServiceConfig | None = None
    effect_retry_config: ModelEffectRetryConfig | None = None
    backup_config: ModelBackupConfig | None = None

    # Subcontracts (composition pattern)
    caching_subcontract: ModelCachingSubcontract | None = None
    event_type_subcontract: ModelEventTypeSubcontract | None = None
    routing_subcontract: ModelRoutingSubcontract | None = None
```

#### 2. ModelContractCompute

**Location**: `/Volumes/PRO-G40/Code/omnibase_core/src/omnibase_core/models/contracts/model_contract_compute.py`

```python
class ModelContractCompute(ModelContractBase):
    """Contract model for NodeCompute implementations."""

    # UUID correlation tracking
    correlation_id: UUID = Field(default_factory=uuid4)
    execution_id: UUID = Field(default_factory=uuid4)

    # Compute-specific configurations
    algorithm_config: ModelAlgorithmConfig | None = None
    caching_config: ModelCachingConfig | None = None
    parallel_config: ModelParallelConfig | None = None
    input_validation: ModelInputValidationConfig | None = None
    output_transformation: ModelOutputTransformationConfig | None = None
```

#### 3. ModelContractOrchestrator

```python
class ModelContractOrchestrator(ModelContractBase):
    """Contract model for NodeOrchestrator implementations."""

    # UUID correlation tracking
    correlation_id: UUID = Field(default_factory=uuid4)
    execution_id: UUID = Field(default_factory=uuid4)

    # Orchestrator-specific configurations
    workflow_config: ModelWorkflowConfig | None = None
    thunk_emission_config: ModelThunkEmissionConfig | None = None
    branching_config: ModelBranchingConfig | None = None
    event_coordination_config: ModelEventCoordinationConfig | None = None
```

#### 4. ModelContractReducer

```python
class ModelContractReducer(ModelContractBase):
    """Contract model for NodeReducer implementations."""

    # UUID correlation tracking
    correlation_id: UUID = Field(default_factory=uuid4)
    execution_id: UUID = Field(default_factory=uuid4)

    # Reducer-specific configurations
    reduction_config: ModelReductionConfig | None = None
    streaming_config: ModelStreamingConfig | None = None
    conflict_resolution: ModelConflictResolutionConfig | None = None
    aggregation_subcontract: ModelAggregationSubcontract | None = None
    memory_management: ModelMemoryManagementConfig | None = None
```

### Subcontracts (Composition Pattern)

**Location**: `/Volumes/PRO-G40/Code/omnibase_core/src/omnibase_core/models/contracts/subcontracts/`

Subcontracts enable clean separation between node logic and functionality patterns:

#### Available Subcontracts:

1. **ModelAggregationSubcontract** - Aggregation patterns for reducers
2. **ModelCachingSubcontract** - Caching strategies across nodes
3. **ModelConfigurationSubcontract** - Dynamic configuration management
4. **ModelEventTypeSubcontract** - Event type definitions
5. **ModelRoutingSubcontract** - Routing patterns for orchestrators
6. **ModelStateManagementSubcontract** - State management patterns
7. **ModelFSMSubcontract** - Finite state machine patterns

Example Subcontract:

```python
class ModelCachingSubcontract(BaseModel):
    """Caching subcontract for cross-node caching strategies."""

    cache_enabled: bool = Field(default=True, description="Enable caching")
    cache_ttl_minutes: int = Field(default=30, description="Cache TTL in minutes")
    cache_key_strategy: str = Field(default="hash", description="Cache key generation strategy")
    cache_invalidation: ModelCacheInvalidation | None = None
    cache_distribution: ModelCacheDistribution | None = None
    cache_performance: ModelCachePerformance | None = None
```

---

## File Organization & Naming Conventions

### Directory Structure

```
omnibase_core/
├── src/omnibase_core/
│   ├── core/                           # Core implementations
│   │   ├── node_core_base.py          # Base class for all nodes
│   │   └── type_constraints.py        # Type constraint protocols
│   ├── models/
│   │   ├── nodes/                     # Node-related models
│   │   │   ├── model_node_type.py    # Node type definitions
│   │   │   ├── model_node_configuration.py
│   │   │   ├── model_node_capability.py
│   │   │   ├── model_node_metadata_info.py
│   │   │   └── ...
│   │   └── contracts/                 # Contract models
│   │       ├── model_contract_base.py        # Base contract
│   │       ├── model_contract_effect.py      # Effect contract
│   │       ├── model_contract_compute.py     # Compute contract
│   │       ├── model_contract_orchestrator.py # Orchestrator contract
│   │       ├── model_contract_reducer.py     # Reducer contract
│   │       └── subcontracts/                 # Subcontract models
│   │           ├── model_aggregation_subcontract.py
│   │           ├── model_caching_subcontract.py
│   │           ├── model_routing_subcontract.py
│   │           └── ...
│   ├── enums/
│   │   ├── enum_node_type.py         # Node type enumerations
│   │   └── enum_node_architecture_type.py
│   └── nodes/                         # Node implementations (current)
│       └── __init__.py
├── archived/src/omnibase_core/core/   # Archived implementations (reference)
│   ├── node_effect.py                 # NodeEffect implementation
│   ├── node_compute.py                # NodeCompute implementation
│   ├── node_orchestrator.py           # NodeOrchestrator implementation
│   ├── node_reducer.py                # NodeReducer implementation
│   ├── node_base.py                   # Legacy base implementation
│   └── contracts/                     # Archived contract models
│       ├── model_contract_effect.py
│       ├── model_contract_compute.py
│       ├── model_contract_orchestrator.py
│       └── model_contract_reducer.py
├── docs/
│   └── ONEX_FOUR_NODE_ARCHITECTURE.md # This architecture documentation
├── tests/
│   └── unit/
│       ├── nodes/                     # Node unit tests
│       ├── models/                    # Model tests
│       └── contracts/                 # Contract tests
└── examples/                          # Implementation examples
```

### Naming Conventions

#### Node Files
- **Pattern**: `node_[type].py`
- **Examples**:
  - `node_effect.py` - Effect node implementation
  - `node_compute.py` - Compute node implementation
  - `node_orchestrator.py` - Orchestrator node implementation
  - `node_reducer.py` - Reducer node implementation

#### Contract Files
- **Pattern**: `model_contract_[type].py`
- **Examples**:
  - `model_contract_effect.py`
  - `model_contract_compute.py`
  - `model_contract_orchestrator.py`
  - `model_contract_reducer.py`

#### Subcontract Files
- **Pattern**: `model_[functionality]_subcontract.py`
- **Examples**:
  - `model_caching_subcontract.py`
  - `model_aggregation_subcontract.py`
  - `model_routing_subcontract.py`
  - `model_event_type_subcontract.py`

#### Service Files
- **Pattern**: `node_[type]_service.py`
- **Examples**:
  - `node_effect_service.py`
  - `node_compute_service.py`
  - `node_orchestrator_service.py`
  - `node_reducer_service.py`

#### Model Files
- **Pattern**: `model_[description].py`
- **Examples**:
  - `model_node_type.py`
  - `model_node_configuration.py`
  - `model_algorithm_config.py`
  - `model_workflow_step.py`

---

## Complete Code Examples

### Example 1: Effect Node - Database Operation

**File**: `node_effect_database.py`

```python
"""
NodeEffect implementation for database operations.

Handles all database interactions with proper connection management,
retry logic, circuit breaker patterns, and transaction support.
"""

import asyncio
from datetime import datetime
from typing import Any
from uuid import uuid4

from omnibase_core.core.node_core_base import NodeCoreBase
from omnibase_core.core.onex_container import ModelONEXContainer
from omnibase_core.models.contracts.model_contract_effect import ModelContractEffect
from omnibase_core.core.errors.core_errors import OnexError, CoreErrorCode
from omnibase_core.core.core_structured_logging import emit_log_event_sync as emit_log_event
from omnibase_core.enums.enum_log_level import EnumLogLevel as LogLevel


class NodeDatabaseWriterEffect(NodeCoreBase):
    """Effect node for database operations."""

    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)

        # Load contract model
        self.contract_model: ModelContractEffect = self._load_contract_model()

        # Database-specific configuration
        self.db_pool = container.get_service("ProtocolDatabasePool")
        self.max_retries = 3
        self.retry_delay_ms = 1000

        # Circuit breaker for database failures
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout_seconds=60
        )

    async def execute_effect(self, contract: ModelContractEffect) -> ModelEffectOutput:
        """Execute database operation with transaction support."""

        # Check circuit breaker
        if not self.circuit_breaker.can_execute():
            raise OnexError(
                code=CoreErrorCode.SERVICE_UNAVAILABLE,
                message="Database circuit breaker is open",
                details={"correlation_id": str(contract.correlation_id)}
            )

        transaction_id = None
        start_time = time.time()

        try:
            # Start transaction if configured
            if contract.transaction_config and contract.transaction_config.enabled:
                transaction_id = await self._begin_transaction(contract)

            # Execute operation with retry
            result = await self._execute_with_retry(contract)

            # Commit transaction
            if transaction_id:
                await self._commit_transaction(transaction_id)

            # Record success
            self.circuit_breaker.record_success()
            execution_time = (time.time() - start_time) * 1000

            emit_log_event(
                LogLevel.INFO,
                "Database operation completed successfully",
                {
                    "correlation_id": str(contract.correlation_id),
                    "execution_time_ms": execution_time,
                    "transaction_id": transaction_id
                }
            )

            return ModelEffectOutput(
                result=result,
                operation_id=str(contract.execution_id),
                effect_type=EffectType.DATABASE_OPERATION,
                transaction_state=TransactionState.COMMITTED,
                processing_time_ms=execution_time,
                metadata={"transaction_id": transaction_id}
            )

        except Exception as e:
            # Rollback transaction on error
            if transaction_id:
                await self._rollback_transaction(transaction_id)

            # Record failure
            self.circuit_breaker.record_failure()

            emit_log_event(
                LogLevel.ERROR,
                f"Database operation failed: {e!s}",
                {
                    "correlation_id": str(contract.correlation_id),
                    "error_type": e.__class__.__name__,
                    "transaction_id": transaction_id
                }
            )

            raise OnexError(
                code=CoreErrorCode.OPERATION_FAILED,
                message=f"Database operation failed: {e!s}",
                cause=e
            )

    async def _execute_with_retry(self, contract: ModelContractEffect) -> Any:
        """Execute database operation with exponential backoff retry."""

        for attempt in range(self.max_retries):
            try:
                async with self.db_pool.acquire() as conn:
                    # Execute the actual database operation
                    query = contract.io_operation_config.parameters["query"]
                    params = contract.io_operation_config.parameters.get("params", {})

                    result = await conn.execute(query, params)
                    return result

            except TemporaryDatabaseError as e:
                if attempt == self.max_retries - 1:
                    raise

                # Exponential backoff
                delay_ms = self.retry_delay_ms * (2 ** attempt)
                await asyncio.sleep(delay_ms / 1000)

                emit_log_event(
                    LogLevel.WARNING,
                    f"Database operation retry attempt {attempt + 1}",
                    {
                        "correlation_id": str(contract.correlation_id),
                        "delay_ms": delay_ms
                    }
                )
```

### Example 2: Compute Node - Data Transformation

**File**: `node_compute_transform.py`

```python
"""
NodeCompute implementation for data transformation.

Handles pure computational operations with caching, parallel processing,
and performance optimization for data transformations.
"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from omnibase_core.core.node_core_base import NodeCoreBase
from omnibase_core.core.onex_container import ModelONEXContainer
from omnibase_core.models.contracts.model_contract_compute import ModelContractCompute


class NodeComputeTransform(NodeCoreBase):
    """Compute node for data transformation operations."""

    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)

        # Load contract model
        self.contract_model: ModelContractCompute = self._load_contract_model()

        # Computation configuration
        self.max_parallel_workers = 4
        self.performance_threshold_ms = 100.0

        # Initialize caching layer
        self.computation_cache = ComputationCache(
            max_size=1000,
            default_ttl_minutes=30
        )

        # Thread pool for parallel execution
        self.thread_pool = ThreadPoolExecutor(max_workers=self.max_parallel_workers)

        # Algorithm registry
        self.algorithm_registry: dict[str, Callable] = {}
        self._register_algorithms()

    def _register_algorithms(self) -> None:
        """Register available transformation algorithms."""
        self.algorithm_registry = {
            "normalize": self._normalize_data,
            "aggregate": self._aggregate_data,
            "transform": self._transform_data,
            "filter": self._filter_data
        }

    async def execute_compute(self, contract: ModelContractCompute) -> ModelComputeOutput:
        """Execute computational transformation."""

        start_time = time.time()
        cache_hit = False

        try:
            # Generate cache key
            cache_key = self._generate_cache_key(contract)

            # Check cache
            if contract.caching_config and contract.caching_config.cache_enabled:
                cached_result = self.computation_cache.get(cache_key)
                if cached_result is not None:
                    cache_hit = True
                    execution_time = (time.time() - start_time) * 1000

                    return ModelComputeOutput(
                        result=cached_result,
                        operation_id=str(contract.execution_id),
                        computation_type=contract.algorithm_config.algorithm_type,
                        processing_time_ms=execution_time,
                        cache_hit=True
                    )

            # Get algorithm
            algorithm = self.algorithm_registry.get(
                contract.algorithm_config.algorithm_type
            )

            if not algorithm:
                raise ValueError(
                    f"Unknown algorithm: {contract.algorithm_config.algorithm_type}"
                )

            # Execute with parallel processing if configured
            if contract.parallel_config and contract.parallel_config.enabled:
                result = await self._execute_parallel(algorithm, contract)
            else:
                result = await self._execute_sequential(algorithm, contract)

            # Cache result
            if contract.caching_config and contract.caching_config.cache_enabled:
                self.computation_cache.put(
                    cache_key,
                    result,
                    ttl_minutes=contract.caching_config.cache_ttl_minutes
                )

            execution_time = (time.time() - start_time) * 1000

            # Check performance threshold
            if execution_time > self.performance_threshold_ms:
                emit_log_event(
                    LogLevel.WARNING,
                    f"Computation exceeded performance threshold: {execution_time}ms",
                    {
                        "correlation_id": str(contract.correlation_id),
                        "threshold_ms": self.performance_threshold_ms
                    }
                )

            return ModelComputeOutput(
                result=result,
                operation_id=str(contract.execution_id),
                computation_type=contract.algorithm_config.algorithm_type,
                processing_time_ms=execution_time,
                cache_hit=False
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            raise OnexError(
                code=CoreErrorCode.COMPUTATION_ERROR,
                message=f"Computation failed: {e!s}",
                cause=e
            )

    async def _execute_parallel(self, algorithm: Callable, contract: ModelContractCompute) -> Any:
        """Execute algorithm with parallel processing."""

        parallel_config = contract.parallel_config
        data = contract.input_data

        # Split data into chunks
        chunk_size = len(data) // parallel_config.worker_count
        chunks = [
            data[i:i + chunk_size]
            for i in range(0, len(data), chunk_size)
        ]

        # Process chunks in parallel
        tasks = [
            asyncio.get_event_loop().run_in_executor(
                self.thread_pool,
                algorithm,
                chunk
            )
            for chunk in chunks
        ]

        results = await asyncio.gather(*tasks)

        # Merge results
        return self._merge_parallel_results(results, parallel_config)

    def _normalize_data(self, data: list[float]) -> list[float]:
        """Normalize data to 0-1 range."""
        min_val = min(data)
        max_val = max(data)
        range_val = max_val - min_val

        if range_val == 0:
            return [0.0] * len(data)

        return [(x - min_val) / range_val for x in data]
```

### Example 3: Contract YAML Definition

**File**: `contract.yaml`

```yaml
# Effect Node Contract Example
name: "database_operations"
version: "1.0.0"
description: "Database operations with transaction support"
node_type: "effect"

# Input/Output models
input_model: "ModelEffectInput"
output_model: "ModelEffectOutput"

# Performance requirements
performance:
  max_execution_time_ms: 5000
  max_memory_mb: 256
  throughput_per_second: 100

# Lifecycle configuration
lifecycle:
  startup_timeout_ms: 10000
  shutdown_timeout_ms: 5000
  health_check_interval_ms: 30000

# Dependencies
dependencies:
  - name: "ProtocolDatabasePool"
    dependency_type: "required"
    version_constraint: ">=1.0.0"
    protocol_interface: "ProtocolConnectionPool"

# I/O operation configuration
io_operation_config:
  operation_type: "database"
  connection_pool_size: 10
  connection_timeout_ms: 5000
  parameters:
    database: "production"
    schema: "public"

# Transaction configuration
transaction_config:
  enabled: true
  isolation_level: "read_committed"
  timeout_ms: 30000
  rollback_on_error: true

# Retry configuration
effect_retry_config:
  enabled: true
  max_retries: 3
  initial_delay_ms: 1000
  max_delay_ms: 10000
  backoff_multiplier: 2.0
  retry_conditions:
    - "TemporaryDatabaseError"
    - "ConnectionTimeout"

# Circuit breaker
circuit_breaker:
  enabled: true
  failure_threshold: 5
  recovery_timeout_seconds: 60
  half_open_max_attempts: 3

# Subcontracts
caching_subcontract:
  cache_enabled: true
  cache_ttl_minutes: 30
  cache_key_strategy: "hash"

event_type_subcontract:
  event_types:
    - name: "DatabaseOperationCompleted"
      description: "Emitted when database operation completes"
      schema:
        correlation_id: "UUID"
        operation_result: "object"
```

---

## Summary

This document provides comprehensive documentation for the ONEX 4-Node Architecture including:

1. **Complete Node Type Definitions** - All 4 node types (Effect, Compute, Orchestrator, Reducer) with full implementation details
2. **Inheritance Hierarchy** - Base classes and common patterns across all nodes
3. **Contract System** - Complete contract model specifications with examples
4. **File Organization** - Directory structure and naming conventions
5. **Code Examples** - Real-world implementation examples for each pattern

All file paths reference actual implementations in the omnibase_core repository at `/Volumes/PRO-G40/Code/omnibase_core`.

---

**Key Takeaways**:

- All nodes inherit from `NodeCoreBase` with standardized patterns
- Contract-driven architecture with strong typing via Pydantic models
- Unidirectional data flow: Effect → Compute → Reducer → Orchestrator
- Subcontract composition pattern for clean separation of concerns
- Comprehensive error handling, performance monitoring, and UUID correlation tracking
- Zero tolerance for `Any` types - all models are strongly typed
