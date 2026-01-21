"""Handler for quality scoring computation.

This module provides pure functions for scoring code quality based on
ONEX-focused dimensions. All functions are side-effect-free and suitable
for use in compute nodes.

The scoring system evaluates Python code across six dimensions:
    - complexity: Cyclomatic complexity approximation (0.20)
    - maintainability: Code structure quality (function length, naming) (0.20)
    - documentation: Docstring and comment coverage (0.15)
    - temporal_relevance: Code freshness indicators (TODO/FIXME, deprecated) (0.15)
    - patterns: ONEX pattern adherence (frozen models, TypedDict, Protocol) (0.15)
    - architectural: Module organization and structure (0.15)

Default weights follow the six-dimension standard for balanced quality assessment.

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
from omniintelligence.nodes.quality_scoring_compute.handlers.presets import (
    OnexStrictnessLevel,
    get_threshold_for_preset,
    get_weights_for_preset,
)
from omniintelligence.nodes.quality_scoring_compute.handlers.protocols import (
    DimensionScores,
    QualityScoringResult,
)

# =============================================================================
# Constants
# =============================================================================

ANALYSIS_VERSION: Final[str] = "1.1.0"

# Six-dimension standard weights
DEFAULT_WEIGHTS: Final[dict[str, float]] = {
    "complexity": 0.20,
    "maintainability": 0.20,
    "documentation": 0.15,
    "temporal_relevance": 0.15,
    "patterns": 0.15,
    "architectural": 0.15,
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

# Pre-compiled patterns for temporal relevance scoring
_COMPILED_TODO_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"#\s*(TODO|FIXME|XXX|HACK)", re.IGNORECASE
)
_COMPILED_DEPRECATED_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"@?deprecated|DeprecationWarning", re.IGNORECASE
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

# Neutral score constants
NO_FUNCTIONS_NEUTRAL_SCORE: Final[float] = 0.5  # Score when no functions to analyze

# Maintainability constants
IDEAL_FUNCTION_LENGTH: Final[int] = 20  # Ideal max function length (lines)
FUNCTION_LENGTH_SCORING_RANGE: Final[int] = 80  # Range for scoring (20 to 100 lines)
NO_ITEMS_MAINTAINABILITY_SCORE: Final[float] = 0.7  # Score when no functions/classes

# Complexity constants
MAX_RAW_COMPLEXITY: Final[int] = 20  # Max raw complexity for scoring
MAX_AVG_COMPLEXITY: Final[int] = 10  # Max average complexity per function

# Temporal relevance constants
STALENESS_PENALTY_PER_INDICATOR: Final[float] = 0.1
MAX_STALENESS_PENALTY: Final[float] = 1.0
DEPRECATED_WEIGHT_MULTIPLIER: Final[int] = 2  # Higher weight for deprecated markers

# Architectural constants
IMPORT_AFTER_CODE_PENALTY: Final[float] = 0.2
MULTIPLE_INHERITANCE_PENALTY: Final[float] = 0.3
DEFAULT_ARCHITECTURAL_SCORE: Final[float] = 0.7  # Default for simple modules

# New architectural check constants
MISSING_ALL_EXPORTS_PENALTY: Final[float] = 0.15  # Penalty for missing __all__ in modules with exports
IMPORTS_INSIDE_FUNCTION_PENALTY: Final[float] = 0.25  # Penalty per import inside functions (circular import risk)
IMPORT_GROUPING_BONUS: Final[float] = 0.1  # Bonus for properly grouped imports (stdlib, third-party, local)
HANDLER_PATTERN_BONUS: Final[float] = 0.1  # Bonus for following handler pattern (private pure functions)
CLASS_ORGANIZATION_PENALTY: Final[float] = 0.15  # Penalty for poor class organization

# Handler pattern constants
MIN_HANDLER_FUNCTIONS_FOR_BONUS: Final[int] = 2  # Minimum private pure functions to indicate handler pattern

# Import grouping detection - common stdlib modules
STDLIB_MODULES: Final[frozenset[str]] = frozenset({
    "abc", "ast", "asyncio", "base64", "collections", "concurrent", "contextlib",
    "copy", "csv", "dataclasses", "datetime", "decimal", "enum", "functools",
    "hashlib", "importlib", "inspect", "io", "itertools", "json", "logging",
    "math", "os", "pathlib", "random", "re", "shutil", "signal",
    "socket", "sqlite3", "ssl", "string", "struct", "subprocess", "sys",
    "tempfile", "threading", "time", "traceback", "types", "typing", "unittest",
    "urllib", "uuid", "warnings", "weakref", "xml", "zipfile",
})

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
    preset: OnexStrictnessLevel | None = None,
) -> QualityScoringResult:
    """Score code quality based on multiple dimensions.

    This is the main entry point for quality scoring. It computes scores
    across six dimensions and aggregates them using configurable weights.

    Configuration Precedence:
        1. preset (highest priority) - When set, overrides weights and threshold.
        2. weights / onex_threshold - Manual configuration.
        3. Defaults (lowest priority) - Standard weights and 0.7 threshold.

    Args:
        content: Source code content to analyze.
        language: Programming language (e.g., "python"). Non-Python languages
            receive baseline scores with an unsupported_language recommendation.
        weights: Optional custom weights for each dimension. Must sum to ~1.0.
            Defaults to six-dimension standard weights if None.
            Ignored when preset is specified.
        onex_threshold: Score threshold for ONEX compliance (default 0.7).
            If quality_score >= onex_threshold, onex_compliant is True.
            Ignored when preset is specified.
        preset: Optional ONEX strictness preset (strict/standard/lenient).
            When set, automatically configures weights and threshold:
            - STRICT: Production-ready, threshold 0.8
            - STANDARD: Balanced, threshold 0.7
            - LENIENT: Development mode, threshold 0.5

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

        >>> # Using a preset
        >>> result = score_code_quality(
        ...     content="class Model(BaseModel): x: int",
        ...     language="python",
        ...     preset=OnexStrictnessLevel.STRICT,
        ... )
        >>> result["onex_compliant"]  # Uses 0.8 threshold
        False
    """
    # Validate inputs
    if not content or not content.strip():
        raise QualityScoringValidationError("Content cannot be empty")

    # Apply preset configuration (highest precedence)
    if preset is not None:
        effective_weights = get_weights_for_preset(preset)
        effective_threshold = get_threshold_for_preset(preset)
    else:
        effective_weights = weights if weights is not None else DEFAULT_WEIGHTS.copy()
        effective_threshold = onex_threshold

    _validate_weights(effective_weights)

    normalized_language = language.lower().strip()

    # Check if language is supported for full analysis
    if normalized_language not in SUPPORTED_LANGUAGES:
        return _create_unsupported_language_result(normalized_language, effective_threshold)

    try:
        # Compute dimension scores
        dimensions = _compute_all_dimensions(content)

        # Calculate weighted aggregate
        quality_score = _compute_weighted_score(dimensions, effective_weights)

        # Determine ONEX compliance
        onex_compliant = quality_score >= effective_threshold

        # Generate recommendations based on low scores
        recommendations = _generate_recommendations(dimensions)

        return QualityScoringResult(
            success=True,
            quality_score=round(quality_score, 4),
            dimensions={k: round(float(v), 4) for k, v in dimensions.items()},  # type: ignore[arg-type, typeddict-item]
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


def _compute_all_dimensions(content: str) -> DimensionScores:
    """Compute all quality dimension scores.

    Parses the AST once and passes it to dimension functions that need it,
    optimizing performance by avoiding redundant parsing.

    Args:
        content: Python source code to analyze.

    Returns:
        DimensionScores with all six dimension scores (0.0-1.0).

    Raises:
        SyntaxError: If the content cannot be parsed as valid Python.
    """
    # Parse AST once for all dimensions that need it
    tree = ast.parse(content)

    return {
        "complexity": _compute_complexity_score(tree),
        "maintainability": _compute_maintainability_score(tree),
        "documentation": _compute_documentation_score(tree, content),
        "temporal_relevance": _compute_temporal_relevance_score(content),
        "patterns": _compute_patterns_score(content),
        "architectural": _compute_architectural_score(tree, content),
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
    if handler_pattern_matches >= MIN_HANDLER_FUNCTIONS_FOR_BONUS:
        positive_count += 1

    # Score calculation:
    # - Base score from positive patterns (max 1.0 at PATTERN_SCORE_DIVISOR+ patterns)
    # - Penalty from anti-patterns (ANTI_PATTERN_PENALTY per anti-pattern, max MAX_ANTI_PATTERN_PENALTY)
    base_score = min(positive_count / PATTERN_SCORE_DIVISOR, 1.0)
    penalty = min(anti_count * ANTI_PATTERN_PENALTY, MAX_ANTI_PATTERN_PENALTY)

    return max(0.0, min(1.0, base_score - penalty + PATTERN_BASELINE_SCORE))


def _compute_maintainability_score(tree: ast.AST) -> float:
    """Compute code maintainability score.

    Evaluates function length, naming conventions, and overall structure.

    Args:
        tree: Parsed AST of the Python source code.

    Returns:
        Score from 0.0 (poor maintainability) to 1.0 (excellent).
    """
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


def _compute_complexity_score(tree: ast.AST) -> float:
    """Compute complexity score (inverted - lower complexity is better).

    Approximates cyclomatic complexity by counting control flow statements.

    Args:
        tree: Parsed AST of the Python source code.

    Returns:
        Score from 0.0 (high complexity) to 1.0 (low complexity).
    """
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


def _compute_documentation_score(tree: ast.AST, content: str) -> float:
    """Compute documentation coverage score.

    Evaluates docstring presence and comment ratio.

    Args:
        tree: Parsed AST of the Python source code.
        content: Raw source code content for comment analysis.

    Returns:
        Score from 0.0 (no documentation) to 1.0 (well documented).
    """
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
        # Score based on having enough comments, don't penalize excess
        # High comment ratios in complex code are legitimate
        comment_score = min(1.0, comment_ratio / IDEAL_DOCSTRING_RATIO)

    # Weight docstrings more heavily than comments
    return docstring_score * 0.7 + comment_score * 0.3


def _compute_temporal_relevance_score(content: str) -> float:
    """Compute temporal relevance score based on code freshness indicators.

    Checks for staleness indicators such as TODO/FIXME comments and
    deprecated markers that suggest code may need updating.

    Args:
        content: Python source code to analyze.

    Returns:
        Score from 0.0 (stale code) to 1.0 (fresh/relevant).
    """
    # Count staleness indicators
    stale_indicators = 0

    # Check for TODO/FIXME/XXX/HACK (using pre-compiled pattern)
    todo_matches = _COMPILED_TODO_PATTERN.findall(content)
    stale_indicators += len(todo_matches)

    # Check for deprecated markers (using pre-compiled pattern)
    deprecated_matches = _COMPILED_DEPRECATED_PATTERN.findall(content)
    stale_indicators += len(deprecated_matches) * DEPRECATED_WEIGHT_MULTIPLIER

    # Score calculation: fewer indicators = higher score
    # Max penalty at 10+ indicators
    penalty = min(stale_indicators * STALENESS_PENALTY_PER_INDICATOR, MAX_STALENESS_PENALTY)
    return max(0.0, 1.0 - penalty)


def _compute_architectural_score(tree: ast.AST, content: str) -> float:
    """Compute architectural compliance score.

    Evaluates module organization, class structure, and import patterns for
    ONEX-compliant code architecture. Performs the following checks:

    1. Import placement: Imports should be at module level, at the top
    2. Multiple inheritance: Penalizes classes with more than one base class
    3. __all__ exports: Checks for explicit public API definition
    4. Circular import risk: Detects imports inside functions
    5. Import grouping: Checks if imports are organized (stdlib, third-party, local)
    6. Handler pattern: Rewards private pure functions with type annotations
    7. Class organization: Checks ClassVar and model_config placement

    Args:
        tree: Parsed AST of the Python source code.
        content: Raw source code content for pattern analysis.

    Returns:
        Score from 0.0 (poor architecture) to 1.0 (good architecture).
    """
    # content parameter included for future extensibility and signature consistency
    _ = content  # Unused but kept for API consistency

    scores: list[float] = []
    bonuses: list[float] = []
    penalties: list[float] = []

    # =========================================================================
    # Check 1: Import placement (imports should be at module level, at the top)
    # =========================================================================
    import_after_code = 0
    seen_non_import = False
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            if seen_non_import:
                import_after_code += 1
        elif not isinstance(node, ast.Expr):  # Skip module docstring (Expr with Constant)
            seen_non_import = True

    import_org_score = max(0.0, 1.0 - import_after_code * IMPORT_AFTER_CODE_PENALTY)
    scores.append(import_org_score)

    # =========================================================================
    # Check 2: Multiple inheritance penalty
    # =========================================================================
    # Single inheritance (e.g., class MyModel(BaseModel)) is encouraged in ONEX patterns
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if len(node.bases) > 1:  # Multiple inheritance - penalize
                scores.append(1.0 - MULTIPLE_INHERITANCE_PENALTY)

    # =========================================================================
    # Check 3: __all__ exports - modules with public items should define __all__
    # =========================================================================
    has_all_exports = _check_has_all_exports(tree)
    has_public_items = _check_has_public_items(tree)

    if has_public_items and not has_all_exports:
        penalties.append(MISSING_ALL_EXPORTS_PENALTY)

    # =========================================================================
    # Check 4: Circular import risk - imports inside functions
    # =========================================================================
    imports_inside_functions = _count_imports_inside_functions(tree)
    if imports_inside_functions > 0:
        # Penalize each import inside a function, capped at a maximum
        penalty = min(imports_inside_functions * IMPORTS_INSIDE_FUNCTION_PENALTY, 0.5)
        penalties.append(penalty)

    # =========================================================================
    # Check 5: Import grouping (stdlib, third-party, local)
    # =========================================================================
    if _check_import_grouping(tree):
        bonuses.append(IMPORT_GROUPING_BONUS)

    # =========================================================================
    # Check 6: Handler pattern - private pure functions with type annotations
    # =========================================================================
    if _check_handler_pattern(tree):
        bonuses.append(HANDLER_PATTERN_BONUS)

    # =========================================================================
    # Check 7: Class organization (ClassVar/model_config at top)
    # =========================================================================
    class_org_issues = _check_class_organization(tree)
    if class_org_issues > 0:
        penalties.append(min(class_org_issues * CLASS_ORGANIZATION_PENALTY, 0.3))

    # Calculate final score
    if not scores:
        base_score = DEFAULT_ARCHITECTURAL_SCORE
    else:
        base_score = sum(scores) / len(scores)

    # Apply bonuses and penalties
    total_bonus = sum(bonuses)
    total_penalty = sum(penalties)

    final_score = base_score + total_bonus - total_penalty
    return max(0.0, min(1.0, final_score))


def _check_has_all_exports(tree: ast.AST) -> bool:
    """Check if module defines __all__ exports.

    Args:
        tree: Parsed AST of the Python source code.

    Returns:
        True if __all__ is defined at module level, False otherwise.
    """
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    return True
    return False


def _check_has_public_items(tree: ast.AST) -> bool:
    """Check if module has public functions or classes (not starting with _).

    Args:
        tree: Parsed AST of the Python source code.

    Returns:
        True if there are public functions or classes, False otherwise.
    """
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            if not node.name.startswith("_"):
                return True
    return False


def _count_imports_inside_functions(tree: ast.AST) -> int:
    """Count imports that occur inside function bodies (circular import risk).

    Args:
        tree: Parsed AST of the Python source code.

    Returns:
        Number of import statements found inside functions.
    """
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for child in ast.walk(node):
                if isinstance(child, ast.Import | ast.ImportFrom):
                    count += 1
    return count


def _check_import_grouping(tree: ast.AST) -> bool:
    """Check if imports are grouped properly (stdlib, third-party, local).

    Imports should be organized with stdlib first, then third-party,
    then local imports, with each group being contiguous.

    Args:
        tree: Parsed AST of the Python source code.

    Returns:
        True if imports appear to be properly grouped, False otherwise.
    """
    imports: list[tuple[int, str, str]] = []  # (line_no, module_name, category)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                category = _categorize_import(alias.name)
                imports.append((node.lineno, alias.name, category))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                category = _categorize_import(node.module)
                imports.append((node.lineno, node.module, category))

    if len(imports) < 2:
        return True  # Too few imports to judge grouping

    # Check that imports are grouped by category (no interleaving)
    # Categories should appear in order: stdlib -> third_party -> local
    seen_categories: list[str] = []
    for _, _, category in imports:
        if not seen_categories or seen_categories[-1] != category:
            # Check for category backtracking (e.g., local then stdlib)
            if category in seen_categories:
                return False  # Category appeared before, now appears again - not grouped
            seen_categories.append(category)

    return True


def _categorize_import(module_name: str) -> str:
    """Categorize an import as stdlib, third_party, or local.

    Args:
        module_name: The name of the module being imported.

    Returns:
        Category string: "stdlib", "third_party", or "local".
    """
    # Get the top-level module name
    top_module = module_name.split(".")[0]

    if top_module in STDLIB_MODULES:
        return "stdlib"
    elif top_module.startswith("_"):
        return "stdlib"  # Private stdlib modules
    else:
        return "third_party"  # Treat all non-stdlib as third-party/local


def _check_handler_pattern(tree: ast.AST) -> bool:
    """Check if module follows handler pattern with private pure functions.

    The handler pattern uses private functions (starting with _) that have
    return type annotations, indicating pure functions with clear contracts.

    Args:
        tree: Parsed AST of the Python source code.

    Returns:
        True if module follows handler pattern, False otherwise.
    """
    private_typed_functions = 0

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            # Check if private function with return type annotation
            if node.name.startswith("_") and node.returns is not None:
                private_typed_functions += 1

    return private_typed_functions >= MIN_HANDLER_FUNCTIONS_FOR_BONUS


def _check_class_organization(tree: ast.AST) -> int:
    """Check class organization (ClassVar and model_config placement).

    Well-organized classes should have ClassVar declarations and model_config
    at the top of the class body, before methods.

    Args:
        tree: Parsed AST of the Python source code.

    Returns:
        Number of class organization issues found.
    """
    issues = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            seen_method = False
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                    seen_method = True
                elif isinstance(item, ast.AnnAssign) and seen_method:
                    # Annotated assignment after method - could be ClassVar out of place
                    if item.annotation:
                        ann_str = ast.unparse(item.annotation) if hasattr(ast, "unparse") else ""
                        if "ClassVar" in ann_str:
                            issues += 1
                elif isinstance(item, ast.Assign) and seen_method:
                    # Check if this is model_config after methods
                    for target in item.targets:
                        if isinstance(target, ast.Name) and target.id == "model_config":
                            issues += 1

    return issues


# =============================================================================
# Recommendation Generation (Pure)
# =============================================================================


def _generate_recommendations(dimensions: DimensionScores) -> list[str]:
    """Generate improvement recommendations based on dimension scores.

    Args:
        dimensions: DimensionScores with all six dimension scores.

    Returns:
        List of actionable recommendation strings.
    """
    recommendations: list[str] = []

    thresholds: dict[str, tuple[float, str]] = {
        "complexity": (
            0.5,
            "Reduce complexity: break down large functions, reduce nesting depth, "
            "consider extracting helper functions",
        ),
        "maintainability": (
            0.6,
            "Improve maintainability: keep functions under 50 lines, use "
            "snake_case for functions and PascalCase for classes",
        ),
        "documentation": (
            0.5,
            "Add documentation: include docstrings for all public functions, "
            "classes, and modules",
        ),
        "temporal_relevance": (
            0.7,
            "Address technical debt: resolve TODO/FIXME comments, update or "
            "remove deprecated code markers",
        ),
        "patterns": (
            0.6,
            "Add ONEX patterns: use frozen=True on models, TypedDict for dicts, "
            "Protocol for interfaces, and extract pure handler functions",
        ),
        "architectural": (
            0.6,
            "Improve architecture: organize imports at module top, avoid deep "
            "inheritance hierarchies, prefer composition over inheritance",
        ),
    }

    for dimension, (threshold, recommendation) in thresholds.items():
        score = float(dimensions.get(dimension, 0.0))  # type: ignore[arg-type]
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

    for key, value in weights.items():
        if not (0.0 <= value <= 1.0):
            raise QualityScoringValidationError(
                f"Weight '{key}' must be between 0.0 and 1.0, got {value}"
            )


def _compute_weighted_score(
    dimensions: DimensionScores, weights: dict[str, float]
) -> float:
    """Compute weighted aggregate score.

    Args:
        dimensions: DimensionScores with all six dimension scores.
        weights: Dictionary of dimension weights.

    Returns:
        Weighted aggregate score (0.0-1.0).
    """
    total = 0.0
    for dimension, score in dimensions.items():
        weight = weights.get(dimension, 0.0)
        total += float(score) * weight  # type: ignore[arg-type]
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
    dimensions: DimensionScores = {
        "complexity": baseline_score,
        "maintainability": baseline_score,
        "documentation": baseline_score,
        "temporal_relevance": baseline_score,
        "patterns": baseline_score,
        "architectural": baseline_score,
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
    dimensions: DimensionScores = {
        "complexity": low_score,
        "maintainability": low_score,
        "documentation": low_score,
        "temporal_relevance": low_score,
        "patterns": low_score,
        "architectural": low_score,
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
    "OnexStrictnessLevel",
    "get_threshold_for_preset",
    "get_weights_for_preset",
    "score_code_quality",
]
