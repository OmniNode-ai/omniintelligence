"""Handler for TF-IDF based intent classification.

This module implements a pure functional TF-IDF based intent classification
algorithm ported from the legacy omniarchon implementation with extensions
for intelligence-focused categories.

The algorithm:
1. Tokenizes and normalizes input text
2. Calculates term frequency (TF) scores for each token
3. Matches tokens against intent-specific keyword patterns
4. Uses weighted scoring (exact matches weighted higher than partial)
5. Normalizes scores to 0.0-1.0 range
6. Returns primary intent with optional secondary intents for multi-label

ONEX Compliance:
- Pure functional design (no side effects)
- Deterministic results for same inputs
- No external service calls or I/O operations
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import TYPE_CHECKING

import time

from omniintelligence.nodes.node_intent_classifier_compute.models import (
    IntentMetadataDict,
    ModelClassificationConfig,
    ModelIntentClassificationInput,
    ModelIntentClassificationOutput,
    SecondaryIntentDict,
)

if TYPE_CHECKING:
    from typing import TypedDict

    class SecondaryIntentResultDict(TypedDict):
        """Secondary intent structure returned by classify_intent.

        This TypedDict provides proper typing for secondary intent items,
        ensuring type safety when processing multi-label classification results.
        """

        intent_category: str
        confidence: float
        keywords: list[str]

    class ClassificationResultDict(TypedDict, total=False):
        """Result structure from classify_intent function."""

        intent_category: str
        confidence: float
        keywords: list[str]
        all_scores: dict[str, float]
        secondary_intents: list[SecondaryIntentResultDict]


logger = logging.getLogger(__name__)

# =============================================================================
# Intent Patterns - Keyword patterns for each intent category
# =============================================================================

# Original patterns from legacy implementation
INTENT_PATTERNS: dict[str, list[str]] = {
    # Original 6 categories from legacy omniarchon
    "code_generation": [
        "generate",
        "create",
        "implement",
        "write",
        "build",
        "develop",
        "make",
        "scaffold",
        "initialize",
        "function",
        "class",
        "module",
        "component",
        "update",
        "configuration",
        "config",
    ],
    "debugging": [
        "debug",
        "fix",
        "error",
        "bug",
        "issue",
        "problem",
        "crash",
        "fail",
        "troubleshoot",
        "diagnose",
        "authentication",
        "token",
        "expiration",
    ],
    "refactoring": [
        "refactor",
        "improve",
        "optimize",
        "restructure",
        "clean",
        "reorganize",
        "simplify",
        "enhance",
        "async",
        "await",
        "pattern",
        "performance",
    ],
    "testing": [
        "test",
        "validate",
        "verify",
        "check",
        "assert",
        "spec",
        "unittest",
        "coverage",
        "unit",
        "comprehensive",
    ],
    "documentation": [
        "documentation",
        "documenting",
        "explain",
        "describe",
        "comment",
        "annotate",
        "readme",
        "guide",
        "docstring",
        "docstrings",
        "comments",
        "add",
        "comprehensive",
    ],
    "analysis": [
        "analyze",
        "review",
        "inspect",
        "examine",
        "evaluate",
        "assess",
        "audit",
        "investigate",
    ],
    # Intelligence-focused categories for OmniIntelligence
    "pattern_learning": [
        "learn",
        "pattern",
        "training",
        "model",
        "embedding",
        "similarity",
        "vector",
        "cluster",
        "classify",
        "recognition",
        "extract",
        "features",
    ],
    "quality_assessment": [
        "quality",
        "assess",
        "score",
        "compliance",
        "onex",
        "validate",
        "standards",
        "metrics",
        "benchmark",
        "grade",
        "rating",
        "evaluation",
    ],
    "semantic_analysis": [
        "semantic",
        "analyze",
        "extract",
        "concept",
        "theme",
        "domain",
        "meaning",
        "context",
        "understand",
        "interpret",
        "nlp",
        "language",
    ],
    # Domain-specific categories (aligned with DOMAIN_TO_INTENT_MAP)
    "api_design": [
        "api",
        "rest",
        "restful",
        "graphql",
        "endpoint",
        "http",
        "request",
        "response",
        "route",
        "controller",
        "middleware",
        "swagger",
        "openapi",
        "websocket",
        "grpc",
        "rpc",
        "service",
    ],
    "architecture": [
        "architecture",
        "design",
        "structure",
        "system",
        "layer",
        "tier",
        "microservice",
        "monolith",
        "distributed",
        "scalable",
        "modular",
        "dependency",
        "coupling",
        "cohesion",
    ],
    "database": [
        "database",
        "sql",
        "nosql",
        "query",
        "table",
        "schema",
        "migration",
        "orm",
        "entity",
        "relationship",
        "index",
        "transaction",
        "postgres",
        "mysql",
        "mongodb",
        "redis",
    ],
    "devops": [
        "deploy",
        "deployment",
        "ci",
        "cd",
        "pipeline",
        "docker",
        "kubernetes",
        "k8s",
        "container",
        "terraform",
        "ansible",
        "jenkins",
        "aws",
        "gcp",
        "azure",
        "cloud",
        "infrastructure",
    ],
    "security": [
        "security",
        "secure",
        "vulnerability",
        "encrypt",
        "decrypt",
        "hash",
        "password",
        "credential",
        "permission",
        "role",
        "access",
        "ssl",
        "tls",
        "https",
        "sanitize",
    ],
}

# Pre-normalized patterns for performance (computed once at module load)
_NORMALIZED_PATTERNS: dict[str, list[str]] = {
    intent: [kw.lower() for kw in keywords]
    for intent, keywords in INTENT_PATTERNS.items()
}

# =============================================================================
# Default Configuration
# =============================================================================
# Immutable default configuration instance for convenience.
# Users can pass custom config to classify_intent() or use this default.
# =============================================================================

DEFAULT_CLASSIFICATION_CONFIG = ModelClassificationConfig()

# =============================================================================
# Pure Functional Classification Algorithm
# =============================================================================


def classify_intent(
    content: str,
    *,
    config: ModelClassificationConfig | None = None,
    confidence_threshold: float | None = None,
    multi_label: bool | None = None,
    max_intents: int | None = None,
) -> ClassificationResultDict:
    """Classify user intent using TF-IDF scoring.

    This function implements a TF-IDF based classification algorithm that
    matches input text against predefined intent patterns. It supports both
    single-label and multi-label classification modes.

    Algorithm Steps:
        1. Tokenize and normalize the input text
        2. Calculate term frequency (TF) scores for each token
        3. Match tokens against intent patterns with weighted scoring
        4. Normalize scores to 0.0-1.0 range
        5. Return classification results based on confidence threshold

    Configuration:
        This function accepts an optional ModelClassificationConfig instance
        for algorithm parameters. If not provided, DEFAULT_CLASSIFICATION_CONFIG
        is used.

    Args:
        content: Text to classify. Must be non-empty for meaningful results.
        config: Optional frozen configuration for classification parameters.
            If None, uses DEFAULT_CLASSIFICATION_CONFIG.
        confidence_threshold: Minimum confidence to return (0.0-1.0).
            Results below this threshold return "unknown" intent.
            Defaults to config.default_confidence_threshold (0.5).
        multi_label: If True, return all intents above threshold as
            secondary_intents. If False, only return primary intent.
            Defaults to config.default_multi_label (False).
        max_intents: Maximum number of secondary intents to return when
            multi_label is True. Defaults to config.default_max_intents (5).

    Returns:
        Dictionary with classification results:
            - intent_category: Primary intent (str)
            - confidence: Confidence score 0.0-1.0 (float)
            - keywords: Matched keywords that influenced classification (list[str])
            - all_scores: Confidence scores for all intent categories (dict[str, float])
            - secondary_intents: List of secondary intents (only if multi_label=True)

    Examples:
        >>> result = classify_intent("Please generate a new Python function")
        >>> result["intent_category"]
        'code_generation'
        >>> result["confidence"] > 0.5
        True

        >>> result = classify_intent("Fix the authentication bug", multi_label=True)
        >>> result["intent_category"]
        'debugging'
        >>> len(result.get("secondary_intents", [])) >= 0
        True

        >>> # Using custom config
        >>> custom_config = ModelClassificationConfig(exact_match_weight=20.0)
        >>> result = classify_intent("Generate code", config=custom_config)
    """
    try:
        # Runtime type validation for defensive programming when called from untyped code.
        # These checks are intentionally guarded against static type analysis since they
        # provide runtime safety for dynamic/untyped callers.
        if not isinstance(content, str):
            logger.warning(  # type: ignore[unreachable]
                "Invalid content type %s, expected str. Converting to string.",
                type(content).__name__,
            )
            content = str(content) if content is not None else ""

        if confidence_threshold is not None and not isinstance(
            confidence_threshold, int | float
        ):
            logger.warning(  # type: ignore[unreachable]
                "Invalid confidence_threshold type %s, using default.",
                type(confidence_threshold).__name__,
            )
            confidence_threshold = None

        if multi_label is not None and not isinstance(multi_label, bool):
            logger.warning(  # type: ignore[unreachable]
                "Invalid multi_label type %s, using default.",
                type(multi_label).__name__,
            )
            multi_label = None

        if max_intents is not None and not isinstance(max_intents, int):
            logger.warning(  # type: ignore[unreachable]
                "Invalid max_intents type %s, using default.",
                type(max_intents).__name__,
            )
            max_intents = None

        # Use provided config or default
        if config is None:
            config = DEFAULT_CLASSIFICATION_CONFIG

        # Apply config defaults for None parameters
        if confidence_threshold is None:
            confidence_threshold = config.default_confidence_threshold
        if max_intents is None:
            max_intents = config.default_max_intents
        if multi_label is None:
            multi_label = config.default_multi_label

        # Step 1: Tokenize and normalize
        tokens = _tokenize(content)

        if not tokens:
            result: ClassificationResultDict = {
                "intent_category": "unknown",
                "confidence": 0.0,
                "keywords": [],
                "all_scores": {},
            }
            # Ensure secondary_intents is included for multi_label mode
            if multi_label:
                result["secondary_intents"] = []
            return result

        # Step 2: Calculate term frequencies
        tf_scores = _calculate_term_frequency(tokens)

        # Step 3: Score each intent category
        intent_scores: dict[str, float] = {}
        intent_keywords: dict[str, list[str]] = {}

        for intent, patterns in _NORMALIZED_PATTERNS.items():
            score, matched_keywords = _calculate_intent_score(
                tf_scores, patterns, tokens, config
            )
            intent_scores[intent] = score
            intent_keywords[intent] = matched_keywords

        # Step 4: Normalize scores to 0.0-1.0 range
        max_score = max(intent_scores.values()) if intent_scores else 1.0
        normalized_scores: dict[str, float] = {
            intent: score / max_score if max_score > 0 else 0.0
            for intent, score in intent_scores.items()
        }

        # Step 5: Rank by confidence (descending)
        sorted_intents = sorted(
            normalized_scores.items(), key=lambda x: x[1], reverse=True
        )

        # Step 6: Build result based on mode
        if multi_label:
            return _build_multi_label_result(
                sorted_intents=sorted_intents,
                intent_keywords=intent_keywords,
                normalized_scores=normalized_scores,
                confidence_threshold=confidence_threshold,
                max_intents=max_intents,
            )

        # Single label mode: return top result
        return _build_single_label_result(
            sorted_intents=sorted_intents,
            intent_keywords=intent_keywords,
            normalized_scores=normalized_scores,
            confidence_threshold=confidence_threshold,
        )

    except Exception as e:
        # Catch-all handler for unexpected exceptions
        logger.exception(
            "Unexpected error during intent classification: %s",
            str(e),
        )
        # Return graceful degradation result
        error_result: ClassificationResultDict = {
            "intent_category": "unknown",
            "confidence": 0.0,
            "keywords": [],
            "all_scores": {},
        }
        # Include secondary_intents if multi_label was requested
        if multi_label:
            error_result["secondary_intents"] = []
        return error_result


# =============================================================================
# Internal Helper Functions
# =============================================================================


def _tokenize(text: str) -> list[str]:
    """Tokenize and normalize text.

    Extracts word tokens from text, converting to lowercase for
    case-insensitive matching.

    Args:
        text: Input text to tokenize.

    Returns:
        List of lowercase word tokens.
    """
    # Extract alphanumeric words and convert to lowercase
    return re.findall(r"\w+", text.lower())


def _calculate_term_frequency(tokens: list[str]) -> dict[str, float]:
    """Calculate term frequency (TF) scores.

    TF(t) = (Number of times term t appears) / (Total number of terms)

    Args:
        tokens: List of tokens from tokenization.

    Returns:
        Dictionary mapping tokens to their TF scores.
    """
    if not tokens:
        return {}

    token_counts = Counter(tokens)
    total_tokens = len(tokens)

    return {token: count / total_tokens for token, count in token_counts.items()}


def _calculate_intent_score(
    tf_scores: dict[str, float],
    patterns: list[str],
    tokens: list[str],
    config: ModelClassificationConfig,
) -> tuple[float, list[str]]:
    """Calculate intent score based on pattern matching and TF scores.

    Combines direct pattern matching with term frequency weighting.
    Exact matches are weighted more heavily than partial matches
    to prioritize clear signals.

    Args:
        tf_scores: Term frequency scores for all tokens.
        patterns: Intent-specific keyword patterns (lowercase).
        tokens: Original tokens from the input text.
        config: Frozen configuration with scoring weights.

    Returns:
        Tuple of (score, matched_keywords) where score is the raw
        weighted score and matched_keywords are the tokens that
        contributed to the score.
    """
    # Read weights from config
    exact_weight = config.exact_match_weight
    partial_weight = config.partial_match_weight
    min_pattern_length = config.min_pattern_length_for_partial

    score = 0.0
    matched_keywords: list[str] = []

    # Direct pattern matches (heavily weighted by TF)
    for pattern in patterns:
        if pattern in tf_scores:
            score += tf_scores[pattern] * exact_weight
            matched_keywords.append(pattern)

    # Partial matches (fuzzy matching for word variations)
    for token in tokens:
        for pattern in patterns:
            # Only do partial matching for patterns of sufficient length
            # Use >= for inclusive threshold (min_pattern_length_for_partial means
            # patterns of at least that length are eligible for partial matching)
            if len(pattern) >= min_pattern_length:
                if pattern in token or token in pattern:
                    # Avoid double-counting exact matches
                    if token not in matched_keywords:
                        score += tf_scores.get(token, 0.0) * partial_weight
                        matched_keywords.append(token)

    return score, matched_keywords


def _build_single_label_result(
    sorted_intents: list[tuple[str, float]],
    intent_keywords: dict[str, list[str]],
    normalized_scores: dict[str, float],
    confidence_threshold: float,
) -> ClassificationResultDict:
    """Build result for single-label classification mode.

    Args:
        sorted_intents: Intents sorted by score descending.
        intent_keywords: Matched keywords for each intent.
        normalized_scores: Normalized 0.0-1.0 scores for all intents.
        confidence_threshold: Minimum confidence threshold.

    Returns:
        Classification result dictionary.
    """
    if sorted_intents and sorted_intents[0][1] >= confidence_threshold:
        top_intent, top_score = sorted_intents[0]
        return {
            "intent_category": top_intent,
            "confidence": top_score,
            "keywords": intent_keywords[top_intent],
            "all_scores": normalized_scores,
        }

    # Below threshold - return unknown
    return {
        "intent_category": "unknown",
        "confidence": 0.0,
        "keywords": [],
        "all_scores": normalized_scores,
    }


def _build_multi_label_result(
    sorted_intents: list[tuple[str, float]],
    intent_keywords: dict[str, list[str]],
    normalized_scores: dict[str, float],
    confidence_threshold: float,
    max_intents: int,
) -> ClassificationResultDict:
    """Build result for multi-label classification mode.

    Returns all intents above the confidence threshold, with the
    highest-scoring intent as primary and others as secondary.

    Args:
        sorted_intents: Intents sorted by score descending.
        intent_keywords: Matched keywords for each intent.
        normalized_scores: Normalized 0.0-1.0 scores for all intents.
        confidence_threshold: Minimum confidence threshold.
        max_intents: Maximum secondary intents to return.

    Returns:
        Classification result dictionary with secondary_intents.
    """
    # Filter to intents above threshold
    filtered_intents = [
        (intent, score)
        for intent, score in sorted_intents
        if score >= confidence_threshold
    ]

    if not filtered_intents:
        return {
            "intent_category": "unknown",
            "confidence": 0.0,
            "keywords": [],
            "all_scores": normalized_scores,
            "secondary_intents": [],
        }

    # Primary intent is the highest scoring
    primary_intent, primary_score = filtered_intents[0]

    # Build secondary intents list (skip primary, limit to max_intents)
    # Using SecondaryIntentResultDict type for proper type safety
    secondary_intents: list[SecondaryIntentResultDict] = []
    for intent, score in filtered_intents[1 : max_intents + 1]:
        secondary_intents.append(
            {
                "intent_category": intent,
                "confidence": score,
                "keywords": intent_keywords[intent],
            }
        )

    return {
        "intent_category": primary_intent,
        "confidence": primary_score,
        "keywords": intent_keywords[primary_intent],
        "all_scores": normalized_scores,
        "secondary_intents": secondary_intents,
    }


# =============================================================================
# Orchestrating Handler - Owns timing, error handling, result building
# =============================================================================


def _build_error_response(
    start_time: float,
    status: str,
    message: str,
    *,
    error_code: str | None = None,
    error_type: str | None = None,
) -> ModelIntentClassificationOutput:
    """Build standardized error response with timing and exception details.

    Args:
        start_time: The perf_counter timestamp when processing started.
        status: Error status type (e.g., "validation_error", "compute_error").
        message: Human-readable error message.
        error_code: Contract-defined error code (e.g., "INTENT_001") for traceability.
        error_type: Exception class name for debugging context.

    Returns:
        ModelIntentClassificationOutput configured for error state.
    """
    processing_time = (time.perf_counter() - start_time) * 1000
    return ModelIntentClassificationOutput(
        success=False,
        intent_category="unknown",
        confidence=0.0,
        secondary_intents=[],
        keywords=[],
        processing_time_ms=processing_time,
        metadata=IntentMetadataDict(
            status=status,
            message=message,
            classification_time_ms=processing_time,
            error_code=error_code,
            error_type=error_type,
        ),
    )


def handle_intent_classification(
    input_data: ModelIntentClassificationInput,
    config: ModelClassificationConfig,
) -> ModelIntentClassificationOutput:
    """Orchestrating handler for intent classification - owns all error handling.

    This handler function follows the declarative node pattern:
    - Owns timing measurement
    - Owns ALL error handling (try/except)
    - Owns ALL logging
    - Returns result models with error info (doesn't raise)

    Args:
        input_data: Typed input model containing content and classification context.
        config: Classification configuration for TF-IDF parameters.

    Returns:
        ModelIntentClassificationOutput with primary intent, confidence,
        secondary intents (if multi-label), and classification metadata.
        On error, returns a failure response with error details.
    """
    start_time = time.perf_counter()

    try:
        # Import exceptions locally to avoid circular imports
        from omniintelligence.nodes.node_intent_classifier_compute.handlers.exceptions import (
            IntentClassificationComputeError,
            IntentClassificationValidationError,
        )

        # Validate input content
        if not input_data.content or not input_data.content.strip():
            raise IntentClassificationValidationError("Content cannot be empty")

        # Extract context parameters - use None to fall through to config defaults
        context = input_data.context or {}
        confidence_threshold = context.get("confidence_threshold")
        max_intents = context.get("max_intents")

        # Call pure classification function for TF-IDF classification
        # Handler applies config defaults when parameters are None
        result = classify_intent(
            content=input_data.content,
            config=config,
            confidence_threshold=confidence_threshold,
            multi_label=True,  # Always compute secondary intents
            max_intents=max_intents,
        )

        processing_time = (time.perf_counter() - start_time) * 1000

        # Map secondary intents from handler to typed output
        secondary_intents: list[SecondaryIntentDict] = []
        for intent in result.get("secondary_intents", []):
            # Extract values with type-safe defaults
            intent_category_raw = intent.get("intent_category", "")
            confidence_raw = intent.get("confidence", 0.0)
            keywords_raw = intent.get("keywords", [])

            secondary_intents.append(
                SecondaryIntentDict(
                    intent_category=str(intent_category_raw),
                    confidence=float(confidence_raw)
                    if isinstance(confidence_raw, (int, float))
                    else 0.0,
                    keywords=list(keywords_raw)
                    if isinstance(keywords_raw, list)
                    else [],
                )
            )

        # Determine actual threshold used (config default if None was passed)
        actual_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else config.default_confidence_threshold
        )

        # Build metadata with classification details
        metadata: IntentMetadataDict = {
            "status": "completed",
            "classifier_version": config.classifier_version,
            "classification_time_ms": processing_time,
            "threshold_used": actual_threshold,
            "raw_scores": result.get("all_scores", {}),
        }

        # Extract primary intent keywords from handler result
        primary_keywords: list[str] = result.get("keywords", [])

        return ModelIntentClassificationOutput(
            success=True,
            intent_category=result["intent_category"],
            confidence=result["confidence"],
            secondary_intents=secondary_intents,
            keywords=primary_keywords,
            processing_time_ms=processing_time,
            metadata=metadata,
        )

    except IntentClassificationValidationError as e:
        logger.warning(
            "Validation error in intent classification: %s (code=%s)",
            e.message,
            e.code,
        )
        return _build_error_response(
            start_time,
            "validation_error",
            str(e),
            error_code=e.code,
            error_type=type(e).__name__,
        )

    except IntentClassificationComputeError as e:
        logger.warning(
            "Compute error in intent classification: %s (code=%s)",
            e.message,
            e.code,
        )
        return _build_error_response(
            start_time,
            "compute_error",
            str(e),
            error_code=e.code,
            error_type=type(e).__name__,
        )

    except Exception as e:
        logger.exception(
            "Unexpected error in intent classification: %s: %s",
            type(e).__name__,
            e,
        )
        return _build_error_response(
            start_time,
            "unexpected_error",
            f"Unexpected error: {type(e).__name__}: {e}",
            error_code=None,
            error_type=type(e).__name__,
        )


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "DEFAULT_CLASSIFICATION_CONFIG",
    "INTENT_PATTERNS",
    "classify_intent",
    "handle_intent_classification",
]
