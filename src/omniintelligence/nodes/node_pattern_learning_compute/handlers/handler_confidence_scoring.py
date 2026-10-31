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

from omniintelligence.nodes.node_pattern_learning_compute.handlers.confidence_scoring_core import (
    _compute_cluster_scores,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.protocols import (
    PatternScoreComponentsDict,
)
from omniintelligence.nodes.node_pattern_learning_compute.models.model_confidence_scoring_request import (
    ModelConfidenceScoringRequest,
)


class HandlerConfidenceScoring:
    """Typed entry point for _compute_cluster_scores."""

    def handle(
        self, request: ModelConfidenceScoringRequest
    ) -> PatternScoreComponentsDict:
        """Delegate to the preserved computation."""
        return _compute_cluster_scores(request.cluster, request.min_frequency)


__all__ = ["HandlerConfidenceScoring"]
