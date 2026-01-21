"""Models for Quality Scoring Compute Node.

This module provides type-safe input and output models for quality scoring.
All models use strong typing to eliminate dict[str, Any].
"""

from omniintelligence.nodes.quality_scoring_compute.models.model_quality_scoring_input import (
    ModelDimensionWeights,
    ModelQualityScoringInput,
)
from omniintelligence.nodes.quality_scoring_compute.models.model_quality_scoring_output import (
    ModelQualityScoringMetadata,
    ModelQualityScoringOutput,
)

__all__ = [
    "ModelDimensionWeights",
    "ModelQualityScoringInput",
    "ModelQualityScoringMetadata",
    "ModelQualityScoringOutput",
]
