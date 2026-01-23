"""Handler for semantic enrichment (pure computation).

This module provides semantic analysis for intent classification enrichment.
Unlike the original HTTP-based implementation, this is a PURE COMPUTE handler
with no external service dependencies.

Design Principles:
    - Pure computation: No HTTP calls, no external services
    - Deterministic: Same input always produces same output
    - Fast: Pattern matching and keyword analysis
    - Self-contained: All domain knowledge embedded in module

The handler extracts:
    - Domain indicators (api, testing, code_generation, etc.)
    - Concepts with confidence scores
    - Theme classification
    - Topic weights for intent boosting

Usage:
    from omniintelligence.nodes.intent_classifier_compute.handlers import (
        analyze_semantics,
        map_semantic_to_intent_boost,
    )

    # Analyze content semantically
    result = analyze_semantics(
        content="Create a REST API endpoint for user authentication",
        context="api_development",
    )

    # Map results to intent boosts
    boosts = map_semantic_to_intent_boost(result)
    # -> {"code_generation": 0.15, "api_design": 0.10, ...}
"""

from __future__ import annotations

import logging
import re
import time
from collections import Counter
from typing import TYPE_CHECKING, Any, Final, cast

if TYPE_CHECKING:
    from typing import TypedDict

    class SemanticResult(TypedDict, total=False):
        """Result from semantic analysis.

        All fields are populated by pure computation.
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
    SemanticResult = dict


logger = logging.getLogger(__name__)

# =============================================================================
# Domain and Topic Knowledge Base (Embedded)
# =============================================================================

# Domain indicators and their associated keywords
# Each domain maps to keywords that suggest that domain
DOMAIN_KEYWORDS: Final[dict[str, list[str]]] = {
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
        "authentication",
        "authorization",
        "oauth",
        "jwt",
        "token",
        "swagger",
        "openapi",
        "postman",
        "curl",
        "websocket",
        "grpc",
        "rpc",
        "service",
    ],
    "code_generation": [
        "generate",
        "create",
        "implement",
        "build",
        "write",
        "develop",
        "code",
        "function",
        "class",
        "method",
        "module",
        "script",
        "program",
        "application",
        "software",
        "component",
        "feature",
        "logic",
        "algorithm",
    ],
    "testing": [
        "test",
        "unit",
        "integration",
        "e2e",
        "end-to-end",
        "mock",
        "stub",
        "fixture",
        "assert",
        "expect",
        "pytest",
        "jest",
        "mocha",
        "coverage",
        "tdd",
        "bdd",
        "qa",
        "quality",
        "verification",
        "validation",
    ],
    "debugging": [
        "debug",
        "fix",
        "bug",
        "error",
        "issue",
        "problem",
        "crash",
        "exception",
        "traceback",
        "stack",
        "breakpoint",
        "logging",
        "trace",
        "diagnose",
        "troubleshoot",
        "investigate",
        "resolve",
        "patch",
    ],
    "refactoring": [
        "refactor",
        "restructure",
        "reorganize",
        "cleanup",
        "improve",
        "optimize",
        "simplify",
        "extract",
        "rename",
        "move",
        "consolidate",
        "modularize",
        "decouple",
        "abstract",
        "generalize",
        "performance",
    ],
    "documentation": [
        "document",
        "documentation",
        "docs",
        "readme",
        "docstring",
        "comment",
        "explain",
        "describe",
        "guide",
        "tutorial",
        "reference",
        "api-doc",
        "specification",
        "wiki",
        "markdown",
    ],
    "architecture": [
        "architecture",
        "design",
        "pattern",
        "structure",
        "system",
        "component",
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
        "model",
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
        "github-actions",
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
        "authentication",
        "authorization",
        "permission",
        "role",
        "access",
        "ssl",
        "tls",
        "https",
        "sanitize",
        "validate",
    ],
    "analysis": [
        "analyze",
        "analysis",
        "review",
        "examine",
        "inspect",
        "evaluate",
        "assess",
        "audit",
        "profile",
        "metrics",
        "measure",
        "benchmark",
        "compare",
        "statistics",
    ],
    "pattern_learning": [
        "pattern",
        "learn",
        "learning",
        "machine",
        "ml",
        "ai",
        "model",
        "train",
        "training",
        "dataset",
        "feature",
        "prediction",
        "classification",
        "regression",
        "neural",
        "deep",
    ],
    "quality_assessment": [
        "quality",
        "assessment",
        "score",
        "rating",
        "grade",
        "compliance",
        "standard",
        "best-practice",
        "lint",
        "linter",
        "static-analysis",
        "code-review",
        "smell",
        "technical-debt",
    ],
    "semantic_analysis": [
        "semantic",
        "meaning",
        "context",
        "intent",
        "nlp",
        "natural-language",
        "parse",
        "extract",
        "entity",
        "concept",
        "topic",
        "theme",
        "sentiment",
        "classification",
    ],
}

# Theme patterns - broader categories that group related domains
THEME_PATTERNS: Final[dict[str, list[str]]] = {
    "development": ["code_generation", "refactoring", "debugging", "architecture"],
    "quality": ["testing", "quality_assessment", "documentation", "security"],
    "operations": ["devops", "database", "api_design"],
    "intelligence": ["analysis", "pattern_learning", "semantic_analysis"],
}

# Intent category mapping for boost calculation
DOMAIN_TO_INTENT_MAP: Final[dict[str, str]] = {
    # API-related
    "api": "api_design",
    "api_design": "api_design",
    "rest": "api_design",
    "graphql": "api_design",
    "endpoint": "api_design",
    "http": "api_design",
    # Code generation
    "code_generation": "code_generation",
    "programming": "code_generation",
    "software_development": "code_generation",
    "implementation": "code_generation",
    "coding": "code_generation",
    # Testing
    "testing": "testing",
    "test": "testing",
    "unit_test": "testing",
    "integration_test": "testing",
    "quality_assurance": "testing",
    # Documentation
    "documentation": "documentation",
    "docs": "documentation",
    "readme": "documentation",
    "technical_writing": "documentation",
    # Architecture
    "architecture": "architecture",
    "design_pattern": "architecture",
    "system_design": "architecture",
    "infrastructure": "architecture",
    # Database
    "database": "database",
    "sql": "database",
    "nosql": "database",
    "data_modeling": "database",
    # DevOps
    "devops": "devops",
    "ci_cd": "devops",
    "deployment": "devops",
    "kubernetes": "devops",
    "docker": "devops",
    # Security
    "security": "security",
    "authentication": "security",
    "authorization": "security",
    "encryption": "security",
    # Debugging
    "debugging": "debugging",
    "troubleshooting": "debugging",
    "error_handling": "debugging",
    "bug_fix": "debugging",
    # Refactoring
    "refactoring": "refactoring",
    "code_cleanup": "refactoring",
    "optimization": "refactoring",
    # Analysis
    "analysis": "analysis",
    "research": "analysis",
    "investigation": "analysis",
    # Pattern learning (maps to our intent categories)
    "pattern_learning": "pattern_learning",
    "quality_assessment": "quality_assessment",
    "semantic_analysis": "semantic_analysis",
}

# =============================================================================
# Configuration Defaults
# =============================================================================
# These values match the contract.yaml configuration section and can be
# overridden via config injection. The module works standalone with these
# defaults.
#
# See: contract.yaml -> configuration.semantic_analysis
# =============================================================================

# Configuration dictionary with defaults from contract.yaml
# Can be updated at runtime via configure_semantic_analysis()
_SEMANTIC_CONFIG: dict[str, float | int] = {
    # Boost amounts
    "domain_match_boost": 0.10,
    "concept_match_boost": 0.05,
    "topic_weight_multiplier": 0.15,
    "max_boost_cap": 0.30,
    "context_boost": 0.15,
    # Default thresholds
    "default_min_confidence": 0.3,
    # Scoring parameters
    "match_base_initial": 0.15,
    "match_base_max": 0.6,
    "density_bonus_max": 0.2,
    "density_multiplier": 0.3,
    "diversity_bonus_max": 0.2,
    "diversity_multiplier": 0.05,
    "concept_confidence_multiplier": 0.8,
    # Limits
    "max_concepts": 20,
    "max_domain_indicators": 5,
}

def configure_semantic_analysis(
    domain_match_boost: float | None = None,
    concept_match_boost: float | None = None,
    topic_weight_multiplier: float | None = None,
    max_boost_cap: float | None = None,
    context_boost: float | None = None,
    default_min_confidence: float | None = None,
    match_base_initial: float | None = None,
    match_base_max: float | None = None,
    density_bonus_max: float | None = None,
    density_multiplier: float | None = None,
    diversity_bonus_max: float | None = None,
    diversity_multiplier: float | None = None,
    concept_confidence_multiplier: float | None = None,
    max_concepts: int | None = None,
    max_domain_indicators: int | None = None,
) -> None:
    """Configure semantic analysis parameters.

    Updates the module-level configuration dictionary. This allows runtime
    configuration without modifying module constants.

    Args:
        domain_match_boost: Boost for domain indicator matches (default: 0.10).
        concept_match_boost: Boost for concept matches (default: 0.05).
        topic_weight_multiplier: Multiplier for topic weights (default: 0.15).
        max_boost_cap: Maximum total boost per intent (default: 0.30).
        context_boost: Boost when context matches domain (default: 0.15).
        default_min_confidence: Default min confidence threshold (default: 0.3).
        match_base_initial: Initial base for match scoring (default: 0.15).
        match_base_max: Maximum base from matches (default: 0.6).
        density_bonus_max: Maximum density bonus (default: 0.2).
        density_multiplier: Multiplier for density calculation (default: 0.3).
        diversity_bonus_max: Maximum diversity bonus (default: 0.2).
        diversity_multiplier: Multiplier for diversity calculation (default: 0.05).
        concept_confidence_multiplier: Multiplier for concept confidence (default: 0.8).
        max_concepts: Maximum concepts to return (default: 20).
        max_domain_indicators: Maximum domain indicators to return (default: 5).

    Example:
        >>> configure_semantic_analysis(max_boost_cap=0.40, default_min_confidence=0.25)
        >>> _SEMANTIC_CONFIG["max_boost_cap"]
        0.4
    """
    if domain_match_boost is not None:
        _SEMANTIC_CONFIG["domain_match_boost"] = domain_match_boost
    if concept_match_boost is not None:
        _SEMANTIC_CONFIG["concept_match_boost"] = concept_match_boost
    if topic_weight_multiplier is not None:
        _SEMANTIC_CONFIG["topic_weight_multiplier"] = topic_weight_multiplier
    if max_boost_cap is not None:
        _SEMANTIC_CONFIG["max_boost_cap"] = max_boost_cap
    if context_boost is not None:
        _SEMANTIC_CONFIG["context_boost"] = context_boost
    if default_min_confidence is not None:
        _SEMANTIC_CONFIG["default_min_confidence"] = default_min_confidence
    if match_base_initial is not None:
        _SEMANTIC_CONFIG["match_base_initial"] = match_base_initial
    if match_base_max is not None:
        _SEMANTIC_CONFIG["match_base_max"] = match_base_max
    if density_bonus_max is not None:
        _SEMANTIC_CONFIG["density_bonus_max"] = density_bonus_max
    if density_multiplier is not None:
        _SEMANTIC_CONFIG["density_multiplier"] = density_multiplier
    if diversity_bonus_max is not None:
        _SEMANTIC_CONFIG["diversity_bonus_max"] = diversity_bonus_max
    if diversity_multiplier is not None:
        _SEMANTIC_CONFIG["diversity_multiplier"] = diversity_multiplier
    if concept_confidence_multiplier is not None:
        _SEMANTIC_CONFIG["concept_confidence_multiplier"] = concept_confidence_multiplier
    if max_concepts is not None:
        _SEMANTIC_CONFIG["max_concepts"] = max_concepts
    if max_domain_indicators is not None:
        _SEMANTIC_CONFIG["max_domain_indicators"] = max_domain_indicators


def get_semantic_config() -> dict[str, float | int]:
    """Get a copy of the current semantic analysis configuration.

    Returns:
        Dictionary with current configuration values.
    """
    return dict(_SEMANTIC_CONFIG)


# =============================================================================
# Factory Functions
# =============================================================================


def create_empty_semantic_result(error: str | None = None) -> SemanticResult:
    """Create an empty semantic result.

    Use this for error cases or empty input.

    Args:
        error: Optional error message.

    Returns:
        SemanticResult with all fields empty/default.

    Example:
        >>> result = create_empty_semantic_result()
        >>> result["concepts"]
        []
    """
    return SemanticResult(
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
# Core Analysis Functions (Pure Computation)
# =============================================================================


def analyze_semantics(
    content: str,
    context: str | None = None,
    min_confidence: float | None = None,
) -> SemanticResult:
    """Analyze content semantically for domain, concepts, and themes.

    This is a PURE FUNCTION with no external dependencies.
    Uses keyword matching and pattern analysis to extract semantic information.

    Configuration:
        This function uses parameters from _SEMANTIC_CONFIG. Defaults
        can be modified via configure_semantic_analysis() or by updating
        the config dict directly. See contract.yaml -> configuration.semantic_analysis.

    Args:
        content: Text content to analyze.
        context: Optional context hint (e.g., "api_development", "testing").
        min_confidence: Minimum confidence threshold for results (0.0-1.0).
            Defaults to config value (0.3).

    Returns:
        SemanticResult with:
        - concepts: Extracted concepts with confidence
        - themes: Identified themes
        - domains: Detected domains with confidence
        - domain_indicators: Raw domain indicator strings
        - topic_weights: Topic -> weight mapping
        - processing_time_ms: Processing time

    Example:
        >>> result = analyze_semantics("Create a REST API for users")
        >>> "api_design" in result["domain_indicators"]
        True
    """
    # Apply config defaults for None parameters
    if min_confidence is None:
        min_confidence = float(_SEMANTIC_CONFIG["default_min_confidence"])

    # Read config values used in this function
    context_boost = float(_SEMANTIC_CONFIG["context_boost"])
    max_domain_indicators = int(_SEMANTIC_CONFIG["max_domain_indicators"])

    if not content or not content.strip():
        logger.debug("Empty content provided, returning empty result")
        return create_empty_semantic_result()

    start_time = time.perf_counter()

    try:
        # Normalize content for analysis
        content_lower = content.lower()
        tokens = _tokenize(content_lower)

        # Detect domains
        domain_scores = _detect_domains(tokens, content_lower)

        # Apply context boost if provided
        if context:
            context_normalized = context.lower().replace("-", "_").replace(" ", "_")
            if context_normalized in domain_scores:
                domain_scores[context_normalized] = min(
                    1.0, domain_scores[context_normalized] + context_boost
                )

        # Filter by confidence
        domains = [
            {"name": domain, "confidence": score}
            for domain, score in domain_scores.items()
            if score >= min_confidence
        ]

        # Extract domain indicators (top domains)
        # Note: Explicit casts for mypy - dict values are Any but runtime types are correct
        domain_indicators: list[str] = [str(d["name"]) for d in sorted(
            domains, key=lambda x: cast(float, x["confidence"]), reverse=True
        )[:max_domain_indicators]]

        # Build concepts from detected keywords
        concepts = _extract_concepts(tokens, domain_scores, min_confidence)

        # Detect themes
        themes = _detect_themes(domain_indicators)

        # Calculate topic weights
        # Note: Explicit casts for mypy - dict values are Any but runtime types are correct
        topic_weights: dict[str, float] = {
            str(d["name"]): cast(float, d["confidence"]) for d in domains
        }

        processing_time_ms = (time.perf_counter() - start_time) * 1000

        logger.debug(
            f"Semantic analysis completed in {processing_time_ms:.2f}ms: "
            f"{len(concepts)} concepts, {len(themes)} themes, "
            f"{len(domains)} domains"
        )

        return SemanticResult(
            concepts=concepts,
            themes=themes,
            domains=domains,
            patterns=[],  # Patterns require more complex analysis
            domain_indicators=domain_indicators,
            topic_weights=topic_weights,
            processing_time_ms=round(processing_time_ms, 2),
            error=None,
        )

    except Exception as e:
        processing_time_ms = (time.perf_counter() - start_time) * 1000
        error_msg = f"Semantic analysis error: {type(e).__name__}: {e}"
        logger.warning(error_msg, exc_info=True)
        return create_empty_semantic_result(error=error_msg)


def map_semantic_to_intent_boost(
    semantic_result: SemanticResult,
) -> dict[str, float]:
    """Map semantic analysis results to intent confidence boosts.

    Uses domain indicators, concepts, and topic weights to calculate
    additive confidence boosts for intent categories.

    Configuration:
        Uses parameters from _SEMANTIC_CONFIG:
        - domain_match_boost: Boost for domain matches (default: 0.10)
        - concept_match_boost: Boost for concept matches (default: 0.05)
        - topic_weight_multiplier: Multiplier for topic weights (default: 0.15)
        - max_boost_cap: Maximum boost per category (default: 0.30)

    Args:
        semantic_result: Result from analyze_semantics().

    Returns:
        Dictionary mapping intent categories to confidence boost amounts.
        Boosts are capped at max_boost_cap per category.

    Example:
        >>> result = analyze_semantics("Write unit tests for the API")
        >>> boosts = map_semantic_to_intent_boost(result)
        >>> "testing" in boosts or "api_design" in boosts
        True
    """
    # Read boost amounts from config
    domain_boost = float(_SEMANTIC_CONFIG["domain_match_boost"])
    concept_boost = float(_SEMANTIC_CONFIG["concept_match_boost"])
    topic_multiplier = float(_SEMANTIC_CONFIG["topic_weight_multiplier"])
    max_boost_cap = float(_SEMANTIC_CONFIG["max_boost_cap"])

    boosts: dict[str, float] = {}

    # Process domain indicators
    domain_indicators = semantic_result.get("domain_indicators", [])
    for indicator in domain_indicators:
        indicator_lower = indicator.lower().replace(" ", "_").replace("-", "_")
        intent = DOMAIN_TO_INTENT_MAP.get(indicator_lower)
        if intent:
            boosts[intent] = boosts.get(intent, 0.0) + domain_boost

    # Process concepts
    concepts = semantic_result.get("concepts", [])
    for concept in concepts:
        concept_name = concept.get("name", "").lower().replace(" ", "_").replace("-", "_")
        concept_category = concept.get("category", "").lower().replace(" ", "_").replace("-", "_")
        concept_confidence = concept.get("confidence", 0.0)

        # Check concept name
        intent = DOMAIN_TO_INTENT_MAP.get(concept_name)
        if intent:
            boosts[intent] = boosts.get(intent, 0.0) + (
                concept_boost * concept_confidence
            )

        # Check concept category
        intent = DOMAIN_TO_INTENT_MAP.get(concept_category)
        if intent:
            boosts[intent] = boosts.get(intent, 0.0) + (
                concept_boost * concept_confidence
            )

    # Process topic weights
    topic_weights = semantic_result.get("topic_weights", {})
    for topic, weight in topic_weights.items():
        topic_normalized = topic.lower().replace(" ", "_").replace("-", "_")
        intent = DOMAIN_TO_INTENT_MAP.get(topic_normalized)
        if intent:
            boosts[intent] = boosts.get(intent, 0.0) + (
                topic_multiplier * weight
            )

    # Process explicit domains
    domains = semantic_result.get("domains", [])
    for domain in domains:
        domain_name = domain.get("name", "").lower().replace(" ", "_").replace("-", "_")
        domain_confidence = domain.get("confidence", 0.0)
        intent = DOMAIN_TO_INTENT_MAP.get(domain_name)
        if intent:
            boosts[intent] = boosts.get(intent, 0.0) + (
                domain_boost * domain_confidence
            )

    # Cap boosts at maximum
    return {intent: min(boost, max_boost_cap) for intent, boost in boosts.items()}


# =============================================================================
# Helper Functions (Pure)
# =============================================================================


def _tokenize(text: str) -> list[str]:
    """Tokenize text into words.

    Args:
        text: Text to tokenize (should be lowercase).

    Returns:
        List of word tokens.
    """
    # Split on non-alphanumeric characters, keep hyphenated words
    words = re.findall(r'\b[\w-]+\b', text)
    return [w for w in words if len(w) > 1]


def _detect_domains(tokens: list[str], content_lower: str) -> dict[str, float]:
    """Detect domains from tokens and content.

    Configuration:
        Uses parameters from _SEMANTIC_CONFIG (scoring section):
        - match_base_initial: Initial base score (default: 0.15)
        - match_base_max: Maximum base score (default: 0.6)
        - density_bonus_max: Maximum density bonus (default: 0.2)
        - density_multiplier: Density calculation multiplier (default: 0.3)
        - diversity_bonus_max: Maximum diversity bonus (default: 0.2)
        - diversity_multiplier: Diversity calculation multiplier (default: 0.05)

    Args:
        tokens: List of word tokens.
        content_lower: Lowercase content string.

    Returns:
        Dictionary of domain -> confidence score.
    """
    # Read scoring parameters from config
    match_base_initial = float(_SEMANTIC_CONFIG["match_base_initial"])
    match_base_max = float(_SEMANTIC_CONFIG["match_base_max"])
    density_bonus_max = float(_SEMANTIC_CONFIG["density_bonus_max"])
    density_multiplier = float(_SEMANTIC_CONFIG["density_multiplier"])
    diversity_bonus_max = float(_SEMANTIC_CONFIG["diversity_bonus_max"])
    diversity_multiplier = float(_SEMANTIC_CONFIG["diversity_multiplier"])

    domain_scores: dict[str, float] = {}
    token_set = set(tokens)
    token_counter = Counter(tokens)
    total_tokens = len(tokens) if tokens else 1

    for domain, keywords in DOMAIN_KEYWORDS.items():
        # Count keyword matches
        matches = 0
        matched_keywords: list[str] = []

        for keyword in keywords:
            keyword_lower = keyword.lower()

            # Exact token match
            if keyword_lower in token_set:
                matches += token_counter[keyword_lower]
                matched_keywords.append(keyword_lower)

            # Partial match for compound keywords
            elif "-" in keyword_lower or "_" in keyword_lower:
                # Check if keyword appears in content
                if keyword_lower.replace("-", " ") in content_lower:
                    matches += 1
                    matched_keywords.append(keyword_lower)
                elif keyword_lower.replace("_", " ") in content_lower:
                    matches += 1
                    matched_keywords.append(keyword_lower)

        if matches > 0:
            # Calculate confidence based on:
            # 1. Absolute match count (strong signal even for short content)
            # 2. Match density (ratio of matches to tokens)
            # 3. Keyword diversity (number of unique keywords matched)

            # Base confidence from absolute matches
            # Formula: match_base = min(max, initial + (matches * initial))
            match_base = min(
                match_base_max,
                match_base_initial + (len(matched_keywords) * match_base_initial),
            )

            # Bonus for high match density
            match_ratio = matches / total_tokens
            density_bonus = min(density_bonus_max, match_ratio * density_multiplier)

            # Bonus for multiple unique keywords (strong domain signal)
            diversity_bonus = min(
                diversity_bonus_max, len(matched_keywords) * diversity_multiplier
            )

            confidence = min(1.0, match_base + density_bonus + diversity_bonus)

            domain_scores[domain] = round(confidence, 3)

    return domain_scores


def _extract_concepts(
    tokens: list[str],
    domain_scores: dict[str, float],
    min_confidence: float,
) -> list[dict[str, Any]]:
    """Extract concepts from tokens based on domain analysis.

    Configuration:
        Uses parameters from _SEMANTIC_CONFIG:
        - concept_confidence_multiplier: Multiplier for concept confidence (default: 0.8)
        - max_concepts: Maximum concepts to return (default: 20)

    Args:
        tokens: List of word tokens.
        domain_scores: Domain confidence scores.
        min_confidence: Minimum confidence threshold.

    Returns:
        List of concept dictionaries.
    """
    # Read config values
    confidence_multiplier = float(_SEMANTIC_CONFIG["concept_confidence_multiplier"])
    max_concepts = int(_SEMANTIC_CONFIG["max_concepts"])

    concepts = []
    seen_concepts = set()

    # Find keywords that match domain patterns
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if domain not in domain_scores:
            continue

        domain_confidence = domain_scores[domain]
        if domain_confidence < min_confidence:
            continue

        keyword_set = set(k.lower() for k in keywords)
        for token in tokens:
            if token in keyword_set and token not in seen_concepts:
                seen_concepts.add(token)
                concepts.append({
                    "name": token,
                    "confidence": round(domain_confidence * confidence_multiplier, 3),
                    "category": domain,
                })

    # Sort by confidence
    # Note: Explicit cast for mypy - dict values are Any but runtime types are correct
    concepts.sort(key=lambda x: cast(float, x["confidence"]), reverse=True)

    # Limit to top concepts
    return concepts[:max_concepts]


def _detect_themes(domain_indicators: list[str]) -> list[dict[str, Any]]:
    """Detect themes from domain indicators.

    Args:
        domain_indicators: List of detected domain names.

    Returns:
        List of theme dictionaries.
    """
    themes = []
    domain_set = set(domain_indicators)

    for theme, theme_domains in THEME_PATTERNS.items():
        # Count how many theme domains are present
        matching = domain_set.intersection(theme_domains)
        if matching:
            coverage = len(matching) / len(theme_domains)
            themes.append({
                "name": theme,
                "weight": round(coverage, 3),
                "related_domains": list(matching),
            })

    # Sort by weight
    # Note: Explicit cast for mypy - dict values are Any but runtime types are correct
    themes.sort(key=lambda x: cast(float, x["weight"]), reverse=True)
    return themes


__all__ = [
    # Core API
    "SemanticResult",
    "analyze_semantics",
    "create_empty_semantic_result",
    "map_semantic_to_intent_boost",
    # Configuration
    "configure_semantic_analysis",
    "get_semantic_config",
]
