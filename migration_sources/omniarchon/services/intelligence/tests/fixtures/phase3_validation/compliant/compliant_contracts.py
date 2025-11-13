"""
Perfect ONEX Contract Examples

This fixture provides fully compliant contract implementations
for all ONEX node types for testing validation logic.

ONEX Contract Requirements:
- Base: ModelContractBase (name, version, description, node_type)
- Specialized: ModelContractEffect, ModelContractCompute, ModelContractReducer, ModelContractOrchestrator
- Subcontracts: FSM, EventType, Aggregation, StateManagement, Routing, Caching
"""

from typing import Any, Dict, List, Optional

# ============================================================================
# Base Contract
# ============================================================================


class ModelContractBase:
    """
    Base contract for all ONEX nodes.

    All contracts must inherit from this base and provide:
    - name: Node name
    - version: Semantic version
    - description: Clear purpose description
    - node_type: One of: effect, compute, reducer, orchestrator
    """

    def __init__(self, name: str, version: str, description: str, node_type: str):
        self.name = name
        self.version = version
        self.description = description
        self.node_type = node_type

    def validate(self) -> bool:
        """Validate contract basic requirements."""
        return all(
            [
                self.name,
                self.version,
                self.description,
                self.node_type in ["effect", "compute", "reducer", "orchestrator"],
            ]
        )


# ============================================================================
# Specialized Contracts
# ============================================================================


class ModelContractEffect(ModelContractBase):
    """
    Contract for Effect nodes (External I/O operations).

    Required fields:
    - target_system: System being affected (database, api, file_system, etc.)
    - operation_type: Type of operation (read, write, update, delete, etc.)
    - timeout_seconds: Maximum execution time
    """

    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        target_system: str,
        operation_type: str,
        timeout_seconds: int = 30,
        retry_strategy: Optional[str] = None,
    ):
        super().__init__(name, version, description, "effect")
        self.target_system = target_system
        self.operation_type = operation_type
        self.timeout_seconds = timeout_seconds
        self.retry_strategy = retry_strategy


class ModelContractCompute(ModelContractBase):
    """
    Contract for Compute nodes (Pure transformations/algorithms).

    Required fields:
    - algorithm_type: Type of computation (transform, calculate, analyze, etc.)
    - input_schema: Expected input structure
    - output_schema: Expected output structure
    """

    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        algorithm_type: str,
        input_schema: Dict[str, Any],
        output_schema: Dict[str, Any],
        deterministic: bool = True,
    ):
        super().__init__(name, version, description, "compute")
        self.algorithm_type = algorithm_type
        self.input_schema = input_schema
        self.output_schema = output_schema
        self.deterministic = deterministic


class ModelContractReducer(ModelContractBase):
    """
    Contract for Reducer nodes (Aggregation, persistence, state).

    Required fields:
    - aggregation_strategy: How to aggregate data (count, sum, merge, etc.)
    - state_key: Key for state storage
    - persistence_required: Whether to persist results
    """

    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        aggregation_strategy: str,
        state_key: str,
        persistence_required: bool = True,
        ttl_seconds: Optional[int] = None,
    ):
        super().__init__(name, version, description, "reducer")
        self.aggregation_strategy = aggregation_strategy
        self.state_key = state_key
        self.persistence_required = persistence_required
        self.ttl_seconds = ttl_seconds


class ModelContractOrchestrator(ModelContractBase):
    """
    Contract for Orchestrator nodes (Workflow coordination).

    Required fields:
    - workflow_steps: List of steps to execute
    - dependency_graph: Dependencies between steps
    - parallelization_enabled: Whether to parallelize execution
    """

    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        workflow_steps: List[Dict[str, Any]],
        dependency_graph: Dict[str, List[str]],
        parallelization_enabled: bool = True,
        error_handling_strategy: str = "fail_fast",
    ):
        super().__init__(name, version, description, "orchestrator")
        self.workflow_steps = workflow_steps
        self.dependency_graph = dependency_graph
        self.parallelization_enabled = parallelization_enabled
        self.error_handling_strategy = error_handling_strategy


# ============================================================================
# Subcontracts (6 types)
# ============================================================================


class ModelFSMSubcontract:
    """Finite State Machine subcontract for state transitions."""

    def __init__(
        self,
        initial_state: str,
        states: List[str],
        transitions: Dict[str, Dict[str, str]],
        final_states: List[str],
    ):
        self.initial_state = initial_state
        self.states = states
        self.transitions = transitions
        self.final_states = final_states


class ModelEventTypeSubcontract:
    """Event type subcontract for event-driven architectures."""

    def __init__(
        self,
        event_name: str,
        event_schema: Dict[str, Any],
        priority: int = 0,
        ttl_seconds: Optional[int] = None,
    ):
        self.event_name = event_name
        self.event_schema = event_schema
        self.priority = priority
        self.ttl_seconds = ttl_seconds


class ModelAggregationSubcontract:
    """Aggregation subcontract for data aggregation strategies."""

    def __init__(
        self,
        aggregation_type: str,  # sum, count, average, min, max, custom
        group_by_fields: List[str],
        aggregation_fields: List[str],
        window_size: Optional[int] = None,
    ):
        self.aggregation_type = aggregation_type
        self.group_by_fields = group_by_fields
        self.aggregation_fields = aggregation_fields
        self.window_size = window_size


class ModelStateManagementSubcontract:
    """State management subcontract for stateful operations."""

    def __init__(
        self,
        state_type: str,  # ephemeral, persistent, distributed
        storage_backend: str,  # memory, redis, postgresql, etc.
        consistency_level: str = "eventual",  # strong, eventual, causal
        ttl_seconds: Optional[int] = None,
    ):
        self.state_type = state_type
        self.storage_backend = storage_backend
        self.consistency_level = consistency_level
        self.ttl_seconds = ttl_seconds


class ModelRoutingSubcontract:
    """Routing subcontract for conditional routing logic."""

    def __init__(
        self,
        routing_strategy: str,  # round_robin, weighted, conditional, hash
        routing_rules: List[Dict[str, Any]],
        default_route: str,
        fallback_enabled: bool = True,
    ):
        self.routing_strategy = routing_strategy
        self.routing_rules = routing_rules
        self.default_route = default_route
        self.fallback_enabled = fallback_enabled


class ModelCachingSubcontract:
    """Caching subcontract for caching strategies."""

    def __init__(
        self,
        cache_strategy: str,  # lru, lfu, fifo, ttl
        cache_backend: str,  # memory, redis, memcached
        ttl_seconds: int = 300,
        max_size: Optional[int] = None,
    ):
        self.cache_strategy = cache_strategy
        self.cache_backend = cache_backend
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size


# ============================================================================
# Test Fixture Contract Instances
# ============================================================================


def create_compliant_effect_contract() -> ModelContractEffect:
    """Create a fully compliant Effect contract."""
    return ModelContractEffect(
        name="DatabaseWriter",
        version="1.0.0",
        description="Writes data to PostgreSQL database",
        target_system="database",
        operation_type="write",
        timeout_seconds=30,
        retry_strategy="exponential_backoff",
    )


def create_compliant_compute_contract() -> ModelContractCompute:
    """Create a fully compliant Compute contract."""
    return ModelContractCompute(
        name="DataTransformer",
        version="1.0.0",
        description="Transforms input data to normalized format",
        algorithm_type="normalize",
        input_schema={
            "required": ["value"],
            "properties": {"value": {"type": "number"}},
        },
        output_schema={
            "required": ["normalized"],
            "properties": {"normalized": {"type": "number"}},
        },
        deterministic=True,
    )


def create_compliant_reducer_contract() -> ModelContractReducer:
    """Create a fully compliant Reducer contract."""
    return ModelContractReducer(
        name="EventAggregator",
        version="1.0.0",
        description="Aggregates events into summary state",
        aggregation_strategy="count",
        state_key="event_summary",
        persistence_required=True,
        ttl_seconds=3600,
    )


def create_compliant_orchestrator_contract() -> ModelContractOrchestrator:
    """Create a fully compliant Orchestrator contract."""
    return ModelContractOrchestrator(
        name="WorkflowCoordinator",
        version="1.0.0",
        description="Coordinates multi-step workflow execution",
        workflow_steps=[
            {"name": "validate", "type": "compute"},
            {"name": "process", "type": "compute"},
            {"name": "persist", "type": "effect"},
        ],
        dependency_graph={
            "validate": [],
            "process": ["validate"],
            "persist": ["process"],
        },
        parallelization_enabled=True,
        error_handling_strategy="fail_fast",
    )


# ============================================================================
# Test Fixture Code Strings
# ============================================================================

COMPLIANT_CONTRACTS_CODE = """
# All ONEX contract types with proper structure

class ModelContractBase:
    def __init__(self, name: str, version: str, description: str, node_type: str):
        self.name = name
        self.version = version
        self.description = description
        self.node_type = node_type

class ModelContractEffect(ModelContractBase):
    def __init__(self, name: str, version: str, description: str,
                 target_system: str, operation_type: str, timeout_seconds: int = 30):
        super().__init__(name, version, description, "effect")
        self.target_system = target_system
        self.operation_type = operation_type
        self.timeout_seconds = timeout_seconds

class ModelContractCompute(ModelContractBase):
    def __init__(self, name: str, version: str, description: str,
                 algorithm_type: str, input_schema: dict, output_schema: dict):
        super().__init__(name, version, description, "compute")
        self.algorithm_type = algorithm_type
        self.input_schema = input_schema
        self.output_schema = output_schema
"""
