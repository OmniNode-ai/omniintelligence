# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Pattern deduplication handler for pattern learning compute node.

Pattern deduplication with versioned signatures and policy
transparency. It removes overlapping patterns while maintaining deterministic
ordering and explicit decision audit trails.

POLICY: Prefer false negatives over false positives.
    You can merge later; you can't un-merge.

OUTPUT CONTRACT (STRICT):
    - threshold_used is explicit in output
    - near_threshold_warnings for borderline cases (within margin)
    - deduplicated_clusters maintains deterministic ordering
    - Signatures are versioned for migration safety

DETERMINISM INVARIANTS:
    - Clusters sorted by cluster_id before comparison
    - Pairwise comparison in sorted order (A < B)
    - Tie-break: higher confidence > larger member_count > smaller member_ids[0]
    - Same input always produces same output

Usage:
    from omniintelligence.nodes.node_pattern_learning_compute.handlers.handler_deduplication import (
        deduplicate_patterns,
        generate_pattern_signature,
    )

    # Deduplicate clusters
    result = deduplicate_patterns(clusters, confidence_scores)

    # Generate signature for a cluster
    sig = generate_pattern_signature(cluster)
"""

from __future__ import annotations

from omniintelligence.nodes.node_pattern_learning_compute.handlers.deduplication_core import (
    _deduplicate_patterns,
    _generate_pattern_signature,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.protocols import (
    DeduplicationResultDict,
    PatternSignatureResultDict,
)
from omniintelligence.nodes.node_pattern_learning_compute.models.model_deduplication_request import (
    ModelDeduplicationRequest,
)
from omniintelligence.nodes.node_pattern_learning_compute.models.model_pattern_signature_request import (
    ModelPatternSignatureRequest,
)


class HandlerPatternSignature:
    """Typed entry point for _generate_pattern_signature."""

    def handle(
        self, request: ModelPatternSignatureRequest
    ) -> PatternSignatureResultDict:
        """Delegate to the preserved computation."""
        return _generate_pattern_signature(request.cluster)


class HandlerDeduplication:
    """Typed entry point for _deduplicate_patterns."""

    def handle(self, request: ModelDeduplicationRequest) -> DeduplicationResultDict:
        """Delegate to the preserved computation."""
        return _deduplicate_patterns(
            request.clusters,
            request.confidence_scores,
            request.similarity_threshold,
            request.near_threshold_margin,
            request.weights,
        )


__all__ = ["HandlerDeduplication", "HandlerPatternSignature"]
