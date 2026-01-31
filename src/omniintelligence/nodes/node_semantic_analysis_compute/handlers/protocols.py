"""Type protocols for semantic analysis handler results.

This module defines TypedDict structures for type-safe handler responses,
enabling static type checking with mypy and improved IDE support.

Design Decisions:
    - TypedDict is used because handlers return dicts, not objects with methods.
    - EntityDict and RelationDict provide typed structures for extracted elements.
    - SemanticAnalysisResult matches the output model shape for direct mapping.
    - Factory functions provide safe defaults for error cases.

Usage:
    from omniintelligence.nodes.node_semantic_analysis_compute.handlers.protocols import (
        EntityDict,
        RelationDict,
        SemanticAnalysisResult,
        create_error_result,
        create_empty_features,
    )

    def analyze_semantics(...) -> SemanticAnalysisResult:
        return {
            "success": True,
            "parse_ok": True,
            "entities": [...],
            "relations": [...],
            ...
        }
"""

from __future__ import annotations

from typing import NotRequired, TypedDict


# =============================================================================
# Semantic Entity Metadata TypedDicts
# =============================================================================
# These TypedDicts define the metadata structure for each entity type.
# Using Semantic* prefix to avoid collisions with other entity types
# (runtime, registry, memory entities, etc.).


class SemanticFunctionMetadata(TypedDict):
    """Metadata specific to function entities.

    Required fields are always populated by the handler.
    Optional fields use NotRequired for cases where data may not exist.

    Attributes:
        is_async: Whether the function is async (always determined).
        arguments: List of argument names (always extracted, may be empty).
        return_type: Return type annotation string, if present in source.
    """

    is_async: bool
    arguments: list[str]
    return_type: NotRequired[str | None]


class SemanticClassMetadata(TypedDict):
    """Metadata specific to class entities.

    All fields are required and always populated (may be empty lists).

    Attributes:
        bases: List of base class names (empty if no explicit inheritance).
        methods: List of method names defined in the class body.
    """

    bases: list[str]
    methods: list[str]


class SemanticImportMetadata(TypedDict):
    """Metadata specific to import entities.

    Captures the structure of Python import statements.
    Fields are optional because different import forms populate different fields.

    Import forms and their metadata:
        - `import foo`         → source_module="foo", alias=None
        - `import foo as f`    → source_module="foo", alias="f"
        - `from foo import bar` → source_module="foo", imported_name="bar"
        - `from foo import bar as b` → source_module="foo", imported_name="bar", alias="b"

    Attributes:
        source_module: The module being imported or imported from.
        imported_name: The specific name being imported (for 'from' imports).
        alias: The alias if 'as X' was used.
    """

    source_module: NotRequired[str | None]
    imported_name: NotRequired[str | None]
    alias: NotRequired[str | None]


class SemanticConstantMetadata(TypedDict):
    """Metadata specific to constant/variable entities.

    Both fields are optional as they depend on source code annotations.

    Attributes:
        type_annotation: Type annotation string if present (e.g., "int", "Final[str]").
        value_ast_type: AST node type of the value (e.g., "Constant", "List", "Call").
    """

    type_annotation: NotRequired[str | None]
    value_ast_type: NotRequired[str | None]


# Union of all semantic entity metadata types
SemanticEntityMetadata = (
    SemanticFunctionMetadata
    | SemanticClassMetadata
    | SemanticImportMetadata
    | SemanticConstantMetadata
)


class EntityDict(TypedDict):
    """Entity extraction result.

    Represents a named entity extracted from source code.

    Attributes:
        name: The entity name (e.g., function name, class name, variable).
        entity_type: The type of entity (e.g., "function", "class", "variable", "import").
        line_start: Starting line number in source code (1-indexed).
        line_end: Ending line number in source code (1-indexed).
        decorators: List of decorator names applied to this entity.
        docstring: Docstring associated with this entity, if present.
        metadata: Additional metadata about the entity (e.g., is_async, bases, arguments).
    """

    name: str
    entity_type: str
    line_start: int
    line_end: int
    decorators: list[str]
    docstring: str | None
    metadata: SemanticEntityMetadata


class RelationDict(TypedDict):
    """Relationship extraction result.

    Represents a relationship between two entities in the code.

    Attributes:
        source: The source entity name.
        target: The target entity name.
        relation_type: The type of relationship (e.g., "calls", "inherits", "imports", "uses").
        confidence: Confidence score for the relationship (0.0-1.0).
    """

    source: str
    target: str
    relation_type: str
    confidence: float


class SemanticFeaturesDict(TypedDict):
    """Typed structure for extracted semantic features.

    Contains the semantic features extracted from code analysis.
    All fields are required (total=True by default).

    Attributes:
        function_count: Number of function definitions.
        class_count: Number of class definitions.
        import_count: Number of import statements.
        line_count: Total lines of code (non-empty).
        complexity_score: Computed complexity score (0.0-1.0).
        primary_language: Detected or specified source language.
        detected_frameworks: List of detected framework names.
        detected_patterns: List of detected design pattern names.
        code_purpose: Inferred purpose of the code.
        entity_names: List of all entity names extracted.
        relationship_count: Total number of relationships detected.
        documentation_ratio: Ratio of documented to total entities (0.0-1.0).
        test_coverage_indicator: Indicator of test-related code presence (0.0-1.0).
    """

    function_count: int
    class_count: int
    import_count: int
    line_count: int
    complexity_score: float
    primary_language: str
    detected_frameworks: list[str]
    detected_patterns: list[str]
    code_purpose: str
    entity_names: list[str]
    relationship_count: int
    documentation_ratio: float
    test_coverage_indicator: float


class SemanticAnalysisMetadataDict(TypedDict, total=False):
    """Typed structure for semantic analysis metadata.

    Contains information about the analysis operation.
    With total=False, all fields are optional.

    Attributes:
        processing_time_ms: Time taken for analysis in milliseconds.
        algorithm_version: Version of the analysis algorithm.
        parser_used: Name of the parser used (e.g., "ast", "tree-sitter").
        input_length: Length of input code in characters.
        input_line_count: Number of lines in input.
        correlation_id: Request correlation ID for tracing.
        timestamp_utc: UTC timestamp of analysis.
    """

    processing_time_ms: float
    algorithm_version: str
    parser_used: str
    input_length: int
    input_line_count: int
    correlation_id: str
    timestamp_utc: str


class SemanticAnalysisResult(TypedDict):
    """Result structure for semantic analysis handler.

    This TypedDict defines the guaranteed structure returned by
    the analyze_semantics function.

    All Attributes are Required:
        success: Whether the analysis completed without errors.
        parse_ok: Whether AST parsing succeeded (may be False with partial results).
        entities: List of extracted entities using EntityDict.
        relations: List of extracted relationships using RelationDict.
        warnings: List of non-fatal warnings encountered during analysis.
        semantic_features: Extracted semantic features using SemanticFeaturesDict.
        metadata: Analysis metadata using SemanticAnalysisMetadataDict.

    Example:
        >>> result: SemanticAnalysisResult = {
        ...     "success": True,
        ...     "parse_ok": True,
        ...     "entities": [
        ...         {"name": "MyClass", "entity_type": "class", "line_number": 1, "scope": "module"},
        ...         {"name": "my_func", "entity_type": "function", "line_number": 5, "scope": "class:MyClass"},
        ...     ],
        ...     "relations": [
        ...         {"source": "my_func", "target": "helper", "relation_type": "calls", "confidence": 1.0},
        ...     ],
        ...     "warnings": [],
        ...     "semantic_features": {
        ...         "function_count": 2,
        ...         "class_count": 1,
        ...         "primary_language": "python",
        ...     },
        ...     "metadata": {
        ...         "algorithm_version": "1.0.0",
        ...         "parser_used": "ast",
        ...     },
        ... }
    """

    success: bool
    parse_ok: bool
    entities: list[EntityDict]
    relations: list[RelationDict]
    warnings: list[str]
    semantic_features: SemanticFeaturesDict
    metadata: SemanticAnalysisMetadataDict


def create_empty_features() -> SemanticFeaturesDict:
    """Create empty semantic features for error or empty cases.

    Returns a valid SemanticFeaturesDict with default values,
    suitable for use when analysis fails or produces no results.

    Returns:
        SemanticFeaturesDict with minimal default values.
    """
    return SemanticFeaturesDict(
        function_count=0,
        class_count=0,
        import_count=0,
        line_count=0,
        complexity_score=0.0,
        primary_language="unknown",
        detected_frameworks=[],
        detected_patterns=[],
        code_purpose="unknown",
        entity_names=[],
        relationship_count=0,
        documentation_ratio=0.0,
        test_coverage_indicator=0.0,
    )


def create_error_result(
    error_message: str,
    *,
    parse_ok: bool = False,
    algorithm_version: str = "1.0.0",
) -> SemanticAnalysisResult:
    """Create an error result for failed analysis.

    Factory function that creates a valid SemanticAnalysisResult
    indicating failure, suitable for returning from handlers when
    validation or computation fails.

    Args:
        error_message: Description of the error (added to warnings).
        parse_ok: Whether parsing succeeded before the error.
        algorithm_version: Version string for metadata.

    Returns:
        SemanticAnalysisResult with success=False and empty data.

    Example:
        >>> result = create_error_result("Syntax error at line 5")
        >>> result["success"]
        False
        >>> result["warnings"]
        ['Syntax error at line 5']
    """
    return SemanticAnalysisResult(
        success=False,
        parse_ok=parse_ok,
        entities=[],
        relations=[],
        warnings=[error_message],
        semantic_features=create_empty_features(),
        metadata=SemanticAnalysisMetadataDict(
            algorithm_version=algorithm_version,
            parser_used="none",
        ),
    )


__all__ = [
    "EntityDict",
    "RelationDict",
    "SemanticAnalysisMetadataDict",
    "SemanticAnalysisResult",
    "SemanticClassMetadata",
    "SemanticConstantMetadata",
    "SemanticEntityMetadata",
    "SemanticFeaturesDict",
    "SemanticFunctionMetadata",
    "SemanticImportMetadata",
    "create_empty_features",
    "create_error_result",
]
