"""Pattern deduplication handler for pattern learning compute node.

This module provides pattern deduplication with versioned signatures and policy
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

import hashlib
from typing import Final

from omniintelligence.nodes.node_pattern_learning_compute.handlers.handler_pattern_clustering import (
    compute_similarity,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.presets import (
    DEFAULT_DEDUPLICATION_THRESHOLD,
    DEFAULT_SIMILARITY_WEIGHTS,
    NEAR_THRESHOLD_MARGIN,
    SIGNATURE_NORMALIZATION,
    SIGNATURE_VERSION,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.protocols import (
    DeduplicationResultDict,
    NearThresholdWarningDict,
    PatternClusterDict,
    PatternSignatureDict,
    PatternSignatureResultDict,
    SimilarityWeightsDict,
)

# =============================================================================
# Constants
# =============================================================================

_SIGNATURE_MAX_KEYWORDS: Final[int] = 20
"""Maximum number of keywords to include in signature (per ticket spec)."""


# =============================================================================
# Public API
# =============================================================================


def generate_pattern_signature(
    cluster: PatternClusterDict | None,
) -> PatternSignatureResultDict:
    """Generate versioned, deterministic signature for a pattern cluster.

    STABILITY CONTRACT:
        - Inputs: pattern_type + sorted(keywords[:20]) + sorted(pattern_indicators)
        - Normalization: lowercase, sort, dedupe
        - Version stored alongside signature for migration

    The signature is computed from the cluster's centroid_features following
    the exact specification from the ticket. This enables:
        - Detecting duplicate patterns across runs
        - Tracking pattern changes over time
        - Debugging "why did this pattern change?" questions

    Args:
        cluster: Pattern cluster to generate signature for.

    Returns:
        PatternSignatureResultDict containing:
        - success: Whether signature generation succeeded.
        - result: PatternSignatureDict with signature data (None on failure).
        - error_message: Error description if success=False, None otherwise.

    Examples:
        >>> sig = generate_pattern_signature(cluster)
        >>> if sig["success"]:
        ...     sig["result"]["signature"]
        'a1b2c3d4...'
    """
    # Guard against None or empty cluster input
    if cluster is None:
        return PatternSignatureResultDict(
            success=False,
            result=None,
            error_message="Empty cluster: cannot generate signature from None or empty input",
        )

    try:
        centroid = cluster["centroid_features"]
        pattern_type = cluster["pattern_type"]

        # Extract and normalize keywords (lowercase, dedupe, sort, limit to 20)
        keywords_raw = centroid["keywords"]
        keywords_normalized = sorted({kw.lower() for kw in keywords_raw})[
            :_SIGNATURE_MAX_KEYWORDS
        ]

        # Extract and normalize pattern indicators (lowercase, dedupe, sort)
        indicators_raw = centroid["pattern_indicators"]
        indicators_normalized = sorted({ind.lower() for ind in indicators_raw})
    except (KeyError, TypeError, AttributeError) as e:
        return PatternSignatureResultDict(
            success=False,
            result=None,
            error_message=f"Malformed cluster: {e}",
        )

    # Build signature inputs tuple
    # Format: pattern_type, then keywords, then indicators
    # All lowercase for consistency
    signature_inputs: tuple[str, ...] = (
        pattern_type.lower(),
        *keywords_normalized,
        *indicators_normalized,
    )

    # Canonical serialization: join with null byte separator
    # This ensures no ambiguity between "a", "b" and "ab"
    canonical_string = "\x00".join(signature_inputs)

    # Compute SHA256
    signature_hash = hashlib.sha256(canonical_string.encode("utf-8")).hexdigest()

    return PatternSignatureResultDict(
        success=True,
        result=PatternSignatureDict(
            signature=signature_hash,
            signature_version=SIGNATURE_VERSION,
            signature_inputs=signature_inputs,
            normalization_applied=SIGNATURE_NORMALIZATION,
        ),
        error_message=None,
    )


def deduplicate_patterns(
    clusters: list[PatternClusterDict],
    confidence_scores: dict[str, float] | None = None,
    similarity_threshold: float = DEFAULT_DEDUPLICATION_THRESHOLD,
    near_threshold_margin: float = NEAR_THRESHOLD_MARGIN,
    weights: SimilarityWeightsDict | None = None,
) -> DeduplicationResultDict:
    """Remove overlapping patterns with policy transparency.

    POLICY DECISIONS:
        - Threshold is explicit in output metadata
        - Near-threshold cases (within margin) emit warnings
        - Prefer false negatives over false positives
          (You can merge later; you can't un-merge)

    Algorithm:
        1. Sort clusters by cluster_id for determinism
        2. For each pair (A, B) where A < B in sort order:
           - Compute similarity using centroid features
           - If similarity >= threshold: drop the weaker cluster
           - If threshold - margin <= similarity < threshold: emit warning
        3. Return surviving clusters in original sorted order

    Tie-break for "weaker" (deterministic):
        1. Lower confidence loses (if confidence_scores provided)
        2. Smaller member_count loses
        3. Larger member_ids[0] loses (alphabetical)

    Args:
        clusters: List of pattern clusters to deduplicate.
        confidence_scores: Optional mapping of cluster_id -> confidence.
            If not provided, uses internal_similarity as strength metric.
        similarity_threshold: Threshold for considering clusters as duplicates.
            Defaults to DEFAULT_DEDUPLICATION_THRESHOLD (0.85).
        near_threshold_margin: Margin for near-threshold warnings.
            Defaults to NEAR_THRESHOLD_MARGIN (0.05).
        weights: Optional custom similarity weights.
            Defaults to DEFAULT_SIMILARITY_WEIGHTS.

    Returns:
        DeduplicationResultDict containing:
        - success: Whether deduplication succeeded.
        - deduplicated_clusters: Surviving clusters after deduplication
        - merged_count: Number of clusters that were removed
        - threshold_used: The threshold that was applied (explicit)
        - near_threshold_warnings: Warnings for borderline cases
        - error_message: Error description if success=False, None otherwise.

    Examples:
        >>> result = deduplicate_patterns(clusters, confidence_scores)
        >>> len(result["deduplicated_clusters"])
        5
        >>> result["merged_count"]
        3
        >>> result["threshold_used"]
        0.85
    """
    # Validate threshold - return structured errors per CLAUDE.md pattern
    if not (0.0 <= similarity_threshold <= 1.0):
        return DeduplicationResultDict(
            deduplicated_clusters=[],
            merged_count=0,
            threshold_used=similarity_threshold,
            near_threshold_warnings=[],
            success=False,
            error_message=f"similarity_threshold must be in [0.0, 1.0], got {similarity_threshold}",
        )

    if not (0.0 <= near_threshold_margin <= 1.0):
        return DeduplicationResultDict(
            deduplicated_clusters=[],
            merged_count=0,
            threshold_used=similarity_threshold,
            near_threshold_warnings=[],
            success=False,
            error_message=f"near_threshold_margin must be in [0.0, 1.0], got {near_threshold_margin}",
        )

    # Handle empty input
    if not clusters:
        return DeduplicationResultDict(
            deduplicated_clusters=[],
            merged_count=0,
            threshold_used=similarity_threshold,
            near_threshold_warnings=[],
            success=True,
            error_message=None,
        )

    # Use default weights if none provided
    if weights is None:
        weights = DEFAULT_SIMILARITY_WEIGHTS

    # Step 1: Sort clusters by cluster_id for deterministic processing
    sorted_clusters = sorted(clusters, key=lambda c: c["cluster_id"])

    # Track which clusters are still alive (not dropped)
    alive: set[str] = {c["cluster_id"] for c in sorted_clusters}
    warnings: list[NearThresholdWarningDict] = []

    # Build lookup for quick access
    cluster_by_id: dict[str, PatternClusterDict] = {
        c["cluster_id"]: c for c in sorted_clusters
    }

    # Step 2: Pairwise comparison in sorted order
    n = len(sorted_clusters)
    for i in range(n):
        cluster_a = sorted_clusters[i]
        cluster_a_id = cluster_a["cluster_id"]

        # Skip if already dropped
        if cluster_a_id not in alive:
            continue

        for j in range(i + 1, n):
            cluster_b = sorted_clusters[j]
            cluster_b_id = cluster_b["cluster_id"]

            # Skip if already dropped
            if cluster_b_id not in alive:
                continue

            # Compute similarity using centroid features
            sim_result = compute_similarity(
                cluster_a["centroid_features"],
                cluster_b["centroid_features"],
                weights,
            )
            similarity = sim_result["similarity"]

            # Check near-threshold (warning zone)
            near_threshold_lower = similarity_threshold - near_threshold_margin
            is_near_threshold = (
                near_threshold_lower <= similarity < similarity_threshold
            )

            # Check if duplicates (should merge)
            if similarity >= similarity_threshold:
                # Determine which is weaker
                loser_id = _determine_loser(
                    cluster_a,
                    cluster_b,
                    confidence_scores,
                )

                # Drop the loser
                alive.discard(loser_id)

                # Emit near-threshold warning if applicable
                # (similarity was >= threshold but also in warning zone is impossible,
                # but we emit warning anyway for the merge action)
                if (
                    is_near_threshold
                    or similarity < similarity_threshold + near_threshold_margin
                ):
                    # Only emit if very close to threshold
                    if abs(similarity - similarity_threshold) < near_threshold_margin:
                        warnings.append(
                            NearThresholdWarningDict(
                                cluster_a_id=cluster_a_id,
                                cluster_b_id=cluster_b_id,
                                similarity=similarity,
                                threshold=similarity_threshold,
                                action_taken="merged",
                            )
                        )

            elif is_near_threshold:
                # Near threshold but kept separate - emit warning
                warnings.append(
                    NearThresholdWarningDict(
                        cluster_a_id=cluster_a_id,
                        cluster_b_id=cluster_b_id,
                        similarity=similarity,
                        threshold=similarity_threshold,
                        action_taken="kept_separate",
                    )
                )

    # Step 3: Collect surviving clusters in original sorted order
    deduplicated = [c for c in sorted_clusters if c["cluster_id"] in alive]
    merged_count = len(sorted_clusters) - len(deduplicated)

    return DeduplicationResultDict(
        deduplicated_clusters=deduplicated,
        merged_count=merged_count,
        threshold_used=similarity_threshold,
        near_threshold_warnings=warnings,
        success=True,
        error_message=None,
    )


# =============================================================================
# Private Helpers
# =============================================================================


def _determine_loser(
    cluster_a: PatternClusterDict,
    cluster_b: PatternClusterDict,
    confidence_scores: dict[str, float] | None,
) -> str:
    """Determine which cluster to drop when two are duplicates.

    Tie-break order (deterministic):
        1. Lower confidence loses (if confidence_scores provided)
        2. Smaller member_count loses
        3. Larger member_ids[0] loses (alphabetical - smaller is better)

    Args:
        cluster_a: First cluster.
        cluster_b: Second cluster.
        confidence_scores: Optional confidence mapping.

    Returns:
        cluster_id of the cluster to drop.
    """
    a_id = cluster_a["cluster_id"]
    b_id = cluster_b["cluster_id"]

    # Get confidence (or fall back to internal_similarity)
    if confidence_scores is not None:
        a_conf = confidence_scores.get(a_id, cluster_a["internal_similarity"])
        b_conf = confidence_scores.get(b_id, cluster_b["internal_similarity"])
    else:
        a_conf = cluster_a["internal_similarity"]
        b_conf = cluster_b["internal_similarity"]

    # Tie-break 1: Lower confidence loses
    if a_conf != b_conf:
        return a_id if a_conf < b_conf else b_id

    # Tie-break 2: Smaller member_count loses
    a_count = cluster_a["member_count"]
    b_count = cluster_b["member_count"]
    if a_count != b_count:
        return a_id if a_count < b_count else b_id

    # Tie-break 3: Larger leader (member_ids[0]) loses
    # Smaller alphabetically is better, so larger loses
    a_members = cluster_a["member_ids"]
    b_members = cluster_b["member_ids"]

    # Guard against empty member_ids: if both are empty, fall back to
    # cluster_id comparison for determinism (larger cluster_id loses).
    if not a_members and not b_members:
        return a_id if a_id > b_id else b_id
    # If only one is empty, the empty one is the loser (less data).
    if not a_members:
        return a_id
    if not b_members:
        return b_id

    a_leader = a_members[0]
    b_leader = b_members[0]
    return a_id if a_leader > b_leader else b_id


__all__ = ["deduplicate_patterns", "generate_pattern_signature"]
