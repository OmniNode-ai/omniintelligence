"""Handler for semantic analysis computation.

This module provides pure functions for extracting semantic information from
Python source code using AST analysis. All functions are side-effect-free
and suitable for use in compute nodes.

The semantic analysis extracts:
    - Entities: functions, classes, imports, constants, decorators
    - Relations: imports, inherits, calls, defines

Design Decisions:
    - Pure functions with no side effects or HTTP calls
    - Never throws exceptions - catches errors and returns parse_ok=False
    - Uses Python's built-in ast module for deterministic analysis
    - Confidence scores reflect static analysis certainty:
        - IMPORTS/INHERITS: 1.0 (deterministic from AST)
        - CALLS: 0.8 base (name resolution is best-effort)
        - DEFINES: 1.0 (structural relationship)

Example:
    from omniintelligence.nodes.semantic_analysis_compute.handlers import (
        analyze_semantics,
    )

    result = analyze_semantics(
        content="class Foo(Base): pass",
        language="python",
    )
    print(f"Entities: {len(result['entities'])}")
    print(f"Relations: {len(result['relations'])}")
"""

from __future__ import annotations

import ast
import contextlib
import time
from collections import Counter
from typing import Final

from omnibase_core.models.primitives.model_semver import ModelSemVer

from omniintelligence.nodes.semantic_analysis_compute.handlers.protocols import (
    EntityDict,
    RelationDict,
    SemanticAnalysisMetadataDict,
    SemanticAnalysisResult,
    SemanticClassMetadata,
    SemanticConstantMetadata,
    SemanticFeaturesDict,
    SemanticFunctionMetadata,
    SemanticImportMetadata,
    create_empty_features,
)

# =============================================================================
# Constants
# =============================================================================

ANALYSIS_VERSION: Final[ModelSemVer] = ModelSemVer(major=1, minor=0, patch=0)
ANALYSIS_VERSION_STR: Final[str] = str(ANALYSIS_VERSION)

# Supported languages for full analysis
SUPPORTED_LANGUAGES: Final[frozenset[str]] = frozenset({"python", "py"})

# Confidence scores for different relation types
CONFIDENCE_IMPORTS: Final[float] = 1.0  # Deterministic from AST
CONFIDENCE_INHERITS: Final[float] = 1.0  # Deterministic from AST
CONFIDENCE_DEFINES: Final[float] = 1.0  # Structural relationship
CONFIDENCE_CALLS_BASE: Final[float] = 0.8  # Best-effort name resolution

# Maximum call frequency for confidence scaling
MAX_CALL_FREQUENCY: Final[int] = 10

# Module scope constant
MODULE_SCOPE: Final[str] = "module"


# =============================================================================
# Helper Functions (Pure)
# =============================================================================


def _get_decorator_name(decorator: ast.expr) -> str:
    """Get the name of a decorator from its AST node.

    Handles simple decorators (@foo), call decorators (@foo()),
    and attribute decorators (@module.foo).

    Args:
        decorator: AST expression node for the decorator.

    Returns:
        String name of the decorator.
    """
    if isinstance(decorator, ast.Name):
        return decorator.id
    elif isinstance(decorator, ast.Attribute):
        return ast.unparse(decorator)
    elif isinstance(decorator, ast.Call):
        # Handle @decorator() or @decorator(args)
        return _get_decorator_name(decorator.func)
    else:
        # Fallback for complex decorators
        try:
            return ast.unparse(decorator)
        except Exception:
            return "<unknown>"


# =============================================================================
# Main Handler Function
# =============================================================================


def analyze_semantics(
    content: str,
    language: str = "python",
    include_call_graph: bool = True,
    include_import_graph: bool = True,
) -> SemanticAnalysisResult:
    """Analyze source code semantics using AST extraction.

    This is the main entry point for semantic analysis. It parses Python
    source code into an AST and extracts entities (functions, classes,
    imports, constants) and relationships (imports, inherits, calls, defines).

    Args:
        content: Source code content to analyze.
        language: Programming language (e.g., "python"). Non-Python languages
            return a result with parse_ok=False.
        include_call_graph: Whether to extract function call relationships.
        include_import_graph: Whether to extract import relationships.

    Returns:
        SemanticAnalysisResult with all extraction data.

    Note:
        This function never throws exceptions. Parse errors and validation
        failures are returned in the result with parse_ok=False and
        appropriate warnings.

    Example:
        >>> result = analyze_semantics(
        ...     content="def foo(): pass",
        ...     language="python",
        ... )
        >>> result["success"]
        True
        >>> len(result["entities"]) >= 1
        True
    """
    start_time = time.perf_counter()
    warnings: list[str] = []

    # Validate inputs
    if not content or not content.strip():
        return _create_validation_error_result(
            "Content cannot be empty",
            start_time,
        )

    normalized_language = language.lower().strip()

    # Check if language is supported
    if normalized_language not in SUPPORTED_LANGUAGES:
        return _create_unsupported_language_result(
            normalized_language,
            start_time,
        )

    # Parse AST with error capture
    tree, parse_errors = _parse_python_ast(content)

    if tree is None:
        # Parsing failed completely
        return _create_parse_error_result(
            parse_errors,
            content,
            start_time,
        )

    # Add any non-fatal parse warnings
    warnings.extend(parse_errors)

    # Extract entities
    entities = _extract_entities(tree)

    # Extract relationships
    relations = _extract_relationships(
        tree=tree,
        entities=entities,
        include_call_graph=include_call_graph,
        include_import_graph=include_import_graph,
    )

    # Compute semantic features
    semantic_features = _compute_semantic_features(
        tree=tree,
        entities=entities,
        relations=relations,
        content=content,
        language=normalized_language,
    )

    # Build metadata
    processing_time_ms = (time.perf_counter() - start_time) * 1000
    metadata = SemanticAnalysisMetadataDict(
        processing_time_ms=round(processing_time_ms, 2),
        algorithm_version=ANALYSIS_VERSION_STR,
        parser_used="ast",
        input_length=len(content),
        input_line_count=len(content.splitlines()),
    )

    return SemanticAnalysisResult(
        success=True,
        parse_ok=True,
        entities=entities,
        relations=relations,
        warnings=warnings,
        semantic_features=semantic_features,
        metadata=metadata,
    )


# =============================================================================
# AST Parsing Functions (Pure)
# =============================================================================


def _parse_python_ast(content: str) -> tuple[ast.Module | None, list[str]]:
    """Parse Python source code into an AST.

    Args:
        content: Python source code to parse.

    Returns:
        Tuple of (ast.Module or None, list of error/warning messages).
        If parsing fails, returns (None, [error_message]).
    """
    errors: list[str] = []

    try:
        tree = ast.parse(content)
        return tree, errors
    except SyntaxError as e:
        error_msg = f"Syntax error at line {e.lineno}: {e.msg}"
        if e.text:
            error_msg += f" near '{e.text.strip()[:50]}'"
        return None, [error_msg]
    except ValueError as e:
        return None, [f"Value error during parsing: {e}"]
    except Exception as e:
        return None, [f"Unexpected parse error: {type(e).__name__}: {e}"]


# =============================================================================
# Entity Extraction Functions (Pure)
# =============================================================================


def _extract_entities(tree: ast.Module) -> list[EntityDict]:
    """Extract all entities from AST.

    Extracts functions, classes, imports, and module-level constants.

    Args:
        tree: Parsed AST module.

    Returns:
        List of EntityDict representing extracted entities.
    """
    entities: list[EntityDict] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            entity = _extract_function_entity(node)
            entities.append(entity)
        elif isinstance(node, ast.ClassDef):
            entity = _extract_class_entity(node)
            entities.append(entity)
        elif isinstance(node, ast.Import | ast.ImportFrom):
            import_entities = _extract_import_entities(node)
            entities.extend(import_entities)

    # Extract module-level constants (top-level assignments with UPPER_CASE names)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            constant_entities = _extract_constant_entities(node)
            entities.extend(constant_entities)
        elif isinstance(node, ast.AnnAssign):
            constant_entity = _extract_annotated_constant_entity(node)
            if constant_entity:
                entities.append(constant_entity)

    return entities


def _extract_function_entity(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> EntityDict:
    """Extract entity information from a function definition.

    Args:
        node: AST FunctionDef or AsyncFunctionDef node.

    Returns:
        EntityDict with function information.
    """
    # Extract decorators
    decorators = [_get_decorator_name(d) for d in node.decorator_list]

    # Extract docstring
    docstring = ast.get_docstring(node)

    # Build metadata
    # Extract argument information
    args = node.args
    arg_names = [arg.arg for arg in args.args]
    if args.vararg:
        arg_names.append(f"*{args.vararg.arg}")
    if args.kwarg:
        arg_names.append(f"**{args.kwarg.arg}")

    # Extract return type annotation if present
    return_type: str | None = None
    if node.returns:
        try:
            return_type = ast.unparse(node.returns)
        except Exception:
            return_type = None

    metadata: SemanticFunctionMetadata = {
        "is_async": isinstance(node, ast.AsyncFunctionDef),
        "arguments": arg_names,
    }
    if return_type is not None:
        metadata["return_type"] = return_type

    return EntityDict(
        name=node.name,
        entity_type="function",
        line_start=node.lineno,
        line_end=node.end_lineno or node.lineno,
        decorators=decorators,
        docstring=docstring,
        metadata=metadata,
    )


def _extract_class_entity(node: ast.ClassDef) -> EntityDict:
    """Extract entity information from a class definition.

    Args:
        node: AST ClassDef node.

    Returns:
        EntityDict with class information.
    """
    # Extract decorators
    decorators = [_get_decorator_name(d) for d in node.decorator_list]

    # Extract docstring
    docstring = ast.get_docstring(node)

    # Build metadata
    # Extract base classes
    bases = [_get_name_from_expr(base) for base in node.bases]

    # Extract method names
    methods = [
        n.name
        for n in node.body
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    ]

    metadata: SemanticClassMetadata = {
        "bases": [b for b in bases if b is not None],
        "methods": methods,
    }

    return EntityDict(
        name=node.name,
        entity_type="class",
        line_start=node.lineno,
        line_end=node.end_lineno or node.lineno,
        decorators=decorators,
        docstring=docstring,
        metadata=metadata,
    )


def _extract_import_entities(node: ast.Import | ast.ImportFrom) -> list[EntityDict]:
    """Extract entity information from import statements.

    Args:
        node: AST Import or ImportFrom node.

    Returns:
        List of EntityDict for each imported name.
    """
    entities: list[EntityDict] = []

    if isinstance(node, ast.Import):
        # `import foo` or `import foo as f`
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name
            import_meta: SemanticImportMetadata = {
                "source_module": alias.name,
            }
            if alias.asname:
                import_meta["alias"] = alias.asname
            entities.append(
                EntityDict(
                    name=name,
                    entity_type="import",
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    decorators=[],
                    docstring=None,
                    metadata=import_meta,
                )
            )
    elif isinstance(node, ast.ImportFrom):
        # `from foo import bar` or `from foo import bar as b`
        source_module = node.module or ""
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name
            from_import_meta: SemanticImportMetadata = {
                "source_module": source_module if source_module else None,
                "imported_name": alias.name,
            }
            if alias.asname:
                from_import_meta["alias"] = alias.asname
            entities.append(
                EntityDict(
                    name=name,
                    entity_type="import",
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    decorators=[],
                    docstring=None,
                    metadata=from_import_meta,
                )
            )

    return entities


def _extract_constant_entities(node: ast.Assign) -> list[EntityDict]:
    """Extract constant entities from assignment statements.

    Module-level assignments with UPPER_CASE names are considered constants.

    Args:
        node: AST Assign node.

    Returns:
        List of EntityDict for detected constants.
    """
    entities: list[EntityDict] = []

    for target in node.targets:
        if isinstance(target, ast.Name):
            # Check if name follows UPPER_CASE convention
            if target.id.isupper() or (
                "_" in target.id and target.id.replace("_", "").isupper()
            ):
                # Capture AST node type for value (safe, no evaluation)
                const_meta: SemanticConstantMetadata = {}
                if node.value:
                    const_meta["value_ast_type"] = node.value.__class__.__name__

                entities.append(
                    EntityDict(
                        name=target.id,
                        entity_type="constant",
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        decorators=[],
                        docstring=None,
                        metadata=const_meta,
                    )
                )

    return entities


def _extract_annotated_constant_entity(node: ast.AnnAssign) -> EntityDict | None:
    """Extract constant entity from annotated assignment.

    Module-level annotated assignments with UPPER_CASE names are constants.

    Args:
        node: AST AnnAssign node.

    Returns:
        EntityDict if this is a constant, None otherwise.
    """
    if isinstance(node.target, ast.Name):
        name = node.target.id
        # Check if name follows UPPER_CASE convention
        if name.isupper() or ("_" in name and name.replace("_", "").isupper()):
            const_meta: SemanticConstantMetadata = {}

            # Extract type annotation if present (unparse may fail on complex annotations)
            if node.annotation:
                with contextlib.suppress(Exception):
                    const_meta["type_annotation"] = ast.unparse(node.annotation)

            # Capture AST node type for value (safe, no evaluation)
            if node.value:
                const_meta["value_ast_type"] = node.value.__class__.__name__

            return EntityDict(
                name=name,
                entity_type="constant",
                line_start=node.lineno,
                line_end=node.end_lineno or node.lineno,
                decorators=[],
                docstring=None,
                metadata=const_meta,
            )

    return None


# =============================================================================
# Relationship Extraction Functions (Pure)
# =============================================================================


def _extract_relationships(
    tree: ast.Module,
    entities: list[EntityDict],
    include_call_graph: bool = True,
    include_import_graph: bool = True,
) -> list[RelationDict]:
    """Extract all relationships from AST.

    Args:
        tree: Parsed AST module.
        entities: Previously extracted entities (for context).
        include_call_graph: Whether to extract CALLS relationships.
        include_import_graph: Whether to extract IMPORTS relationships.

    Returns:
        List of RelationDict representing extracted relationships.
    """
    relations: list[RelationDict] = []

    # Extract IMPORTS relationships
    if include_import_graph:
        import_relations = _extract_import_relations(tree)
        relations.extend(import_relations)

    # Extract INHERITS relationships
    inherits_relations = _extract_inheritance_relations(tree)
    relations.extend(inherits_relations)

    # Extract CALLS relationships
    if include_call_graph:
        call_relations = _extract_call_relations(tree)
        relations.extend(call_relations)

    # Extract DEFINES relationships (file -> entity)
    defines_relations = _extract_defines_relations(entities)
    relations.extend(defines_relations)

    return relations


def _extract_import_relations(tree: ast.Module) -> list[RelationDict]:
    """Extract IMPORTS relationships from import statements.

    Args:
        tree: Parsed AST module.

    Returns:
        List of RelationDict for import relationships.
    """
    relations: list[RelationDict] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                relations.append(
                    RelationDict(
                        source=MODULE_SCOPE,
                        target=alias.name,
                        relation_type="imports",
                        confidence=CONFIDENCE_IMPORTS,
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                target = f"{module}.{alias.name}" if module else alias.name
                relations.append(
                    RelationDict(
                        source=MODULE_SCOPE,
                        target=target,
                        relation_type="imports",
                        confidence=CONFIDENCE_IMPORTS,
                    )
                )

    return relations


def _extract_inheritance_relations(tree: ast.Module) -> list[RelationDict]:
    """Extract INHERITS relationships from class definitions.

    Args:
        tree: Parsed AST module.

    Returns:
        List of RelationDict for inheritance relationships.
    """
    relations: list[RelationDict] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            for base in node.bases:
                base_name = _get_name_from_expr(base)
                if base_name:
                    relations.append(
                        RelationDict(
                            source=class_name,
                            target=base_name,
                            relation_type="inherits",
                            confidence=CONFIDENCE_INHERITS,
                        )
                    )

    return relations


def _extract_call_relations(tree: ast.Module) -> list[RelationDict]:
    """Extract CALLS relationships from function calls.

    Uses call frequency to adjust confidence scores. More frequent calls
    to the same target indicate stronger relationships.

    Args:
        tree: Parsed AST module.

    Returns:
        List of RelationDict for call relationships.
    """
    # Track calls per (caller, callee) pair with frequency
    call_counter: Counter[tuple[str, str]] = Counter()

    # Walk through all function/method definitions
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            caller_name = node.name
            # Find all calls within this function
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    callee_name = _get_call_target_name(child)
                    if callee_name and callee_name != caller_name:
                        call_counter[(caller_name, callee_name)] += 1

    # Convert to relations with frequency-adjusted confidence
    relations: list[RelationDict] = []
    for (caller, callee), frequency in call_counter.items():
        # Adjust confidence based on frequency (more calls = higher confidence)
        # Scale from 0.8 to 1.0 based on frequency
        frequency_factor = min(frequency / MAX_CALL_FREQUENCY, 1.0)
        confidence = CONFIDENCE_CALLS_BASE + (1.0 - CONFIDENCE_CALLS_BASE) * frequency_factor

        relations.append(
            RelationDict(
                source=caller,
                target=callee,
                relation_type="calls",
                confidence=round(confidence, 2),
            )
        )

    return relations


def _extract_defines_relations(entities: list[EntityDict]) -> list[RelationDict]:
    """Extract DEFINES relationships (file defines entities).

    Creates DEFINES relationships for entities that are defined by the module
    (functions, classes, constants). Import entities are excluded because their
    relationship to the module is already captured by IMPORTS relations.

    Args:
        entities: List of extracted entities.

    Returns:
        List of RelationDict for defines relationships.
    """
    relations: list[RelationDict] = []

    for entity in entities:
        # Skip imports - they have IMPORTS relations instead
        if entity["entity_type"] == "import":
            continue
        relations.append(
            RelationDict(
                source=MODULE_SCOPE,
                target=entity["name"],
                relation_type="defines",
                confidence=CONFIDENCE_DEFINES,
            )
        )

    return relations


def _get_name_from_expr(expr: ast.expr) -> str | None:
    """Get name string from an AST expression.

    Handles Name, Attribute, and Subscript nodes.

    Args:
        expr: AST expression node.

    Returns:
        Name string or None if not resolvable.
    """
    if isinstance(expr, ast.Name):
        return expr.id
    elif isinstance(expr, ast.Attribute):
        return ast.unparse(expr)
    elif isinstance(expr, ast.Subscript):
        # Handle Generic[T] style expressions
        return _get_name_from_expr(expr.value)

    return None


def _get_call_target_name(call: ast.Call) -> str | None:
    """Get the target function name from a Call node.

    Args:
        call: AST Call node.

    Returns:
        Target function name or None if not resolvable.
    """
    func = call.func

    if isinstance(func, ast.Name):
        return func.id
    elif isinstance(func, ast.Attribute):
        # For method calls like obj.method(), return the method name
        return func.attr

    return None


# =============================================================================
# Semantic Feature Computation Functions (Pure)
# =============================================================================


def _compute_semantic_features(
    tree: ast.Module,
    entities: list[EntityDict],
    relations: list[RelationDict],
    content: str,
    language: str,
) -> SemanticFeaturesDict:
    """Compute semantic features from extracted data.

    Args:
        tree: Parsed AST module.
        entities: Extracted entities.
        relations: Extracted relationships.
        content: Original source code.
        language: Source language.

    Returns:
        SemanticFeaturesDict with computed features.
    """
    # Count entities by type
    function_count = sum(1 for e in entities if e["entity_type"] == "function")
    class_count = sum(1 for e in entities if e["entity_type"] == "class")
    import_count = sum(1 for e in entities if e["entity_type"] == "import")

    # Count lines
    lines = content.splitlines()
    line_count = len([ln for ln in lines if ln.strip()])

    # Compute complexity score (based on control flow)
    complexity_score = _compute_complexity_score(tree)

    # Detect frameworks from import statements
    detected_frameworks = _detect_frameworks_from_imports(entities)

    # Detect patterns
    detected_patterns = _detect_patterns(tree, entities)

    # Infer code purpose
    code_purpose = _infer_code_purpose(entities, detected_frameworks)

    # Extract entity names
    entity_names = [e["name"] for e in entities]

    # Compute documentation ratio
    documentation_ratio = _compute_documentation_ratio(tree)

    # Compute test coverage indicator
    test_coverage_indicator = _compute_test_indicator(entities)

    return SemanticFeaturesDict(
        function_count=function_count,
        class_count=class_count,
        import_count=import_count,
        line_count=line_count,
        complexity_score=round(complexity_score, 2),
        primary_language=language,
        detected_frameworks=detected_frameworks,
        detected_patterns=detected_patterns,
        code_purpose=code_purpose,
        entity_names=entity_names,
        relationship_count=len(relations),
        documentation_ratio=round(documentation_ratio, 2),
        test_coverage_indicator=round(test_coverage_indicator, 2),
    )


def _compute_complexity_score(tree: ast.Module) -> float:
    """Compute a complexity score based on control flow.

    Higher score means MORE complex (inverted from quality scoring).

    Args:
        tree: Parsed AST module.

    Returns:
        Complexity score from 0.0 (simple) to 1.0 (complex).
    """
    complexity_count = 0
    function_count = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            function_count += 1
        elif isinstance(node, ast.If | ast.While | ast.For | ast.AsyncFor):
            complexity_count += 1
        elif isinstance(node, ast.BoolOp):
            complexity_count += len(node.values) - 1
        elif isinstance(node, ast.Try | ast.ExceptHandler | ast.comprehension):
            complexity_count += 1

    if function_count == 0:
        # No functions - use raw complexity capped at 20
        return min(complexity_count / 20.0, 1.0)

    # Average complexity per function, capped at 10
    avg_complexity = complexity_count / function_count
    return min(avg_complexity / 10.0, 1.0)


def _detect_frameworks_from_imports(entities: list[EntityDict]) -> list[str]:
    """Detect frameworks from import entities only.

    Uses import entity names and their source_module metadata for accurate detection.
    Does NOT scan raw content to avoid false positives from comments/strings.

    Args:
        entities: Extracted entities.

    Returns:
        List of detected framework names.
    """
    frameworks: list[str] = []

    # Collect all import-related names and modules from import entities
    import_names: set[str] = set()
    for e in entities:
        if e["entity_type"] == "import":
            import_names.add(e["name"].lower())
            metadata = e["metadata"]
            # source_module covers both `import x` and `from x import y` cases
            if source_module := metadata.get("source_module"):
                import_names.add(str(source_module).lower())
            # imported_name for `from x import y` (the `y` part)
            if imported_name := metadata.get("imported_name"):
                import_names.add(str(imported_name).lower())

    # Framework detection patterns
    framework_patterns: dict[str, list[str]] = {
        "fastapi": ["fastapi", "FastAPI"],
        "flask": ["flask", "Flask"],
        "django": ["django", "Django"],
        "pydantic": ["pydantic", "BaseModel", "Field"],
        "pytest": ["pytest", "fixture"],
        "asyncio": ["asyncio", "async_"],
        "sqlalchemy": ["sqlalchemy", "SQLAlchemy"],
        "requests": ["requests", "httpx"],
        "numpy": ["numpy", "np"],
        "pandas": ["pandas", "pd"],
    }

    for framework, patterns in framework_patterns.items():
        for pattern in patterns:
            if pattern.lower() in import_names:
                frameworks.append(framework)
                break

    return list(set(frameworks))


def _detect_patterns(tree: ast.Module, entities: list[EntityDict]) -> list[str]:
    """Detect design patterns from AST structure.

    Args:
        tree: Parsed AST module.
        entities: Extracted entities.

    Returns:
        List of detected pattern names.
    """
    patterns: list[str] = []

    # Check for singleton pattern (class with _instance attribute)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            attr_names = set()
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            attr_names.add(target.id)
                elif isinstance(item, ast.AnnAssign):
                    if isinstance(item.target, ast.Name):
                        attr_names.add(item.target.id)

            if "_instance" in attr_names:
                patterns.append("singleton")

    # Check for factory pattern (functions ending in _factory or Factory)
    for entity in entities:
        if entity["entity_type"] == "function":
            name_lower = entity["name"].lower()
            if "factory" in name_lower or name_lower.endswith("_create"):
                patterns.append("factory")
                break

    # Check for strategy pattern (multiple classes inheriting from common base)
    class_bases: Counter[str] = Counter()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                base_name = _get_name_from_expr(base)
                if base_name:
                    class_bases[base_name] += 1

    for base_class, count in class_bases.items():
        if count >= 2 and base_class not in ("object", "ABC", "BaseModel"):
            patterns.append("strategy")
            break

    return list(set(patterns))


def _infer_code_purpose(
    entities: list[EntityDict],
    frameworks: list[str],
) -> str:
    """Infer the purpose of the code from entities and frameworks.

    Args:
        entities: Extracted entities.
        frameworks: Detected frameworks.

    Returns:
        Inferred purpose string.
    """
    # Check for test code
    test_indicators = sum(
        1
        for e in entities
        if e["entity_type"] == "function" and e["name"].startswith("test_")
    )
    if test_indicators > 0 or "pytest" in frameworks:
        return "testing"

    # Check for API code
    if "fastapi" in frameworks or "flask" in frameworks or "django" in frameworks:
        return "web_api"

    # Check for data processing
    if "pandas" in frameworks or "numpy" in frameworks:
        return "data_processing"

    # Check for models/schemas
    model_count = sum(
        1
        for e in entities
        if e["entity_type"] == "class" and "model" in e["name"].lower()
    )
    if model_count > 0 or "pydantic" in frameworks:
        return "data_modeling"

    # Check for utility/helper code
    helper_indicators = sum(
        1
        for e in entities
        if e["entity_type"] == "function" and e["name"].startswith("_")
    )
    if helper_indicators > 0:
        return "utility"

    return "general"


def _compute_documentation_ratio(tree: ast.Module) -> float:
    """Compute ratio of documented entities to total.

    Args:
        tree: Parsed AST module.

    Returns:
        Documentation ratio from 0.0 to 1.0.
    """
    needs_docstring = 0
    has_docstring = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Module):
            needs_docstring += 1
            docstring = ast.get_docstring(node)
            if docstring:
                has_docstring += 1

    if needs_docstring == 0:
        return 0.0

    return has_docstring / needs_docstring


def _compute_test_indicator(entities: list[EntityDict]) -> float:
    """Compute indicator of test-related code presence.

    Detects both function-based tests (test_* prefix) and
    class-based tests (Test* prefix on classes).

    Args:
        entities: Extracted entities.

    Returns:
        Test indicator from 0.0 to 1.0.
    """
    total_functions = sum(1 for e in entities if e["entity_type"] == "function")
    total_classes = sum(1 for e in entities if e["entity_type"] == "class")

    if total_functions == 0 and total_classes == 0:
        return 0.0

    test_functions = sum(
        1
        for e in entities
        if e["entity_type"] == "function" and e["name"].startswith("test_")
    )
    test_classes = sum(
        1
        for e in entities
        if e["entity_type"] == "class" and e["name"].startswith("Test")
    )

    total_testable = total_functions + total_classes
    total_tests = test_functions + test_classes

    return min(total_tests / total_testable, 1.0) if total_testable > 0 else 0.0


# =============================================================================
# Error Result Factory Functions (Pure)
# =============================================================================


def _create_validation_error_result(
    error_message: str,
    start_time: float,
) -> SemanticAnalysisResult:
    """Create result for validation errors.

    Args:
        error_message: Description of the validation error.
        start_time: Start time for processing duration.

    Returns:
        SemanticAnalysisResult indicating validation failure.
    """
    processing_time_ms = (time.perf_counter() - start_time) * 1000

    return SemanticAnalysisResult(
        success=False,
        parse_ok=False,
        entities=[],
        relations=[],
        warnings=[f"Validation error: {error_message}"],
        semantic_features=create_empty_features(),
        metadata=SemanticAnalysisMetadataDict(
            processing_time_ms=round(processing_time_ms, 2),
            algorithm_version=ANALYSIS_VERSION_STR,
            parser_used="none",
            input_length=0,
            input_line_count=0,
        ),
    )


def _create_unsupported_language_result(
    language: str,
    start_time: float,
) -> SemanticAnalysisResult:
    """Create result for unsupported languages.

    Args:
        language: The unsupported language name.
        start_time: Start time for processing duration.

    Returns:
        SemanticAnalysisResult with unsupported language warning.
    """
    processing_time_ms = (time.perf_counter() - start_time) * 1000

    return SemanticAnalysisResult(
        success=True,  # Operation succeeded, just no analysis available
        parse_ok=False,
        entities=[],
        relations=[],
        warnings=[
            f"Unsupported language: '{language}'. Only Python is fully supported."
        ],
        semantic_features=SemanticFeaturesDict(
            primary_language=language,
            function_count=0,
            class_count=0,
            import_count=0,
            line_count=0,
            complexity_score=0.0,
            detected_frameworks=[],
            detected_patterns=[],
            code_purpose="unknown",
            entity_names=[],
            relationship_count=0,
            documentation_ratio=0.0,
            test_coverage_indicator=0.0,
        ),
        metadata=SemanticAnalysisMetadataDict(
            processing_time_ms=round(processing_time_ms, 2),
            algorithm_version=ANALYSIS_VERSION_STR,
            parser_used="none",
            input_length=0,
            input_line_count=0,
        ),
    )


def _create_parse_error_result(
    errors: list[str],
    content: str,
    start_time: float,
) -> SemanticAnalysisResult:
    """Create result for parse errors.

    Args:
        errors: List of parse error messages.
        content: Original source content.
        start_time: Start time for processing duration.

    Returns:
        SemanticAnalysisResult indicating parse failure.
    """
    processing_time_ms = (time.perf_counter() - start_time) * 1000

    return SemanticAnalysisResult(
        success=True,  # Operation completed, just couldn't parse
        parse_ok=False,
        entities=[],
        relations=[],
        warnings=errors,
        semantic_features=SemanticFeaturesDict(
            primary_language="python",
            function_count=0,
            class_count=0,
            import_count=0,
            line_count=len(content.splitlines()),
            complexity_score=0.0,
            detected_frameworks=[],
            detected_patterns=[],
            code_purpose="unknown",
            entity_names=[],
            relationship_count=0,
            documentation_ratio=0.0,
            test_coverage_indicator=0.0,
        ),
        metadata=SemanticAnalysisMetadataDict(
            processing_time_ms=round(processing_time_ms, 2),
            algorithm_version=ANALYSIS_VERSION_STR,
            parser_used="ast",
            input_length=len(content),
            input_line_count=len(content.splitlines()),
        ),
    )


__all__ = [
    "ANALYSIS_VERSION",
    "ANALYSIS_VERSION_STR",
    "analyze_semantics",
]
