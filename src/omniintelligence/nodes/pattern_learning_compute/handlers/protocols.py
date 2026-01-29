"""Internal type protocols for pattern learning handler results.

This module defines TypedDict structures for type-safe handler responses,
enabling static type checking with mypy and improved IDE support.

IMPORTANT - INTERNAL ONLY:
    These TypedDicts are IMPLEMENTATION DETAILS and MUST NOT be exported to other repos.
    They define handler-to-handler intermediate data structures that may change
    as the implementation improves.

    Contract models (LearnedPatternDict, PatternScoreComponentsDict, etc.) are
    defined in `omnibase_core` (OMN-1683) and should be used for external APIs.

Design Decisions:
    - TypedDict is used because handlers return dicts, not objects with methods.
    - All scores are normalized to 0.0-1.0 range for consistency.
    - Required fields use total=True (default) for strict validation.
    - Optional fields use total=False for flexibility.

Usage:
    from omniintelligence.nodes.pattern_learning_compute.handlers.protocols import (
        ExtractedFeaturesDict,
        SimilarityResultDict,
        PatternClusterDict,
    )

    def extract_features(code: str) -> ExtractedFeaturesDict:
        return {
            "keywords": ("def", "class", "import"),
            "pattern_indicators": ("NodeCompute", "frozen"),
            ...
        }
"""

from __future__ import annotations

from typing import Literal, TypedDict

from omnibase_core.models.pattern_learning import (
    ModelLearnedPattern,
    ModelPatternLearningMetadata,
    ModelPatternLearningMetrics,
)


class StructuralFeaturesDict(TypedDict):
    """Structural code metrics extracted from AST analysis.

    These metrics describe the shape and complexity of the code
    independent of its semantic content.

    Attributes:
        class_count: Number of class definitions.
        function_count: Number of function/method definitions.
        max_nesting_depth: Maximum depth of nested control structures.
        line_count: Total lines of code (excluding blank lines).
        cyclomatic_complexity: Simplified cyclomatic complexity estimate.
        has_type_hints: Whether the code uses type annotations.
        has_docstrings: Whether the code has docstrings.
    """

    class_count: int
    function_count: int
    max_nesting_depth: int
    line_count: int
    cyclomatic_complexity: int
    has_type_hints: bool
    has_docstrings: bool


class ExtractedFeaturesDict(TypedDict):
    """Features extracted from a code snippet for pattern analysis.

    OUTPUT CONTRACT (STRICT):
        - Output is normalized, domain-agnostic
        - Downstream handlers MUST NOT re-parse ASTs
        - All features are deterministic given the same input

    Attributes:
        item_id: Unique identifier for the training item.
        keywords: Tuple of identifiers, imports, function/class names (normalized).
        pattern_indicators: Tuple of detected ONEX/design pattern markers.
        structural: Structural code metrics.
        base_classes: Tuple of inherited base class names.
        decorators: Tuple of decorator names used.
        labels: Original training labels from input.
        language: Programming language of the snippet.
        extraction_quality: Indicates the depth of feature extraction performed.
            - "full": Complete AST-based extraction (Python). All features are
              populated from parsed syntax tree with high confidence.
            - "minimal": Basic extraction without AST (non-Python or fallback).
              Features are derived from text patterns with lower confidence.
              Enables distinguishing "empty because no code" from "empty because
              language not supported."
    """

    item_id: str
    keywords: tuple[str, ...]
    pattern_indicators: tuple[str, ...]
    structural: StructuralFeaturesDict
    base_classes: tuple[str, ...]
    decorators: tuple[str, ...]
    labels: tuple[str, ...]
    language: str
    extraction_quality: Literal["full", "minimal"]


class SimilarityWeightsDict(TypedDict, total=False):
    """Weights for the 5-component similarity calculation.

    All weights should sum to 1.0. These are INPUTS (configurable),
    not canonical constants.

    Attributes:
        keyword: Weight for keyword/identifier similarity (default 0.30).
        pattern: Weight for pattern indicator similarity (default 0.25).
        structural: Weight for structural metric similarity (default 0.20).
        label: Weight for training label agreement (default 0.15).
        context: Weight for domain/framework alignment (default 0.10).
    """

    keyword: float
    pattern: float
    structural: float
    label: float
    context: float


class SimilarityResultDict(TypedDict):
    """Result of similarity computation between two feature sets.

    IMPORTANT: Log raw similarity vectors, not just the final scalar.
    This enables debugging "matched structurally but not semantically".

    Attributes:
        similarity: Final weighted similarity score (0.0-1.0).
        keyword_similarity: Raw keyword Jaccard similarity.
        pattern_similarity: Raw pattern indicator Jaccard similarity.
        structural_similarity: Normalized structural distance (inverted to similarity).
        label_similarity: Label agreement score.
        context_similarity: Domain/framework alignment score.
        weights_used: The weights applied to compute final similarity.
    """

    similarity: float
    keyword_similarity: float
    pattern_similarity: float
    structural_similarity: float
    label_similarity: float
    context_similarity: float
    weights_used: SimilarityWeightsDict


class PatternClusterDict(TypedDict):
    """A cluster of similar patterns identified during aggregation.

    Clusters represent groups of training items that share common
    characteristics and can be summarized into a single pattern.

    Attributes:
        cluster_id: Unique identifier for this cluster.
        pattern_type: The dominant pattern type in this cluster.
        member_ids: Tuple of item_ids that belong to this cluster.
        centroid_features: Representative features for the cluster.
        member_count: Number of items in the cluster.
        internal_similarity: Average pairwise similarity within cluster.
    """

    cluster_id: str
    pattern_type: str
    member_ids: tuple[str, ...]
    centroid_features: ExtractedFeaturesDict
    member_count: int
    internal_similarity: float


class NearThresholdWarningDict(TypedDict):
    """Warning for clusters that were near the deduplication threshold.

    Near-threshold cases (within 0.05 of threshold) are logged for
    review as they may represent borderline duplicates.

    Attributes:
        cluster_a_id: First cluster identifier.
        cluster_b_id: Second cluster identifier.
        similarity: Computed similarity between clusters.
        threshold: The threshold used for deduplication.
        action_taken: "kept_separate" or "merged".
    """

    cluster_a_id: str
    cluster_b_id: str
    similarity: float
    threshold: float
    action_taken: str


class DeduplicationResultDict(TypedDict):
    """Result of pattern deduplication with policy transparency.

    POLICY DECISIONS:
        - Threshold is explicit in output metadata
        - Near-threshold cases emit warnings
        - Prefer false negatives over false positives
          (You can merge later; you can't un-merge)

    Attributes:
        deduplicated_clusters: Clusters after deduplication.
        merged_count: Number of clusters that were merged.
        threshold_used: The similarity threshold applied (explicit).
        near_threshold_warnings: Warnings for borderline cases.
    """

    deduplicated_clusters: list[PatternClusterDict]
    merged_count: int
    threshold_used: float
    near_threshold_warnings: list[NearThresholdWarningDict]


class PatternLearningResult(TypedDict):
    """Final result from the pattern learning (aggregation) handler.

    This wraps the full pipeline output for return to the node shell.

    Attributes:
        success: Whether aggregation completed successfully.
        candidate_patterns: Patterns below promotion threshold (need more evidence).
        learned_patterns: Patterns meeting promotion threshold (ready for use).
        metrics: Aggregation metrics for monitoring and debugging.
        metadata: Processing metadata (timing, versions, etc.).
        warnings: List of warnings generated during processing.
    """

    success: bool
    candidate_patterns: list[ModelLearnedPattern]
    learned_patterns: list[ModelLearnedPattern]
    metrics: ModelPatternLearningMetrics
    metadata: ModelPatternLearningMetadata
    warnings: list[str]


__all__ = [
    "DeduplicationResultDict",
    "ExtractedFeaturesDict",
    "NearThresholdWarningDict",
    "PatternClusterDict",
    "PatternLearningResult",
    "SimilarityResultDict",
    "SimilarityWeightsDict",
    "StructuralFeaturesDict",
]
