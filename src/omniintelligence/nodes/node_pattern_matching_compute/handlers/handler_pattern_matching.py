"""Pure pattern matching handler functions.

This module provides pure functions for matching code against patterns.
Handlers implement the computation logic following the ONEX "pure shell pattern"
where nodes delegate to side-effect-free handler functions.

Matching Algorithms:
    - keyword_overlap: Score based on shared keywords between code and pattern
    - regex_match: Match pattern signature as regex/substring against code

Operation Routing:
    - "match": Uses keyword_overlap (best for categorical matching)
    - "similarity": Uses keyword_overlap with lower threshold
    - "classify": Uses keyword_overlap (categorization)
    - "validate": Uses regex_match (structural validation)

Usage:
    from omniintelligence.nodes.node_pattern_matching_compute.handlers import (
        match_patterns,
        PatternRecord,
        PatternMatchingHandlerResult,
    )

    patterns: list[PatternRecord] = [...]
    result = match_patterns(
        code_snippet="def foo(): return None",
        patterns=patterns,
        min_confidence=0.5,
        max_results=10,
        operation="match",
    )
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Final, Literal

from omniintelligence.nodes.node_pattern_matching_compute.handlers.exceptions import (
    PatternMatchingValidationError,
)
from omniintelligence.nodes.node_pattern_matching_compute.handlers.protocols import (
    PatternMatchDetail,
    PatternMatchingHandlerResult,
    PatternRecord,
    create_empty_handler_result,
)

# Algorithm version for traceability
ALGORITHM_VERSION: Final[str] = "1.0.0"

# Supported operations
PatternOperation = Literal["match", "similarity", "classify", "validate"]


def match_patterns(
    code_snippet: str,
    patterns: Sequence[PatternRecord],
    *,
    min_confidence: float = 0.5,
    max_results: int = 10,
    operation: PatternOperation = "match",
    language: str | None = None,
    pattern_categories: Sequence[str] | None = None,
) -> PatternMatchingHandlerResult:
    """Match code against a pattern library.

    Pure function that implements pattern matching algorithms. The operation
    parameter determines which algorithm is used.

    Algorithm Routing:
        - match: keyword_overlap (categorical matching)
        - similarity: keyword_overlap with looser threshold
        - classify: keyword_overlap (for categorization)
        - validate: regex_match (structural validation)

    Args:
        code_snippet: The code to match against patterns.
        patterns: Sequence of pattern records to match against.
        min_confidence: Minimum confidence threshold (0.0-1.0).
        max_results: Maximum number of matches to return.
        operation: Type of matching operation ("match", "similarity", "classify", "validate").
        language: Optional language hint for better matching.
        pattern_categories: Optional category filter (empty = all categories).

    Returns:
        PatternMatchingHandlerResult with matches sorted by confidence (descending).

    Raises:
        PatternMatchingValidationError: If input validation fails.
        PatternMatchingComputeError: If matching computation fails.
    """
    # Validate inputs
    _validate_inputs(code_snippet, min_confidence, max_results)

    # Handle empty pattern library
    if not patterns:
        return create_empty_handler_result(min_confidence)

    # Filter patterns by category if specified
    filtered_patterns = _filter_by_category(patterns, pattern_categories)

    # Route to appropriate algorithm based on operation
    algorithm, algorithm_name = _get_algorithm_for_operation(operation)

    # Match patterns
    matches: list[PatternMatchDetail] = []
    patterns_filtered = 0

    for pattern in filtered_patterns:
        try:
            confidence = algorithm(code_snippet, pattern, language)
        except Exception as e:
            # Individual pattern failures don't fail the entire operation
            # Log and skip (in production, this would be logged)
            continue

        if confidence >= min_confidence:
            matches.append(
                _create_match_detail(pattern, confidence, algorithm_name)
            )
        else:
            patterns_filtered += 1

    # Sort by confidence (descending) and limit results
    matches.sort(key=lambda m: m["confidence"], reverse=True)
    matches = matches[:max_results]

    return PatternMatchingHandlerResult(
        success=True,
        matches=matches,
        patterns_analyzed=len(filtered_patterns),
        patterns_matched=len(matches),
        patterns_filtered=patterns_filtered,
        threshold_used=min_confidence,
        algorithm_version=ALGORITHM_VERSION,
    )


def _validate_inputs(
    code_snippet: str,
    min_confidence: float,
    max_results: int,
) -> None:
    """Validate matching inputs.

    Raises:
        PatternMatchingValidationError: If validation fails.
    """
    if not code_snippet or not code_snippet.strip():
        raise PatternMatchingValidationError("Code snippet cannot be empty")

    if not 0.0 <= min_confidence <= 1.0:
        raise PatternMatchingValidationError(
            f"min_confidence must be between 0.0 and 1.0, got {min_confidence}"
        )

    if max_results < 1:
        raise PatternMatchingValidationError(
            f"max_results must be at least 1, got {max_results}"
        )


def _filter_by_category(
    patterns: Sequence[PatternRecord],
    categories: Sequence[str] | None,
) -> list[PatternRecord]:
    """Filter patterns by category.

    Args:
        patterns: All patterns to filter.
        categories: Categories to include (None or empty = all).

    Returns:
        Filtered list of patterns.
    """
    if not categories:
        return list(patterns)

    category_set = set(categories)
    return [
        p for p in patterns
        if p.get("category", "") in category_set
    ]


def _get_algorithm_for_operation(
    operation: PatternOperation,
) -> tuple[callable, Literal["keyword_overlap", "regex_match", "semantic"]]:
    """Get the appropriate matching algorithm for an operation.

    Args:
        operation: The matching operation type.

    Returns:
        Tuple of (algorithm_function, algorithm_name).
    """
    if operation in ("match", "similarity", "classify"):
        return _keyword_overlap_score, "keyword_overlap"
    elif operation == "validate":
        return _regex_match_score, "regex_match"
    else:
        # Default to keyword overlap
        return _keyword_overlap_score, "keyword_overlap"


def _keyword_overlap_score(
    code_snippet: str,
    pattern: PatternRecord,
    _language: str | None = None,
) -> float:
    """Compute keyword overlap score between code and pattern.

    This algorithm extracts keywords from the code snippet and computes
    the Jaccard similarity with the pattern's keywords.

    Args:
        code_snippet: The code to analyze.
        pattern: The pattern to match against.
        _language: Language hint (reserved for future language-specific matching).

    Returns:
        Confidence score between 0.0 and 1.0.
    """
    # Extract keywords from code
    code_keywords = _extract_keywords(code_snippet)

    # Get pattern keywords
    pattern_keywords = set(pattern.get("keywords", []))

    # Also extract keywords from signature if no explicit keywords
    if not pattern_keywords:
        pattern_keywords = _extract_keywords(pattern.get("signature", ""))

    # Compute Jaccard similarity
    if not code_keywords or not pattern_keywords:
        return 0.0

    intersection = code_keywords & pattern_keywords
    union = code_keywords | pattern_keywords

    if not union:
        return 0.0

    return len(intersection) / len(union)


def _regex_match_score(
    code_snippet: str,
    pattern: PatternRecord,
    _language: str | None = None,
) -> float:
    """Compute regex/substring match score.

    Attempts to match the pattern signature against the code:
    1. First tries as regex
    2. Falls back to substring match if regex invalid

    Args:
        code_snippet: The code to analyze.
        pattern: The pattern to match against.
        _language: Language hint (reserved for future language-specific matching).

    Returns:
        Confidence score: 1.0 for regex match, 0.8 for substring, 0.0 for no match.
    """
    signature = pattern.get("signature", "")
    if not signature:
        return 0.0

    # Try regex match first
    try:
        if re.search(signature, code_snippet, re.MULTILINE | re.DOTALL):
            return 1.0
    except re.error:
        # Invalid regex, fall through to substring match
        pass

    # Try substring match
    if signature.lower() in code_snippet.lower():
        return 0.8

    return 0.0


def _extract_keywords(text: str) -> set[str]:
    """Extract keywords from text for matching.

    Extracts meaningful identifiers and keywords from code/text.
    Filters out common noise words and very short tokens.

    Args:
        text: The text to extract keywords from.

    Returns:
        Set of normalized keywords.
    """
    # Common Python keywords and noise words to filter out
    noise_words = {
        "def", "class", "return", "if", "else", "elif", "for", "while",
        "try", "except", "finally", "with", "as", "import", "from",
        "in", "is", "not", "and", "or", "none", "true", "false",
        "self", "cls", "args", "kwargs", "the", "a", "an", "of", "to",
        "pass", "raise", "yield", "async", "await", "lambda",
    }

    # Extract word-like tokens
    tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text)

    # Normalize and filter
    keywords = set()
    for token in tokens:
        normalized = token.lower()
        # Filter noise words and very short tokens
        if normalized not in noise_words and len(normalized) > 2:
            keywords.add(normalized)

    return keywords


def _create_match_detail(
    pattern: PatternRecord,
    confidence: float,
    algorithm: Literal["keyword_overlap", "regex_match", "semantic"],
) -> PatternMatchDetail:
    """Create a PatternMatchDetail from a matched pattern.

    Args:
        pattern: The matched pattern record.
        confidence: The computed confidence score.
        algorithm: The algorithm that produced this match.

    Returns:
        PatternMatchDetail with all fields populated.
    """
    # Create human-readable name from signature (first 50 chars)
    signature = pattern.get("signature", "")
    pattern_name = signature[:50] + "..." if len(signature) > 50 else signature

    # Generate match reason based on algorithm
    if algorithm == "keyword_overlap":
        reason = "Keyword overlap with pattern vocabulary"
    elif algorithm == "regex_match":
        reason = "Pattern signature matches code structure"
    else:
        reason = "Semantic similarity detected"

    return PatternMatchDetail(
        pattern_id=pattern.get("pattern_id", "unknown"),
        pattern_name=pattern_name or pattern.get("domain", "unknown"),
        confidence=confidence,
        category=pattern.get("category", "uncategorized"),
        match_reason=reason,
        algorithm_used=algorithm,
    )


__all__ = [
    "ALGORITHM_VERSION",
    "PatternOperation",
    "match_patterns",
]
