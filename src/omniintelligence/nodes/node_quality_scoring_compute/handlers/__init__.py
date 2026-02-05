"""Quality Scoring Compute Handlers.

This module provides pure handler functions for quality scoring operations.
Handlers implement the computation logic following the ONEX "pure shell pattern"
where nodes delegate to side-effect-free handler functions.

Handler Pattern:
    Each handler is a pure function that:
    - Accepts source code content and configuration parameters
    - Computes quality scores across multiple dimensions
    - Returns a typed QualityScoringResult dictionary
    - Has no side effects (pure computation)

Six-Dimension Standard:
    - complexity (0.20): Cyclomatic complexity approximation (inverted - lower is better)
    - maintainability (0.20): Code structure quality (function length, naming conventions)
    - documentation (0.15): Docstring and comment coverage
    - temporal_relevance (0.15): Code freshness indicators (TODO/FIXME, deprecated)
    - patterns (0.15): ONEX pattern adherence (frozen models, TypedDict, Protocol, etc.)
    - architectural (0.15): Module organization and structure

ONEX Presets:
    Three pre-configured strictness levels are available:
    - STRICT: Production-ready (threshold 0.8, emphasizes docs/patterns)
    - STANDARD: Balanced (threshold 0.7, equal distribution)
    - LENIENT: Development mode (threshold 0.5, forgiving on docs/patterns)

Usage:
    from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
        score_code_quality,
        QualityScoringResult,
        DimensionScores,
        DEFAULT_WEIGHTS,
        OnexStrictnessLevel,
    )

    # Using default configuration
    result: QualityScoringResult = score_code_quality(
        content="class MyModel(BaseModel): x: int",
        language="python",
        weights=DEFAULT_WEIGHTS,
        onex_threshold=0.7,
    )

    # Using a preset (recommended)
    result = score_code_quality(
        content="class MyModel(BaseModel): x: int",
        language="python",
        preset=OnexStrictnessLevel.STRICT,
    )

    if result["success"]:
        print(f"Quality score: {result['quality_score']}")
        print(f"ONEX compliant: {result['onex_compliant']}")
        dimensions: DimensionScores = result["dimensions"]
        print(f"Complexity: {dimensions['complexity']}")
        for rec in result["recommendations"]:
            print(f"  - {rec}")

Example:
    >>> from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
    ...     score_code_quality,
    ...     OnexStrictnessLevel,
    ... )
    >>> code = '''
    ... from pydantic import BaseModel, Field
    ...
    ... class UserModel(BaseModel):
    ...     name: str = Field(..., description="User name")
    ...     age: int = Field(..., ge=0)
    ...
    ...     model_config = {"frozen": True, "extra": "forbid"}
    ... '''
    >>> result = score_code_quality(code, "python")
    >>> result["success"]
    True
    >>> result["quality_score"] > 0.5
    True
    >>> # Using strict preset for production
    >>> result = score_code_quality(code, "python", preset=OnexStrictnessLevel.STRICT)
    >>> result["success"]
    True
"""

from omniintelligence.nodes.node_quality_scoring_compute.handlers.enum_onex_strictness_level import (
    OnexStrictnessLevel,
)
from omniintelligence.nodes.node_quality_scoring_compute.handlers.exceptions import (
    QualityScoringComputeError,
    QualityScoringValidationError,
)
from omniintelligence.nodes.node_quality_scoring_compute.handlers.handler_compute import (
    handle_quality_scoring_compute,
)
from omniintelligence.nodes.node_quality_scoring_compute.handlers.handler_quality_scoring import (
    ANALYSIS_VERSION,
    DEFAULT_WEIGHTS,
    score_code_quality,
)
from omniintelligence.nodes.node_quality_scoring_compute.handlers.presets import (
    LENIENT_THRESHOLD,
    LENIENT_WEIGHTS,
    STANDARD_THRESHOLD,
    STANDARD_WEIGHTS,
    STRICT_THRESHOLD,
    STRICT_WEIGHTS,
    get_threshold_for_preset,
    get_weights_for_preset,
)
from omniintelligence.nodes.node_quality_scoring_compute.handlers.protocols import (
    DimensionScores,
    QualityScoringResult,
    create_error_dimensions,
)

__all__ = [
    "ANALYSIS_VERSION",
    "DEFAULT_WEIGHTS",
    "LENIENT_THRESHOLD",
    "LENIENT_WEIGHTS",
    "STANDARD_THRESHOLD",
    "STANDARD_WEIGHTS",
    "STRICT_THRESHOLD",
    "STRICT_WEIGHTS",
    "DimensionScores",
    "OnexStrictnessLevel",
    "QualityScoringComputeError",
    "QualityScoringResult",
    "QualityScoringValidationError",
    "create_error_dimensions",
    "get_threshold_for_preset",
    "get_weights_for_preset",
    "handle_quality_scoring_compute",
    "score_code_quality",
]
