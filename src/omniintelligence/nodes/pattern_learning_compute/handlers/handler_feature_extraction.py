"""AST-based feature extraction handler for pattern learning.

This handler extracts features from training data items to enable pattern clustering.
It sits between the orchestrator (receives TrainingDataItemDict) and clustering
(emits ExtractedFeaturesDict).

OUTPUT CONTRACT (STRICT):
    - Output is normalized, domain-agnostic ExtractedFeaturesDict
    - Downstream handlers MUST NOT re-parse ASTs
    - All features are deterministic given the same input

PROVENANCE INVARIANT:
    - item_id is preserved from input to output
    - labels are preserved from input to output
    - language is preserved from input to output

DETERMINISM INVARIANT:
    - Same input always produces same output
    - Identifiers are normalized (lowercase, sorted, deduped)
    - Batch processing sorts by item_id before processing

GRACEFUL FALLBACK:
    - Non-Python code returns minimal features with extraction_quality="minimal"
    - Syntax errors return minimal features with extraction_quality="minimal"
    - Handler NEVER crashes - always returns valid ExtractedFeaturesDict

Usage:
    from omniintelligence.nodes.pattern_learning_compute.handlers.handler_feature_extraction import (
        extract_features,
        extract_features_batch,
    )

    # Single item extraction
    features = extract_features(training_item)

    # Batch extraction with deterministic ordering
    features_list = extract_features_batch(training_items)
"""

from __future__ import annotations

import ast
from collections.abc import Sequence

from omniintelligence.nodes.pattern_learning_compute.handlers.presets import (
    ONEX_BASE_CLASSES,
    ONEX_PATTERN_KEYWORDS,
)
from omniintelligence.nodes.pattern_learning_compute.handlers.protocols import (
    ExtractedFeaturesDict,
    StructuralFeaturesDict,
)
from omniintelligence.nodes.pattern_learning_compute.handlers.utils import (
    normalize_identifiers,
)
from omniintelligence.nodes.pattern_learning_compute.models import (
    TrainingDataItemDict,
)


# =============================================================================
# Public API
# =============================================================================


def extract_features(item: TrainingDataItemDict) -> ExtractedFeaturesDict:
    """Extract features from a single training item.

    OUTPUT CONTRACT (STRICT):
        - Output is normalized, domain-agnostic ExtractedFeaturesDict
        - Downstream handlers MUST NOT re-parse ASTs
        - All features are deterministic given the same input

    PROVENANCE PRESERVATION:
        - item_id is copied from input
        - labels are copied from input (converted to tuple)
        - language is copied from input

    EXTRACTION BEHAVIOR:
        - Python code with valid syntax: full AST extraction (extraction_quality="full")
        - Non-Python code OR syntax error: minimal features (extraction_quality="minimal")
        - Never crashes - always returns valid ExtractedFeaturesDict

    Args:
        item: Training data item containing code_snippet, item_id, labels, language.

    Returns:
        ExtractedFeaturesDict with normalized, deterministic features.
    """
    item_id = item.get("item_id", "")
    labels = item.get("labels", [])
    language = item.get("language", "")
    code_snippet = item.get("code_snippet", "")

    # Convert labels to tuple for immutability
    # Handle: tuple (use as-is), list (convert), single value (wrap), empty/None (empty tuple)
    if isinstance(labels, tuple):
        labels_tuple = labels
    elif isinstance(labels, list):
        labels_tuple = tuple(labels)
    else:
        labels_tuple = (labels,) if labels else ()

    # Check if this is Python code
    is_python = _is_python_language(language)

    if not is_python:
        return _create_minimal_features(
            item_id=item_id,
            labels=labels_tuple,
            language=language,
        )

    # Attempt AST parsing
    try:
        tree = ast.parse(code_snippet)
    except SyntaxError:
        # Graceful fallback for syntax errors
        return _create_minimal_features(
            item_id=item_id,
            labels=labels_tuple,
            language=language,
        )

    # Extract features from valid AST
    return _extract_features_from_ast(
        tree=tree,
        content=code_snippet,
        item_id=item_id,
        labels=labels_tuple,
        language=language,
    )


def extract_features_batch(
    items: Sequence[TrainingDataItemDict],
) -> list[ExtractedFeaturesDict]:
    """Extract features from multiple training items with deterministic ordering.

    DETERMINISM INVARIANT:
        - Inputs are sorted by item_id before processing
        - Output order matches sorted input order
        - Enables replay comparison and debugging

    Args:
        items: Sequence of training data items.

    Returns:
        List of ExtractedFeaturesDict in deterministic order (sorted by item_id).
    """
    # Sort by item_id for deterministic processing
    sorted_items = sorted(items, key=lambda x: x.get("item_id", ""))

    # Extract features for each item
    return [extract_features(item) for item in sorted_items]


# =============================================================================
# Internal Helpers - AST Extraction
# =============================================================================


def _extract_features_from_ast(
    tree: ast.AST,
    content: str,
    item_id: str,
    labels: tuple[str, ...],
    language: str,
) -> ExtractedFeaturesDict:
    """Extract full features from a valid Python AST.

    Args:
        tree: Parsed AST.
        content: Original source code.
        item_id: Training item identifier.
        labels: Training labels.
        language: Programming language.

    Returns:
        ExtractedFeaturesDict with full feature extraction.
    """
    keywords = _extract_keywords(tree)
    structural = _extract_structural_features(tree, content)
    pattern_indicators = _extract_pattern_indicators(tree, content)
    base_classes = _extract_base_classes(tree)
    decorators = _extract_decorators(tree)

    return ExtractedFeaturesDict(
        item_id=item_id,
        keywords=keywords,
        pattern_indicators=pattern_indicators,
        structural=structural,
        base_classes=base_classes,
        decorators=decorators,
        labels=labels,
        language=language,
        extraction_quality="full",
    )


def _create_minimal_features(
    item_id: str,
    labels: tuple[str, ...],
    language: str,
) -> ExtractedFeaturesDict:
    """Create minimal features for non-Python or syntax error cases.

    Used as a graceful fallback when full extraction is not possible.

    Args:
        item_id: Training item identifier.
        labels: Training labels.
        language: Programming language.

    Returns:
        ExtractedFeaturesDict with minimal/empty features.
    """
    minimal_structural = StructuralFeaturesDict(
        class_count=0,
        function_count=0,
        max_nesting_depth=0,
        line_count=0,
        cyclomatic_complexity=0,
        has_type_hints=False,
        has_docstrings=False,
    )

    return ExtractedFeaturesDict(
        item_id=item_id,
        keywords=(),
        pattern_indicators=(),
        structural=minimal_structural,
        base_classes=(),
        decorators=(),
        labels=labels,
        language=language,
        extraction_quality="minimal",
    )


def _is_python_language(language: str) -> bool:
    """Check if the language string indicates Python.

    Args:
        language: Language string from training item.

    Returns:
        True if the language is Python (case-insensitive).
    """
    if not language:
        return False
    return language.lower() in ("python", "python3", "py", "python2")


def _extract_keywords(tree: ast.AST) -> tuple[str, ...]:
    """Extract identifiers, imports, function/class names from AST.

    Collects:
        - Function and method names
        - Class names
        - Import names and module names
        - Variable names (Name nodes in Store context)

    All identifiers are normalized (lowercase, sorted, deduped).

    Args:
        tree: Parsed AST.

    Returns:
        Tuple of normalized identifier strings.
    """
    identifiers: list[str] = []

    for node in ast.walk(tree):
        # Function/method/class names
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            identifiers.append(node.name)

        # Import names
        elif isinstance(node, ast.Import):
            for alias in node.names:
                identifiers.append(alias.name.split(".")[0])  # Top-level module
                if alias.asname:
                    identifiers.append(alias.asname)

        # Import from
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                identifiers.append(node.module.split(".")[0])  # Top-level module
            for alias in node.names:
                identifiers.append(alias.name)
                if alias.asname:
                    identifiers.append(alias.asname)

        # Variable names (loaded)
        elif isinstance(node, ast.Name):
            identifiers.append(node.id)

        # Attribute access
        elif isinstance(node, ast.Attribute):
            identifiers.append(node.attr)

    return normalize_identifiers(identifiers)


def _extract_structural_features(tree: ast.AST, content: str) -> StructuralFeaturesDict:
    """Extract structural metrics from AST and content.

    Metrics:
        - class_count: Number of class definitions
        - function_count: Number of function/method definitions
        - max_nesting_depth: Maximum depth of nested control structures
        - line_count: Non-blank line count
        - cyclomatic_complexity: Simplified complexity measure
        - has_type_hints: Whether type annotations are present
        - has_docstrings: Whether docstrings are present

    Args:
        tree: Parsed AST.
        content: Original source code.

    Returns:
        StructuralFeaturesDict with computed metrics.
    """
    class_count = 0
    function_count = 0
    has_type_hints = False
    has_docstrings = False

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_count += 1
            # Check for class docstring
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                has_docstrings = True

        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            function_count += 1
            # Check for function docstring
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                has_docstrings = True
            # Check for return type hint
            if node.returns is not None:
                has_type_hints = True
            # Check for argument type hints
            if node.args:
                for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
                    if arg.annotation is not None:
                        has_type_hints = True
                        break

        elif isinstance(node, ast.AnnAssign):
            # Variable annotation
            has_type_hints = True

    # Compute line count (non-blank lines)
    line_count = len([line for line in content.splitlines() if line.strip()])

    # Compute structural metrics
    max_nesting_depth = _compute_max_depth(tree)
    cyclomatic_complexity = _compute_cyclomatic_complexity(tree)

    return StructuralFeaturesDict(
        class_count=class_count,
        function_count=function_count,
        max_nesting_depth=max_nesting_depth,
        line_count=line_count,
        cyclomatic_complexity=cyclomatic_complexity,
        has_type_hints=has_type_hints,
        has_docstrings=has_docstrings,
    )


def _extract_pattern_indicators(tree: ast.AST, _content: str) -> tuple[str, ...]:
    """Detect ONEX patterns via base class inheritance and keywords.

    ONEX patterns are identified by:
        1. Inheritance from ONEX base classes (NodeCompute, NodeEffect, etc.)
        2. Presence of ONEX pattern keywords (frozen, extra, forbid, etc.)

    Args:
        tree: Parsed AST.
        _content: Original source code (reserved for future text-based detection).

    Returns:
        Tuple of normalized pattern indicator strings.
    """
    indicators: list[str] = []

    # Extract base classes that match ONEX patterns
    base_classes = set(_extract_base_classes(tree))
    for base in base_classes:
        # Check lowercase version against ONEX_BASE_CLASSES
        if base in ONEX_BASE_CLASSES:
            indicators.append(base)

    # Extract keywords that match ONEX patterns
    for node in ast.walk(tree):
        # Check identifiers against ONEX_PATTERN_KEYWORDS
        if isinstance(node, ast.Name):
            if node.id in ONEX_PATTERN_KEYWORDS:
                indicators.append(node.id)
        elif isinstance(node, ast.Attribute):
            if node.attr in ONEX_PATTERN_KEYWORDS:
                indicators.append(node.attr)

    return normalize_identifiers(indicators)


def _extract_base_classes(tree: ast.AST) -> tuple[str, ...]:
    """Extract inherited base class names.

    Args:
        tree: Parsed AST.

    Returns:
        Tuple of base class name strings (not normalized, preserves case).
    """
    base_classes: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                name = _get_name(base)
                if name:
                    base_classes.append(name)

    # Dedupe and sort for determinism, but don't lowercase (preserve original names)
    return tuple(sorted(set(base_classes)))


def _extract_decorators(tree: ast.AST) -> tuple[str, ...]:
    """Extract decorator names used.

    Args:
        tree: Parsed AST.

    Returns:
        Tuple of decorator name strings (normalized).
    """
    decorators: list[str] = []

    for node in ast.walk(tree):
        decorator_list: list[ast.expr] = []

        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            decorator_list = node.decorator_list

        for decorator in decorator_list:
            name = _get_name(decorator)
            if name:
                decorators.append(name)

    return normalize_identifiers(decorators)


def _get_name(node: ast.AST) -> str:
    """Get the name from various AST node types.

    Handles:
        - ast.Name: Direct name (e.g., `BaseModel`)
        - ast.Attribute: Attribute access (e.g., `pydantic.BaseModel` -> `BaseModel`)
        - ast.Call: Function call (e.g., `dataclass()` -> `dataclass`)
        - ast.Subscript: Generic subscript (e.g., `List[str]` -> `List`)

    Args:
        node: AST node to extract name from.

    Returns:
        Name string, or empty string if cannot extract.
    """
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return node.attr
    elif isinstance(node, ast.Call):
        return _get_name(node.func)
    elif isinstance(node, ast.Subscript):
        return _get_name(node.value)
    return ""


def _compute_max_depth(tree: ast.AST) -> int:
    """Compute maximum nesting depth of control structures.

    Control structures counted:
        - if/elif/else
        - for/while loops
        - try/except/finally
        - with statements
        - match statements (Python 3.10+)

    Args:
        tree: Parsed AST.

    Returns:
        Maximum nesting depth (0 if no control structures).
    """
    max_depth = 0

    # Control flow node types that contribute to nesting
    control_flow_types: tuple[type[ast.AST], ...] = (
        ast.If,
        ast.For,
        ast.While,
        ast.Try,
        ast.With,
        ast.AsyncFor,
        ast.AsyncWith,
        ast.Match,
    )

    def compute_depth(node: ast.AST, current_depth: int) -> int:
        """Recursively compute depth."""
        nonlocal max_depth

        if isinstance(node, control_flow_types):
            current_depth += 1
            max_depth = max(max_depth, current_depth)

        for child in ast.iter_child_nodes(node):
            compute_depth(child, current_depth)

        return max_depth

    compute_depth(tree, 0)
    return max_depth


def _compute_cyclomatic_complexity(tree: ast.AST) -> int:
    """Compute simplified cyclomatic complexity.

    Simplified complexity counts:
        - 1 (base complexity)
        - +1 for each if/elif
        - +1 for each for/while loop
        - +1 for each except handler
        - +1 for each and/or in boolean expressions
        - +1 for each comprehension

    This is a simplified version of McCabe complexity that provides
    a reasonable approximation for pattern comparison.

    Args:
        tree: Parsed AST.

    Returns:
        Cyclomatic complexity score (minimum 1).
    """
    complexity = 1  # Base complexity

    for node in ast.walk(tree):
        # Branches that add +1 complexity each
        if isinstance(
            node,
            ast.If
            | ast.For
            | ast.While
            | ast.AsyncFor
            | ast.ExceptHandler
            | ast.ListComp
            | ast.SetComp
            | ast.DictComp
            | ast.GeneratorExp
            | ast.Assert,
        ):
            complexity += 1
        elif isinstance(node, ast.BoolOp):
            # Each and/or adds a branch
            complexity += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            # Each if clause in comprehension
            complexity += len(node.ifs)

    return complexity


# =============================================================================
# Module Exports
# =============================================================================


__all__ = [
    "extract_features",
    "extract_features_batch",
]
