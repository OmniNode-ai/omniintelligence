"""Shared utility functions for pattern learning handlers.

This module provides common utility functions used across multiple
pattern learning handlers, following DRY principles.

ONEX Compliance:
    - Pure functional design (no side effects)
    - Deterministic results for same inputs
    - No external service calls or I/O operations

Usage:
    from omniintelligence.nodes.node_pattern_learning_compute.handlers.utils import (
        jaccard_similarity,
        normalize_identifier,
        normalize_identifiers,
        validate_similarity_weights,
    )

    # Compute similarity between two sets
    sim = jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"})
    assert sim == 0.5  # intersection=2, union=4

    # Normalize identifiers for consistent comparison
    normalized = normalize_identifiers(["MyClass", "my_func", "MY_CONST"])
    assert normalized == ("myclass", "my_const", "my_func")  # sorted

    # Validate custom similarity weights
    weights = {"keyword": 0.30, "pattern": 0.25, "structural": 0.20, "label": 0.15, "context": 0.10}
    validate_similarity_weights(weights)  # Returns True
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omniintelligence.nodes.node_pattern_learning_compute.handlers.protocols import (
        SimilarityWeightsDict,
    )


def jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    """Compute Jaccard similarity coefficient between two sets.

    Jaccard similarity is defined as |A intersection B| / |A union B|.
    Returns 0.0 if both sets are empty (by convention).

    Args:
        set_a: First set of strings.
        set_b: Second set of strings.

    Returns:
        Jaccard similarity coefficient in range [0.0, 1.0].
        Returns 1.0 if both sets are identical.
        Returns 0.0 if sets are disjoint OR both empty.

    Examples:
        >>> jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"})
        0.5
        >>> jaccard_similarity({"a", "b"}, {"a", "b"})
        1.0
        >>> jaccard_similarity({"a"}, {"b"})
        0.0
        >>> jaccard_similarity(set(), set())
        0.0
    """
    if not set_a and not set_b:
        return 0.0

    intersection = len(set_a & set_b)
    union = len(set_a | set_b)

    return intersection / union if union > 0 else 0.0


def normalize_identifier(identifier: str) -> str:
    """Normalize a single identifier for consistent comparison.

    Normalization:
        - Convert to lowercase
        - Strip leading/trailing whitespace

    Args:
        identifier: The identifier string to normalize.

    Returns:
        Normalized identifier string.

    Examples:
        >>> normalize_identifier("MyClassName")
        'myclassname'
        >>> normalize_identifier("  CONSTANT  ")
        'constant'
    """
    return identifier.strip().lower()


def normalize_identifiers(identifiers: Iterable[str]) -> tuple[str, ...]:
    """Normalize and sort a collection of identifiers.

    Applies normalization to each identifier, removes duplicates,
    and returns a sorted tuple for deterministic comparison.

    Normalization (per identifier):
        - Convert to lowercase
        - Strip whitespace
        - Remove empty strings

    Args:
        identifiers: Iterable of identifier strings.

    Returns:
        Sorted tuple of unique normalized identifiers.

    Examples:
        >>> normalize_identifiers(["MyClass", "my_func", "MyClass"])
        ('my_func', 'myclass')
        >>> normalize_identifiers(["B", "A", "C"])
        ('a', 'b', 'c')
        >>> normalize_identifiers([])
        ()
    """
    normalized = {normalize_identifier(ident) for ident in identifiers}
    # Remove empty strings that may result from whitespace-only inputs
    normalized.discard("")
    return tuple(sorted(normalized))


def compute_normalized_distance(
    value_a: float,
    value_b: float,
    max_expected: float,
) -> float:
    """Compute normalized distance between two numeric values.

    Distance is normalized to [0.0, 1.0] range using max_expected
    as the scaling factor. Values beyond max_expected are clamped.

    Args:
        value_a: First numeric value.
        value_b: Second numeric value.
        max_expected: Maximum expected difference for normalization.
            Must be positive.

    Returns:
        Normalized distance in [0.0, 1.0].
        0.0 means identical, 1.0 means maximally different.

    Raises:
        ValueError: If max_expected is not positive.

    Examples:
        >>> compute_normalized_distance(10, 10, 100)
        0.0
        >>> compute_normalized_distance(0, 100, 100)
        1.0
        >>> compute_normalized_distance(25, 75, 100)
        0.5
    """
    if max_expected <= 0:
        raise ValueError(f"max_expected must be positive, got {max_expected}")

    diff = abs(value_a - value_b)
    normalized = min(diff / max_expected, 1.0)
    return normalized


def distance_to_similarity(distance: float) -> float:
    """Convert a distance metric to a similarity metric.

    Simply inverts the distance: similarity = 1.0 - distance.

    Args:
        distance: Distance value in [0.0, 1.0].

    Returns:
        Similarity value in [0.0, 1.0].

    Examples:
        >>> distance_to_similarity(0.0)
        1.0
        >>> distance_to_similarity(1.0)
        0.0
        >>> distance_to_similarity(0.3)
        0.7
    """
    return 1.0 - distance


# Required keys for SimilarityWeightsDict
_REQUIRED_WEIGHT_KEYS: frozenset[str] = frozenset(
    {"keyword", "pattern", "structural", "label", "context"}
)

# Default tolerance for weight sum validation (floating point comparison)
_WEIGHT_SUM_TOLERANCE: float = 1e-6


def validate_similarity_weights(
    weights: SimilarityWeightsDict,
    *,
    tolerance: float = _WEIGHT_SUM_TOLERANCE,
) -> bool:
    """Validate similarity weights for completeness and correctness.

    Validates that:
    1. All required keys are present (keyword, pattern, structural, label, context)
    2. All values are floats in the range [0.0, 1.0]
    3. All values sum to approximately 1.0 (within tolerance)

    This function should be called when callers provide custom weights
    to ensure they form a valid probability distribution.

    Args:
        weights: Dictionary of similarity weights to validate.
        tolerance: Tolerance for floating-point comparison when checking
            that weights sum to 1.0. Defaults to 1e-6.

    Returns:
        True if weights are valid. This enables chaining/assertions:
            assert validate_similarity_weights(custom_weights)

    Raises:
        PatternLearningValidationError: If validation fails. The error
            message describes the specific validation failure:
            - Missing keys
            - Values outside [0.0, 1.0] range
            - Sum not equal to 1.0 (within tolerance)

    Examples:
        >>> from omniintelligence.nodes.node_pattern_learning_compute.handlers.presets import (
        ...     DEFAULT_SIMILARITY_WEIGHTS,
        ... )
        >>> validate_similarity_weights(DEFAULT_SIMILARITY_WEIGHTS)
        True

        >>> # Custom weights that sum to 1.0
        >>> custom = {"keyword": 0.4, "pattern": 0.3, "structural": 0.15, "label": 0.1, "context": 0.05}
        >>> validate_similarity_weights(custom)
        True

        >>> # Missing key raises error
        >>> validate_similarity_weights({"keyword": 0.5})  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        PatternLearningValidationError: Missing required weight keys: ...

        >>> # Value out of range raises error
        >>> bad_weights = {"keyword": 1.5, "pattern": 0.25, "structural": 0.20, "label": 0.15, "context": 0.10}
        >>> validate_similarity_weights(bad_weights)  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        PatternLearningValidationError: Weight values must be in range [0.0, 1.0]: ...

        >>> # Weights not summing to 1.0 raises error
        >>> bad_sum = {"keyword": 0.5, "pattern": 0.5, "structural": 0.5, "label": 0.5, "context": 0.5}
        >>> validate_similarity_weights(bad_sum)  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        PatternLearningValidationError: Weight values must sum to 1.0: ...
    """
    # Import here to avoid circular imports at module level
    from omniintelligence.nodes.node_pattern_learning_compute.handlers.exceptions import (
        PatternLearningValidationError,
    )

    # Check for missing required keys
    provided_keys = set(weights.keys())
    missing_keys = _REQUIRED_WEIGHT_KEYS - provided_keys
    if missing_keys:
        sorted_missing = sorted(missing_keys)
        raise PatternLearningValidationError(
            f"Missing required weight keys: {sorted_missing}. "
            f"Required keys are: {sorted(_REQUIRED_WEIGHT_KEYS)}"
        )

    # Check for extra keys (warning-worthy but not an error)
    extra_keys = provided_keys - _REQUIRED_WEIGHT_KEYS
    # We don't raise for extra keys, just ignore them (TypedDict allows extras)

    # Validate each weight value is in [0.0, 1.0]
    out_of_range: list[tuple[str, float]] = []
    for key in _REQUIRED_WEIGHT_KEYS:
        value = weights[key]  # type: ignore[literal-required]
        if not isinstance(value, int | float):
            raise PatternLearningValidationError(
                f"Weight value for '{key}' must be a number, got {type(value).__name__}"
            )
        if not (0.0 <= value <= 1.0):
            out_of_range.append((key, value))

    if out_of_range:
        details = ", ".join(f"{k}={v}" for k, v in sorted(out_of_range))
        raise PatternLearningValidationError(
            f"Weight values must be in range [0.0, 1.0]: {details}"
        )

    # Validate weights sum to approximately 1.0
    total = sum(weights[key] for key in _REQUIRED_WEIGHT_KEYS)  # type: ignore[literal-required]
    if abs(total - 1.0) > tolerance:
        raise PatternLearningValidationError(
            f"Weight values must sum to 1.0 (within tolerance {tolerance}): "
            f"got {total:.10f}"
        )

    return True


__all__ = [
    "compute_normalized_distance",
    "distance_to_similarity",
    "jaccard_similarity",
    "normalize_identifier",
    "normalize_identifiers",
    "validate_similarity_weights",
]
