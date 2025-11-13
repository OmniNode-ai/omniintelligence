"""
Workflow Coordination Subcontract Example - ONEX Documentation.

Demonstrates multi-node workflow orchestration patterns for Orchestrator nodes.
Based on: omnibase_core/src/omnibase_core/models/contracts/subcontracts/model_workflow_coordination_subcontract.py

This example shows how Orchestrator nodes coordinate complex workflows across
multiple nodes with progress tracking, synchronization, and error handling.
"""

from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

# === ENUMS ===


class WorkflowStatus(str, Enum):
    """Workflow execution status."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class NodeExecutionStatus(str, Enum):
    """Individual node execution status in workflow."""

    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    RETRYING = "RETRYING"


class CoordinationStrategy(str, Enum):
    """Workflow coordination strategies."""

    SEQUENTIAL = "SEQUENTIAL"  # Execute nodes one at a time
    PARALLEL = "PARALLEL"  # Execute all nodes concurrently
    DAG = "DAG"  # Execute based on dependency graph
    PRIORITY = "PRIORITY"  # Execute based on priority
    ADAPTIVE = "ADAPTIVE"  # Dynamically adjust based on load


class SynchronizationType(str, Enum):
    """Synchronization point types."""

    BARRIER = "BARRIER"  # Wait for all nodes before proceeding
    QUORUM = "QUORUM"  # Wait for majority/threshold
    ANY = "ANY"  # Proceed when any node completes
    CUSTOM = "CUSTOM"  # Custom synchronization logic


# === MODELS ===


class ModelWorkflowNode(BaseModel):
    """Workflow node specification."""

    node_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this workflow node",
    )

    node_name: str = Field(
        ...,
        description="Name of the node to execute",
        examples=["data_validator", "transform_processor", "output_writer"],
    )

    node_type: str = Field(
        ...,
        description="Type of node (EFFECT, COMPUTE, REDUCER)",
        examples=["EFFECT", "COMPUTE"],
    )

    dependencies: list[UUID] = Field(
        default_factory=list,
        description="List of node IDs this node depends on",
    )

    priority: int = Field(
        default=100,
        description="Execution priority (higher = executes first)",
        ge=0,
        le=1000,
    )

    timeout_seconds: int = Field(
        default=300,
        description="Maximum execution time for this node",
        gt=0,
    )

    retry_count: int = Field(
        default=0,
        description="Number of retries on failure",
        ge=0,
    )

    fail_workflow_on_error: bool = Field(
        default=True,
        description="Whether failure of this node fails entire workflow",
    )


class ModelNodeAssignment(BaseModel):
    """Node-to-worker assignment tracking."""

    node_id: UUID = Field(
        ...,
        description="Workflow node ID",
    )

    worker_id: str = Field(
        ...,
        description="ID of worker assigned to execute this node",
        examples=["worker-1", "pod-abc123"],
    )

    assigned_at: str = Field(
        ...,
        description="ISO timestamp of assignment",
    )

    status: NodeExecutionStatus = Field(
        default=NodeExecutionStatus.ASSIGNED,
        description="Current execution status",
    )


class ModelSynchronizationPoint(BaseModel):
    """Workflow synchronization point."""

    sync_id: UUID = Field(
        default_factory=uuid4,
        description="Unique synchronization point ID",
    )

    sync_type: SynchronizationType = Field(
        ...,
        description="Type of synchronization",
    )

    wait_for_nodes: list[UUID] = Field(
        default_factory=list,
        description="Node IDs to wait for",
    )

    quorum_threshold: int | None = Field(
        default=None,
        description="For QUORUM type: minimum nodes required",
        ge=1,
    )

    timeout_seconds: int = Field(
        default=600,
        description="Maximum wait time before timeout",
        gt=0,
    )


class ModelCoordinationRules(BaseModel):
    """Workflow coordination behavior rules."""

    max_parallel_nodes: int = Field(
        default=10,
        description="Maximum nodes executing in parallel",
        ge=1,
    )

    enable_adaptive_scheduling: bool = Field(
        default=False,
        description="Adjust scheduling based on node performance",
    )

    allow_node_preemption: bool = Field(
        default=False,
        description="Allow higher-priority nodes to preempt lower-priority ones",
    )

    failure_tolerance_threshold: float = Field(
        default=0.0,
        description="Acceptable failure rate (0.0 = no tolerance, 1.0 = all can fail)",
        ge=0.0,
        le=1.0,
    )

    checkpoint_interval_seconds: int = Field(
        default=60,
        description="How often to checkpoint workflow state",
        ge=1,
    )


class ModelWorkflowMetrics(BaseModel):
    """Workflow execution metrics."""

    total_nodes: int = Field(
        default=0,
        description="Total number of nodes in workflow",
        ge=0,
    )

    completed_nodes: int = Field(
        default=0,
        description="Number of completed nodes",
        ge=0,
    )

    failed_nodes: int = Field(
        default=0,
        description="Number of failed nodes",
        ge=0,
    )

    average_node_duration_seconds: float = Field(
        default=0.0,
        description="Average node execution time",
        ge=0.0,
    )

    workflow_start_time: str | None = Field(
        default=None,
        description="ISO timestamp of workflow start",
    )

    workflow_end_time: str | None = Field(
        default=None,
        description="ISO timestamp of workflow completion",
    )


class ModelWorkflowCoordinationSubcontract(BaseModel):
    """
    Workflow Coordination Subcontract for ORCHESTRATOR nodes.

    Provides comprehensive workflow orchestration capabilities for coordinating
    multi-node execution with progress tracking, synchronization, error handling,
    and performance optimization.

    Features:
    - Multi-strategy coordination (sequential, parallel, DAG, priority)
    - Progress tracking and monitoring
    - Synchronization points (barriers, quorums)
    - Adaptive scheduling based on performance
    - Checkpoint/recovery for long-running workflows
    - Failure tolerance and recovery
    """

    subcontract_name: str = Field(
        default="workflow_coordination_subcontract",
        description="Subcontract identifier",
    )

    subcontract_version: str = Field(
        default="1.0.0",
        description="Subcontract version",
    )

    applicable_node_types: list[str] = Field(
        default=["ORCHESTRATOR"],
        description="Only applicable to Orchestrator nodes",
    )

    # === WORKFLOW CONFIGURATION ===

    max_concurrent_workflows: int = Field(
        default=100,
        description="Maximum number of concurrent workflows",
        ge=1,
    )

    workflow_execution_timeout_seconds: int = Field(
        default=3600,
        description="Maximum time for entire workflow execution",
        gt=0,
    )

    coordination_strategy: CoordinationStrategy = Field(
        default=CoordinationStrategy.DAG,
        description="Workflow coordination strategy",
    )

    # === WORKFLOW DEFINITION ===

    workflow_nodes: list[ModelWorkflowNode] = Field(
        default_factory=list,
        description="Nodes in this workflow",
    )

    synchronization_points: list[ModelSynchronizationPoint] = Field(
        default_factory=list,
        description="Synchronization points in workflow",
    )

    # === COORDINATION RULES ===

    coordination_rules: ModelCoordinationRules = Field(
        default_factory=ModelCoordinationRules,
        description="Workflow coordination behavior rules",
    )

    # === STATE MANAGEMENT ===

    enable_workflow_checkpointing: bool = Field(
        default=True,
        description="Enable workflow state checkpointing",
    )

    checkpoint_storage_path: str = Field(
        default="/tmp/workflow-checkpoints",
        description="Path for storing workflow checkpoints",
    )

    enable_workflow_recovery: bool = Field(
        default=True,
        description="Enable automatic workflow recovery after failure",
    )

    # === MONITORING ===

    enable_progress_tracking: bool = Field(
        default=True,
        description="Track and report workflow progress",
    )

    progress_update_interval_seconds: int = Field(
        default=10,
        description="How often to emit progress updates",
        ge=1,
    )

    emit_workflow_events: bool = Field(
        default=True,
        description="Emit events for workflow state changes",
    )


# === USAGE EXAMPLES ===

# Example 1: Sequential data processing workflow
sequential_workflow = ModelWorkflowCoordinationSubcontract(
    coordination_strategy=CoordinationStrategy.SEQUENTIAL,
    workflow_nodes=[
        ModelWorkflowNode(
            node_name="data_validator",
            node_type="EFFECT",
            priority=100,
        ),
        ModelWorkflowNode(
            node_name="data_transformer",
            node_type="COMPUTE",
            priority=90,
        ),
        ModelWorkflowNode(
            node_name="data_writer",
            node_type="EFFECT",
            priority=80,
        ),
    ],
    coordination_rules=ModelCoordinationRules(
        max_parallel_nodes=1,
        failure_tolerance_threshold=0.0,
    ),
)

# Example 2: Parallel processing with synchronization
parallel_workflow = ModelWorkflowCoordinationSubcontract(
    coordination_strategy=CoordinationStrategy.PARALLEL,
    max_concurrent_workflows=50,
    workflow_nodes=[
        # Phase 1: Data validation (parallel)
        ModelWorkflowNode(
            node_id=UUID("11111111-1111-1111-1111-111111111111"),
            node_name="validator_a",
            node_type="COMPUTE",
            priority=100,
        ),
        ModelWorkflowNode(
            node_id=UUID("22222222-2222-2222-2222-222222222222"),
            node_name="validator_b",
            node_type="COMPUTE",
            priority=100,
        ),
        # Phase 2: Data processing (depends on validators)
        ModelWorkflowNode(
            node_id=UUID("33333333-3333-3333-3333-333333333333"),
            node_name="processor",
            node_type="EFFECT",
            dependencies=[
                UUID("11111111-1111-1111-1111-111111111111"),
                UUID("22222222-2222-2222-2222-222222222222"),
            ],
            priority=90,
        ),
    ],
    synchronization_points=[
        ModelSynchronizationPoint(
            sync_type=SynchronizationType.BARRIER,
            wait_for_nodes=[
                UUID("11111111-1111-1111-1111-111111111111"),
                UUID("22222222-2222-2222-2222-222222222222"),
            ],
        ),
    ],
    coordination_rules=ModelCoordinationRules(
        max_parallel_nodes=10,
        checkpoint_interval_seconds=30,
    ),
)

# Example 3: Complex DAG workflow with adaptive scheduling
dag_workflow = ModelWorkflowCoordinationSubcontract(
    coordination_strategy=CoordinationStrategy.DAG,
    workflow_nodes=[
        # Source nodes (no dependencies)
        ModelWorkflowNode(
            node_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            node_name="source_1",
            node_type="EFFECT",
        ),
        ModelWorkflowNode(
            node_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            node_name="source_2",
            node_type="EFFECT",
        ),
        # Processing nodes (depend on sources)
        ModelWorkflowNode(
            node_id=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
            node_name="processor_1",
            node_type="COMPUTE",
            dependencies=[UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")],
        ),
        ModelWorkflowNode(
            node_id=UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
            node_name="processor_2",
            node_type="COMPUTE",
            dependencies=[UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")],
        ),
        # Aggregation node (depends on all processors)
        ModelWorkflowNode(
            node_id=UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
            node_name="aggregator",
            node_type="REDUCER",
            dependencies=[
                UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
                UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
            ],
        ),
    ],
    coordination_rules=ModelCoordinationRules(
        max_parallel_nodes=5,
        enable_adaptive_scheduling=True,
        failure_tolerance_threshold=0.2,  # Tolerate 20% failure
    ),
    enable_workflow_checkpointing=True,
    enable_workflow_recovery=True,
)

# Example 4: High-throughput parallel workflow
high_throughput_workflow = ModelWorkflowCoordinationSubcontract(
    coordination_strategy=CoordinationStrategy.PARALLEL,
    max_concurrent_workflows=1000,
    workflow_execution_timeout_seconds=600,
    coordination_rules=ModelCoordinationRules(
        max_parallel_nodes=100,
        enable_adaptive_scheduling=True,
        allow_node_preemption=True,
        checkpoint_interval_seconds=120,
    ),
    enable_progress_tracking=True,
    progress_update_interval_seconds=5,
    emit_workflow_events=True,
)
