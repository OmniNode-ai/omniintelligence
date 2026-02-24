# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Pattern Learning Compute Node.

This package provides the pattern learning (aggregation) compute node
following the ONEX "thin shell, fat handler" pattern.

SEMANTIC NOTE:
    The term "learning" in the node name is legacy. This node AGGREGATES and
    SUMMARIZES observed patterns. It does NOT perform statistical learning
    or weight updates. Conceptually, this is pattern summarization:
    extract, cluster, score, deduplicate.

Pipeline Flow:
    1. Feature Extraction (handler_feature_extraction)
    2. Similarity + Clustering (handler_pattern_clustering)
    3. Confidence Scoring (handler_confidence_scoring)
    4. Deduplication (handler_deduplication)
    5. Orchestration (handler_pattern_learning)

Usage:
    from omniintelligence.nodes.node_pattern_learning_compute import (
        NodePatternLearningCompute,
        aggregate_patterns,
        PatternLearningValidationError,
        PatternLearningComputeError,
    )

Ticket: OMN-1663
"""

from omniintelligence.nodes.node_pattern_learning_compute.handlers import (
    PatternLearningComputeError,
    PatternLearningValidationError,
    aggregate_patterns,
)
from omniintelligence.nodes.node_pattern_learning_compute.node import (
    NodePatternLearningCompute,
)

__all__ = [
    "NodePatternLearningCompute",
    "PatternLearningComputeError",
    "PatternLearningValidationError",
    "aggregate_patterns",
]
