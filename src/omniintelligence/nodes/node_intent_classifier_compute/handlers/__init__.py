# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Intent Classifier Compute Handlers.

This module provides handler functions for intent classification operations,
including TF-IDF based classification and semantic analysis.

Handler Pattern:
    Each handler is a PURE FUNCTION that:
    - Accepts input parameters
    - Performs computation (no external I/O)
    - Returns a typed result dictionary
    - Handles errors gracefully without raising

Core Classification:
    The classify_intent handler implements TF-IDF based classification:
    - Tokenizes and normalizes input text
    - Calculates term frequency (TF) scores
    - Matches against 9 intent categories (6 original + 3 intelligence-focused)
    - Supports multi-label classification
    - Pure functional design (no side effects)

Semantic Analysis:
    The analyze_semantics handler provides semantic enrichment:
    - Extracts concepts, themes, domains from text using keyword patterns
    - Pure computation - no HTTP calls or external services
    - Enhances intent classification with domain-specific boosts

Error Handling:
    Contract-defined exceptions with error codes for structured handling:
    - IntentClassificationValidationError (INTENT_001): Non-recoverable input errors
    - IntentClassificationComputeError (INTENT_002): Recoverable computation errors
    - SemanticAnalysisError (INTENT_003): Non-blocking semantic errors

Usage:
    from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
        classify_intent,
        handle_intent_classification,
        INTENT_PATTERNS,
        analyze_semantics,
        map_semantic_to_intent_boost,
        IntentClassificationValidationError,
        IntentClassificationComputeError,
    )

    # Core TF-IDF classification
    result = classify_intent(
        content="Create a REST API endpoint",
        confidence_threshold=0.5,
        multi_label=False,
    )
    print(f"Intent: {result['intent_category']} ({result['confidence']:.2f})")

    # Optional semantic analysis
    semantic_result = analyze_semantics(
        content="Create a REST API endpoint",
        context="api_development",
    )

    # Map semantics to intent confidence boosts
    boosts = map_semantic_to_intent_boost(semantic_result)

    # Error handling with contract codes
    try:
        result = classify_intent(content="...")
    except IntentClassificationValidationError as e:
        log.error(f"Validation failed: {e.code} - {e.message}")
    except IntentClassificationComputeError as e:
        log.warning(f"Compute error: {e.code} - {e.message}, retrying...")

Example:
    >>> from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
    ...     classify_intent,
    ...     INTENT_PATTERNS,
    ... )
    >>> result = classify_intent("Please generate a Python function")
    >>> result["intent_category"]
    'code_generation'
    >>> len(INTENT_PATTERNS)
    9
"""

from omniintelligence.nodes.node_intent_classifier_compute.handlers.exceptions import (
    IntentClassificationComputeError,
    IntentClassificationError,
    IntentClassificationValidationError,
    SemanticAnalysisError,
)
from omniintelligence.nodes.node_intent_classifier_compute.handlers.handler_adaptive_classification import (
    UNKNOWN_CONFIDENCE_THRESHOLD,
    AdaptiveClassificationResult,
    classify_intent_adaptive,
    get_classifier_version,
    reset_classifier,
)
from omniintelligence.nodes.node_intent_classifier_compute.handlers.handler_intent_classification import (
    DEFAULT_CLASSIFICATION_CONFIG,
    INTENT_PATTERNS,
    classify_intent,
    handle_intent_classification,
)
from omniintelligence.nodes.node_intent_classifier_compute.handlers.handler_langextract import (
    DEFAULT_SEMANTIC_CONFIG,
    SemanticResult,
    analyze_semantics,
    create_empty_semantic_result,
    map_semantic_to_intent_boost,
)
from omniintelligence.nodes.node_intent_classifier_compute.handlers.handler_typed_classification import (
    DEFAULT_TYPED_CONFIDENCE_THRESHOLD,
    get_category_to_typed_class_mapping,
    resolve_typed_intent,
)

__all__ = [
    "DEFAULT_CLASSIFICATION_CONFIG",
    "DEFAULT_SEMANTIC_CONFIG",
    "DEFAULT_TYPED_CONFIDENCE_THRESHOLD",
    "INTENT_PATTERNS",
    "IntentClassificationComputeError",
    "IntentClassificationError",
    "IntentClassificationValidationError",
    "SemanticAnalysisError",
    "SemanticResult",
    "UNKNOWN_CONFIDENCE_THRESHOLD",
    "AdaptiveClassificationResult",
    "analyze_semantics",
    "classify_intent",
    "classify_intent_adaptive",
    "create_empty_semantic_result",
    "get_category_to_typed_class_mapping",
    "get_classifier_version",
    "handle_intent_classification",
    "map_semantic_to_intent_boost",
    "reset_classifier",
    "resolve_typed_intent",
]
