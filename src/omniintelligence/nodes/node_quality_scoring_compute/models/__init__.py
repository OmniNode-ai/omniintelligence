# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Models for Quality Scoring Compute Node.

This module provides type-safe input and output models for quality scoring.
All models use strong typing to eliminate dict[str, Any].
"""

from omniintelligence.nodes.node_quality_scoring_compute.models.model_dimension_weights import (
    ModelDimensionWeights,
)
from omniintelligence.nodes.node_quality_scoring_compute.models.model_quality_scoring_input import (
    ModelQualityScoringInput,
)
from omniintelligence.nodes.node_quality_scoring_compute.models.model_quality_scoring_metadata import (
    ModelQualityScoringMetadata,
)
from omniintelligence.nodes.node_quality_scoring_compute.models.model_quality_scoring_output import (
    ModelQualityScoringOutput,
)

__all__ = [
    "ModelDimensionWeights",
    "ModelQualityScoringInput",
    "ModelQualityScoringMetadata",
    "ModelQualityScoringOutput",
]
