"""
Workflow step type enums for omniintelligence.

Contains workflow step types for Llama Index workflows.
"""

from enum import Enum


class EnumWorkflowStepType(str, Enum):
    """Workflow step types for Llama Index workflows."""
    VALIDATION = "VALIDATION"
    COMPUTE = "COMPUTE"
    EFFECT = "EFFECT"
    INTENT = "INTENT"
    PARALLEL = "PARALLEL"
    SEQUENTIAL = "SEQUENTIAL"
    CONDITIONAL = "CONDITIONAL"


__all__ = [
    "EnumWorkflowStepType",
]
