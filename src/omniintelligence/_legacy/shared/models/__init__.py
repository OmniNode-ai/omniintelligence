"""
Shared models for omniintelligence.

DEPRECATED: This module is kept for backwards compatibility.
Please import from omniintelligence.models instead:

    # Preferred import
    from omniintelligence.models import ModelIntent, ModelReducerInput

    # Deprecated import (still works)
    from omniintelligence.shared.models import ModelIntent, ModelReducerInput

Data models used across all nodes for consistency.
"""

# Re-export all models from the canonical location
from omniintelligence.models import (
    ModelIntent,
    ModelReducerInput,
    ModelReducerOutput,
    ModelReducerConfig,
    ModelOrchestratorInput,
    ModelOrchestratorOutput,
    ModelOrchestratorConfig,
    ModelEntity,
    ModelRelationship,
    ModelQualityScore,
    ModelFSMState,
    ModelWorkflowStep,
    ModelWorkflowExecution,
)

__all__ = [
    "ModelEntity",
    "ModelFSMState",
    "ModelIntent",
    "ModelOrchestratorConfig",
    "ModelOrchestratorInput",
    "ModelOrchestratorOutput",
    "ModelQualityScore",
    "ModelReducerConfig",
    "ModelReducerInput",
    "ModelReducerOutput",
    "ModelRelationship",
    "ModelWorkflowExecution",
    "ModelWorkflowStep",
]
