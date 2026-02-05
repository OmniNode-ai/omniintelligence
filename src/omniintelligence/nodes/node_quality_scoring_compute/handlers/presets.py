"""ONEX configuration presets for quality scoring.

This module provides pre-configured weight sets and thresholds for different
ONEX compliance strictness levels. Presets enable users to quickly apply
standardized quality requirements without manually configuring all parameters.

Strictness Levels:
    - STRICT: Production-ready code with high quality bar. Emphasizes documentation
      and pattern adherence. Use for production deployments and code reviews.
    - STANDARD: Default balanced requirements suitable for most use cases.
      Provides good coverage across all dimensions without being overly strict.
    - LENIENT: Development/prototyping mode with lower quality bar. More forgiving
      on documentation and pattern requirements. Use for rapid prototyping,
      exploratory code, or legacy code assessment.

Weight Distribution:
    All presets use weights that sum to 1.0 across six dimensions:
    - complexity: Cyclomatic complexity (inverted - lower is better)
    - maintainability: Code structure and naming conventions
    - documentation: Docstring and comment coverage
    - temporal_relevance: Code freshness indicators
    - patterns: ONEX pattern adherence
    - architectural: Module organization

Usage:
    from omniintelligence.nodes.node_quality_scoring_compute.handlers.presets import (
        OnexStrictnessLevel,
        get_weights_for_preset,
        get_threshold_for_preset,
    )

    # Get preset configuration
    weights = get_weights_for_preset(OnexStrictnessLevel.STRICT)
    threshold = get_threshold_for_preset(OnexStrictnessLevel.STRICT)

    # Use with score_code_quality
    result = score_code_quality(
        content=code,
        language="python",
        weights=weights,
        onex_threshold=threshold,
    )

Example:
    >>> from omniintelligence.nodes.node_quality_scoring_compute.handlers.presets import (
    ...     OnexStrictnessLevel,
    ...     get_weights_for_preset,
    ...     get_threshold_for_preset,
    ... )
    >>> weights = get_weights_for_preset(OnexStrictnessLevel.STANDARD)
    >>> sum(weights.values())
    1.0
    >>> threshold = get_threshold_for_preset(OnexStrictnessLevel.STANDARD)
    >>> threshold
    0.7
"""

from __future__ import annotations

from typing import Final

from omniintelligence.nodes.node_quality_scoring_compute.handlers.enum_onex_strictness_level import (
    OnexStrictnessLevel,
)

# =============================================================================
# Preset Weight Configurations
# =============================================================================

STRICT_WEIGHTS: Final[dict[str, float]] = {
    "complexity": 0.15,
    "maintainability": 0.20,
    "documentation": 0.20,  # Higher doc requirements for production
    "temporal_relevance": 0.10,
    "patterns": 0.20,  # Higher pattern requirements for production
    "architectural": 0.15,
}
"""Weights for STRICT preset - production-ready code.

Emphasizes documentation and ONEX pattern adherence.
Lower weight on temporal_relevance since production code
should already have resolved TODO/FIXME items.
"""

STANDARD_WEIGHTS: Final[dict[str, float]] = {
    "complexity": 0.20,
    "maintainability": 0.20,
    "documentation": 0.15,
    "temporal_relevance": 0.15,
    "patterns": 0.15,
    "architectural": 0.15,
}
"""Weights for STANDARD preset - balanced requirements.

Equal emphasis across all quality dimensions.
This matches the DEFAULT_WEIGHTS used when no preset is specified.
"""

LENIENT_WEIGHTS: Final[dict[str, float]] = {
    "complexity": 0.25,  # More forgiving on complexity for prototypes
    "maintainability": 0.20,
    "documentation": 0.10,  # Lower doc requirements for rapid development
    "temporal_relevance": 0.20,
    "patterns": 0.10,  # Lower pattern requirements for exploration
    "architectural": 0.15,
}
"""Weights for LENIENT preset - development/prototyping mode.

Higher tolerance for complexity and lower requirements for
documentation and patterns. Useful for:
- Rapid prototyping
- Exploratory coding
- Legacy code assessment
- Learning exercises
"""

# =============================================================================
# Preset Thresholds
# =============================================================================

STRICT_THRESHOLD: Final[float] = 0.8
"""ONEX compliance threshold for STRICT preset.

Code must score 0.8 or higher to be considered ONEX compliant.
This is a high bar suitable for production deployments.
"""

STANDARD_THRESHOLD: Final[float] = 0.7
"""ONEX compliance threshold for STANDARD preset.

Code must score 0.7 or higher to be considered ONEX compliant.
This is the default threshold providing a balanced quality gate.
"""

LENIENT_THRESHOLD: Final[float] = 0.5
"""ONEX compliance threshold for LENIENT preset.

Code must score 0.5 or higher to be considered ONEX compliant.
This low bar is suitable for development and prototyping phases.
"""

# =============================================================================
# Mapping Dictionaries
# =============================================================================

_PRESET_WEIGHTS: Final[dict[OnexStrictnessLevel, dict[str, float]]] = {
    OnexStrictnessLevel.STRICT: STRICT_WEIGHTS,
    OnexStrictnessLevel.STANDARD: STANDARD_WEIGHTS,
    OnexStrictnessLevel.LENIENT: LENIENT_WEIGHTS,
}
"""Internal mapping from strictness level to weight configuration."""

_PRESET_THRESHOLDS: Final[dict[OnexStrictnessLevel, float]] = {
    OnexStrictnessLevel.STRICT: STRICT_THRESHOLD,
    OnexStrictnessLevel.STANDARD: STANDARD_THRESHOLD,
    OnexStrictnessLevel.LENIENT: LENIENT_THRESHOLD,
}
"""Internal mapping from strictness level to compliance threshold."""


# =============================================================================
# Helper Functions
# =============================================================================


def get_weights_for_preset(preset: OnexStrictnessLevel) -> dict[str, float]:
    """Get dimension weights for a given ONEX strictness preset.

    Args:
        preset: The ONEX strictness level to get weights for.

    Returns:
        Dictionary mapping dimension names to their weights.
        All weights sum to 1.0.

    Example:
        >>> weights = get_weights_for_preset(OnexStrictnessLevel.STRICT)
        >>> weights["documentation"]
        0.2
        >>> sum(weights.values())
        1.0
    """
    return _PRESET_WEIGHTS[preset].copy()


def get_threshold_for_preset(preset: OnexStrictnessLevel) -> float:
    """Get ONEX compliance threshold for a given strictness preset.

    Args:
        preset: The ONEX strictness level to get threshold for.

    Returns:
        Float threshold value (0.0-1.0). Scores at or above this
        threshold are considered ONEX compliant.

    Example:
        >>> threshold = get_threshold_for_preset(OnexStrictnessLevel.STRICT)
        >>> threshold
        0.8
    """
    return _PRESET_THRESHOLDS[preset]


__all__ = [
    "LENIENT_THRESHOLD",
    "LENIENT_WEIGHTS",
    "STANDARD_THRESHOLD",
    "STANDARD_WEIGHTS",
    "STRICT_THRESHOLD",
    "STRICT_WEIGHTS",
    "OnexStrictnessLevel",
    "get_threshold_for_preset",
    "get_weights_for_preset",
]
