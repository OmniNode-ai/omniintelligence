"""
Workflow Models for omniintelligence.

Models for workflow step definitions and execution state.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from omniintelligence.enums import EnumOperationType


class ModelWorkflowStep(BaseModel):
    """Workflow step definition."""

    name: str = Field(..., description="Step name")
    step_type: str = Field(..., description="Step type")
    description: Optional[str] = Field(None, description="Step description")
    depends_on: list[str] = Field(default_factory=list, description="Dependencies")
    input_data: Optional[dict[str, Any]] = Field(None, description="Step input")
    output_key: Optional[str] = Field(None, description="Output key")


class ModelWorkflowExecution(BaseModel):
    """Workflow execution state."""

    workflow_id: str = Field(..., description="Workflow ID")
    operation_type: EnumOperationType = Field(..., description="Operation type")
    status: str = Field(..., description="Execution status")
    current_step: Optional[str] = Field(None, description="Current step")
    completed_steps: list[str] = Field(
        default_factory=list, description="Completed steps"
    )
    failed_step: Optional[str] = Field(None, description="Failed step")
    started_at: datetime = Field(..., description="Start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    results: Optional[dict[str, Any]] = Field(None, description="Execution results")


__all__ = [
    "ModelWorkflowExecution",
    "ModelWorkflowStep",
]
