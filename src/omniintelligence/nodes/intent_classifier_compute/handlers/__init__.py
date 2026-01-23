"""Intent Classifier Compute Handlers.

This module provides handler functions for intent classification operations,
including TF-IDF based classification and semantic enrichment.

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

Usage:
    from omniintelligence.nodes.intent_classifier_compute.handlers import (
        classify_intent,
        INTENT_PATTERNS,
        enrich_with_semantics,
        map_semantic_to_intent_boost,
        LangextractResult,
        create_empty_langextract_result,
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

    # Optional semantic enrichment
    semantic_result = await enrich_with_semantics(
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
    >>> from omniintelligence.nodes.intent_classifier_compute.handlers import (
    ...     classify_intent,
    ...     INTENT_PATTERNS,
    ... )
    >>> result = classify_intent("Please generate a Python function")
    >>> result["intent_category"]
    'code_generation'
    >>> len(INTENT_PATTERNS)
    9
"""

from omniintelligence.nodes.intent_classifier_compute.handlers.exceptions import (
    IntentClassificationComputeError,
    IntentClassificationError,
    IntentClassificationValidationError,
    SemanticAnalysisError,
)
from omniintelligence.nodes.intent_classifier_compute.handlers.handler_intent_classification import (
    INTENT_PATTERNS,
    classify_intent,
)
from omniintelligence.nodes.intent_classifier_compute.handlers.handler_langextract import (
    LANGEXTRACT_SERVICE_URL,
    LANGEXTRACT_TIMEOUT_SECONDS,
    LangextractResult,
    SemanticResult,
    analyze_semantics,
    create_empty_langextract_result,
    create_empty_semantic_result,
    enrich_with_semantics,
    map_semantic_to_intent_boost,
)

__all__ = [
    # Core classification
    "INTENT_PATTERNS",
    "classify_intent",
    # Semantic analysis (new API)
    "SemanticResult",
    "analyze_semantics",
    "create_empty_semantic_result",
    "map_semantic_to_intent_boost",
    # Exceptions (contract-defined)
    "IntentClassificationComputeError",  # INTENT_002
    "IntentClassificationError",  # Base class
    "IntentClassificationValidationError",  # INTENT_001
    "SemanticAnalysisError",  # INTENT_003
    # Backwards compatibility aliases
    "LANGEXTRACT_SERVICE_URL",
    "LANGEXTRACT_TIMEOUT_SECONDS",
    "LangextractResult",
    "create_empty_langextract_result",
    "enrich_with_semantics",
]
