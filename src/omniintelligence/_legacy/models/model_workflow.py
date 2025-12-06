"""
Workflow Models for omniintelligence.

Models for workflow step definitions and execution state.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.enums import EnumOperationType


class ModelWorkflowStep(BaseModel):
    """Workflow step definition."""

    model_config = ConfigDict(populate_by_name=True)

    step_name: str = Field(..., description="Step name", alias="name")
    step_type: str = Field(..., description="Step type")
    step_description: Optional[str] = Field(
        None, description="Step description", alias="description"
    )
    depends_on: list[str] = Field(default_factory=list, description="Dependencies")
    input_data: Optional[dict[str, Any]] = Field(None, description="Step input")
    output_key: Optional[str] = Field(None, description="Output key")


class ModelWorkflowExecution(BaseModel):
    """Workflow execution state."""

    model_config = ConfigDict(populate_by_name=True)

    workflow_id: str = Field(..., description="Workflow ID")
    operation_type: EnumOperationType = Field(..., description="Operation type")
    execution_status: str = Field(..., description="Execution status", alias="status")
    current_step: Optional[str] = Field(None, description="Current step")
    completed_steps: list[str] = Field(
        default_factory=list, description="Completed steps"
    )
    failed_step: Optional[str] = Field(None, description="Failed step")
    started_at: datetime = Field(..., description="Start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    execution_results: Optional[dict[str, Any]] = Field(
        None, description="Execution results", alias="results"
    )


__all__ = [
    "ModelWorkflowExecution",
    "ModelWorkflowStep",
]
