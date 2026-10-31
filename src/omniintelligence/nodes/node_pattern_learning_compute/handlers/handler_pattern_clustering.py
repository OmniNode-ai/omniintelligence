# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Pattern clustering handler for pattern learning compute node.

Core clustering functionality for the pattern learning
pipeline. It computes similarity between extracted features and clusters similar
patterns together using single-linkage clustering.

Algorithm Overview:
    1. Compute pairwise similarity matrix between all feature sets
    2. Apply single-linkage clustering (merge if ANY pair >= threshold)
    3. Select medoid (most representative member) as centroid
    4. Emit replay artifacts for debugging and comparison

Determinism Guarantees (CRITICAL):
    All operations are deterministic given the same input:
    - Items sorted by item_id before processing
    - Edges built in sorted (i, j) order where i < j
    - Cluster leader = smallest item_id in cluster
    - cluster_id assigned by sorted leader order
    - Medoid tie-break by smallest item_id

Similarity Components (5-component weighted):
    - keyword (0.30): Identifier/import Jaccard similarity
    - pattern (0.25): ONEX pattern indicator Jaccard similarity
    - structural (0.20): Normalized structural distance (inverted)
    - label (0.15): Training label Jaccard similarity
    - context (0.10): Domain/framework alignment

Context Similarity Rules:
    - Both empty: 0.5 (neutral - no information)
    - One empty: 0.0 (asymmetric penalty for missing context)
    - Both present: Jaccard similarity

Usage:
    from omniintelligence.nodes.node_pattern_learning_compute.handlers.handler_pattern_clustering import (
        compute_similarity,
        cluster_patterns,
    )

    # Compute similarity between two feature sets
    result = compute_similarity(features_a, features_b)

    # Cluster a list of feature sets
    clusters = cluster_patterns(features_list, threshold=0.70)
"""

from __future__ import annotations

from omniintelligence.nodes.node_pattern_learning_compute.handlers.pattern_clustering_core import (
    _cluster_patterns,
    _compute_similarity,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.protocols import (
    PatternClusterDict,
    SimilarityResultDict,
)
from omniintelligence.nodes.node_pattern_learning_compute.models.model_pattern_clustering_request import (
    ModelPatternClusteringRequest,
)
from omniintelligence.nodes.node_pattern_learning_compute.models.model_similarity_request import (
    ModelSimilarityRequest,
)


class HandlerSimilarity:
    """Typed entry point for _compute_similarity."""

    def handle(self, request: ModelSimilarityRequest) -> SimilarityResultDict:
        """Delegate to the preserved computation."""
        return _compute_similarity(
            request.features_a, request.features_b, request.weights
        )


class HandlerPatternClustering:
    """Typed entry point for _cluster_patterns."""

    def handle(
        self, request: ModelPatternClusteringRequest
    ) -> list[PatternClusterDict]:
        """Delegate to the preserved computation."""
        return _cluster_patterns(
            request.features_list,
            request.threshold,
            request.weights,
            request.max_input_items,
            request.replay_emitter,
        )


__all__ = ["HandlerPatternClustering", "HandlerSimilarity"]
