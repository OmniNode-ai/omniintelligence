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

import re
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import TypedDict

    class ClassificationResultDict(TypedDict, total=False):
        """Result structure from classify_intent function."""

        intent_category: str
        confidence: float
        keywords: list[str]
        all_scores: dict[str, float]
        secondary_intents: list[dict[str, object]]


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
}

# Pre-normalized patterns for performance (computed once at module load)
_NORMALIZED_PATTERNS: dict[str, list[str]] = {
    intent: [kw.lower() for kw in keywords]
    for intent, keywords in INTENT_PATTERNS.items()
}

# Algorithm weights for scoring
_EXACT_MATCH_WEIGHT: float = 15.0  # Weight for exact keyword matches
_PARTIAL_MATCH_WEIGHT: float = 3.0  # Weight for partial/fuzzy matches
_MIN_PATTERN_LENGTH_FOR_PARTIAL: int = 3  # Minimum pattern length for partial matching


# =============================================================================
# Pure Functional Classification Algorithm
# =============================================================================


def classify_intent(
    content: str,
    confidence_threshold: float = 0.5,
    multi_label: bool = False,
    max_intents: int = 5,
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

    Args:
        content: Text to classify. Must be non-empty for meaningful results.
        confidence_threshold: Minimum confidence to return (0.0-1.0).
            Results below this threshold return "unknown" intent.
        multi_label: If True, return all intents above threshold as
            secondary_intents. If False, only return primary intent.
        max_intents: Maximum number of secondary intents to return when
            multi_label is True.

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
    """
    # Step 1: Tokenize and normalize
    tokens = _tokenize(content)

    if not tokens:
        return {
            "intent_category": "unknown",
            "confidence": 0.0,
            "keywords": [],
            "all_scores": {},
        }

    # Step 2: Calculate term frequencies
    tf_scores = _calculate_term_frequency(tokens)

    # Step 3: Score each intent category
    intent_scores: dict[str, float] = {}
    intent_keywords: dict[str, list[str]] = {}

    for intent, patterns in _NORMALIZED_PATTERNS.items():
        score, matched_keywords = _calculate_intent_score(tf_scores, patterns, tokens)
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
) -> tuple[float, list[str]]:
    """Calculate intent score based on pattern matching and TF scores.

    Combines direct pattern matching with term frequency weighting.
    Exact matches are weighted more heavily than partial matches
    to prioritize clear signals.

    Args:
        tf_scores: Term frequency scores for all tokens.
        patterns: Intent-specific keyword patterns (lowercase).
        tokens: Original tokens from the input text.

    Returns:
        Tuple of (score, matched_keywords) where score is the raw
        weighted score and matched_keywords are the tokens that
        contributed to the score.
    """
    score = 0.0
    matched_keywords: list[str] = []

    # Direct pattern matches (heavily weighted by TF)
    for pattern in patterns:
        if pattern in tf_scores:
            score += tf_scores[pattern] * _EXACT_MATCH_WEIGHT
            matched_keywords.append(pattern)

    # Partial matches (fuzzy matching for word variations)
    for token in tokens:
        for pattern in patterns:
            # Only do partial matching for patterns of sufficient length
            if len(pattern) > _MIN_PATTERN_LENGTH_FOR_PARTIAL:
                if pattern in token or token in pattern:
                    # Avoid double-counting exact matches
                    if token not in matched_keywords:
                        score += tf_scores.get(token, 0.0) * _PARTIAL_MATCH_WEIGHT
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
    secondary_intents: list[dict[str, object]] = []
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
# Module Exports
# =============================================================================

__all__ = [
    "INTENT_PATTERNS",
    "classify_intent",
]
