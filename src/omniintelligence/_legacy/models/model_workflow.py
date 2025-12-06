"""
Workflow Models for omniintelligence.

Models for workflow step definitions and execution state.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from omniintelligence._legacy.enums import EnumOperationType


class ModelWorkflowStep(BaseModel):
    """Workflow step definition."""

    step_name: str = Field(..., description="Step name")
    step_type: str = Field(..., description="Step type")
    step_description: str | None = Field(None, description="Step description")
    depends_on: list[str] = Field(default_factory=list, description="Dependencies")
    input_data: dict[str, Any] | None = Field(None, description="Step input")
    output_key: str | None = Field(None, description="Output key")


class ModelWorkflowExecution(BaseModel):
    """Workflow execution state."""

    workflow_id: str = Field(..., description="Workflow ID")
    operation_type: EnumOperationType = Field(..., description="Operation type")
    execution_status: str = Field(..., description="Execution status")
    current_step: str | None = Field(None, description="Current step")
    completed_steps: list[str] = Field(
        default_factory=list, description="Completed steps"
    )
    failed_step: str | None = Field(None, description="Failed step")
    started_at: datetime = Field(..., description="Start timestamp")
    completed_at: datetime | None = Field(None, description="Completion timestamp")
    execution_results: dict[str, Any] | None = Field(
        None, description="Execution results"
    )


__all__ = [
    "ModelWorkflowExecution",
    "ModelWorkflowStep",
]
