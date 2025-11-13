# Omnibase 3 Contracts and Subcontracts Comprehensive Reference

**Generated**: 2025-10-01
**Source**: /Volumes/PRO-G40/Code/omnibase_3
**Purpose**: Complete documentation of all contract definitions, subcontract implementations, and usage patterns in Omnibase 3

---

## Table of Contents

1. [Overview](#overview)
2. [Contract Architecture](#contract-architecture)
3. [Base Contract Model](#base-contract-model)
4. [Specialized Contract Models](#specialized-contract-models)
   - [Effect Contract](#effect-contract)
   - [Compute Contract](#compute-contract)
   - [Reducer Contract](#reducer-contract)
   - [Orchestrator Contract](#orchestrator-contract)
5. [Subcontract Models](#subcontract-models)
   - [FSM Subcontract](#fsm-subcontract)
   - [Event Type Subcontract](#event-type-subcontract)
   - [Aggregation Subcontract](#aggregation-subcontract)
   - [State Management Subcontract](#state-management-subcontract)
   - [Routing Subcontract](#routing-subcontract)
   - [Caching Subcontract](#caching-subcontract)
6. [Contract Usage Patterns](#contract-usage-patterns)
7. [Node Method Signatures](#node-method-signatures)
8. [Real-World Contract Examples](#real-world-contract-examples)

---

## Overview

Omnibase 3 uses a **contract-driven architecture** where all nodes are defined by YAML contracts that specify their behavior, requirements, and capabilities. The contract system provides:

- **Type Safety**: Strong Pydantic models with zero tolerance for `Any` types
- **Clean Architecture**: Separation between node logic and cross-cutting concerns via subcontracts
- **Validation**: Automatic validation of contract compliance at runtime
- **Flexibility**: Support for both FSM patterns and infrastructure patterns
- **Composition**: Subcontract composition for reusable functionality patterns

### Key Principles

1. **Zero Tolerance**: No `Any` types allowed in contract implementations
2. **Contract-Driven Validation**: Validate only what's specified in the contract
3. **Subcontract Composition**: Clean separation via subcontract models
4. **ONEX Compliance**: Full compliance with ONEX 4-node architecture standards

---

## Contract Architecture

### Contract Hierarchy

```
ModelContractBase (Base)
├── ModelContractEffect (EFFECT nodes)
├── ModelContractCompute (COMPUTE nodes)
├── ModelContractReducer (REDUCER nodes)
└── ModelContractOrchestrator (ORCHESTRATOR nodes)
```

### Subcontract Composition

Contracts compose subcontracts to provide reusable functionality:

```
NodeContract
├── state_transitions: ModelFSMSubcontract (optional)
├── event_type: ModelEventTypeSubcontract (optional)
├── aggregation: ModelAggregationSubcontract (optional)
├── state_management: ModelStateManagementSubcontract (optional)
├── routing: ModelRoutingSubcontract (optional)
└── caching: ModelCachingSubcontract (optional)
```

---

## Base Contract Model

**File**: `/src/omnibase/core/model_contract_base.py`

### Class Definition

```python
class ModelContractBase(BaseModel):
    """
    Base contract model for all ONEX node implementations.

    Provides common contract fields and validation logic shared across
    all node types in the 4-node architecture.

    ZERO TOLERANCE: No Any types allowed in implementation.
    """
```

### Core Fields

```python
# Identity and versioning
node_name: str = Field(..., description="Unique node implementation identifier", min_length=1)
node_version: ModelSemVer = Field(..., description="Node implementation semantic version")
contract_version: ModelSemVer = Field(..., description="Contract specification version")

# Classification
node_type: EnumNodeType = Field(..., description="Node type classification (EFFECT, COMPUTE, REDUCER, ORCHESTRATOR)")
main_tool_class: str = Field(..., description="Main implementation class name", min_length=1)

# Documentation
description: str = Field(..., description="Human-readable node description", min_length=1)
domain: str = Field(..., description="Problem domain classification", min_length=1)

# State specifications
input_state: ModelStateSchema = Field(..., description="Input state schema")
output_state: ModelStateSchema = Field(..., description="Output state schema")

# Performance requirements
performance: ModelPerformanceRequirements = Field(
    default_factory=ModelPerformanceRequirements,
    description="Performance and timing requirements"
)

# Organizational metadata
coordinates: ModelCoordinates = Field(
    default_factory=ModelCoordinates,
    description="Organizational coordinates"
)

# Dependencies and protocols
dependencies: Optional[List[Union[str, Dict[str, str]]]] = Field(
    default=None,
    description="Node dependencies (string or structured format)"
)

protocols: Optional[List[ModelProtocol]] = Field(
    default=None,
    description="Protocol interfaces implemented by the node"
)
```

### Key Methods

```python
def validate_node_specific_config(self, original_contract_data: Optional[Dict] = None) -> None:
    """
    Validate node-specific configuration requirements.
    Override in specialized contracts.
    """
    pass

def validate_subcontract_constraints(self, original_contract_data: Optional[Dict] = None) -> None:
    """
    Validate subcontract architectural constraints.
    Override in specialized contracts to enforce node-specific rules.
    """
    pass
```

### Supporting Models

```python
class ModelSemVer(BaseModel):
    """Semantic version model for contract versioning."""
    major: int = Field(..., ge=0)
    minor: int = Field(..., ge=0)
    patch: int = Field(..., ge=0)

class ModelStateSchema(BaseModel):
    """State schema specification model."""
    type: str = Field(..., description="Schema type (object, array, string, etc.)")
    description: str = Field(..., description="Schema description")
    properties: Optional[Dict[str, Any]] = Field(default=None)
    required: Optional[List[str]] = Field(default=None)

class ModelPerformanceRequirements(BaseModel):
    """Performance requirements specification."""
    single_operation_max_ms: Optional[int] = Field(default=None, ge=1)
    batch_operation_max_ms: Optional[int] = Field(default=None, ge=1)
    throughput_min_ops_per_second: Optional[int] = Field(default=None, ge=1)
    memory_max_mb: Optional[int] = Field(default=None, ge=1)
```

---

## Specialized Contract Models

### Effect Contract

**File**: `/src/omnibase/core/model_contract_effect.py`

**Node Type**: `EFFECT` - Side-effect management and external interactions

#### Purpose

Effect contracts define nodes that handle external I/O operations, database interactions, API calls, and other side effects with transaction support and retry policies.

#### Key Configuration Models

```python
class ModelIOOperationConfig(BaseModel):
    """I/O operation specifications."""
    operation_type: str  # file_read, file_write, db_query, api_call, etc.
    atomic: bool = True
    backup_enabled: bool = False
    permissions: Optional[str] = None
    recursive: bool = False
    buffer_size: int = 8192
    timeout_seconds: int = 30
    validation_enabled: bool = True

class ModelTransactionConfig(BaseModel):
    """Transaction management configuration."""
    enabled: bool = True
    isolation_level: str = "read_committed"
    timeout_seconds: int = 30
    rollback_on_error: bool = True
    lock_timeout_seconds: int = 10
    deadlock_retry_count: int = 3
    consistency_check_enabled: bool = True

class ModelRetryConfig(BaseModel):
    """Retry policies and circuit breaker configuration."""
    max_attempts: int = 3
    backoff_strategy: str = "exponential"  # linear, exponential, constant
    base_delay_ms: int = 100
    max_delay_ms: int = 5000
    jitter_enabled: bool = True
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout_s: int = 60

class ModelExternalServiceConfig(BaseModel):
    """External service integration patterns."""
    service_type: str  # rest_api, graphql, grpc, message_queue, etc.
    endpoint_url: Optional[str] = None
    authentication_method: str = "none"  # bearer_token, api_key, oauth2
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 60
    connection_pooling_enabled: bool = True
    max_connections: int = 10
    timeout_seconds: int = 30
```

#### Effect Contract Definition

```python
class ModelContractEffect(ModelContractBase):
    """
    Contract model for NodeEffect implementations.

    Specialized contract for side-effect nodes with I/O operations,
    transaction management, and external service integration.
    """

    node_type: Literal[EnumNodeType.EFFECT] = EnumNodeType.EFFECT

    # Side-effect configuration
    io_operations: List[ModelIOOperationConfig] = Field(..., min_items=1)
    transaction_management: ModelTransactionConfig = Field(default_factory=ModelTransactionConfig)
    retry_policies: ModelRetryConfig = Field(default_factory=ModelRetryConfig)

    # External service integration
    external_services: List[ModelExternalServiceConfig] = Field(default_factory=list)

    # Backup and recovery
    backup_config: ModelBackupConfig = Field(default_factory=ModelBackupConfig)

    # Effect-specific settings
    idempotent_operations: bool = True
    side_effect_logging_enabled: bool = True
    audit_trail_enabled: bool = True
    consistency_validation_enabled: bool = True
```

#### Node Usage Pattern

```python
# From node_effect.py
class NodeEffect(NodeCoreBase):
    """NodeEffect - Side Effect Management Node."""

    def __init__(self, contract: ModelContractEffect, container: ONEXContainer):
        """Initialize effect node with contract."""
        super().__init__(contract=contract, container=container)
        self.contract: ModelContractEffect = contract

    async def _execute_effect(self, input_data: Dict[str, Any],
                              transaction: Optional[Any] = None) -> Dict[str, Any]:
        """Execute side-effect operations defined in contract."""
        # Implementation uses contract.io_operations, contract.retry_policies, etc.
        pass
```

---

### Compute Contract

**File**: `/src/omnibase/core/model_contract_compute.py`

**Node Type**: `COMPUTE` - Pure computation and data transformation

#### Purpose

Compute contracts define stateless computation nodes that transform data without side effects. They focus on algorithm execution, data processing, and pure functional transformations.

#### Key Configuration Models

```python
class ModelComputationConfig(BaseModel):
    """Computation specifications."""
    algorithm_type: str  # transformation, calculation, analysis, etc.
    complexity_class: str = "polynomial"  # constant, logarithmic, linear, polynomial, exponential
    parallelizable: bool = True
    deterministic: bool = True
    memoization_enabled: bool = False
    cache_results: bool = False

class ModelDataValidation(BaseModel):
    """Input/output data validation."""
    input_validation_enabled: bool = True
    output_validation_enabled: bool = True
    schema_validation: bool = True
    type_checking: bool = True
    range_validation: bool = False
    custom_validators: List[str] = []
```

#### Compute Contract Definition

```python
class ModelContractCompute(ModelContractBase):
    """
    Contract model for NodeCompute implementations.

    Specialized contract for pure computation nodes with algorithm
    specifications and data transformation rules.
    """

    node_type: Literal[EnumNodeType.COMPUTE] = EnumNodeType.COMPUTE

    # Computation configuration
    computation: ModelComputationConfig = Field(default_factory=ModelComputationConfig)
    data_validation: ModelDataValidation = Field(default_factory=ModelDataValidation)

    # Algorithm specifications
    algorithm_description: str = Field(..., min_length=1)
    input_transformations: List[str] = Field(default_factory=list)
    output_transformations: List[str] = Field(default_factory=list)

    # Compute-specific settings
    pure_function: bool = True  # Guaranteed no side effects
    supports_streaming: bool = False
    batch_processing_enabled: bool = False
```

---

### Reducer Contract

**File**: `/src/omnibase/core/model_contract_reducer.py`

**Node Type**: `REDUCER` - Data aggregation and state reduction

#### Purpose

Reducer contracts define nodes that aggregate, consolidate, and reduce data from multiple sources. They handle state management, conflict resolution, and data reduction operations.

#### Key Configuration Models

```python
class ModelReductionConfig(BaseModel):
    """Data reduction operation specifications."""
    operation_type: str  # fold, accumulate, merge, aggregate, etc.
    reduction_function: str
    associative: bool = True
    commutative: bool = False
    identity_element: Optional[str] = None
    chunk_size: int = 1000
    parallel_enabled: bool = True
    intermediate_results_caching: bool = True

class ModelStreamingConfig(BaseModel):
    """Streaming configuration for large datasets."""
    enabled: bool = True
    buffer_size: int = 8192
    window_size: int = 1000
    memory_threshold_mb: int = 512
    backpressure_enabled: bool = True

class ModelConflictResolutionConfig(BaseModel):
    """Conflict resolution strategies."""
    strategy: str = "last_writer_wins"  # first_writer_wins, merge, manual
    detection_enabled: bool = True
    timestamp_based_resolution: bool = True
    conflict_logging_enabled: bool = True

class ModelMemoryManagementConfig(BaseModel):
    """Memory management for batch processing."""
    max_memory_mb: int = 1024
    gc_threshold: float = 0.8  # 0.0-1.0
    lazy_loading_enabled: bool = True
    spill_to_disk_enabled: bool = True
```

#### Reducer Contract Definition

```python
class ModelContractReducer(ModelContractBase):
    """
    Contract model for NodeReducer implementations.

    Specialized contract for data aggregation nodes using subcontract composition
    for clean separation between node logic and functionality patterns.
    """

    node_type: Literal[EnumNodeType.REDUCER] = Field(
        default=EnumNodeType.REDUCER,
        description="Node type classification"
    )

    # Core reduction functionality
    reduction_operations: Optional[List[ModelReductionConfig]] = None
    streaming: Optional[ModelStreamingConfig] = None
    conflict_resolution: Optional[ModelConflictResolutionConfig] = None
    memory_management: Optional[ModelMemoryManagementConfig] = None

    # Reducer-specific settings
    order_preserving: bool = False
    incremental_processing: bool = True
    result_caching_enabled: bool = True
    partial_results_enabled: bool = True

    # SUBCONTRACT COMPOSITION
    state_transitions: Optional[Union[ModelFSMSubcontract, Dict[str, str]]] = None
    event_type: Optional[ModelEventTypeSubcontract] = None
    aggregation: Optional[ModelAggregationSubcontract] = None
    state_management: Optional[ModelStateManagementSubcontract] = None
    caching: Optional[ModelCachingSubcontract] = None

    # Infrastructure pattern support (backward compatibility)
    dependencies: Optional[List[Union[str, Dict[str, str], ModelDependencySpec]]] = None
    tool_specification: Optional[Dict[str, Any]] = None
    service_configuration: Optional[Dict[str, Any]] = None
    input_state: Optional[Dict[str, Any]] = None
    output_state: Optional[Dict[str, Any]] = None
    actions: Optional[List[Dict[str, Any]]] = None
    infrastructure: Optional[Dict[str, Any]] = None
    validation_rules: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None
```

#### Validation Methods

```python
def validate_subcontract_constraints(self, original_contract_data: Optional[Dict] = None) -> None:
    """
    Validate REDUCER node subcontract architectural constraints.

    REDUCER nodes are stateful and should have state_transitions subcontracts.
    They can have aggregation and state_management subcontracts.
    """
    violations = []

    # REDUCER nodes should have state_transitions
    if "state_transitions" not in contract_data:
        violations.append("⚠️ MISSING SUBCONTRACT: REDUCER nodes should have state_transitions")
        violations.append("   💡 Add state_transitions for proper stateful workflow management")

    # All nodes should have event_type
    if "event_type" not in contract_data:
        violations.append("⚠️ MISSING SUBCONTRACT: All nodes should define event_type")
        violations.append("   💡 Add event_type configuration for event-driven architecture")

    if violations:
        raise ValueError("\n".join(violations))
```

---

### Orchestrator Contract

**File**: `/src/omnibase/core/model_contract_orchestrator.py`

**Node Type**: `ORCHESTRATOR` - Workflow coordination and thunk emission

#### Purpose

Orchestrator contracts define nodes that coordinate complex workflows, emit thunks for deferred execution, manage conditional branching, and integrate with Event Registry for event-driven coordination.

#### Key Configuration Models

```python
class ModelThunkEmissionConfig(BaseModel):
    """Thunk emission patterns and deferred execution rules."""
    emission_strategy: str = "on_demand"  # batch, scheduled, event_driven
    batch_size: int = 10
    max_deferred_thunks: int = 1000
    execution_delay_ms: int = 0
    priority_based_emission: bool = True
    dependency_aware_emission: bool = True
    retry_failed_thunks: bool = True

class ModelWorkflowDefinition(BaseModel):
    """Individual workflow definition with execution patterns."""
    workflow_id: str
    workflow_name: str
    workflow_type: str = "sequential"  # parallel, conditional, saga, pipeline
    steps: List[Dict[str, Union[str, int, bool]]] = []
    dependencies: List[str] = []
    conditions: Optional[Dict[str, Union[str, bool, int]]] = None
    compensation_plan: Optional[Dict[str, Union[str, List[str]]]] = None
    priority: int = 100  # 1-1000

class ModelWorkflowRegistry(BaseModel):
    """Registry of available workflows."""
    workflows: Dict[str, ModelWorkflowDefinition] = {}
    default_workflow_id: str
    workflow_selection_strategy: str = "explicit"  # conditional, priority_based, load_balanced
    max_concurrent_workflows: int = 10

class ModelBranchingConfig(BaseModel):
    """Conditional branching logic and decision trees."""
    decision_points: List[str] = []
    condition_evaluation_strategy: str = "eager"  # lazy, cached
    branch_merge_strategy: str = "wait_all"  # wait_any, wait_majority
    default_branch_enabled: bool = True
    condition_timeout_ms: int = 1000
    nested_branching_enabled: bool = True
    max_branch_depth: int = 10

class ModelEventRegistryConfig(BaseModel):
    """Event Registry integration configuration."""
    discovery_enabled: bool = True
    auto_provisioning_enabled: bool = True
    registry_endpoint: Optional[str] = None
    health_check_enabled: bool = True
    health_check_interval_s: int = 30
    cache_enabled: bool = True
    cache_ttl_s: int = 300
    security_enabled: bool = True
```

#### Orchestrator Contract Definition

```python
class ModelContractOrchestrator(ModelContractBase):
    """
    Contract model for NodeOrchestrator implementations.

    Specialized contract for workflow coordination nodes using subcontract composition.
    Handles thunk emission, conditional branching, and Event Registry integration.
    """

    node_type: Literal[EnumNodeType.ORCHESTRATOR] = Field(
        default=EnumNodeType.ORCHESTRATOR,
        description="Node type classification"
    )

    # Core orchestration functionality
    thunk_emission: ModelThunkEmissionConfig = Field(default_factory=ModelThunkEmissionConfig)
    workflow_coordination: ModelWorkflowConfig = Field(default_factory=ModelWorkflowConfig)
    workflow_registry: ModelWorkflowRegistry = Field(...)
    conditional_branching: ModelBranchingConfig = Field(default_factory=ModelBranchingConfig)

    # Event Registry integration
    event_registry: ModelEventRegistryConfig = Field(default_factory=ModelEventRegistryConfig)
    published_events: List[ModelEventDescriptor] = []
    consumed_events: List[ModelEventSubscription] = []
    event_coordination: ModelEventCoordinationConfig = Field(default_factory=ModelEventCoordinationConfig)

    # Orchestrator-specific settings
    load_balancing_enabled: bool = True
    failure_isolation_enabled: bool = True
    monitoring_enabled: bool = True
    metrics_collection_enabled: bool = True

    # SUBCONTRACT COMPOSITION
    event_type: Optional[ModelEventTypeSubcontract] = None
    routing: Optional[ModelRoutingSubcontract] = None
    state_management: Optional[ModelStateManagementSubcontract] = None

    # Infrastructure pattern support
    node_name: str = Field(..., min_length=1)
    main_tool_class: str = Field(..., min_length=1)
    dependencies: Optional[List[Union[str, Dict[str, str], ModelDependencySpec]]] = None
```

#### Validation Methods

```python
def validate_subcontract_constraints(self, original_contract_data: Optional[Dict] = None) -> None:
    """
    Validate ORCHESTRATOR node subcontract architectural constraints.

    ORCHESTRATOR nodes coordinate workflows and can have routing and state_management
    subcontracts, but should not have aggregation subcontracts.
    """
    violations = []

    # ORCHESTRATOR nodes should not have aggregation
    if "aggregation" in contract_data:
        violations.append("❌ SUBCONTRACT VIOLATION: ORCHESTRATOR nodes should not have aggregation")
        violations.append("   💡 Use REDUCER nodes for data aggregation")

    # All nodes should have event_type
    if "event_type" not in contract_data:
        violations.append("⚠️ MISSING SUBCONTRACT: All nodes should define event_type")
        violations.append("   💡 Add event_type configuration for event-driven architecture")

    if violations:
        raise ValueError("\n".join(violations))
```

---

## Subcontract Models

### FSM Subcontract

**File**: `/src/omnibase/core/subcontracts/model_fsm_subcontract.py`

**Purpose**: Finite State Machine functionality for stateful workflows

#### FSM State Definition

```python
class ModelFSMStateDefinition(BaseModel):
    """State definition for FSM subcontract."""
    state_name: str
    state_type: str  # operational, snapshot, error, terminal
    description: str
    is_terminal: bool = False
    is_recoverable: bool = True
    timeout_ms: Optional[int] = None
    entry_actions: List[str] = []
    exit_actions: List[str] = []
    required_data: List[str] = []
    optional_data: List[str] = []
    validation_rules: List[str] = []
```

#### FSM Transition Specification

```python
class ModelFSMStateTransition(BaseModel):
    """State transition specification."""
    transition_name: str
    from_state: str
    to_state: str
    trigger: str
    priority: int = 1
    conditions: List[ModelFSMTransitionCondition] = []
    actions: List[ModelFSMTransitionAction] = []
    rollback_transitions: List[str] = []
    is_atomic: bool = True
    retry_enabled: bool = False
    max_retries: int = 0
    retry_delay_ms: int = 1000

class ModelFSMTransitionCondition(BaseModel):
    """Condition specification for transitions."""
    condition_name: str
    condition_type: str  # validation, state, processing, custom
    expression: str
    required: bool = True
    error_message: Optional[str] = None
    retry_count: int = 0
    timeout_ms: Optional[int] = None

class ModelFSMTransitionAction(BaseModel):
    """Action specification for transitions."""
    action_name: str
    action_type: str  # log, validate, modify, event, cleanup
    action_config: Dict[str, Union[str, int, float, bool, List[str]]] = {}
    execution_order: int = 1
    is_critical: bool = False
    rollback_action: Optional[str] = None
    timeout_ms: Optional[int] = None
```

#### FSM Operation Definition

```python
class ModelFSMOperation(BaseModel):
    """Operation specification for FSM."""
    operation_name: str
    operation_type: str  # create, update, delete, transition, snapshot, restore
    description: str
    requires_atomic_execution: bool = True
    supports_rollback: bool = True
    allowed_from_states: List[str] = []
    blocked_from_states: List[str] = []
    required_permissions: List[str] = []
    side_effects: List[str] = []
    performance_impact: str = "low"  # medium, high
    timeout_ms: Optional[int] = None
```

#### FSM Subcontract Model

```python
class ModelFSMSubcontract(BaseModel):
    """
    FSM (Finite State Machine) subcontract model.

    Comprehensive state machine subcontract providing state definitions,
    transitions, operations, validation, and recovery mechanisms.
    """

    # Core FSM identification
    state_machine_name: str
    state_machine_version: str
    description: str

    # State definitions
    states: List[ModelFSMStateDefinition] = Field(..., min_length=1)
    initial_state: str
    terminal_states: List[str] = []
    error_states: List[str] = []

    # Transition specifications
    transitions: List[ModelFSMStateTransition] = Field(..., min_length=1)

    # Operation definitions
    operations: List[ModelFSMOperation] = []

    # FSM persistence and recovery
    persistence_enabled: bool = True
    checkpoint_interval_ms: int = 30000
    max_checkpoints: int = 10
    recovery_enabled: bool = True
    rollback_enabled: bool = True

    # Conflict resolution
    conflict_resolution_strategy: str = "priority_based"
    concurrent_transitions_allowed: bool = False
    transition_timeout_ms: int = 5000

    # Validation and monitoring
    strict_validation_enabled: bool = True
    state_monitoring_enabled: bool = True
    event_logging_enabled: bool = True
```

---

### Event Type Subcontract

**File**: `/src/omnibase/core/subcontracts/model_event_type_subcontract.py`

**Purpose**: Event-driven architecture functionality

#### Event Definition

```python
class ModelEventDefinition(BaseModel):
    """Event definition for event-driven architecture."""
    event_name: str
    event_category: str
    description: str
    schema_version: str = "1.0.0"
    required_fields: List[str] = []
    optional_fields: List[str] = []
    routing_key: Optional[str] = None
    priority: int = 1  # 1-10
    ttl_seconds: Optional[int] = None
```

#### Event Transformation

```python
class ModelEventTransformation(BaseModel):
    """Event transformation specification."""
    transformation_name: str
    transformation_type: str  # filter, map, enrich, validate
    conditions: List[str] = []
    mapping_rules: Dict[str, str] = {}
    enrichment_sources: List[str] = []
    validation_schema: Optional[str] = None
    execution_order: int = 1
```

#### Event Routing

```python
class ModelEventRouting(BaseModel):
    """Event routing configuration."""
    routing_strategy: str  # broadcast, unicast, multicast, topic
    target_groups: List[str] = []
    routing_rules: List[str] = []
    load_balancing: str = "round_robin"
    retry_policy: Dict[str, Union[int, bool]] = {}
    dead_letter_queue: Optional[str] = None
    circuit_breaker_enabled: bool = False
```

#### Event Type Subcontract Model

```python
class ModelEventTypeSubcontract(BaseModel):
    """
    Event Type subcontract model for event-driven architecture.

    Comprehensive event handling subcontract providing event definitions,
    transformations, routing, and persistence configuration.
    """

    # Primary event configuration
    primary_events: List[str] = Field(..., min_length=1)
    event_categories: List[str] = Field(..., min_length=1)

    # Event behavior
    publish_events: bool = True
    subscribe_events: bool = False
    event_routing: str

    # Advanced event definitions
    event_definitions: List[ModelEventDefinition] = []
    transformations: List[ModelEventTransformation] = []
    routing_config: Optional[ModelEventRouting] = None
    persistence_config: Optional[ModelEventPersistence] = None

    # Event filtering and processing
    event_filters: List[str] = []
    batch_processing: bool = False
    batch_size: int = 100
    batch_timeout_ms: int = 5000

    # Event ordering and delivery
    ordering_required: bool = False
    delivery_guarantee: str = "at_least_once"  # at_most_once, exactly_once
    deduplication_enabled: bool = False
    deduplication_window_ms: int = 60000

    # Performance and monitoring
    async_processing: bool = True
    max_concurrent_events: int = 100
    event_metrics_enabled: bool = True
    event_tracing_enabled: bool = False
```

---

### Aggregation Subcontract

**File**: `/src/omnibase/core/subcontracts/model_aggregation_subcontract.py`

**Purpose**: Data aggregation functionality

#### Aggregation Function

```python
class ModelAggregationFunction(BaseModel):
    """Aggregation function definition."""
    function_name: str
    function_type: str  # statistical, mathematical, custom
    description: str
    input_fields: List[str]
    output_field: str
    parameters: Dict[str, Union[str, int, float, bool]] = {}
    null_handling: str = "ignore"
    precision_digits: int = 6
    requires_sorting: bool = False
    is_associative: bool = False
    is_commutative: bool = False
```

#### Data Grouping

```python
class ModelDataGrouping(BaseModel):
    """Data grouping configuration."""
    grouping_enabled: bool = True
    grouping_fields: List[str] = []
    grouping_strategy: str = "hash_based"
    case_sensitive_grouping: bool = True
    null_group_handling: str = "separate"
    max_groups: Optional[int] = None
    group_expiration_ms: Optional[int] = None
```

#### Windowing Strategy

```python
class ModelWindowingStrategy(BaseModel):
    """Windowing strategy for time-based aggregation."""
    windowing_enabled: bool = False
    window_type: str = "tumbling"  # sliding, session
    window_size_ms: int = 60000
    window_slide_ms: Optional[int] = None
    session_timeout_ms: Optional[int] = None
    window_trigger: str = "time_based"
    late_arrival_handling: str = "ignore"
    allowed_lateness_ms: int = 10000
    watermark_strategy: str = "event_time"
```

#### Aggregation Subcontract Model

```python
class ModelAggregationSubcontract(BaseModel):
    """
    Aggregation subcontract model for data aggregation functionality.

    Comprehensive aggregation subcontract providing aggregation functions,
    grouping strategies, windowing, and statistical computations.
    """

    # Core aggregation configuration
    aggregation_enabled: bool = True
    aggregation_mode: str = "batch"  # streaming, hybrid

    # Aggregation functions
    aggregation_functions: List[str] = Field(..., min_length=1)
    function_definitions: List[ModelAggregationFunction] = []

    # Data grouping
    grouping: ModelDataGrouping = Field(default_factory=ModelDataGrouping)

    # Windowing strategy
    windowing: Optional[ModelWindowingStrategy] = None

    # Statistical computations
    statistical: Optional[ModelStatisticalComputation] = None

    # Performance optimization
    performance: ModelAggregationPerformance = Field(default_factory=ModelAggregationPerformance)

    # Data handling and quality
    null_handling_strategy: str = "ignore"
    duplicate_handling: str = "include"
    data_validation_enabled: bool = True
    schema_enforcement: bool = True

    # Output configuration
    output_format: str = "structured"
    result_caching: bool = True
    result_ttl_seconds: int = 300
    incremental_updates: bool = False

    # Monitoring and metrics
    metrics_enabled: bool = True
    performance_monitoring: bool = True
    memory_usage_tracking: bool = False

    # Error handling
    error_handling_strategy: str = "continue"
    partial_results_on_error: bool = True
    retry_failed_aggregations: bool = False
    max_retries: int = 3
```

#### Supported Aggregation Functions

```python
SUPPORTED_FUNCTIONS = {
    # Basic aggregations
    "sum", "count", "avg", "min", "max", "median", "std", "var",
    "percentile", "mode", "first", "last", "unique_count",

    # Infrastructure-specific
    "status_merge", "health_aggregate", "result_combine",

    # Statistical
    "skewness", "kurtosis", "correlation", "covariance"
}
```

---

### State Management Subcontract

**File**: `/src/omnibase/core/subcontracts/model_state_management_subcontract.py`

**Purpose**: State persistence and synchronization

#### State Persistence

```python
class ModelStatePersistence(BaseModel):
    """State persistence configuration."""
    persistence_enabled: bool = True
    storage_backend: str = "postgresql"
    backup_enabled: bool = True
    backup_interval_ms: int = 300000
    backup_retention_days: int = 7
    checkpoint_enabled: bool = True
    checkpoint_interval_ms: int = 60000
    recovery_enabled: bool = True
    compression_enabled: bool = False
```

#### State Validation

```python
class ModelStateValidation(BaseModel):
    """State validation configuration."""
    validation_enabled: bool = True
    schema_validation: bool = True
    integrity_checks: bool = True
    consistency_checks: bool = False
    validation_rules: List[str] = []
    repair_enabled: bool = False
    repair_strategies: List[str] = []
```

#### State Synchronization

```python
class ModelStateSynchronization(BaseModel):
    """State synchronization configuration."""
    synchronization_enabled: bool = False
    consistency_level: str = "eventual"
    sync_interval_ms: int = 30000
    conflict_resolution: str = "timestamp_based"
    replication_factor: int = 1
    leader_election_enabled: bool = False
    distributed_locking: bool = False
```

#### State Management Subcontract Model

```python
class ModelStateManagementSubcontract(BaseModel):
    """
    State Management subcontract model for state handling functionality.

    Comprehensive state management subcontract providing persistence,
    validation, synchronization, and versioning capabilities.
    """

    # Core state management
    state_management_enabled: bool = True
    state_scope: str = "node_local"
    state_lifecycle: str = "persistent"

    # State persistence
    persistence: ModelStatePersistence = Field(default_factory=ModelStatePersistence)

    # State validation
    validation: ModelStateValidation = Field(default_factory=ModelStateValidation)

    # State synchronization
    synchronization: Optional[ModelStateSynchronization] = None

    # State versioning
    versioning: ModelStateVersioning = Field(default_factory=ModelStateVersioning)

    # State access and concurrency
    concurrent_access_enabled: bool = True
    locking_strategy: str = "optimistic"
    transaction_support: bool = True
    isolation_level: str = "read_committed"

    # State caching and performance
    caching_enabled: bool = True
    cache_size: int = 1000
    cache_ttl_seconds: int = 300
    lazy_loading: bool = True

    # State monitoring
    monitoring_enabled: bool = True
    metrics_collection: bool = True
    performance_tracking: bool = False
    alert_on_corruption: bool = True

    # State security
    encryption_enabled: bool = False
    encryption_algorithm: str = "aes256"
    key_rotation_enabled: bool = False
    access_control_enabled: bool = False

    # State cleanup
    cleanup_enabled: bool = True
    cleanup_interval_ms: int = 3600000
    orphan_cleanup: bool = True
    compaction_enabled: bool = False
```

---

### Routing Subcontract

**File**: `/src/omnibase/core/subcontracts/model_routing_subcontract.py`

**Purpose**: Request routing and load balancing

#### Route Definition

```python
class ModelRouteDefinition(BaseModel):
    """Route definition for request routing."""
    route_name: str
    route_pattern: str
    method: Optional[str] = None  # GET, POST, etc.
    conditions: List[str] = []
    targets: List[str]
    weight: int = 100  # 0-1000
    priority: int = 1
    timeout_ms: int = 30000
    retry_enabled: bool = True
    max_retries: int = 3
```

#### Load Balancing

```python
class ModelLoadBalancing(BaseModel):
    """Load balancing configuration."""
    strategy: str = "round_robin"
    health_check_enabled: bool = True
    health_check_path: str = "/health"
    health_check_interval_ms: int = 30000
    health_check_timeout_ms: int = 5000
    unhealthy_threshold: int = 3
    healthy_threshold: int = 2
    sticky_sessions: bool = False
    session_affinity_cookie: Optional[str] = None
```

#### Circuit Breaker

```python
class ModelCircuitBreaker(BaseModel):
    """Circuit breaker configuration."""
    enabled: bool = True
    failure_threshold: int = 5
    success_threshold: int = 3
    timeout_ms: int = 60000
    half_open_max_calls: int = 3
    failure_rate_threshold: float = 0.5
    minimum_calls: int = 10
    slow_call_duration_ms: int = 60000
    slow_call_rate_threshold: float = 0.6
```

#### Routing Subcontract Model

```python
class ModelRoutingSubcontract(BaseModel):
    """
    Routing subcontract model for request routing functionality.

    Comprehensive routing subcontract providing route definitions,
    load balancing, circuit breaking, and request transformation.
    """

    # Core routing configuration
    routing_enabled: bool = True
    routing_strategy: str = "path_based"
    default_target: Optional[str] = None

    # Route definitions
    routes: List[ModelRouteDefinition] = []

    # Load balancing
    load_balancing: ModelLoadBalancing = Field(default_factory=ModelLoadBalancing)

    # Circuit breaker
    circuit_breaker: ModelCircuitBreaker = Field(default_factory=ModelCircuitBreaker)

    # Request/Response transformation
    transformation: ModelRequestTransformation = Field(default_factory=ModelRequestTransformation)

    # Routing metrics
    metrics: ModelRoutingMetrics = Field(default_factory=ModelRoutingMetrics)

    # Advanced features
    rate_limiting_enabled: bool = False
    rate_limit_requests_per_minute: int = 1000
    cors_enabled: bool = False
    cors_origins: List[str] = []

    # Security
    authentication_required: bool = False
    authorization_rules: List[str] = []

    # Request logging
    request_logging: bool = True
    trace_sampling_rate: float = 0.1

    # Connection management
    connection_pool_size: int = 100
    keep_alive_timeout_ms: int = 60000
    idle_timeout_ms: int = 300000

    # Failover
    failover_enabled: bool = True
    backup_targets: List[str] = []
    disaster_recovery_mode: bool = False
```

---

### Caching Subcontract

**File**: `/src/omnibase/core/subcontracts/model_caching_subcontract.py`

**Purpose**: Caching and performance optimization

#### Cache Key Strategy

```python
class ModelCacheKeyStrategy(BaseModel):
    """Cache key generation strategy."""
    key_generation_method: str
    namespace: Optional[str] = None
    include_version: bool = True
    hash_algorithm: str = "sha256"
    key_separator: str = ":"
    max_key_length: int = 250
```

#### Cache Invalidation

```python
class ModelCacheInvalidation(BaseModel):
    """Cache invalidation policy."""
    invalidation_strategy: str
    ttl_seconds: int = 300
    max_idle_seconds: int = 600
    invalidation_triggers: List[str] = []
    batch_invalidation: bool = False
    lazy_expiration: bool = True
```

#### Caching Subcontract Model

```python
class ModelCachingSubcontract(BaseModel):
    """
    Caching subcontract model for cache functionality.

    Comprehensive caching subcontract providing cache strategies,
    key generation, invalidation policies, and performance tuning.
    """

    # Core caching configuration
    caching_enabled: bool = True
    cache_strategy: str = "lru"
    cache_backend: str = "memory"

    # Cache sizing
    max_entries: int = 10000
    max_memory_mb: int = 512
    entry_size_limit_kb: int = 1024

    # Cache key management
    key_strategy: ModelCacheKeyStrategy

    # Cache invalidation
    invalidation_policy: ModelCacheInvalidation

    # Distributed caching
    distribution_config: Optional[ModelCacheDistribution] = None

    # Performance tuning
    performance_config: ModelCachePerformance = Field(default_factory=ModelCachePerformance)

    # Cache warming
    warm_up_enabled: bool = False
    warm_up_sources: List[str] = []
    warm_up_batch_size: int = 100

    # Cache monitoring
    metrics_enabled: bool = True
    detailed_metrics: bool = False
    hit_ratio_threshold: float = 0.8
    performance_monitoring: bool = True

    # Cache persistence
    persistence_enabled: bool = False
    persistence_interval_ms: int = 60000
    recovery_enabled: bool = False

    # Multi-level caching
    multi_level_enabled: bool = False
    l1_cache_size: int = 1000
    l2_cache_size: int = 10000
    promotion_threshold: int = 3
```

---

## Contract Usage Patterns

### Pattern 1: Basic Node with Contract

```python
# Define contract in YAML
contract_yaml = """
name: MyComputeNode
node_name: MyComputeNode
node_version: {major: 1, minor: 0, patch: 0}
contract_version: {major: 1, minor: 0, patch: 0}
node_type: COMPUTE
description: Example compute node
domain: computation

input_state:
  type: object
  properties:
    input_data:
      type: array
      items:
        type: integer

output_state:
  type: object
  properties:
    result:
      type: integer
"""

# Load and validate contract
from omnibase.core.model_contract_compute import ModelContractCompute
import yaml

contract_data = yaml.safe_load(contract_yaml)
contract = ModelContractCompute(**contract_data)

# Use contract in node implementation
from omnibase.core.node_compute import NodeCompute

class MyComputeNode(NodeCompute):
    def __init__(self, contract: ModelContractCompute, container):
        super().__init__(contract=contract, container=container)

    async def execute_compute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        # Access contract specifications
        algorithm = self.contract.algorithm_description

        # Perform computation
        result = sum(input_data['input_data'])

        return {'result': result}
```

### Pattern 2: Node with FSM Subcontract

```python
# Contract YAML with FSM subcontract
contract_yaml = """
name: StatefulProcessor
node_type: REDUCER
description: Stateful data processor with FSM

state_transitions:
  state_machine_name: processor_fsm
  state_machine_version: "1.0.0"
  description: Processing state machine

  initial_state: idle

  states:
    - state_name: idle
      state_type: operational
      description: Waiting for work
      is_terminal: false

    - state_name: processing
      state_type: operational
      description: Processing data
      is_terminal: false

    - state_name: completed
      state_type: terminal
      description: Processing completed
      is_terminal: true

  transitions:
    - transition_name: start_processing
      from_state: idle
      to_state: processing
      trigger: process_request
      is_atomic: true

    - transition_name: finish_processing
      from_state: processing
      to_state: completed
      trigger: processing_done
      is_atomic: true
"""

# Load contract with FSM subcontract
from omnibase.core.model_contract_reducer import ModelContractReducer

contract = ModelContractReducer(**yaml.safe_load(contract_yaml))

# Access FSM subcontract
if contract.state_transitions:
    fsm = contract.state_transitions
    print(f"Initial state: {fsm.initial_state}")
    print(f"Number of states: {len(fsm.states)}")
    print(f"Number of transitions: {len(fsm.transitions)}")
```

### Pattern 3: Node with Multiple Subcontracts

```python
# Contract with multiple subcontracts
contract_yaml = """
name: AdvancedReducer
node_type: REDUCER

# FSM subcontract for state management
state_transitions:
  state_machine_name: advanced_fsm
  state_machine_version: "1.0.0"
  description: Advanced processing FSM
  initial_state: ready
  states: [...]
  transitions: [...]

# Event Type subcontract
event_type:
  primary_events: [data_received, processing_complete]
  event_categories: [data_processing, system_events]
  event_routing: processing_queue
  publish_events: true
  subscribe_events: true

# Aggregation subcontract
aggregation:
  aggregation_enabled: true
  aggregation_mode: streaming
  aggregation_functions: [sum, avg, count]
  grouping:
    grouping_enabled: true
    grouping_fields: [category, timestamp]

# State Management subcontract
state_management:
  state_management_enabled: true
  persistence:
    persistence_enabled: true
    storage_backend: postgresql
    checkpoint_enabled: true

# Caching subcontract
caching:
  caching_enabled: true
  cache_strategy: lru
  max_entries: 10000
  key_strategy:
    key_generation_method: composite_hash
"""

# Access all subcontracts
contract = ModelContractReducer(**yaml.safe_load(contract_yaml))

# FSM functionality
if contract.state_transitions:
    fsm = contract.state_transitions
    # Use FSM for state management

# Event functionality
if contract.event_type:
    events = contract.event_type
    # Use event publishing/subscription

# Aggregation functionality
if contract.aggregation:
    agg = contract.aggregation
    # Use aggregation functions

# State management
if contract.state_management:
    state_mgmt = contract.state_management
    # Use state persistence

# Caching
if contract.caching:
    cache = contract.caching
    # Use caching functionality
```

### Pattern 4: Infrastructure Pattern Support

```python
# Contract supporting infrastructure patterns
contract_yaml = """
name: InfrastructureNode
node_type: REDUCER
node_name: InfrastructureNode

# Infrastructure-specific fields
tool_specification:
  tool_name: InfrastructureTool
  main_tool_class: InfrastructureNodeImpl

service_configuration:
  service_type: monitoring
  endpoint: http://localhost:8080

dependencies:
  - name: database
    type: protocol
    class_name: ProtocolDatabaseManager
    module: omnibase.protocols.database

actions:
  - name: monitor
    type: health_check
    schedule: "*/5 * * * *"

validation_rules:
  - rule: service_accessible
    severity: error
    validation_expression: "endpoint.is_accessible()"
"""

# Load infrastructure contract
contract = ModelContractReducer(**yaml.safe_load(contract_yaml))

# Access infrastructure fields
if contract.tool_specification:
    tool_name = contract.tool_specification['tool_name']
    main_class = contract.tool_specification['main_tool_class']

if contract.dependencies:
    for dep in contract.dependencies:
        if isinstance(dep, str):
            # Simple string dependency
            print(f"Dependency: {dep}")
        elif isinstance(dep, dict):
            # Dict format dependency
            print(f"Dependency: {dep.get('name')}")
        else:
            # Structured ModelDependencySpec
            print(f"Dependency: {dep.name} ({dep.type})")
```

---

## Node Method Signatures

### EFFECT Node Methods

```python
class NodeEffect(NodeCoreBase):
    """Side-effect management node."""

    async def execute_effect(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute side-effect operations.

        Args:
            input_data: Input data conforming to contract.input_state
            context: Optional execution context

        Returns:
            Output data conforming to contract.output_state
        """
        pass

    async def _execute_effect(
        self,
        input_data: Dict[str, Any],
        transaction: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Internal effect execution with transaction support.

        Uses contract.io_operations, contract.retry_policies, etc.
        """
        pass
```

### COMPUTE Node Methods

```python
class NodeCompute(NodeCoreBase):
    """Pure computation node."""

    async def execute_compute(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute pure computation.

        Args:
            input_data: Input data conforming to contract.input_state
            context: Optional execution context

        Returns:
            Output data conforming to contract.output_state
        """
        pass

    def _validate_computation_purity(self) -> bool:
        """
        Validate that computation is pure (no side effects).

        Uses contract.pure_function flag.
        """
        return self.contract.pure_function
```

### REDUCER Node Methods

```python
class NodeReducer(NodeCoreBase):
    """Data aggregation and reduction node."""

    async def execute_reduction(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute data reduction operations.

        Args:
            input_data: Input data conforming to contract.input_state
            context: Optional execution context

        Returns:
            Reduced output data conforming to contract.output_state
        """
        pass

    async def _perform_aggregation(
        self,
        data: List[Any],
        aggregation_functions: List[str]
    ) -> Dict[str, Any]:
        """
        Perform aggregation using contract.aggregation subcontract.

        Uses contract.aggregation.aggregation_functions if available.
        """
        if self.contract.aggregation:
            functions = self.contract.aggregation.aggregation_functions
            # Perform aggregation
        pass
```

### ORCHESTRATOR Node Methods

```python
class NodeOrchestrator(NodeCoreBase):
    """Workflow coordination and orchestration node."""

    async def execute_orchestration(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute workflow orchestration.

        Args:
            input_data: Input data conforming to contract.input_state
            context: Optional execution context

        Returns:
            Orchestration results conforming to contract.output_state
        """
        pass

    async def _emit_thunks(
        self,
        workflow_steps: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Emit thunks for deferred execution.

        Uses contract.thunk_emission configuration.
        """
        if self.contract.thunk_emission:
            strategy = self.contract.thunk_emission.emission_strategy
            # Emit thunks based on strategy
        pass

    async def _execute_workflow(
        self,
        workflow_id: str
    ) -> Dict[str, Any]:
        """
        Execute workflow from contract.workflow_registry.
        """
        if workflow_id in self.contract.workflow_registry.workflows:
            workflow = self.contract.workflow_registry.workflows[workflow_id]
            # Execute workflow steps
        pass
```

---

## Real-World Contract Examples

### Example 1: Tool Model Splitter (COMPUTE)

**File**: `/src/omnibase/tools/tool_model_splitter/v1_0_0/contract.yaml`

```yaml
contract_version: "1.0.0"
node_name: "tool_model_splitter"
description: "Tool for analyzing and splitting Python files with multiple models"

input_state:
  type: "object"
  properties:
    file_path:
      type: "string"
      description: "Path to the Python file to analyze or split"
    output_dir:
      type: "string"
      description: "Directory where split model files will be created"
    config:
      $ref: "#/definitions/ModelSplitterConfig"
    operation:
      type: "string"
      enum: ["analyze", "split", "plan"]
      default: "analyze"
  required:
    - file_path

output_state:
  type: "object"
  properties:
    success:
      type: "boolean"
    operation_result:
      $ref: "#/definitions/ModelSplitterResult"
    models_found:
      type: "integer"
    files_created:
      type: "integer"
    processing_time_ms:
      type: "number"
  required:
    - success
    - models_found
```

**Key Features**:
- Simple COMPUTE node for code analysis
- Structured input/output states
- Reference to complex type definitions
- Enumerated operation types

### Example 2: PostgreSQL Monitoring (ORCHESTRATOR)

**File**: `/contracts/postgres_monitoring_contract.yaml`

```yaml
name: PostgresMonitoring
node_type: ORCHESTRATOR
description: PostgreSQL performance monitoring, health checks, and SLA validation

protocols:
  - name: ProtocolPostgresMonitoringManager
    methods:
      - name: setup_performance_monitoring
        parameters:
          - name: monitoring_config
            type: ModelPerformanceMonitoringConfig
          - name: metrics_collection_config
            type: ModelMetricsCollectionConfig
        returns:
          type: ModelPerformanceMonitoringResult

      - name: validate_sla_compliance
        parameters:
          - name: sla_config
            type: ModelSLAConfig
        returns:
          type: ModelSLAValidationResult

models:
  - name: PerformanceMonitoringConfig
    fields:
      - name: monitoring_level
        type: str
        enum: [basic, standard, detailed, comprehensive]
        default: standard
      - name: collection_interval_seconds
        type: int
        default: 30
      - name: enable_query_monitoring
        type: bool
        default: true

validation_rules:
  - rule: availability_target_realistic
    severity: warning
    validation_expression: "availability_target_percent >= 95.0"

  - rule: health_check_frequency_balanced
    severity: warning
    validation_expression: "check_frequency_minutes >= 1 and <= 60"
```

**Key Features**:
- ORCHESTRATOR node for complex monitoring workflows
- Protocol definitions for structured interfaces
- Complex model hierarchies
- Validation rules with severity levels

### Example 3: Error Code Usage Validator (EFFECT)

**File**: `/src/omnibase/tools/tool_error_code_usage/v1_0_0/contract.yaml`

```yaml
name: error_code_usage
version: 1.0.0
node_type: error_code_validator
category: validation

input_state:
  type: object
  properties:
    discovered_nodes:
      type: array
      items:
        $ref: '#/definitions/DiscoveredNode'
    validation_config:
      type: object
      properties:
        required_error_code_suffix:
          type: string
          default: "ErrorCode"
        minimum_error_codes:
          type: integer
          default: 1

output_state:
  type: object
  properties:
    status:
      type: string
      enum: [success, warning, error]
    error_code_violations:
      type: array
      items:
        $ref: '#/definitions/ErrorCodeViolation'
    validation_summary:
      type: object
      properties:
        passed_count: {type: integer}
        failed_count: {type: integer}

cli_interface:
  commands:
    - name: validate
      arguments:
        - name: node_paths
          type: positional
          required: true
          multiple: true
      options:
        - name: --correlation-id
          type: string
        - name: --minimum-error-codes
          type: integer

error_codes:
  ERROR_CODE_VALIDATION_ERROR:
    code: ERROR_CODE_VALIDATION_ERROR
    message: Error occurred during validation
    exit_code: 2
```

**Key Features**:
- EFFECT node for validation operations
- CLI interface specification
- Error code definitions
- Complex nested structures

---

## Summary

### Contract System Benefits

1. **Type Safety**: Strong Pydantic models prevent runtime type errors
2. **Validation**: Automatic contract compliance validation
3. **Documentation**: Self-documenting through contract specifications
4. **Flexibility**: Support for both FSM and infrastructure patterns
5. **Composition**: Reusable functionality via subcontracts
6. **Evolution**: Version-aware contract evolution

### Subcontract Composition Matrix

| Node Type | FSM | Event Type | Aggregation | State Mgmt | Routing | Caching |
|-----------|-----|------------|-------------|------------|---------|---------|
| EFFECT    | ✓   | ✓          | ✗           | ✓          | ✓       | ✓       |
| COMPUTE   | ✗   | ✓          | ✗           | ✗          | ✗       | ✓       |
| REDUCER   | ✓   | ✓          | ✓           | ✓          | ✗       | ✓       |
| ORCHESTRATOR | ✗ | ✓        | ✗           | ✓          | ✓       | ✓       |

**Legend**:
- ✓ = Recommended or commonly used
- ✗ = Not recommended or architectural violation

### File Locations Reference

```
omnibase_3/
├── src/omnibase/core/
│   ├── model_contract_base.py         # Base contract model
│   ├── model_contract_effect.py       # EFFECT contract
│   ├── model_contract_compute.py      # COMPUTE contract
│   ├── model_contract_reducer.py      # REDUCER contract
│   ├── model_contract_orchestrator.py # ORCHESTRATOR contract
│   ├── node_effect.py                 # EFFECT node implementation
│   ├── node_compute.py                # COMPUTE node implementation
│   ├── node_reducer.py                # REDUCER node implementation
│   ├── node_orchestrator.py           # ORCHESTRATOR node implementation
│   └── subcontracts/
│       ├── __init__.py
│       ├── model_fsm_subcontract.py
│       ├── model_event_type_subcontract.py
│       ├── model_aggregation_subcontract.py
│       ├── model_state_management_subcontract.py
│       ├── model_routing_subcontract.py
│       └── model_caching_subcontract.py
├── contracts/
│   ├── postgres_monitoring_contract.yaml
│   ├── rsd_priority_engine_contract.yaml
│   └── test_simple_tool_cli.yaml
└── src/omnibase/tools/
    ├── tool_model_splitter/v1_0_0/contract.yaml
    ├── tool_error_code_usage/v1_0_0/contract.yaml
    └── tool_schema_discovery/v1_0_0/contract.yaml
```

---

**End of Report**
