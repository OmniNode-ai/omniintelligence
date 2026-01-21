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

Quality Dimensions:
    - patterns: ONEX pattern adherence (frozen models, TypedDict, Protocol, etc.)
    - type_coverage: Type annotation completeness
    - maintainability: Code structure quality (function length, naming conventions)
    - complexity: Cyclomatic complexity approximation (inverted - lower is better)
    - documentation: Docstring and comment coverage

Usage:
    from omniintelligence.nodes.quality_scoring_compute.handlers import (
        score_code_quality,
        QualityScoringResult,
        DEFAULT_WEIGHTS,
    )

    result: QualityScoringResult = score_code_quality(
        content="class MyModel(BaseModel): x: int",
        language="python",
        weights=DEFAULT_WEIGHTS,
        onex_threshold=0.7,
    )

    if result["success"]:
        print(f"Quality score: {result['quality_score']}")
        print(f"ONEX compliant: {result['onex_compliant']}")
        for rec in result["recommendations"]:
            print(f"  - {rec}")

Example:
    >>> from omniintelligence.nodes.quality_scoring_compute.handlers import (
    ...     score_code_quality,
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
"""

from omniintelligence.nodes.quality_scoring_compute.handlers.exceptions import (
    QualityScoringComputeError,
    QualityScoringValidationError,
)
from omniintelligence.nodes.quality_scoring_compute.handlers.handler_quality_scoring import (
    ANALYSIS_VERSION,
    DEFAULT_WEIGHTS,
    score_code_quality,
)
from omniintelligence.nodes.quality_scoring_compute.handlers.protocols import (
    QualityScoringResult,
)

__all__ = [
    "ANALYSIS_VERSION",
    "DEFAULT_WEIGHTS",
    "QualityScoringComputeError",
    "QualityScoringResult",
    "QualityScoringValidationError",
    "score_code_quality",
]
