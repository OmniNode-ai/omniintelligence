# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Confidence scoring handler for pattern learning compute node.

This module computes decomposed confidence scores for pattern clusters,
providing component-level visibility for debugging and analysis.

Design Philosophy:
    Confidence scores are DECOMPOSED, not monolithic. A single confidence
    value cannot answer "why did this pattern score high?" - but component
    scores can.

    Components:
    - label_agreement: Do cluster members agree on pattern_type?
    - cluster_cohesion: Are cluster members structurally similar?
    - frequency_factor: Is the pattern observed frequently enough?

Confidence Formula:
    confidence = 0.40 * label_agreement + 0.30 * cluster_cohesion + 0.30 * frequency_factor

    Weight rationale:
    - Label agreement (0.40): Strongest signal - consistent labeling indicates clear pattern
    - Cluster cohesion (0.30): Strong pattern has similar members
    - Frequency factor (0.30): Rare patterns need more scrutiny

WARNING:
    NEVER make downstream decisions solely on the confidence field.
    The rolled-up score is for convenience only. Inspect components.

Usage:
    from omniintelligence.nodes.node_pattern_learning_compute.handlers.handler_confidence_scoring import (
        compute_cluster_scores,
    )

    scores = compute_cluster_scores(cluster)
    # scores["label_agreement"], scores["cluster_cohesion"], etc.
"""

from __future__ import annotations

from omniintelligence.nodes.node_pattern_learning_compute.handlers.exceptions import (
    PatternLearningValidationError,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.presets import (
    DEFAULT_MIN_FREQUENCY,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.protocols import (
    PatternClusterDict,
    PatternScoreComponentsDict,
)

# =============================================================================
# Confidence Weight Constants
# =============================================================================

# Weights for combining score components into confidence.
# These are canonical for this handler and NOT configurable inputs.
_LABEL_AGREEMENT_WEIGHT: float = 0.40
_CLUSTER_COHESION_WEIGHT: float = 0.30
_FREQUENCY_FACTOR_WEIGHT: float = 0.30

# Validate weights sum to 1.0 at module load time
_confidence_weights_sum = (
    _LABEL_AGREEMENT_WEIGHT + _CLUSTER_COHESION_WEIGHT + _FREQUENCY_FACTOR_WEIGHT
)
assert abs(_confidence_weights_sum - 1.0) < 1e-9, (
    f"Confidence weights must sum to 1.0, got {_confidence_weights_sum}"
)


# =============================================================================
# Public API
# =============================================================================


def compute_cluster_scores(
    cluster: PatternClusterDict,
    min_frequency: int = DEFAULT_MIN_FREQUENCY,
) -> PatternScoreComponentsDict:
    """Compute decomposed confidence scores for a pattern cluster.

    This function reads pre-computed values from the cluster (label_agreement,
    internal_similarity) and computes frequency_factor based on member_count.

    IMPORTANT: This function does NOT recompute similarity or agreement.
    Those values are computed once during clustering and read directly here.

    Args:
        cluster: Pattern cluster with pre-computed label_agreement and
            internal_similarity fields.
        min_frequency: Minimum cluster size for full frequency contribution.
            Defaults to DEFAULT_MIN_FREQUENCY (5).

    Returns:
        PatternScoreComponentsDict containing:
        - label_agreement: Read directly from cluster
        - cluster_cohesion: Read from cluster["internal_similarity"]
        - frequency_factor: min(1.0, member_count / min_frequency)
        - confidence: Weighted sum of components (0.40 + 0.30 + 0.30)

    Raises:
        PatternLearningValidationError: If cluster is empty (member_count == 0),
            if min_frequency is not positive, or if pre-computed values
            (label_agreement, internal_similarity) are outside [0.0, 1.0].
            These conditions indicate a bug upstream and should explode loudly.

    Examples:
        >>> cluster = {"member_count": 5, "internal_similarity": 0.8, "label_agreement": 0.9, ...}
        >>> scores = compute_cluster_scores(cluster)
        >>> scores["confidence"]
        0.86  # = 0.4*0.9 + 0.3*0.8 + 0.3*1.0

        >>> # Inspect components to understand the score
        >>> if scores["cluster_cohesion"] < 0.5:
        ...     print("Low cohesion: members are structurally different")
    """
    # Validate non-empty cluster
    member_count = cluster["member_count"]
    if member_count == 0:
        raise PatternLearningValidationError(
            f"Cannot compute scores for empty cluster {cluster['cluster_id']}. "
            "Empty clusters indicate a bug in the clustering phase."
        )

    # Validate min_frequency is positive (prevents division by zero)
    if min_frequency <= 0:
        raise PatternLearningValidationError(
            f"min_frequency must be positive, got {min_frequency}. "
            "A zero or negative min_frequency is invalid for frequency factor calculation."
        )

    # Read pre-computed values (do NOT recompute)
    label_agreement = cluster["label_agreement"]
    cluster_cohesion = cluster["internal_similarity"]

    # Validate pre-computed values are in valid range [0.0, 1.0]
    # If upstream has a bug producing invalid values, fail loudly here
    if not (0.0 <= label_agreement <= 1.0):
        raise PatternLearningValidationError(
            f"label_agreement must be in range [0.0, 1.0], got {label_agreement} "
            f"for cluster {cluster['cluster_id']}. "
            "This indicates a bug in the clustering phase."
        )
    if not (0.0 <= cluster_cohesion <= 1.0):
        raise PatternLearningValidationError(
            f"internal_similarity must be in range [0.0, 1.0], got {cluster_cohesion} "
            f"for cluster {cluster['cluster_id']}. "
            "This indicates a bug in the clustering phase."
        )

    # Compute frequency factor: monotonic and capped at 1.0
    frequency_factor = min(1.0, member_count / min_frequency)

    # Compute derived confidence score
    confidence = (
        _LABEL_AGREEMENT_WEIGHT * label_agreement
        + _CLUSTER_COHESION_WEIGHT * cluster_cohesion
        + _FREQUENCY_FACTOR_WEIGHT * frequency_factor
    )

    return PatternScoreComponentsDict(
        label_agreement=label_agreement,
        cluster_cohesion=cluster_cohesion,
        frequency_factor=frequency_factor,
        confidence=confidence,
    )


__all__ = ["compute_cluster_scores"]
