"""Shared utility functions for pattern learning handlers.

This module provides common utility functions used across multiple
pattern learning handlers, following DRY principles.

ONEX Compliance:
    - Pure functional design (no side effects)
    - Deterministic results for same inputs
    - No external service calls or I/O operations

Usage:
    from omniintelligence.nodes.pattern_learning_compute.handlers.utils import (
        jaccard_similarity,
        normalize_identifier,
        normalize_identifiers,
    )

    # Compute similarity between two sets
    sim = jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"})
    assert sim == 0.5  # intersection=2, union=4

    # Normalize identifiers for consistent comparison
    normalized = normalize_identifiers(["MyClass", "my_func", "MY_CONST"])
    assert normalized == ("myclass", "my_const", "my_func")  # sorted
"""

from __future__ import annotations

from collections.abc import Iterable


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


__all__ = [
    "compute_normalized_distance",
    "distance_to_similarity",
    "jaccard_similarity",
    "normalize_identifier",
    "normalize_identifiers",
]
