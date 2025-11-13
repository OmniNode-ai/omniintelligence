"""
Workflow Coordinator Request/Response Models

Models for OmniNode Bridge Workflow Coordinator service API interactions.
These models represent the structured data for workflow orchestration.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# NOTE: correlation_id support enabled for tracing
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


class WorkflowNode(BaseModel):
    """Workflow node specification."""

    node_id: Optional[UUID] = Field(
        default=None,
        description="Unique identifier for this workflow node",
    )

    node_name: str = Field(
        ...,
        description="Name of the node to execute",
        examples=["data_validator", "transform_processor", "output_writer"],
    )

    node_type: str = Field(
        ...,
        description="Type of node (EFFECT, COMPUTE, REDUCER, ORCHESTRATOR)",
        examples=["EFFECT", "COMPUTE", "REDUCER"],
    )

    dependencies: List[UUID] = Field(
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

    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Node execution parameters",
    )


class TriggerWorkflowRequest(BaseModel):
    """Request to trigger a new workflow execution."""

    workflow_name: str = Field(
        ...,
        description="Name/identifier of the workflow to execute",
        min_length=1,
    )

    coordination_strategy: CoordinationStrategy = Field(
        default=CoordinationStrategy.DAG,
        description="Workflow coordination strategy",
    )

    workflow_nodes: List[WorkflowNode] = Field(
        ...,
        description="Nodes to execute in this workflow",
        min_items=1,
    )

    workflow_parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Global workflow parameters",
    )

    timeout_seconds: int = Field(
        default=3600,
        description="Maximum time for entire workflow execution",
        gt=0,
    )

    enable_checkpointing: bool = Field(
        default=True,
        description="Enable workflow state checkpointing",
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional workflow metadata",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "workflow_name": "data_processing_pipeline",
                "coordination_strategy": "DAG",
                "workflow_nodes": [
                    {
                        "node_name": "data_validator",
                        "node_type": "COMPUTE",
                        "priority": 100,
                        "timeout_seconds": 300,
                        "parameters": {"strict_mode": True},
                    },
                    {
                        "node_name": "data_transformer",
                        "node_type": "COMPUTE",
                        "priority": 90,
                        "timeout_seconds": 600,
                        "parameters": {"format": "json"},
                    },
                ],
                "workflow_parameters": {"batch_size": 1000},
                "timeout_seconds": 3600,
                "enable_checkpointing": True,
                "metadata": {"project_id": "proj-123", "environment": "production"},
            }
        }
    )


class WorkflowNodeStatus(BaseModel):
    """Status of an individual node in the workflow."""

    node_id: UUID = Field(..., description="Node identifier")
    node_name: str = Field(..., description="Node name")
    node_type: str = Field(..., description="Node type")
    status: NodeExecutionStatus = Field(..., description="Execution status")
    start_time: Optional[str] = Field(None, description="ISO timestamp of start")
    end_time: Optional[str] = Field(None, description="ISO timestamp of completion")
    duration_seconds: Optional[float] = Field(None, description="Execution duration")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    retry_count: int = Field(default=0, description="Number of retries attempted")
    output: Optional[Dict[str, Any]] = Field(None, description="Node output data")


class WorkflowStatusResponse(BaseModel):
    """Response containing workflow execution status."""

    workflow_id: UUID = Field(..., description="Workflow execution ID")
    workflow_name: str = Field(..., description="Workflow name")
    status: WorkflowStatus = Field(..., description="Overall workflow status")
    coordination_strategy: CoordinationStrategy = Field(
        ..., description="Coordination strategy used"
    )

    # Timing information
    created_at: str = Field(..., description="ISO timestamp of creation")
    started_at: Optional[str] = Field(None, description="ISO timestamp of start")
    completed_at: Optional[str] = Field(None, description="ISO timestamp of completion")
    duration_seconds: Optional[float] = Field(
        None, description="Total execution duration"
    )

    # Progress tracking
    total_nodes: int = Field(..., description="Total number of nodes", ge=0)
    completed_nodes: int = Field(..., description="Number of completed nodes", ge=0)
    failed_nodes: int = Field(..., description="Number of failed nodes", ge=0)
    progress_percentage: float = Field(
        ..., description="Completion percentage (0-100)", ge=0.0, le=100.0
    )

    # Node details
    nodes: List[WorkflowNodeStatus] = Field(
        default_factory=list, description="Status of individual nodes"
    )

    # Error tracking
    error_message: Optional[str] = Field(
        None, description="Error message if workflow failed"
    )
    failed_node_id: Optional[UUID] = Field(
        None, description="ID of node that caused failure"
    )

    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Workflow metadata"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
                "workflow_name": "data_processing_pipeline",
                "status": "RUNNING",
                "coordination_strategy": "DAG",
                "created_at": "2025-10-06T10:00:00Z",
                "started_at": "2025-10-06T10:00:05Z",
                "completed_at": None,
                "duration_seconds": 125.5,
                "total_nodes": 5,
                "completed_nodes": 3,
                "failed_nodes": 0,
                "progress_percentage": 60.0,
                "nodes": [
                    {
                        "node_id": "11111111-1111-1111-1111-111111111111",
                        "node_name": "data_validator",
                        "node_type": "COMPUTE",
                        "status": "COMPLETED",
                        "start_time": "2025-10-06T10:00:05Z",
                        "end_time": "2025-10-06T10:00:15Z",
                        "duration_seconds": 10.0,
                        "retry_count": 0,
                        "output": {"validation_result": "passed"},
                    }
                ],
                "metadata": {"project_id": "proj-123"},
            }
        }
    )


class TriggerWorkflowResponse(BaseModel):
    """Response from triggering a workflow."""

    success: bool = Field(
        ..., description="Whether workflow was triggered successfully"
    )
    workflow_id: UUID = Field(..., description="Unique workflow execution ID")
    workflow_name: str = Field(..., description="Workflow name")
    status: WorkflowStatus = Field(..., description="Initial workflow status")
    message: str = Field(..., description="Response message")
    created_at: str = Field(..., description="ISO timestamp of creation")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
                "workflow_name": "data_processing_pipeline",
                "status": "PENDING",
                "message": "Workflow triggered successfully",
                "created_at": "2025-10-06T10:00:00Z",
            }
        }
    )


class ActiveWorkflow(BaseModel):
    """Summary of an active workflow."""

    workflow_id: UUID = Field(..., description="Workflow execution ID")
    workflow_name: str = Field(..., description="Workflow name")
    status: WorkflowStatus = Field(..., description="Current status")
    created_at: str = Field(..., description="ISO timestamp of creation")
    started_at: Optional[str] = Field(None, description="ISO timestamp of start")
    progress_percentage: float = Field(
        ..., description="Completion percentage", ge=0.0, le=100.0
    )
    total_nodes: int = Field(..., description="Total nodes", ge=0)
    completed_nodes: int = Field(..., description="Completed nodes", ge=0)


class ListActiveWorkflowsResponse(BaseModel):
    """Response containing list of active workflows."""

    workflows: List[ActiveWorkflow] = Field(
        default_factory=list, description="List of active workflows"
    )
    total_count: int = Field(..., description="Total number of active workflows", ge=0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "workflows": [
                    {
                        "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
                        "workflow_name": "data_processing_pipeline",
                        "status": "RUNNING",
                        "created_at": "2025-10-06T10:00:00Z",
                        "started_at": "2025-10-06T10:00:05Z",
                        "progress_percentage": 60.0,
                        "total_nodes": 5,
                        "completed_nodes": 3,
                    }
                ],
                "total_count": 1,
            }
        }
    )


class CancelWorkflowResponse(BaseModel):
    """Response from canceling a workflow."""

    success: bool = Field(..., description="Whether workflow was canceled successfully")
    workflow_id: UUID = Field(..., description="Workflow execution ID")
    previous_status: WorkflowStatus = Field(
        ..., description="Status before cancellation"
    )
    message: str = Field(..., description="Response message")
    cancelled_at: str = Field(..., description="ISO timestamp of cancellation")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
                "previous_status": "RUNNING",
                "message": "Workflow cancelled successfully",
                "cancelled_at": "2025-10-06T10:05:00Z",
            }
        }
    )
