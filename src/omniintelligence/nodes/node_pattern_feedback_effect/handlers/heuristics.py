# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Pure heuristic functions for contribution attribution.

This module implements contribution heuristics for attributing session outcomes
to patterns. These are explicitly HEURISTICS, not causal attribution - multi-injection
sessions make true causal attribution impossible without controlled experiments.

The functions are pure (no side effects) and operate on ordered lists of pattern IDs.
The order must be canonical: (injected_at, injection_id) from the database.

Duplicate Handling:
    Patterns that appear multiple times across injections accumulate weights.
    For RECENCY_WEIGHTED, later appearances contribute more. After accumulation,
    weights are normalized to sum to 1.0.

Reference:
    - OMN-1679: FEEDBACK-004 contribution heuristic implementation
    - ~/.claude/plans/elegant-waddling-hinton.md

Example:
    >>> from uuid import UUID
    >>> pattern_ids = [UUID('...'), UUID('...'), UUID('...')]
    >>> weights, confidence = apply_heuristic(
    ...     method=EnumHeuristicMethod.EQUAL_SPLIT,
    ...     ordered_pattern_ids=pattern_ids,
    ... )
    >>> assert abs(sum(weights.values()) - 1.0) < 1e-9
"""

from __future__ import annotations

from uuid import UUID

from omniintelligence.enums import EnumHeuristicMethod, HEURISTIC_CONFIDENCE


# =============================================================================
# Type Definitions
# =============================================================================

# Weights map pattern_id (as string for JSON) to contribution score
ContributionWeights = dict[str, float]


# =============================================================================
# Core Heuristic Functions
# =============================================================================


def compute_equal_split(ordered_pattern_ids: list[UUID]) -> ContributionWeights:
    """Compute equal contribution weights for all patterns.

    Each unique pattern gets equal credit (1/N). If a pattern appears multiple
    times, its weight is multiplied by the occurrence count, then normalized.

    Args:
        ordered_pattern_ids: Pattern IDs in canonical order (injected_at, injection_id).
            May contain duplicates.

    Returns:
        Dictionary mapping pattern_id (as string) to weight. Weights sum to 1.0.

    Example:
        >>> from uuid import UUID
        >>> p1, p2 = UUID(int=1), UUID(int=2)
        >>> weights = compute_equal_split([p1, p2, p1])  # p1 appears twice
        >>> weights[str(p1)]  # 2/3
        0.6666666666666666
        >>> weights[str(p2)]  # 1/3
        0.3333333333333333
    """
    if not ordered_pattern_ids:
        return {}

    n = len(ordered_pattern_ids)
    weight_per_occurrence = 1.0 / n

    # Accumulate weights for each pattern
    weights: dict[str, float] = {}
    for pid in ordered_pattern_ids:
        key = str(pid)
        weights[key] = weights.get(key, 0.0) + weight_per_occurrence

    return weights


def compute_recency_weighted(ordered_pattern_ids: list[UUID]) -> ContributionWeights:
    """Compute recency-weighted contribution scores.

    Later patterns get more credit using a linear ramp: position i (1-indexed)
    gets raw weight i. Weights are then normalized to sum to 1.0.

    If a pattern appears multiple times, it accumulates weight from each
    position, preserving the "later is better" signal across the session.

    Args:
        ordered_pattern_ids: Pattern IDs in canonical order (injected_at, injection_id).
            May contain duplicates. Earlier = lower index.

    Returns:
        Dictionary mapping pattern_id (as string) to weight. Weights sum to 1.0.

    Example:
        >>> from uuid import UUID
        >>> p1, p2, p3 = UUID(int=1), UUID(int=2), UUID(int=3)
        >>> weights = compute_recency_weighted([p1, p2, p3])
        >>> # Raw weights: 1, 2, 3. Sum = 6.
        >>> weights[str(p1)]  # 1/6
        0.16666666666666666
        >>> weights[str(p3)]  # 3/6
        0.5
    """
    if not ordered_pattern_ids:
        return {}

    n = len(ordered_pattern_ids)
    # Sum of 1..n = n*(n+1)/2
    total_weight = n * (n + 1) / 2

    # Accumulate weights with position-based scoring
    weights: dict[str, float] = {}
    for i, pid in enumerate(ordered_pattern_ids):
        key = str(pid)
        position_weight = (i + 1) / total_weight  # 1-indexed position
        weights[key] = weights.get(key, 0.0) + position_weight

    return weights


def compute_first_match(ordered_pattern_ids: list[UUID]) -> ContributionWeights:
    """Assign all credit to the first pattern.

    This is the simplest heuristic but has the lowest confidence because it
    ignores all patterns except the first one injected.

    Args:
        ordered_pattern_ids: Pattern IDs in canonical order (injected_at, injection_id).
            May contain duplicates.

    Returns:
        Dictionary mapping the first pattern_id (as string) to 1.0.
        Empty dict if no patterns.

    Example:
        >>> from uuid import UUID
        >>> p1, p2 = UUID(int=1), UUID(int=2)
        >>> weights = compute_first_match([p1, p2, p1])
        >>> weights
        {'00000000-0000-0000-0000-000000000001': 1.0}
    """
    if not ordered_pattern_ids:
        return {}

    return {str(ordered_pattern_ids[0]): 1.0}


# =============================================================================
# Dispatcher
# =============================================================================


def apply_heuristic(
    method: EnumHeuristicMethod,
    ordered_pattern_ids: list[UUID],
) -> tuple[ContributionWeights, float]:
    """Apply the specified heuristic method to compute contribution weights.

    This is the main entry point for heuristic computation. It dispatches to
    the appropriate method implementation and returns both the weights and
    the confidence score.

    Args:
        method: The heuristic method to use.
        ordered_pattern_ids: Pattern IDs in canonical order (injected_at, injection_id).
            May contain duplicates.

    Returns:
        Tuple of (weights, confidence):
            - weights: Dict mapping pattern_id (as string) to contribution score.
                       Weights sum to 1.0 (or empty dict if no patterns).
            - confidence: Float between 0 and 1 indicating confidence in the heuristic.

    Raises:
        ValueError: If method is not a valid EnumHeuristicMethod.

    Example:
        >>> from uuid import UUID
        >>> from omniintelligence.enums import EnumHeuristicMethod
        >>> patterns = [UUID(int=1), UUID(int=2)]
        >>> weights, confidence = apply_heuristic(
        ...     method=EnumHeuristicMethod.EQUAL_SPLIT,
        ...     ordered_pattern_ids=patterns,
        ... )
        >>> confidence
        0.5
    """
    if not ordered_pattern_ids:
        return {}, 0.0

    # Dispatch to appropriate method
    if method == EnumHeuristicMethod.EQUAL_SPLIT:
        weights = compute_equal_split(ordered_pattern_ids)
    elif method == EnumHeuristicMethod.RECENCY_WEIGHTED:
        weights = compute_recency_weighted(ordered_pattern_ids)
    elif method == EnumHeuristicMethod.FIRST_MATCH:
        weights = compute_first_match(ordered_pattern_ids)
    else:
        raise ValueError(f"Unknown heuristic method: {method}")

    confidence = HEURISTIC_CONFIDENCE.get(method.value, 0.0)

    return weights, confidence


__all__ = [
    "ContributionWeights",
    "apply_heuristic",
    "compute_equal_split",
    "compute_first_match",
    "compute_recency_weighted",
]
