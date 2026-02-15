"""OmniIntelligence - ONEX-compliant intelligence nodes.

This package provides code quality analysis and intelligence operations
as first-class ONEX nodes.

Quick Start - Quality Scoring:
    >>> from omniintelligence import score_code_quality, OnexStrictnessLevel
    >>> result = score_code_quality(
    ...     content="class Model(BaseModel): x: int",
    ...     language="python",
    ...     preset=OnexStrictnessLevel.STRICT,
    ... )
    >>> result["success"]
    True
    >>> result["quality_score"]  # 0.0 to 1.0
    0.65
"""

from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
    DEFAULT_WEIGHTS,
    DimensionScores,
    OnexStrictnessLevel,
    QualityScoringComputeError,
    QualityScoringResult,
    QualityScoringValidationError,
    score_code_quality,
)

__version__ = "0.2.0"

__all__ = [
    # Configuration
    "DEFAULT_WEIGHTS",
    "DimensionScores",
    "OnexStrictnessLevel",
    "QualityScoringComputeError",
    # Types
    "QualityScoringResult",
    # Exceptions
    "QualityScoringValidationError",
    # Main API
    "score_code_quality",
]
