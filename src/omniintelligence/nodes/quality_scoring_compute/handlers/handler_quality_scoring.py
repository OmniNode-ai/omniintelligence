"""Handler for quality scoring computation.

This module provides pure functions for scoring code quality based on
ONEX-focused dimensions. All functions are side-effect-free and suitable
for use in compute nodes.

The scoring system evaluates Python code across five dimensions:
    - patterns: ONEX pattern adherence (frozen models, TypedDict, Protocol)
    - type_coverage: Type annotation completeness
    - maintainability: Code structure quality (function length, naming)
    - complexity: Cyclomatic complexity approximation
    - documentation: Docstring and comment coverage

Default weights are ONEX-focused, prioritizing pattern adherence and type coverage.

Example:
    from omniintelligence.nodes.quality_scoring_compute.handlers import (
        score_code_quality,
    )

    result = score_code_quality(
        content="def foo(x: int) -> int: return x * 2",
        language="python",
    )
    print(f"Quality score: {result['quality_score']}")
"""

from __future__ import annotations

import ast
import re
from typing import Final

from omniintelligence.nodes.quality_scoring_compute.handlers.exceptions import (
    QualityScoringComputeError,
    QualityScoringValidationError,
)
from omniintelligence.nodes.quality_scoring_compute.handlers.protocols import (
    QualityScoringResult,
)

# =============================================================================
# Constants
# =============================================================================

ANALYSIS_VERSION: Final[str] = "1.0.0"

DEFAULT_WEIGHTS: Final[dict[str, float]] = {
    "patterns": 0.30,
    "type_coverage": 0.25,
    "maintainability": 0.20,
    "complexity": 0.15,
    "documentation": 0.10,
}

# ONEX patterns to detect (positive indicators)
ONEX_POSITIVE_PATTERNS: Final[list[str]] = [
    r"frozen\s*=\s*True",
    r'extra\s*=\s*["\']forbid["\']',
    r"\bClassVar\b",
    r"\bTypedDict\b",
    r"\bProtocol\b",
    r"\bField\s*\(",
    r"@field_validator",
    r"@model_validator",
    r"model_config\s*=",
    r"\bFinal\b",
]

# Anti-patterns to detect (negative indicators)
ONEX_ANTI_PATTERNS: Final[list[str]] = [
    r"dict\s*\[\s*str\s*,\s*Any\s*\]",
    r"\*\*kwargs",
    r":\s*Any\s*[,\)]",
    r"=\s*\[\s*\]",  # Mutable default: = []
    r"=\s*\{\s*\}",  # Mutable default: = {}
]

# Pre-compiled patterns for performance
_COMPILED_POSITIVE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = tuple(
    re.compile(p) for p in ONEX_POSITIVE_PATTERNS
)

_COMPILED_ANTI_PATTERNS: Final[tuple[re.Pattern[str], ...]] = tuple(
    re.compile(p) for p in ONEX_ANTI_PATTERNS
)

# Pre-compiled handler pattern (private pure functions)
_COMPILED_HANDLER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"def\s+_[a-z_]+\s*\([^)]*\)\s*->"
)

# Maximum reasonable values for heuristics
MAX_FUNCTION_LENGTH: Final[int] = 50
MAX_NESTING_DEPTH: Final[int] = 4
IDEAL_DOCSTRING_RATIO: Final[float] = 0.15

# Supported languages for full analysis
SUPPORTED_LANGUAGES: Final[frozenset[str]] = frozenset({"python", "py"})

# Pattern scoring constants
PATTERN_SCORE_DIVISOR: Final[int] = 5  # Max patterns for full score
ANTI_PATTERN_PENALTY: Final[float] = 0.1  # Penalty per anti-pattern
MAX_ANTI_PATTERN_PENALTY: Final[float] = 0.5  # Maximum total penalty
PATTERN_BASELINE_SCORE: Final[float] = 0.3  # Baseline added to pattern score

# Type coverage constants
NO_FUNCTIONS_NEUTRAL_SCORE: Final[float] = 0.5  # Score when no functions to type

# Maintainability constants
IDEAL_FUNCTION_LENGTH: Final[int] = 20  # Ideal max function length (lines)
FUNCTION_LENGTH_SCORING_RANGE: Final[int] = 80  # Range for scoring (20 to 100 lines)
NO_ITEMS_MAINTAINABILITY_SCORE: Final[float] = 0.7  # Score when no functions/classes

# Complexity constants
MAX_RAW_COMPLEXITY: Final[int] = 20  # Max raw complexity for scoring
MAX_AVG_COMPLEXITY: Final[int] = 10  # Max average complexity per function

# Baseline scores
SYNTAX_ERROR_BASELINE: Final[float] = 0.3  # Score when syntax errors present
UNSUPPORTED_LANGUAGE_BASELINE: Final[float] = 0.5  # Score for unsupported languages


# =============================================================================
# Main Handler Function
# =============================================================================


def score_code_quality(
    content: str,
    language: str,
    weights: dict[str, float] | None = None,
    onex_threshold: float = 0.7,
) -> QualityScoringResult:
    """Score code quality based on multiple dimensions.

    This is the main entry point for quality scoring. It computes scores
    across five dimensions and aggregates them using configurable weights.

    Args:
        content: Source code content to analyze.
        language: Programming language (e.g., "python"). Non-Python languages
            receive baseline scores with an unsupported_language recommendation.
        weights: Optional custom weights for each dimension. Must sum to ~1.0.
            Defaults to ONEX-focused weights if None.
        onex_threshold: Score threshold for ONEX compliance (default 0.7).
            If quality_score >= onex_threshold, onex_compliant is True.

    Returns:
        QualityScoringResult with all scoring data.

    Raises:
        QualityScoringValidationError: If content is empty or weights are invalid.
        QualityScoringComputeError: If scoring computation fails unexpectedly.

    Example:
        >>> result = score_code_quality(
        ...     content="class Foo(BaseModel):\\n    x: int",
        ...     language="python",
        ... )
        >>> result["success"]
        True
        >>> 0.0 <= result["quality_score"] <= 1.0
        True
    """
    # Validate inputs
    if not content or not content.strip():
        raise QualityScoringValidationError("Content cannot be empty")

    effective_weights = weights if weights is not None else DEFAULT_WEIGHTS.copy()
    _validate_weights(effective_weights)

    normalized_language = language.lower().strip()

    # Check if language is supported for full analysis
    if normalized_language not in SUPPORTED_LANGUAGES:
        return _create_unsupported_language_result(normalized_language, onex_threshold)

    try:
        # Compute dimension scores
        dimensions = _compute_all_dimensions(content)

        # Calculate weighted aggregate
        quality_score = _compute_weighted_score(dimensions, effective_weights)

        # Determine ONEX compliance
        onex_compliant = quality_score >= onex_threshold

        # Generate recommendations based on low scores
        recommendations = _generate_recommendations(dimensions)

        return QualityScoringResult(
            success=True,
            quality_score=round(quality_score, 4),
            dimensions={k: round(v, 4) for k, v in dimensions.items()},
            onex_compliant=onex_compliant,
            recommendations=recommendations,
            source_language=normalized_language,
            analysis_version=ANALYSIS_VERSION,
        )

    except SyntaxError as e:
        # Code has syntax errors - return partial result
        return _create_syntax_error_result(normalized_language, str(e))

    except Exception as e:
        raise QualityScoringComputeError(
            f"Unexpected error during quality scoring: {e}"
        ) from e


# =============================================================================
# Dimension Computation Functions (Pure)
# =============================================================================


def _compute_all_dimensions(content: str) -> dict[str, float]:
    """Compute all quality dimension scores.

    Each dimension function handles syntax errors gracefully by returning
    a baseline score of SYNTAX_ERROR_BASELINE, so this function will not
    raise SyntaxError.

    Args:
        content: Python source code to analyze.

    Returns:
        Dictionary mapping dimension names to scores (0.0-1.0).
    """
    return {
        "patterns": _compute_patterns_score(content),
        "type_coverage": _compute_type_coverage_score(content),
        "maintainability": _compute_maintainability_score(content),
        "complexity": _compute_complexity_score(content),
        "documentation": _compute_documentation_score(content),
    }


def _compute_patterns_score(content: str) -> float:
    """Compute ONEX pattern adherence score.

    Checks for positive ONEX patterns (frozen models, TypedDict, etc.)
    and penalizes anti-patterns (dict[str, Any], **kwargs, etc.).

    Args:
        content: Python source code to analyze.

    Returns:
        Score from 0.0 (no patterns/many anti-patterns) to 1.0 (excellent).
    """
    # Count positive pattern matches (using pre-compiled patterns)
    positive_count = 0
    for pattern in _COMPILED_POSITIVE_PATTERNS:
        if pattern.search(content):
            positive_count += 1

    # Count anti-pattern matches (using pre-compiled patterns)
    anti_count = 0
    for pattern in _COMPILED_ANTI_PATTERNS:
        matches = pattern.findall(content)
        anti_count += len(matches)

    # Check for handler pattern (private pure functions)
    handler_pattern_matches = len(_COMPILED_HANDLER_PATTERN.findall(content))
    if handler_pattern_matches >= 2:
        positive_count += 1

    # Score calculation:
    # - Base score from positive patterns (max 1.0 at PATTERN_SCORE_DIVISOR+ patterns)
    # - Penalty from anti-patterns (ANTI_PATTERN_PENALTY per anti-pattern, max MAX_ANTI_PATTERN_PENALTY)
    base_score = min(positive_count / PATTERN_SCORE_DIVISOR, 1.0)
    penalty = min(anti_count * ANTI_PATTERN_PENALTY, MAX_ANTI_PATTERN_PENALTY)

    return max(0.0, min(1.0, base_score - penalty + PATTERN_BASELINE_SCORE))


def _compute_type_coverage_score(content: str) -> float:
    """Compute type annotation coverage score.

    Analyzes AST to count typed vs untyped function parameters and returns.
    If the content has syntax errors, returns SYNTAX_ERROR_BASELINE.

    Args:
        content: Python source code to analyze.

    Returns:
        Score from 0.0 (no type hints) to 1.0 (fully typed).
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        # Syntax errors are handled upstream, return baseline
        return SYNTAX_ERROR_BASELINE

    typed_count = 0
    untyped_count = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            # Check return annotation
            if node.returns:
                typed_count += 1
            else:
                untyped_count += 1

            # Check argument annotations
            for arg in node.args.args:
                if arg.arg == "self" or arg.arg == "cls":
                    continue  # Skip self/cls
                if arg.annotation:
                    typed_count += 1
                else:
                    untyped_count += 1

            # Check kwonly args
            for arg in node.args.kwonlyargs:
                if arg.annotation:
                    typed_count += 1
                else:
                    untyped_count += 1

    total = typed_count + untyped_count
    if total == 0:
        return NO_FUNCTIONS_NEUTRAL_SCORE  # No functions to type, neutral score

    return typed_count / total


def _compute_maintainability_score(content: str) -> float:
    """Compute code maintainability score.

    Evaluates function length, naming conventions, and overall structure.
    If the content has syntax errors, returns SYNTAX_ERROR_BASELINE.

    Args:
        content: Python source code to analyze.

    Returns:
        Score from 0.0 (poor maintainability) to 1.0 (excellent).
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return SYNTAX_ERROR_BASELINE

    scores: list[float] = []

    # Check function lengths
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            # Count lines in function
            if node.end_lineno and node.lineno:
                func_length = node.end_lineno - node.lineno + 1
                # Score: 1.0 for <= IDEAL_FUNCTION_LENGTH lines, decreasing to 0.0 at 100+ lines
                length_score = max(
                    0.0,
                    min(
                        1.0,
                        1.0
                        - (func_length - IDEAL_FUNCTION_LENGTH)
                        / FUNCTION_LENGTH_SCORING_RANGE,
                    ),
                )
                scores.append(length_score)

            # Check naming convention (snake_case for functions)
            if re.match(r"^[a-z_][a-z0-9_]*$", node.name):
                scores.append(1.0)
            elif node.name.startswith("_"):  # Private is ok
                scores.append(0.9)
            else:
                scores.append(0.5)

    # Check class naming (PascalCase)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if re.match(r"^[A-Z][a-zA-Z0-9]*$", node.name):
                scores.append(1.0)
            else:
                scores.append(0.6)

    if not scores:
        return NO_ITEMS_MAINTAINABILITY_SCORE  # No functions/classes, moderate score

    # Clamp to [0.0, 1.0] for safety
    return max(0.0, min(1.0, sum(scores) / len(scores)))


def _compute_complexity_score(content: str) -> float:
    """Compute complexity score (inverted - lower complexity is better).

    Approximates cyclomatic complexity by counting control flow statements.
    If the content has syntax errors, returns SYNTAX_ERROR_BASELINE.

    Args:
        content: Python source code to analyze.

    Returns:
        Score from 0.0 (high complexity) to 1.0 (low complexity).
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return SYNTAX_ERROR_BASELINE

    # Count complexity indicators
    complexity_count = 0
    function_count = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            function_count += 1
        elif isinstance(node, ast.If | ast.While | ast.For | ast.AsyncFor):
            complexity_count += 1
        elif isinstance(node, ast.BoolOp):
            # Count and/or operators
            complexity_count += len(node.values) - 1
        elif isinstance(node, ast.Try | ast.ExceptHandler | ast.comprehension):
            complexity_count += 1

    if function_count == 0:
        # No functions, use raw complexity
        if complexity_count == 0:
            return 1.0
        return max(0.0, 1.0 - complexity_count / MAX_RAW_COMPLEXITY)

    # Average complexity per function
    avg_complexity = complexity_count / function_count

    # Score: 1.0 at 0 avg, 0.0 at MAX_AVG_COMPLEXITY+ avg
    return max(0.0, 1.0 - avg_complexity / MAX_AVG_COMPLEXITY)


def _compute_documentation_score(content: str) -> float:
    """Compute documentation coverage score.

    Evaluates docstring presence and comment ratio.
    If the content has syntax errors, returns SYNTAX_ERROR_BASELINE.

    Args:
        content: Python source code to analyze.

    Returns:
        Score from 0.0 (no documentation) to 1.0 (well documented).
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return SYNTAX_ERROR_BASELINE

    # Count items that should have docstrings
    needs_docstring = 0
    has_docstring = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Module):
            needs_docstring += 1
            docstring = ast.get_docstring(node)
            if docstring:
                has_docstring += 1

    # Calculate docstring coverage
    if needs_docstring == 0:
        docstring_score = NO_FUNCTIONS_NEUTRAL_SCORE
    else:
        docstring_score = has_docstring / needs_docstring

    # Calculate comment ratio
    lines = content.split("\n")
    total_lines = len([ln for ln in lines if ln.strip()])
    comment_lines = len([ln for ln in lines if ln.strip().startswith("#")])

    if total_lines == 0:
        comment_score = NO_FUNCTIONS_NEUTRAL_SCORE
    else:
        comment_ratio = comment_lines / total_lines
        # Ideal is around 10-15%, penalize both too few and too many
        if comment_ratio < IDEAL_DOCSTRING_RATIO:
            comment_score = comment_ratio / IDEAL_DOCSTRING_RATIO
        else:
            # Too many comments can indicate code smell
            excess = comment_ratio - IDEAL_DOCSTRING_RATIO
            comment_score = max(NO_FUNCTIONS_NEUTRAL_SCORE, 1.0 - excess * 2)

    # Weight docstrings more heavily than comments
    return docstring_score * 0.7 + comment_score * 0.3


# =============================================================================
# Recommendation Generation (Pure)
# =============================================================================


def _generate_recommendations(dimensions: dict[str, float]) -> list[str]:
    """Generate improvement recommendations based on dimension scores.

    Args:
        dimensions: Dictionary of dimension scores (0.0-1.0).

    Returns:
        List of actionable recommendation strings.
    """
    recommendations: list[str] = []

    thresholds: dict[str, tuple[float, str]] = {
        "patterns": (
            0.6,
            "Add ONEX patterns: use frozen=True on models, TypedDict for dicts, "
            "Protocol for interfaces, and extract pure handler functions",
        ),
        "type_coverage": (
            0.7,
            "Improve type coverage: add type hints to function parameters and "
            "return types, avoid 'Any' type",
        ),
        "maintainability": (
            0.6,
            "Improve maintainability: keep functions under 50 lines, use "
            "snake_case for functions and PascalCase for classes",
        ),
        "complexity": (
            0.5,
            "Reduce complexity: break down large functions, reduce nesting depth, "
            "consider extracting helper functions",
        ),
        "documentation": (
            0.5,
            "Add documentation: include docstrings for all public functions, "
            "classes, and modules",
        ),
    }

    for dimension, (threshold, recommendation) in thresholds.items():
        score = dimensions.get(dimension, 0.0)
        if score < threshold:
            recommendations.append(f"[{dimension}] {recommendation}")

    return recommendations


# =============================================================================
# Helper Functions (Pure)
# =============================================================================


def _validate_weights(weights: dict[str, float]) -> None:
    """Validate that weights sum to approximately 1.0.

    Args:
        weights: Dictionary of dimension weights.

    Raises:
        QualityScoringValidationError: If weights don't sum to ~1.0 or have invalid keys.
    """
    expected_keys = set(DEFAULT_WEIGHTS.keys())
    actual_keys = set(weights.keys())

    if actual_keys != expected_keys:
        missing = expected_keys - actual_keys
        extra = actual_keys - expected_keys
        raise QualityScoringValidationError(
            f"Invalid weight keys. Missing: {missing}, Extra: {extra}"
        )

    total = sum(weights.values())
    if not (0.99 <= total <= 1.01):
        raise QualityScoringValidationError(
            f"Weights must sum to 1.0, got {total:.4f}"
        )


def _compute_weighted_score(
    dimensions: dict[str, float], weights: dict[str, float]
) -> float:
    """Compute weighted aggregate score.

    Args:
        dimensions: Dictionary of dimension scores.
        weights: Dictionary of dimension weights.

    Returns:
        Weighted aggregate score (0.0-1.0).
    """
    total = 0.0
    for dimension, score in dimensions.items():
        weight = weights.get(dimension, 0.0)
        total += score * weight
    return total


def _create_unsupported_language_result(
    language: str, onex_threshold: float
) -> QualityScoringResult:
    """Create result for unsupported language.

    Args:
        language: The unsupported language name.
        onex_threshold: ONEX compliance threshold.

    Returns:
        QualityScoringResult with baseline scores and recommendation.
    """
    baseline_score = UNSUPPORTED_LANGUAGE_BASELINE
    dimensions = {
        "patterns": baseline_score,
        "type_coverage": baseline_score,
        "maintainability": baseline_score,
        "complexity": baseline_score,
        "documentation": baseline_score,
    }

    return QualityScoringResult(
        success=True,
        quality_score=baseline_score,
        dimensions=dimensions,
        onex_compliant=baseline_score >= onex_threshold,
        recommendations=[
            f"[unsupported_language] Full analysis not available for '{language}'. "
            f"Only Python is fully supported. Baseline scores applied."
        ],
        source_language=language,
        analysis_version=ANALYSIS_VERSION,
    )


def _create_syntax_error_result(language: str, error_msg: str) -> QualityScoringResult:
    """Create result when code has syntax errors.

    Args:
        language: The source language.
        error_msg: The syntax error message.

    Returns:
        QualityScoringResult indicating syntax error with low scores.
    """
    low_score = SYNTAX_ERROR_BASELINE
    dimensions = {
        "patterns": low_score,
        "type_coverage": low_score,
        "maintainability": low_score,
        "complexity": low_score,
        "documentation": low_score,
    }

    return QualityScoringResult(
        success=True,  # Scoring succeeded, code just has issues
        quality_score=low_score,
        dimensions=dimensions,
        onex_compliant=False,
        recommendations=[
            f"[syntax_error] Code contains syntax errors and cannot be fully analyzed: {error_msg}"
        ],
        source_language=language,
        analysis_version=ANALYSIS_VERSION,
    )


__all__ = [
    "ANALYSIS_VERSION",
    "DEFAULT_WEIGHTS",
    "score_code_quality",
]
