"""Handler for langextract semantic enrichment (optional).

This module provides an async HTTP client for the langextract service,
enabling optional semantic enrichment for intent classification.

IMPORTANT: This handler is OPTIONAL and designed for graceful degradation.
If the langextract service is unavailable, all functions return empty results
without raising exceptions.

Design Decisions:
    - Never raises exceptions - all errors return empty/default results
    - Configurable via environment variables
    - Uses httpx for async HTTP with proper timeout handling
    - No hard dependency on langextract service availability
    - Provides mapping from semantic concepts to intent confidence boosts

Langextract API:
    Endpoint: POST /analyze/semantic
    Request: {"content": str, "context": str?, "language": str}
    Response: {
        "concepts": [...],
        "themes": [...],
        "semantic_patterns": [...],
        "domain_indicators": [...],
        "topic_weights": {...},
        ...
    }

Usage:
    from omniintelligence.nodes.intent_classifier_compute.handlers import (
        enrich_with_semantics,
        map_semantic_to_intent_boost,
    )

    # Enrich with semantic analysis (graceful fallback on failure)
    result = await enrich_with_semantics(
        content="Create a REST API endpoint for user authentication",
        context="api_development",
    )

    # Map results to intent boosts
    boosts = map_semantic_to_intent_boost(result)
    # -> {"code_generation": 0.15, "api_design": 0.10, ...}

Example:
    >>> import asyncio
    >>> from omniintelligence.nodes.intent_classifier_compute.handlers import (
    ...     create_empty_langextract_result,
    ...     map_semantic_to_intent_boost,
    ... )
    >>> result = create_empty_langextract_result()
    >>> boosts = map_semantic_to_intent_boost(result)
    >>> boosts
    {}
"""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Any, Final, cast

import httpx

if TYPE_CHECKING:
    from typing import TypedDict

    class LangextractResult(TypedDict, total=False):
        """Result from langextract semantic analysis.

        All fields are optional to support graceful degradation.
        An empty result (all fields empty/None) indicates either:
        - Service unavailable
        - Request timeout
        - Invalid response

        Nested dict structures:
            - concepts: list of {concept_id?, name, confidence, category?}
            - themes: list of {theme_id?, name, weight?}
            - domains: list of {domain_id?, name, confidence}
            - patterns: list of {pattern_id?, pattern_type, pattern_name, confidence_score}
        """

        concepts: list[dict[str, Any]]
        themes: list[dict[str, Any]]
        domains: list[dict[str, Any]]
        patterns: list[dict[str, Any]]
        domain_indicators: list[str]
        topic_weights: dict[str, float]
        processing_time_ms: float
        error: str | None

else:
    # Runtime type aliases for non-TYPE_CHECKING context
    LangextractResult = dict


logger = logging.getLogger(__name__)

# =============================================================================
# Configuration (Environment Variables)
# =============================================================================

LANGEXTRACT_SERVICE_URL: Final[str] = os.getenv(
    "LANGEXTRACT_SERVICE_URL",
    "http://localhost:8156",
)
LANGEXTRACT_TIMEOUT_SECONDS: Final[float] = float(
    os.getenv("LANGEXTRACT_TIMEOUT_SECONDS", "10.0")
)

# Intent category to semantic domain/concept mapping
# Maps langextract domains/concepts to intent categories for confidence boosting
DOMAIN_TO_INTENT_MAP: Final[dict[str, str]] = {
    # API-related domains
    "api": "api_design",
    "api_design": "api_design",
    "rest": "api_design",
    "graphql": "api_design",
    "endpoint": "api_design",
    "http": "api_design",
    # Code generation domains
    "code_generation": "code_generation",
    "programming": "code_generation",
    "software_development": "code_generation",
    "implementation": "code_generation",
    "coding": "code_generation",
    # Testing domains
    "testing": "testing",
    "test": "testing",
    "unit_test": "testing",
    "integration_test": "testing",
    "quality_assurance": "testing",
    # Documentation domains
    "documentation": "documentation",
    "docs": "documentation",
    "readme": "documentation",
    "technical_writing": "documentation",
    # Architecture domains
    "architecture": "architecture",
    "design_pattern": "architecture",
    "system_design": "architecture",
    "infrastructure": "architecture",
    # Database domains
    "database": "database",
    "sql": "database",
    "nosql": "database",
    "data_modeling": "database",
    # DevOps domains
    "devops": "devops",
    "ci_cd": "devops",
    "deployment": "devops",
    "kubernetes": "devops",
    "docker": "devops",
    # Security domains
    "security": "security",
    "authentication": "security",
    "authorization": "security",
    "encryption": "security",
    # Debugging domains
    "debugging": "debugging",
    "troubleshooting": "debugging",
    "error_handling": "debugging",
    "bug_fix": "debugging",
    # Refactoring domains
    "refactoring": "refactoring",
    "code_cleanup": "refactoring",
    "optimization": "refactoring",
    # Research domains
    "research": "research",
    "investigation": "research",
    "analysis": "research",
}

# Confidence boost amounts for different match types
DOMAIN_MATCH_BOOST: Final[float] = 0.10
CONCEPT_MATCH_BOOST: Final[float] = 0.05
TOPIC_WEIGHT_MULTIPLIER: Final[float] = 0.15


# =============================================================================
# Factory Functions
# =============================================================================


def create_empty_langextract_result(error: str | None = None) -> LangextractResult:
    """Create an empty langextract result.

    Use this when the service is unavailable or an error occurred.

    Args:
        error: Optional error message to include.

    Returns:
        LangextractResult with all fields empty/default.

    Example:
        >>> result = create_empty_langextract_result()
        >>> result["concepts"]
        []
        >>> result["error"] is None
        True
    """
    return LangextractResult(
        concepts=[],
        themes=[],
        domains=[],
        patterns=[],
        domain_indicators=[],
        topic_weights={},
        processing_time_ms=0.0,
        error=error,
    )


# =============================================================================
# Main Handler Functions
# =============================================================================


async def enrich_with_semantics(
    content: str,
    context: str | None = None,
    language: str = "en",
    min_confidence: float = 0.7,
) -> LangextractResult:
    """Enrich intent classification with semantic analysis from langextract.

    This is OPTIONAL and should be used when deeper semantic understanding
    is needed. Falls back gracefully if langextract service is unavailable.

    The function never raises exceptions. All errors are captured and
    returned as empty results with an error message.

    Args:
        content: Text content to analyze.
        context: Optional context hint (e.g., "api_development", "testing").
            Helps langextract provide more relevant analysis.
        language: Language code (default: "en").
        min_confidence: Minimum confidence threshold for results (0.0-1.0).
            Lower values return more results with potentially lower quality.

    Returns:
        LangextractResult with semantic analysis data:
        - concepts: Extracted semantic concepts
        - themes: Identified themes
        - domains: Detected domains
        - patterns: Semantic patterns
        - domain_indicators: Raw domain indicator strings
        - topic_weights: Topic -> weight mapping
        - processing_time_ms: Time taken for analysis
        - error: Error message if any (None on success)

    Note:
        This function NEVER raises exceptions. Errors are captured and
        returned in the result's "error" field.

    Example:
        >>> import asyncio
        >>> result = asyncio.run(enrich_with_semantics("Create a REST API"))
        >>> # Returns empty result if service unavailable
        >>> isinstance(result.get("concepts", []), list)
        True
    """
    if not content or not content.strip():
        logger.debug("Empty content provided, returning empty result")
        return create_empty_langextract_result()

    start_time = time.perf_counter()
    url = f"{LANGEXTRACT_SERVICE_URL.rstrip('/')}/analyze/semantic"

    # Build request payload
    request_payload: dict[str, Any] = {
        "content": content,
        "language": language,
    }
    if context:
        request_payload["context"] = context

    try:
        async with httpx.AsyncClient() as client:
            logger.debug(f"Calling langextract at {url}")

            response = await client.post(
                url,
                json=request_payload,
                timeout=LANGEXTRACT_TIMEOUT_SECONDS,
            )

            processing_time_ms = (time.perf_counter() - start_time) * 1000

            # Handle non-200 responses gracefully
            if response.status_code != 200:
                error_msg = f"Langextract returned status {response.status_code}"
                logger.warning(error_msg)
                return create_empty_langextract_result(error=error_msg)

            # Parse response
            data = response.json()

            # Extract and filter results by confidence threshold
            # Use cast() to preserve type information after filtering
            concepts = cast(
                list[dict[str, Any]],
                _filter_by_confidence(
                    data.get("concepts", []),
                    min_confidence,
                    confidence_key="confidence",
                ),
            )
            themes = cast(list[dict[str, Any]], data.get("themes", []))
            domains = cast(
                list[dict[str, Any]],
                _filter_by_confidence(
                    data.get("domains", []),
                    min_confidence,
                    confidence_key="confidence",
                ),
            )
            patterns = cast(
                list[dict[str, Any]],
                _filter_by_confidence(
                    data.get("semantic_patterns", []),
                    min_confidence,
                    confidence_key="confidence_score",
                ),
            )
            domain_indicators = cast(list[str], data.get("domain_indicators", []))
            topic_weights = cast(dict[str, float], data.get("topic_weights", {}))

            logger.info(
                f"Langextract enrichment completed in {processing_time_ms:.2f}ms: "
                f"{len(concepts)} concepts, {len(themes)} themes, "
                f"{len(domains)} domains, {len(patterns)} patterns"
            )

            return LangextractResult(
                concepts=concepts,
                themes=themes,
                domains=domains,
                patterns=patterns,
                domain_indicators=domain_indicators,
                topic_weights=topic_weights,
                processing_time_ms=round(processing_time_ms, 2),
                error=None,
            )

    except httpx.TimeoutException:
        processing_time_ms = (time.perf_counter() - start_time) * 1000
        error_msg = f"Langextract timeout after {LANGEXTRACT_TIMEOUT_SECONDS}s"
        logger.warning(error_msg)
        return create_empty_langextract_result(error=error_msg)

    except httpx.ConnectError as e:
        processing_time_ms = (time.perf_counter() - start_time) * 1000
        error_msg = f"Cannot connect to langextract at {LANGEXTRACT_SERVICE_URL}: {e}"
        logger.warning(error_msg)
        return create_empty_langextract_result(error=error_msg)

    except httpx.HTTPError as e:
        processing_time_ms = (time.perf_counter() - start_time) * 1000
        error_msg = f"HTTP error calling langextract: {e}"
        logger.warning(error_msg)
        return create_empty_langextract_result(error=error_msg)

    except Exception as e:
        processing_time_ms = (time.perf_counter() - start_time) * 1000
        error_msg = f"Unexpected error calling langextract: {type(e).__name__}: {e}"
        logger.warning(error_msg, exc_info=True)
        return create_empty_langextract_result(error=error_msg)


def map_semantic_to_intent_boost(
    semantic_result: LangextractResult,
) -> dict[str, float]:
    """Map semantic analysis results to intent confidence boosts.

    Use semantic concepts, domains, and topics to boost intent classification
    confidence. Higher semantic confidence in a domain increases the boost
    for the corresponding intent category.

    This function is pure and never raises exceptions.

    Args:
        semantic_result: Result from enrich_with_semantics().

    Returns:
        Dictionary mapping intent categories to confidence boost amounts.
        Boosts are additive values (typically 0.05-0.20) that can be
        added to intent classification confidence scores.

    Example:
        >>> from omniintelligence.nodes.intent_classifier_compute.handlers import (
        ...     create_empty_langextract_result,
        ...     map_semantic_to_intent_boost,
        ... )
        >>> # Empty result produces no boosts
        >>> empty_result = create_empty_langextract_result()
        >>> boosts = map_semantic_to_intent_boost(empty_result)
        >>> boosts
        {}

    Note:
        Boost values are capped to prevent over-weighting semantic signals.
        Maximum boost per intent category is 0.30.
    """
    boosts: dict[str, float] = {}

    # Process domain indicators
    domain_indicators = semantic_result.get("domain_indicators", [])
    for indicator in domain_indicators:
        indicator_lower = indicator.lower().replace(" ", "_").replace("-", "_")
        intent = DOMAIN_TO_INTENT_MAP.get(indicator_lower)
        if intent:
            boosts[intent] = boosts.get(intent, 0.0) + DOMAIN_MATCH_BOOST

    # Process concepts
    concepts = semantic_result.get("concepts", [])
    for concept in concepts:
        concept_name = concept.get("name", "").lower().replace(" ", "_").replace("-", "_")
        concept_category = concept.get("category", "").lower().replace(" ", "_").replace("-", "_")
        concept_confidence = concept.get("confidence", 0.0)

        # Check concept name against mapping
        intent = DOMAIN_TO_INTENT_MAP.get(concept_name)
        if intent:
            # Scale boost by concept confidence
            boosts[intent] = boosts.get(intent, 0.0) + (
                CONCEPT_MATCH_BOOST * concept_confidence
            )

        # Check concept category against mapping
        intent = DOMAIN_TO_INTENT_MAP.get(concept_category)
        if intent:
            boosts[intent] = boosts.get(intent, 0.0) + (
                CONCEPT_MATCH_BOOST * concept_confidence
            )

    # Process topic weights
    topic_weights = semantic_result.get("topic_weights", {})
    for topic, weight in topic_weights.items():
        topic_normalized = topic.lower().replace(" ", "_").replace("-", "_")
        intent = DOMAIN_TO_INTENT_MAP.get(topic_normalized)
        if intent:
            # Scale boost by topic weight
            boosts[intent] = boosts.get(intent, 0.0) + (
                TOPIC_WEIGHT_MULTIPLIER * weight
            )

    # Process explicit domains
    domains = semantic_result.get("domains", [])
    for domain in domains:
        domain_name = domain.get("name", "").lower().replace(" ", "_").replace("-", "_")
        domain_confidence = domain.get("confidence", 0.0)
        intent = DOMAIN_TO_INTENT_MAP.get(domain_name)
        if intent:
            boosts[intent] = boosts.get(intent, 0.0) + (
                DOMAIN_MATCH_BOOST * domain_confidence
            )

    # Cap boosts to prevent over-weighting
    max_boost = 0.30
    return {intent: min(boost, max_boost) for intent, boost in boosts.items()}


# =============================================================================
# Helper Functions (Pure)
# =============================================================================


def _filter_by_confidence(
    items: list[dict[str, Any]],
    min_confidence: float,
    confidence_key: str = "confidence",
) -> list[dict[str, Any]]:
    """Filter items by confidence threshold.

    Args:
        items: List of items with confidence scores.
        min_confidence: Minimum confidence threshold.
        confidence_key: Key name for the confidence field.

    Returns:
        Filtered list containing only items above threshold.
    """
    if not items:
        return []

    return [
        item
        for item in items
        if item.get(confidence_key, 0.0) >= min_confidence
    ]


__all__ = [
    "LANGEXTRACT_SERVICE_URL",
    "LANGEXTRACT_TIMEOUT_SECONDS",
    "LangextractResult",
    "create_empty_langextract_result",
    "enrich_with_semantics",
    "map_semantic_to_intent_boost",
]
