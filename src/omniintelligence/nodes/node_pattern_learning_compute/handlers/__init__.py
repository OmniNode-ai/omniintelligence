"""Pattern Learning Compute Handlers.

This module provides pure handler functions for pattern learning (aggregation) operations.
Handlers implement the computation logic following the ONEX "pure shell pattern"
where nodes delegate to side-effect-free handler functions.

SEMANTIC NOTE:
    The term "learning" in the node name is legacy. This node AGGREGATES and SUMMARIZES
    observed patterns. It does NOT perform statistical learning or weight updates.
    Conceptually, this is pattern summarization: extract, cluster, score, deduplicate.

Handler Pattern:
    Each handler is a pure function that:
    - Accepts training data and configuration parameters
    - Performs pattern aggregation across code examples
    - Returns typed result dictionaries
    - Has no side effects (pure computation)

Pipeline Flow:
    1. Feature Extraction (handler_feature_extraction)
    2. Similarity + Clustering (handler_pattern_clustering)
    3. Confidence Scoring (handler_confidence_scoring)
    4. Deduplication (handler_deduplication)
    5. Orchestration (handler_pattern_learning)

Usage:
    from omniintelligence.nodes.node_pattern_learning_compute.handlers import (
        PatternLearningValidationError,
        PatternLearningComputeError,
        SIGNATURE_VERSION,
        DEFAULT_SIMILARITY_WEIGHTS,
        jaccard_similarity,
    )

    # Compute similarity between two sets
    similarity = jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"})
"""

from omniintelligence.nodes.node_pattern_learning_compute.handlers.exceptions import (
    PatternLearningComputeError,
    PatternLearningValidationError,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.handler_confidence_scoring import (
    compute_cluster_scores,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.handler_deduplication import (
    deduplicate_patterns,
    generate_pattern_signature,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.handler_feature_extraction import (
    extract_features,
    extract_features_batch,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.handler_pattern_clustering import (
    cluster_patterns,
    compute_similarity,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.handler_pattern_learning import (
    HANDLER_ID_PATTERN_LEARNING,
    HandlerPatternLearning,
    aggregate_patterns,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.presets import (
    DEFAULT_SIMILARITY_WEIGHTS,
    SIGNATURE_NORMALIZATION,
    SIGNATURE_VERSION,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.protocols import (
    DeduplicationResultDict,
    ExtractedFeaturesDict,
    NearThresholdWarningDict,
    PatternClusterDict,
    PatternLearningResult,
    PatternScoreComponentsDict,
    PatternSignatureDict,
    SimilarityResultDict,
    SimilarityWeightsDict,
    StructuralFeaturesDict,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.replay import (
    NULL_EMITTER,
    NullEmitter,
    ReplayArtifactEmitter,
    assert_json_safe,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.union_find import (
    UnionFind,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.utils import (
    jaccard_similarity,
    normalize_identifier,
    normalize_identifiers,
    validate_similarity_weights,
)

__all__ = [
    "DEFAULT_SIMILARITY_WEIGHTS",
    "HANDLER_ID_PATTERN_LEARNING",
    "NULL_EMITTER",
    "SIGNATURE_NORMALIZATION",
    "SIGNATURE_VERSION",
    "DeduplicationResultDict",
    "ExtractedFeaturesDict",
    "HandlerPatternLearning",
    "NearThresholdWarningDict",
    "NullEmitter",
    "PatternClusterDict",
    "PatternLearningComputeError",
    "PatternLearningResult",
    "PatternLearningValidationError",
    "PatternScoreComponentsDict",
    "PatternSignatureDict",
    "ReplayArtifactEmitter",
    "SimilarityResultDict",
    "SimilarityWeightsDict",
    "StructuralFeaturesDict",
    "UnionFind",
    "aggregate_patterns",
    "assert_json_safe",
    "cluster_patterns",
    "compute_cluster_scores",
    "compute_similarity",
    "deduplicate_patterns",
    "extract_features",
    "extract_features_batch",
    "generate_pattern_signature",
    "jaccard_similarity",
    "normalize_identifier",
    "normalize_identifiers",
    "validate_similarity_weights",
]
