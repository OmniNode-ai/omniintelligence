"""Pattern clustering handler for pattern learning compute node.

This module provides the core clustering functionality for the pattern learning
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

from collections import Counter

from omniintelligence.nodes.node_pattern_learning_compute.handlers.exceptions import (
    PatternLearningValidationError,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.presets import (
    DEFAULT_CLUSTERING_THRESHOLD,
    DEFAULT_SIMILARITY_WEIGHTS,
    ONEX_PATTERN_KEYWORDS,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.protocols import (
    ExtractedFeaturesDict,
    PatternClusterDict,
    SimilarityResultDict,
    SimilarityWeightsDict,
    StructuralFeaturesDict,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.replay import (
    NULL_EMITTER,
    ReplayArtifactEmitter,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.union_find import (
    UnionFind,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.utils import (
    compute_normalized_distance,
    distance_to_similarity,
    jaccard_similarity,
    validate_similarity_weights,
)


# =============================================================================
# Constants for Structural Similarity Computation
# =============================================================================

# Maximum expected differences for structural feature normalization.
# These values define the scaling factors for computing normalized distances.
_MAX_CLASS_COUNT_DIFF: float = 20.0
_MAX_FUNCTION_COUNT_DIFF: float = 50.0
_MAX_NESTING_DEPTH_DIFF: float = 10.0
_MAX_LINE_COUNT_DIFF: float = 500.0
_MAX_CYCLOMATIC_COMPLEXITY_DIFF: float = 50.0

# Weights for combining structural sub-features into a single similarity score.
# These weights prioritize function count and complexity as primary indicators
# of structural similarity.
_STRUCTURAL_WEIGHTS: dict[str, float] = {
    "class_count": 0.15,
    "function_count": 0.25,
    "max_nesting_depth": 0.15,
    "line_count": 0.15,
    "cyclomatic_complexity": 0.20,
    "has_type_hints": 0.05,
    "has_docstrings": 0.05,
}

# Validate weights sum to 1.0 at module load time
_structural_weights_sum = sum(_STRUCTURAL_WEIGHTS.values())
assert abs(_structural_weights_sum - 1.0) < 1e-9, (
    f"_STRUCTURAL_WEIGHTS must sum to 1.0, got {_structural_weights_sum}"
)


# =============================================================================
# Private Helper Functions
# =============================================================================


def _extract_context_tokens(features: ExtractedFeaturesDict) -> frozenset[str]:
    """Extract context tokens from features for domain/framework alignment.

    Context tokens are extracted from keywords that match known ONEX pattern
    keywords. This provides a signal for domain/framework alignment between
    two code snippets.

    Args:
        features: Extracted features dictionary.

    Returns:
        Frozenset of context tokens found in the keywords.
        May be empty if no context keywords are present.

    Examples:
        >>> features = {"keywords": ("frozen", "Field", "BaseModel", "my_func"), ...}
        >>> _extract_context_tokens(features)
        frozenset({'frozen', 'Field'})
    """
    keywords_set = set(features["keywords"])
    context_tokens = keywords_set & ONEX_PATTERN_KEYWORDS
    return frozenset(context_tokens)


def _compute_context_similarity(
    ctx_a: frozenset[str],
    ctx_b: frozenset[str],
) -> float:
    """Compute context similarity between two context token sets.

    Context similarity uses special handling for empty cases:
    - Both empty: 0.5 (neutral - no information available)
    - One empty: 0.0 (asymmetric penalty for missing context)
    - Both present: Jaccard similarity

    This design ensures that:
    - Missing context penalizes similarity (encourages context extraction)
    - Two items with no context are treated neutrally (don't artificially boost)

    Args:
        ctx_a: First context token set.
        ctx_b: Second context token set.

    Returns:
        Context similarity in [0.0, 1.0] with special empty handling.

    Examples:
        >>> _compute_context_similarity(frozenset(), frozenset())
        0.5
        >>> _compute_context_similarity(frozenset({"a"}), frozenset())
        0.0
        >>> _compute_context_similarity(frozenset({"a", "b"}), frozenset({"b", "c"}))
        0.3333...
    """
    # Both empty: neutral score (no information)
    if not ctx_a and not ctx_b:
        return 0.5

    # One empty: asymmetric penalty
    if not ctx_a or not ctx_b:
        return 0.0

    # Both present: standard Jaccard
    return jaccard_similarity(set(ctx_a), set(ctx_b))


def _compute_structural_similarity(
    struct_a: StructuralFeaturesDict,
    struct_b: StructuralFeaturesDict,
) -> float:
    """Compute structural similarity between two structural feature sets.

    Structural similarity combines multiple sub-features using weighted
    distances. Each sub-feature is normalized to [0.0, 1.0] range and
    then combined with predefined weights.

    Boolean features (has_type_hints, has_docstrings) contribute 1.0 if
    both match, 0.0 if different.

    Args:
        struct_a: First structural features dictionary.
        struct_b: Second structural features dictionary.

    Returns:
        Structural similarity in [0.0, 1.0].

    Examples:
        >>> struct_a = {"class_count": 2, "function_count": 10, ...}
        >>> struct_b = {"class_count": 2, "function_count": 12, ...}
        >>> _compute_structural_similarity(struct_a, struct_b)
        0.85...  # Close structural similarity
    """
    # Compute feature similarities with explicit key access to avoid type: ignore
    # comments from dynamic string indexing on TypedDict. Build a list of
    # (name, similarity) tuples in the same order as the original implementation
    # to preserve identical floating point behavior with sum().
    similarities: list[tuple[str, float]] = [
        (
            "class_count",
            distance_to_similarity(
                compute_normalized_distance(
                    float(struct_a["class_count"]),
                    float(struct_b["class_count"]),
                    _MAX_CLASS_COUNT_DIFF,
                )
            ),
        ),
        (
            "function_count",
            distance_to_similarity(
                compute_normalized_distance(
                    float(struct_a["function_count"]),
                    float(struct_b["function_count"]),
                    _MAX_FUNCTION_COUNT_DIFF,
                )
            ),
        ),
        (
            "max_nesting_depth",
            distance_to_similarity(
                compute_normalized_distance(
                    float(struct_a["max_nesting_depth"]),
                    float(struct_b["max_nesting_depth"]),
                    _MAX_NESTING_DEPTH_DIFF,
                )
            ),
        ),
        (
            "line_count",
            distance_to_similarity(
                compute_normalized_distance(
                    float(struct_a["line_count"]),
                    float(struct_b["line_count"]),
                    _MAX_LINE_COUNT_DIFF,
                )
            ),
        ),
        (
            "cyclomatic_complexity",
            distance_to_similarity(
                compute_normalized_distance(
                    float(struct_a["cyclomatic_complexity"]),
                    float(struct_b["cyclomatic_complexity"]),
                    _MAX_CYCLOMATIC_COMPLEXITY_DIFF,
                )
            ),
        ),
        # Boolean features: 1.0 if match, 0.0 if different
        (
            "has_type_hints",
            1.0 if struct_a["has_type_hints"] == struct_b["has_type_hints"] else 0.0,
        ),
        (
            "has_docstrings",
            1.0 if struct_a["has_docstrings"] == struct_b["has_docstrings"] else 0.0,
        ),
    ]

    # Weighted combination using sum() to preserve original floating point behavior
    total_similarity = sum(
        _STRUCTURAL_WEIGHTS[name] * sim for name, sim in similarities
    )

    return total_similarity


def _select_medoid(
    members: list[ExtractedFeaturesDict],
    weights: SimilarityWeightsDict,
) -> ExtractedFeaturesDict:
    """Select the medoid (most representative member) of a cluster.

    The medoid is the member with the highest average similarity to all
    other members. In case of ties, the member with the smallest item_id
    is selected for determinism.

    For single-member clusters, returns the only member.

    Args:
        members: List of cluster members (ExtractedFeaturesDict).
        weights: Similarity weights to use for medoid computation.

    Returns:
        The medoid member (most representative features).

    Raises:
        PatternLearningValidationError: If members list is empty.

    Examples:
        >>> # Member B has highest average similarity to others
        >>> medoid = _select_medoid([member_a, member_b, member_c], weights)
        >>> medoid["item_id"]
        'member_b'
    """
    if not members:
        raise PatternLearningValidationError(
            "Cannot select medoid from empty member list"
        )

    if len(members) == 1:
        return members[0]

    # Compute average similarity for each member to all others
    avg_similarities: list[tuple[str, float, ExtractedFeaturesDict]] = []

    for i, member_i in enumerate(members):
        total_sim = 0.0
        count = 0
        for j, member_j in enumerate(members):
            if i != j:
                result = compute_similarity(member_i, member_j, weights)
                total_sim += result["similarity"]
                count += 1

        avg_sim = total_sim / count if count > 0 else 0.0
        avg_similarities.append((member_i["item_id"], avg_sim, member_i))

    # Sort by: (negative avg_similarity for descending, item_id for ascending tie-break)
    avg_similarities.sort(key=lambda x: (-x[1], x[0]))

    # Return member with highest average similarity (first after sort)
    return avg_similarities[0][2]


def _compute_intra_cluster_similarity(
    members: list[ExtractedFeaturesDict],
    weights: SimilarityWeightsDict,
) -> float:
    """Compute average pairwise similarity within a cluster.

    For single-member clusters, returns 1.0 (perfect self-similarity).
    For multi-member clusters, computes average of all pairwise similarities.

    Args:
        members: List of cluster members.
        weights: Similarity weights for computation.

    Returns:
        Average intra-cluster similarity in [0.0, 1.0].
    """
    if len(members) <= 1:
        return 1.0

    total_sim = 0.0
    count = 0

    for i in range(len(members)):
        for j in range(i + 1, len(members)):
            result = compute_similarity(members[i], members[j], weights)
            total_sim += result["similarity"]
            count += 1

    # Single-member cluster has perfect self-similarity
    return total_sim / count if count > 0 else 1.0


# =============================================================================
# Public API
# =============================================================================


def compute_similarity(
    features_a: ExtractedFeaturesDict,
    features_b: ExtractedFeaturesDict,
    weights: SimilarityWeightsDict | None = None,
) -> SimilarityResultDict:
    """Compute weighted 5-component similarity between two feature sets.

    Combines five similarity components with configurable weights:
    - keyword (0.30): Jaccard similarity of identifiers/imports
    - pattern (0.25): Jaccard similarity of ONEX pattern indicators
    - structural (0.20): Weighted structural metric similarity
    - label (0.15): Jaccard similarity of training labels
    - context (0.10): Domain/framework alignment from context tokens

    Args:
        features_a: First extracted features dictionary.
        features_b: Second extracted features dictionary.
        weights: Optional custom weights. If None, uses DEFAULT_SIMILARITY_WEIGHTS.
            Weights must sum to 1.0 and include all five components.

    Returns:
        SimilarityResultDict containing:
        - similarity: Final weighted similarity score [0.0, 1.0]
        - keyword_similarity: Raw keyword component score
        - pattern_similarity: Raw pattern component score
        - structural_similarity: Raw structural component score
        - label_similarity: Raw label component score
        - context_similarity: Raw context component score (with empty handling)
        - weights_used: The weights applied for this computation

    Raises:
        PatternLearningValidationError: If custom weights are invalid
            (missing keys, out of range, or don't sum to 1.0).

    Examples:
        >>> # Using default weights
        >>> result = compute_similarity(features_a, features_b)
        >>> result["similarity"]
        0.72

        >>> # Using custom weights (emphasize structure)
        >>> custom_weights = {
        ...     "keyword": 0.20, "pattern": 0.20, "structural": 0.40,
        ...     "label": 0.10, "context": 0.10
        ... }
        >>> result = compute_similarity(features_a, features_b, custom_weights)
    """
    # Use default weights if none provided
    if weights is None:
        weights = DEFAULT_SIMILARITY_WEIGHTS
    else:
        # Validate custom weights
        validate_similarity_weights(weights)

    # 1. Keyword similarity (Jaccard on identifiers)
    keyword_sim = jaccard_similarity(
        set(features_a["keywords"]),
        set(features_b["keywords"]),
    )

    # 2. Pattern similarity (Jaccard on pattern indicators)
    pattern_sim = jaccard_similarity(
        set(features_a["pattern_indicators"]),
        set(features_b["pattern_indicators"]),
    )

    # 3. Structural similarity (weighted distance-based)
    structural_sim = _compute_structural_similarity(
        features_a["structural"],
        features_b["structural"],
    )

    # 4. Label similarity (Jaccard on training labels)
    label_sim = jaccard_similarity(
        set(features_a["labels"]),
        set(features_b["labels"]),
    )

    # 5. Context similarity (with special empty handling)
    ctx_a = _extract_context_tokens(features_a)
    ctx_b = _extract_context_tokens(features_b)
    context_sim = _compute_context_similarity(ctx_a, ctx_b)

    # Compute weighted final similarity
    final_similarity = (
        weights["keyword"] * keyword_sim
        + weights["pattern"] * pattern_sim
        + weights["structural"] * structural_sim
        + weights["label"] * label_sim
        + weights["context"] * context_sim
    )

    return SimilarityResultDict(
        similarity=final_similarity,
        keyword_similarity=keyword_sim,
        pattern_similarity=pattern_sim,
        structural_similarity=structural_sim,
        label_similarity=label_sim,
        context_similarity=context_sim,
        weights_used=weights,
    )


def cluster_patterns(
    features_list: list[ExtractedFeaturesDict],
    threshold: float = DEFAULT_CLUSTERING_THRESHOLD,
    weights: SimilarityWeightsDict | None = None,
    max_input_items: int = 500,
    replay_emitter: ReplayArtifactEmitter = NULL_EMITTER,
) -> list[PatternClusterDict]:
    """Cluster similar patterns using single-linkage clustering.

    Algorithm:
        1. Sort items by item_id for determinism
        2. Build similarity edges in sorted (i, j) order where i < j
        3. Apply single-linkage clustering (merge if ANY pair >= threshold)
        4. Assign cluster_id by sorted leader (smallest item_id in cluster)
        5. Select medoid as centroid for each cluster

    Determinism Guarantees:
        - Items sorted by item_id before processing
        - Edges built in deterministic order
        - Cluster leader = smallest item_id in cluster
        - cluster_id assigned in sorted leader order: cluster-0001, cluster-0002, ...
        - Medoid tie-break by smallest item_id

    Args:
        features_list: List of extracted features to cluster.
        threshold: Similarity threshold for clustering. Pairs with
            similarity >= threshold are grouped together.
            Defaults to DEFAULT_CLUSTERING_THRESHOLD (0.70).
        weights: Optional custom similarity weights.
            Defaults to DEFAULT_SIMILARITY_WEIGHTS.
        max_input_items: Maximum allowed input items. Raises error if exceeded.
            Defaults to 500 to prevent O(n^2) explosion.
        replay_emitter: Emitter for replay artifacts. Defaults to NULL_EMITTER
            which discards artifacts (useful for tests).

    Returns:
        List of PatternClusterDict, each containing:
        - cluster_id: Unique identifier (e.g., "cluster-0001")
        - pattern_type: Dominant pattern type (most common pattern indicator
          in cluster; ties broken by alphabetical order for determinism).
          Returns "unknown" if no pattern indicators present.
        - member_ids: Tuple of item_ids in this cluster
        - centroid_features: Medoid member's features
        - member_count: Number of items in cluster
        - internal_similarity: Average pairwise similarity within cluster

    Raises:
        PatternLearningValidationError: If len(features_list) > max_input_items
            to prevent O(n^2) memory/time explosion.

    Replay Artifacts Emitted:
        "clustering_result" with:
        - cluster_assignment_map: {item_id: cluster_id}
        - cluster_leaders: {cluster_id: leader_item_id}
        - cluster_scores_summary: {cluster_id: {"size": n, "avg_intra_similarity": x}}

    Examples:
        >>> # Basic clustering
        >>> clusters = cluster_patterns(features_list, threshold=0.70)
        >>> len(clusters)
        5

        >>> # With custom threshold and replay logging
        >>> from my_replay import FileEmitter
        >>> emitter = FileEmitter("/tmp/replay.json")
        >>> clusters = cluster_patterns(features_list, threshold=0.75, replay_emitter=emitter)
    """
    # Input validation
    if len(features_list) > max_input_items:
        raise PatternLearningValidationError(
            f"Input size {len(features_list)} exceeds maximum allowed "
            f"{max_input_items}. Reduce input size or increase max_input_items "
            f"(warning: O(n^2) memory/time complexity)."
        )

    # Handle empty input
    if not features_list:
        replay_emitter.emit(
            "clustering_result",
            {
                "cluster_assignment_map": {},
                "cluster_leaders": {},
                "cluster_scores_summary": {},
            },
        )
        return []

    # Use default weights if none provided
    if weights is None:
        weights = DEFAULT_SIMILARITY_WEIGHTS
    else:
        validate_similarity_weights(weights)

    # Step 1: Sort items by item_id for determinism
    sorted_features = sorted(features_list, key=lambda f: f["item_id"])
    n = len(sorted_features)

    # Step 2: Build similarity edges in sorted order using Union-Find
    # for single-linkage clustering (deterministic: smaller index becomes root)
    uf = UnionFind(n)

    # Compute pairwise similarities and build edges
    # Single-linkage: merge if ANY pair >= threshold
    for i in range(n):
        for j in range(i + 1, n):
            result = compute_similarity(
                sorted_features[i], sorted_features[j], weights
            )
            if result["similarity"] >= threshold:
                uf.union(i, j)

    # Step 3: Group items by cluster root
    clusters_by_root = uf.components()

    # Step 4: Assign cluster_id by sorted leader
    # Leader = smallest item_id in cluster (which is smallest index due to sorting)
    # Sort clusters by their leader's index (root)
    sorted_roots = sorted(clusters_by_root.keys())

    # Build final clusters
    result_clusters: list[PatternClusterDict] = []
    cluster_assignment_map: dict[str, str] = {}
    cluster_leaders: dict[str, str] = {}
    cluster_scores_summary: dict[str, dict[str, object]] = {}

    for cluster_idx, root in enumerate(sorted_roots):
        member_indices = clusters_by_root[root]
        members = [sorted_features[i] for i in member_indices]

        # Cluster ID with 4-digit padding
        cluster_id = f"cluster-{cluster_idx + 1:04d}"

        # Leader is the smallest item_id (first member after sorting by item_id)
        member_ids_sorted = tuple(sorted(m["item_id"] for m in members))
        leader_id = member_ids_sorted[0]

        # Build member_pattern_indicators parallel to member_ids_sorted
        # Create a lookup dict for O(1) access by item_id
        members_by_id = {m["item_id"]: m for m in members}
        member_pattern_indicators = tuple(
            members_by_id[item_id]["pattern_indicators"]
            for item_id in member_ids_sorted
        )

        # Determine dominant pattern type
        all_patterns: list[str] = []
        for m in members:
            all_patterns.extend(m["pattern_indicators"])

        if all_patterns:
            # Most common pattern indicator
            # Tie-break: alphabetically ascending (smallest string wins)
            # This matches the item_id determinism pattern used elsewhere
            pattern_counts = Counter(all_patterns)
            # Sort by count descending, then alphabetically ascending for ties
            sorted_patterns = sorted(
                pattern_counts.keys(),
                key=lambda k: (-pattern_counts[k], k),
            )
            pattern_type = sorted_patterns[0]
        else:
            pattern_type = "unknown"

        # Compute label_agreement: fraction of members whose pattern_indicators
        # contain the dominant pattern_type
        if pattern_type != "unknown":
            match_count = sum(
                1
                for indicators in member_pattern_indicators
                if pattern_type in indicators
            )
            label_agreement = match_count / len(members)
        else:
            # No pattern_type means no agreement possible
            label_agreement = 0.0

        # Select medoid as centroid
        centroid = _select_medoid(members, weights)

        # Compute internal similarity
        internal_sim = _compute_intra_cluster_similarity(members, weights)

        # Invariant checks (enforced at construction)
        assert len(member_pattern_indicators) == len(member_ids_sorted), (
            f"member_pattern_indicators length {len(member_pattern_indicators)} "
            f"!= member_ids length {len(member_ids_sorted)}"
        )
        assert len(members) == len(member_ids_sorted), (
            f"member_count {len(members)} != member_ids length {len(member_ids_sorted)}"
        )

        # Build cluster dict
        cluster_dict = PatternClusterDict(
            cluster_id=cluster_id,
            pattern_type=pattern_type,
            member_ids=member_ids_sorted,
            centroid_features=centroid,
            member_count=len(members),
            internal_similarity=internal_sim,
            member_pattern_indicators=member_pattern_indicators,
            label_agreement=label_agreement,
        )
        result_clusters.append(cluster_dict)

        # Update tracking dicts for replay artifact
        for item_id in member_ids_sorted:
            cluster_assignment_map[item_id] = cluster_id

        cluster_leaders[cluster_id] = leader_id
        cluster_scores_summary[cluster_id] = {
            "size": len(members),
            "avg_intra_similarity": internal_sim,
        }

    # Emit replay artifact
    replay_emitter.emit(
        "clustering_result",
        {
            "cluster_assignment_map": cluster_assignment_map,
            "cluster_leaders": cluster_leaders,
            "cluster_scores_summary": cluster_scores_summary,
        },
    )

    return result_clusters


__all__ = ["cluster_patterns", "compute_similarity"]
