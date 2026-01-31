"""Semantic Analysis Compute Handlers.

This module provides pure handler functions for semantic analysis operations.
Handlers implement the computation logic following the ONEX "pure shell pattern"
where nodes delegate to side-effect-free handler functions.

Handler Pattern:
    Each handler is a pure function that:
    - Accepts source code content and configuration parameters
    - Extracts semantic entities and relationships via AST analysis
    - Returns a typed SemanticAnalysisResult dictionary
    - Has no side effects (pure computation)

Semantic Analysis Components:
    - Entity Extraction: Functions, classes, variables, imports
    - Relationship Detection: Calls, inheritance, imports, usage
    - Feature Computation: Counts, ratios, complexity metrics
    - Pattern Detection: Design patterns, framework usage

Usage:
    from omniintelligence.nodes.node_semantic_analysis_compute.handlers import (
        analyze_semantics,
        SemanticAnalysisResult,
        EntityDict,
        RelationDict,
        SemanticFeaturesDict,
        create_error_result,
        create_empty_features,
    )

    result: SemanticAnalysisResult = analyze_semantics(
        content="class MyModel: ...",
        language="python",
    )

Example:
    >>> from omniintelligence.nodes.node_semantic_analysis_compute.handlers import (
    ...     analyze_semantics,
    ...     create_error_result,
    ...     create_empty_features,
    ... )
    >>> result = analyze_semantics("def foo(): pass")
    >>> result["success"]
    True
    >>> len(result["entities"]) >= 1
    True
    >>> result = create_error_result("Test error")
    >>> result["success"]
    False
    >>> features = create_empty_features()
    >>> features["function_count"]
    0
"""

from omniintelligence.nodes.node_semantic_analysis_compute.handlers.exceptions import (
    SemanticAnalysisComputeError,
    SemanticAnalysisParseError,
    SemanticAnalysisValidationError,
)
from omniintelligence.nodes.node_semantic_analysis_compute.handlers.handler_compute_semantic_analysis import (
    compute_semantic_analysis,
)
from omniintelligence.nodes.node_semantic_analysis_compute.handlers.handler_semantic_analysis import (
    ANALYSIS_VERSION,
    ANALYSIS_VERSION_STR,
    analyze_semantics,
)
from omniintelligence.nodes.node_semantic_analysis_compute.handlers.protocols import (
    EntityDict,
    RelationDict,
    SemanticAnalysisMetadataDict,
    SemanticAnalysisResult,
    SemanticClassMetadata,
    SemanticConstantMetadata,
    SemanticEntityMetadata,
    SemanticFeaturesDict,
    SemanticFunctionMetadata,
    SemanticImportMetadata,
    create_empty_features,
    create_error_result,
)

__all__ = [
    "ANALYSIS_VERSION",
    "ANALYSIS_VERSION_STR",
    "EntityDict",
    "RelationDict",
    "SemanticAnalysisComputeError",
    "SemanticAnalysisMetadataDict",
    "SemanticAnalysisParseError",
    "SemanticAnalysisResult",
    "SemanticAnalysisValidationError",
    "SemanticClassMetadata",
    "SemanticConstantMetadata",
    "SemanticEntityMetadata",
    "SemanticFeaturesDict",
    "SemanticFunctionMetadata",
    "SemanticImportMetadata",
    "analyze_semantics",
    "compute_semantic_analysis",
    "create_empty_features",
    "create_error_result",
]
