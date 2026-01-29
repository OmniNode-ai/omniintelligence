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
    from omniintelligence.nodes.pattern_learning_compute.handlers import (
        PatternLearningValidationError,
        PatternLearningComputeError,
        SIGNATURE_VERSION,
        DEFAULT_SIMILARITY_WEIGHTS,
        jaccard_similarity,
    )

    # Compute similarity between two sets
    similarity = jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"})
"""

from omniintelligence.nodes.pattern_learning_compute.handlers.exceptions import (
    PatternLearningComputeError,
    PatternLearningValidationError,
)
from omniintelligence.nodes.pattern_learning_compute.handlers.presets import (
    DEFAULT_SIMILARITY_WEIGHTS,
    SIGNATURE_NORMALIZATION,
    SIGNATURE_VERSION,
)
from omniintelligence.nodes.pattern_learning_compute.handlers.protocols import (
    DeduplicationResultDict,
    ExtractedFeaturesDict,
    NearThresholdWarningDict,
    PatternClusterDict,
    PatternLearningResult,
    SimilarityResultDict,
    SimilarityWeightsDict,
    StructuralFeaturesDict,
)
from omniintelligence.nodes.pattern_learning_compute.handlers.utils import (
    jaccard_similarity,
    normalize_identifier,
    normalize_identifiers,
    validate_similarity_weights,
)

__all__ = [
    "DEFAULT_SIMILARITY_WEIGHTS",
    "SIGNATURE_NORMALIZATION",
    "SIGNATURE_VERSION",
    "DeduplicationResultDict",
    "ExtractedFeaturesDict",
    "NearThresholdWarningDict",
    "PatternClusterDict",
    "PatternLearningComputeError",
    "PatternLearningResult",
    "PatternLearningValidationError",
    "SimilarityResultDict",
    "SimilarityWeightsDict",
    "StructuralFeaturesDict",
    "jaccard_similarity",
    "normalize_identifier",
    "normalize_identifiers",
    "validate_similarity_weights",
]
