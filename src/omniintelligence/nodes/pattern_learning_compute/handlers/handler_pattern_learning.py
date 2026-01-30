"""Main orchestration handler for pattern learning pipeline.

This handler wires together the existing pipeline handlers to produce
aggregated patterns from training data. It is the main entry point for
pattern learning compute operations.

Pipeline Flow:
    1. validate_inputs (fail-fast on invalid input)
    2. extract_features_batch() - Extract features from training data
    3. cluster_patterns() - Group similar patterns
    4. compute_cluster_scores() - Score each cluster
    5. deduplicate_patterns() - Remove overlapping patterns
    6. split_by_promotion_threshold() - Separate learned vs candidate
    7. compute_learning_metrics() - Generate metrics

SEMANTIC FRAMING (CRITICAL):
    This node describes STRUCTURE. It does NOT decide IMPORTANCE.

    EXPLICITLY BANNED in this handler:
    - Model training or weight updates
    - Adaptive threshold changes
    - Persistence decisions
    - Importance/promotion scoring

    All thresholds and weights are INPUTS, not decisions made here.
    This handler orchestrates structure discovery, not policy enforcement.

Output Contract:
    Returns PatternLearningResult containing:
    - learned_patterns: Patterns meeting promotion threshold (lifecycle=VALIDATED)
    - candidate_patterns: Patterns below threshold (lifecycle=CANDIDATE)
    - metrics: Aggregation metrics for monitoring
    - metadata: Processing context
    - warnings: Near-threshold and other warnings

Usage:
    from omniintelligence.nodes.pattern_learning_compute.handlers.handler_pattern_learning import (
        aggregate_patterns,
        split_by_promotion_threshold,
        compute_learning_metrics,
    )

    result = aggregate_patterns(
        training_data=training_items,
        parameters=learning_params,
        similarity_weights=weights,
        promotion_threshold=0.7,
    )

    if result["success"]:
        learned = result["learned_patterns"]
        candidates = result["candidate_patterns"]
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from omnibase_core.enums.pattern_learning import (
    EnumPatternLearningStatus,
    EnumPatternLifecycleState,
    EnumPatternType,
)
from omnibase_core.models.pattern_learning import (
    ModelLearnedPattern,
    ModelPatternLearningMetadata,
    ModelPatternLearningMetrics,
    ModelPatternScoreComponents,
    ModelPatternSignature,
)
from omnibase_core.models.primitives import ModelSemVer

from omniintelligence.nodes.pattern_learning_compute.handlers.exceptions import (
    PatternLearningValidationError,
)
from omniintelligence.nodes.pattern_learning_compute.handlers.handler_confidence_scoring import (
    compute_cluster_scores,
)
from omniintelligence.nodes.pattern_learning_compute.handlers.handler_deduplication import (
    deduplicate_patterns,
    generate_pattern_signature,
)
from omniintelligence.nodes.pattern_learning_compute.handlers.handler_feature_extraction import (
    extract_features_batch,
)
from omniintelligence.nodes.pattern_learning_compute.handlers.handler_pattern_clustering import (
    cluster_patterns,
)
from omniintelligence.nodes.pattern_learning_compute.handlers.presets import (
    DEFAULT_DEDUPLICATION_THRESHOLD,
    DEFAULT_PROMOTION_THRESHOLD,
    DEFAULT_SIMILARITY_WEIGHTS,
    SIGNATURE_VERSION,
)
from omniintelligence.nodes.pattern_learning_compute.handlers.protocols import (
    DeduplicationResultDict,
    PatternClusterDict,
    PatternLearningResult,
    PatternScoreComponentsDict,
    SimilarityWeightsDict,
)
from omniintelligence.nodes.pattern_learning_compute.models import (
    LearningParametersDict,
    TrainingDataItemDict,
)

# =============================================================================
# Constants
# =============================================================================

# Model version for metadata tracking
_MODEL_VERSION = ModelSemVer(major=1, minor=0, patch=0)

# Pattern type mapping from string to enum
# Unknown types map to CODE_PATTERN as a safe default
_PATTERN_TYPE_MAP: dict[str, EnumPatternType] = {
    "code": EnumPatternType.CODE_PATTERN,
    "code_pattern": EnumPatternType.CODE_PATTERN,
    "error": EnumPatternType.ERROR_PATTERN,
    "error_pattern": EnumPatternType.ERROR_PATTERN,
    "workflow": EnumPatternType.WORKFLOW_PATTERN,
    "workflow_pattern": EnumPatternType.WORKFLOW_PATTERN,
    "interaction": EnumPatternType.INTERACTION_PATTERN,
    "interaction_pattern": EnumPatternType.INTERACTION_PATTERN,
    "configuration": EnumPatternType.CONFIGURATION_PATTERN,
    "configuration_pattern": EnumPatternType.CONFIGURATION_PATTERN,
    # ONEX base class indicators
    "nodecompute": EnumPatternType.CODE_PATTERN,
    "nodeeffect": EnumPatternType.CODE_PATTERN,
    "nodereducer": EnumPatternType.CODE_PATTERN,
    "nodeorchestrator": EnumPatternType.WORKFLOW_PATTERN,
    "basemodel": EnumPatternType.CODE_PATTERN,
    # Short forms commonly used in tests and elsewhere
    "compute": EnumPatternType.CODE_PATTERN,
    "effect": EnumPatternType.CODE_PATTERN,
    "reducer": EnumPatternType.CODE_PATTERN,
    "orchestrator": EnumPatternType.WORKFLOW_PATTERN,
}

# =============================================================================
# Public API
# =============================================================================


def aggregate_patterns(
    training_data: Sequence[TrainingDataItemDict],
    parameters: LearningParametersDict | None = None,
    similarity_weights: SimilarityWeightsDict | None = None,
    promotion_threshold: float = DEFAULT_PROMOTION_THRESHOLD,
) -> PatternLearningResult:
    """Orchestrate the full pattern learning pipeline.

    This function coordinates the complete pipeline from raw training data
    to aggregated patterns ready for use or further validation.

    SEMANTIC FRAMING (CRITICAL):
        This function describes STRUCTURE. It does NOT decide IMPORTANCE.

        EXPLICITLY BANNED:
        - Model training or weight updates
        - Adaptive threshold changes
        - Persistence decisions
        - Importance/promotion scoring

        All thresholds and weights are INPUTS, not decisions made here.

    Pipeline Steps:
        1. Validate inputs (fail-fast on first invalid item)
        2. Extract features from all training items
        3. Cluster similar patterns together
        4. Score each cluster for confidence
        5. Deduplicate overlapping patterns
        6. Split by promotion threshold
        7. Compute aggregation metrics

    Args:
        training_data: Sequence of training items containing code snippets
            and metadata. Must not be empty.
        parameters: Optional learning parameters. Not used for thresholds
            (those are explicit args) but available for future extensions.
        similarity_weights: Optional custom similarity weights. If None,
            uses DEFAULT_SIMILARITY_WEIGHTS.
        promotion_threshold: Confidence threshold for promotion. Patterns
            with confidence >= threshold become learned_patterns with
            lifecycle_state=VALIDATED. Below threshold become candidates
            with lifecycle_state=CANDIDATE. Defaults to 0.70.

    Returns:
        PatternLearningResult containing:
        - success: True if pipeline completed without errors
        - learned_patterns: Patterns meeting promotion threshold
        - candidate_patterns: Patterns below threshold
        - metrics: Aggregation metrics for monitoring
        - metadata: Processing context and thresholds used
        - warnings: Near-threshold and other warnings

    Raises:
        PatternLearningValidationError: If training_data is empty or
            contains invalid items. Fail-fast on first invalid input.

    Examples:
        >>> result = aggregate_patterns(training_data, promotion_threshold=0.7)
        >>> if result["success"]:
        ...     print(f"Learned: {len(result['learned_patterns'])}")
        ...     print(f"Candidates: {len(result['candidate_patterns'])}")
    """
    start_time_ms = time.perf_counter() * 1000

    # Reserved for future extensions (suppress unused argument warning)
    _ = parameters

    # Use default weights if none provided
    if similarity_weights is None:
        similarity_weights = DEFAULT_SIMILARITY_WEIGHTS

    # Initialize warnings list
    warnings: list[str] = []

    # Step 1: Validate inputs (fail-fast)
    _validate_training_data(training_data)

    # Step 2: Extract features from training data
    training_list = list(training_data)  # Ensure list for handlers
    features_list = extract_features_batch(training_list)

    # Step 3: Cluster similar patterns
    clusters = cluster_patterns(
        features_list=features_list,
        weights=similarity_weights,
    )

    # Handle empty clusters case
    if not clusters:
        end_time_ms = time.perf_counter() * 1000
        processing_time_ms = end_time_ms - start_time_ms

        return _create_empty_result(
            input_count=len(training_data),
            processing_time_ms=processing_time_ms,
            promotion_threshold=promotion_threshold,
            warnings=["No clusters formed from training data"],
        )

    # Step 4: Score each cluster for confidence
    confidence_scores: dict[str, PatternScoreComponentsDict] = {}
    for cluster in clusters:
        scores = compute_cluster_scores(cluster)
        confidence_scores[cluster["cluster_id"]] = scores

    # Step 5: Deduplicate overlapping patterns
    confidence_map = {
        cid: scores["confidence"] for cid, scores in confidence_scores.items()
    }
    dedup_result = deduplicate_patterns(
        clusters=clusters,
        confidence_scores=confidence_map,
        weights=similarity_weights,
    )

    # Collect near-threshold warnings
    for warning in dedup_result["near_threshold_warnings"]:
        warnings.append(
            f"Near-threshold pair: {warning['cluster_a_id']} and {warning['cluster_b_id']} "
            f"(similarity={warning['similarity']:.3f}, threshold={warning['threshold']:.3f}, "
            f"action={warning['action_taken']})"
        )

    # Step 6: Split by promotion threshold
    learned_patterns, candidate_patterns = split_by_promotion_threshold(
        clusters=dedup_result["deduplicated_clusters"],
        confidence_scores=confidence_scores,
        threshold=promotion_threshold,
    )

    # Step 7: Compute metrics
    end_time_ms = time.perf_counter() * 1000
    processing_time_ms = end_time_ms - start_time_ms

    metrics = compute_learning_metrics(
        input_count=len(training_data),
        clusters=clusters,
        confidence_scores=confidence_scores,
        dedup_result=dedup_result,
        processing_time_ms=processing_time_ms,
        learned_count=len(learned_patterns),
        candidate_count=len(candidate_patterns),
    )

    # Build metadata
    metadata = ModelPatternLearningMetadata(
        status=EnumPatternLearningStatus.COMPLETED,
        model_version=_MODEL_VERSION,
        timestamp=datetime.now(UTC),
        deduplication_threshold_used=dedup_result["threshold_used"],
        promotion_threshold_used=promotion_threshold,
        training_samples=len(training_data),
        validation_samples=0,  # No separate validation set in this pipeline
        convergence_achieved=True,  # Non-iterative algorithm
        early_stopped=False,  # Non-iterative algorithm
        final_epoch=1,  # Single pass
    )

    return PatternLearningResult(
        success=True,
        candidate_patterns=candidate_patterns,
        learned_patterns=learned_patterns,
        metrics=metrics,
        metadata=metadata,
        warnings=warnings,
    )


def split_by_promotion_threshold(
    clusters: list[PatternClusterDict],
    confidence_scores: dict[str, PatternScoreComponentsDict],
    threshold: float = DEFAULT_PROMOTION_THRESHOLD,
) -> tuple[list[ModelLearnedPattern], list[ModelLearnedPattern]]:
    """Split patterns by confidence threshold into learned vs candidate.

    Patterns meeting the threshold are assigned lifecycle_state=VALIDATED
    and returned as learned_patterns. Patterns below threshold are assigned
    lifecycle_state=CANDIDATE and returned as candidate_patterns.

    SEMANTIC FRAMING (CRITICAL):
        This function describes STRUCTURE. It does NOT decide IMPORTANCE.

        EXPLICITLY BANNED:
        - Adaptive threshold changes
        - Importance/promotion scoring
        - Any modification to the threshold

        The threshold is an INPUT, not a decision made here.

    Args:
        clusters: Deduplicated pattern clusters to split.
        confidence_scores: Mapping of cluster_id to score components.
            Must contain entries for all clusters.
        threshold: Confidence threshold for promotion. Defaults to 0.70.

    Returns:
        Tuple of (learned_patterns, candidate_patterns):
        - learned_patterns: Patterns with confidence >= threshold
        - candidate_patterns: Patterns with confidence < threshold

    Raises:
        PatternLearningValidationError: If a cluster is missing from
            confidence_scores.

    Examples:
        >>> learned, candidates = split_by_promotion_threshold(
        ...     clusters, scores, threshold=0.7
        ... )
        >>> print(f"Learned: {len(learned)}, Candidates: {len(candidates)}")
    """
    learned_patterns: list[ModelLearnedPattern] = []
    candidate_patterns: list[ModelLearnedPattern] = []

    for cluster in clusters:
        cluster_id = cluster["cluster_id"]

        # Get confidence scores for this cluster
        if cluster_id not in confidence_scores:
            raise PatternLearningValidationError(
                f"Missing confidence scores for cluster {cluster_id}. "
                "This indicates a bug in the pipeline."
            )

        scores = confidence_scores[cluster_id]
        confidence = scores["confidence"]

        # Determine lifecycle state based on threshold
        if confidence >= threshold:
            lifecycle_state = EnumPatternLifecycleState.VALIDATED
        else:
            lifecycle_state = EnumPatternLifecycleState.CANDIDATE

        # Convert to ModelLearnedPattern
        pattern = _cluster_to_learned_pattern(
            cluster=cluster,
            scores=scores,
            lifecycle_state=lifecycle_state,
        )

        # Route to appropriate list
        if lifecycle_state == EnumPatternLifecycleState.VALIDATED:
            learned_patterns.append(pattern)
        else:
            candidate_patterns.append(pattern)

    return learned_patterns, candidate_patterns


def compute_learning_metrics(
    input_count: int,
    clusters: list[PatternClusterDict],
    confidence_scores: dict[str, PatternScoreComponentsDict],
    dedup_result: DeduplicationResultDict,
    processing_time_ms: float,
    learned_count: int,
    candidate_count: int,
) -> ModelPatternLearningMetrics:
    """Compute aggregation metrics from handler outputs.

    Aggregates metrics across all clusters and scores for monitoring
    and debugging pattern learning quality over time.

    Args:
        input_count: Number of training items processed.
        clusters: All clusters formed (before deduplication).
        confidence_scores: Mapping of cluster_id to score components.
        dedup_result: Result from deduplication handler.
        processing_time_ms: Total processing time in milliseconds.
        learned_count: Number of patterns that met the promotion threshold
            (lifecycle_state=VALIDATED).
        candidate_count: Number of patterns below the promotion threshold
            (lifecycle_state=CANDIDATE).

    Returns:
        ModelPatternLearningMetrics with computed values.

    Examples:
        >>> metrics = compute_learning_metrics(
        ...     input_count=100,
        ...     clusters=clusters,
        ...     confidence_scores=scores,
        ...     dedup_result=dedup_result,
        ...     processing_time_ms=150.0,
        ...     learned_count=5,
        ...     candidate_count=10,
        ... )
        >>> print(f"Mean confidence: {metrics.mean_confidence:.3f}")
    """
    # Count final patterns after deduplication
    final_clusters = dedup_result["deduplicated_clusters"]

    # Compute means from confidence scores
    # Use scores from deduplicated clusters only for mean calculations
    deduplicated_ids = {c["cluster_id"] for c in final_clusters}
    deduplicated_scores = [
        confidence_scores[cid]
        for cid in deduplicated_ids
        if cid in confidence_scores
    ]

    if deduplicated_scores:
        mean_confidence = sum(s["confidence"] for s in deduplicated_scores) / len(
            deduplicated_scores
        )
        mean_label_agreement = sum(
            s["label_agreement"] for s in deduplicated_scores
        ) / len(deduplicated_scores)
        mean_cluster_cohesion = sum(
            s["cluster_cohesion"] for s in deduplicated_scores
        ) / len(deduplicated_scores)
    else:
        mean_confidence = 0.0
        mean_label_agreement = 0.0
        mean_cluster_cohesion = 0.0

    return ModelPatternLearningMetrics(
        input_count=input_count,
        cluster_count=len(clusters),
        candidate_count=candidate_count,
        learned_count=learned_count,
        discarded_count=0,  # Fail-fast means no discards
        merged_count=dedup_result["merged_count"],
        mean_confidence=mean_confidence,
        mean_label_agreement=mean_label_agreement,
        mean_cluster_cohesion=mean_cluster_cohesion,
        processing_time_ms=processing_time_ms,
    )


# =============================================================================
# Private Helpers
# =============================================================================


def _validate_training_data(training_data: Sequence[TrainingDataItemDict]) -> None:
    """Validate training data inputs.

    Fail-fast on first invalid input.

    Args:
        training_data: Sequence of training items to validate.

    Raises:
        PatternLearningValidationError: If training_data is empty.
    """
    if not training_data:
        raise PatternLearningValidationError(
            "Training data cannot be empty. "
            "Provide at least one training item with code_snippet."
        )


def _create_empty_result(
    input_count: int,
    processing_time_ms: float,
    promotion_threshold: float,
    warnings: list[str],
) -> PatternLearningResult:
    """Create an empty result when no patterns are formed.

    Args:
        input_count: Number of input items processed.
        processing_time_ms: Processing time in milliseconds.
        promotion_threshold: The threshold that was used.
        warnings: Warnings to include.

    Returns:
        PatternLearningResult with empty pattern lists.
    """
    metrics = ModelPatternLearningMetrics(
        input_count=input_count,
        cluster_count=0,
        candidate_count=0,
        learned_count=0,
        discarded_count=0,
        merged_count=0,
        mean_confidence=0.0,
        mean_label_agreement=0.0,
        mean_cluster_cohesion=0.0,
        processing_time_ms=processing_time_ms,
    )

    metadata = ModelPatternLearningMetadata(
        status=EnumPatternLearningStatus.COMPLETED,
        model_version=_MODEL_VERSION,
        timestamp=datetime.now(UTC),
        deduplication_threshold_used=DEFAULT_DEDUPLICATION_THRESHOLD,
        promotion_threshold_used=promotion_threshold,
        training_samples=input_count,
        validation_samples=0,
        convergence_achieved=True,
        early_stopped=False,
        final_epoch=1,
    )

    return PatternLearningResult(
        success=True,
        candidate_patterns=[],
        learned_patterns=[],
        metrics=metrics,
        metadata=metadata,
        warnings=warnings,
    )


def _cluster_to_learned_pattern(
    cluster: PatternClusterDict,
    scores: PatternScoreComponentsDict,
    lifecycle_state: EnumPatternLifecycleState,
) -> ModelLearnedPattern:
    """Convert a PatternClusterDict to ModelLearnedPattern.

    Maps internal cluster representation to the contract model.

    SEMANTIC FRAMING (CRITICAL):
        This function describes STRUCTURE. It does NOT decide IMPORTANCE.

        EXPLICITLY BANNED:
        - Modifying scores or confidence
        - Changing lifecycle_state
        - Any policy decisions

    Args:
        cluster: Pattern cluster from clustering handler.
        scores: Confidence score components for this cluster.
        lifecycle_state: Lifecycle state to assign (VALIDATED or CANDIDATE).

    Returns:
        ModelLearnedPattern with all fields populated.
    """
    cluster_id = cluster["cluster_id"]
    centroid = cluster["centroid_features"]

    # Generate pattern_id from cluster_id using UUID5
    pattern_id = uuid.uuid5(uuid.NAMESPACE_DNS, cluster_id)

    # Map pattern_type string to enum
    pattern_type_str = cluster["pattern_type"].lower()
    pattern_type = _PATTERN_TYPE_MAP.get(
        pattern_type_str, EnumPatternType.CODE_PATTERN
    )

    # Derive category from pattern_type
    category = _derive_category(pattern_type)
    subcategory = "default"

    # Extract tags from labels (convert to tuple)
    tags = tuple(centroid["labels"]) if centroid["labels"] else ()

    # Extract keywords from centroid (already a tuple)
    keywords = centroid["keywords"]

    # Build score components model
    score_components = ModelPatternScoreComponents(
        label_agreement=scores["label_agreement"],
        cluster_cohesion=scores["cluster_cohesion"],
        frequency_factor=scores["frequency_factor"],
        confidence=scores["confidence"],
    )

    # Generate signature
    signature_dict = generate_pattern_signature(cluster)
    # Strip "v" prefix from SIGNATURE_VERSION if present for ModelSemVer
    version_str = SIGNATURE_VERSION.lstrip("v")
    signature_info = ModelPatternSignature(
        signature=signature_dict["signature"],
        signature_version=ModelSemVer.parse(version_str),
        signature_inputs=signature_dict["signature_inputs"],
        normalization_applied=signature_dict["normalization_applied"],
    )

    # Timestamps
    now = datetime.now(UTC)

    # Build pattern name
    pattern_name = f"{pattern_type_str}_pattern"

    return ModelLearnedPattern(
        pattern_id=pattern_id,
        pattern_name=pattern_name,
        pattern_type=pattern_type,
        category=category,
        subcategory=subcategory,
        tags=tags,
        keywords=keywords,
        score_components=score_components,
        signature_info=signature_info,
        lifecycle_state=lifecycle_state,
        source_count=cluster["member_count"],
        first_seen=now,
        last_seen=now,
    )


def _derive_category(pattern_type: EnumPatternType) -> str:
    """Derive category string from pattern type.

    Args:
        pattern_type: The pattern type enum.

    Returns:
        Category string for the pattern.
    """
    category_map = {
        EnumPatternType.CODE_PATTERN: "code",
        EnumPatternType.ERROR_PATTERN: "error_handling",
        EnumPatternType.WORKFLOW_PATTERN: "workflow",
        EnumPatternType.INTERACTION_PATTERN: "interaction",
        EnumPatternType.CONFIGURATION_PATTERN: "configuration",
    }
    return category_map.get(pattern_type, "general")


__all__ = [
    "aggregate_patterns",
    "compute_learning_metrics",
    "split_by_promotion_threshold",
]
