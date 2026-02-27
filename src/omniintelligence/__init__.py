# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

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

import contextlib

# omnibase_core is a required runtime dependency for full functionality.
# This guard prevents hard failures in environments where omnibase_core is
# not yet installed (e.g., pre-commit isolated venvs, CI without editable
# installs). Callers that need these symbols must install omnibase_core.
with contextlib.suppress(ImportError):  # pragma: no cover
    from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
        DEFAULT_WEIGHTS,
        DimensionScores,
        OnexStrictnessLevel,
        QualityScoringComputeError,
        QualityScoringResult,
        QualityScoringValidationError,
        score_code_quality,
    )

__version__ = "0.7.0"

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
