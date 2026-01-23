"""Semantic Analysis Compute - Pure compute node for AST-based semantic analysis.

This node performs deterministic semantic analysis on Python source code using
the built-in ast module. It extracts entities (functions, classes, imports,
constants) and relationships (calls, imports, inherits, defines).

Key characteristics:
    - Pure computation: no HTTP calls, no LLM, no side effects
    - Deterministic: same input always produces same output
    - Never throws: parse errors return parse_ok=False with warnings
    - Python-only: other languages return empty results with warning
"""
from __future__ import annotations

import logging
from typing import Any, ClassVar, cast

logger = logging.getLogger(__name__)

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.semantic_analysis_compute.handlers import (
    ANALYSIS_VERSION_STR,
    EntityDict,
    RelationDict,
    analyze_semantics,
)
from omniintelligence.nodes.semantic_analysis_compute.models import (
    EnumSemanticEntityType,
    EnumSemanticRelationType,
    ModelSemanticAnalysisInput,
    ModelSemanticAnalysisOutput,
    ModelSemanticEntity,
    ModelSemanticRelation,
    SemanticAnalysisMetadataDict,
    SemanticFeaturesDict,
)


class NodeSemanticAnalysisCompute(NodeCompute[ModelSemanticAnalysisInput, ModelSemanticAnalysisOutput]):
    """Pure compute node for semantic analysis of code.

    This node performs AST-based semantic analysis on Python source code,
    extracting entities and relationships without any external dependencies.

    Attributes:
        is_stub: Class attribute indicating this is NOT a stub implementation.

    Features:
        - Extract functions, classes, imports, and constants as entities
        - Detect calls, imports, inheritance, and defines relationships
        - Compute semantic features (complexity, patterns, frameworks)
        - Handle parse errors gracefully with warnings

    Note:
        This node follows the declarative node pattern - no custom __init__ is needed.
        The base NodeCompute class handles initialization.
    """

    is_stub: ClassVar[bool] = False

    async def compute(
        self, input_data: ModelSemanticAnalysisInput
    ) -> ModelSemanticAnalysisOutput:
        """Compute semantic analysis on source code.

        Performs AST-based semantic analysis to extract entities and relationships
        from Python source code. The analysis is deterministic and never throws
        exceptions.

        Args:
            input_data: Typed input model containing code snippet and context.

        Returns:
            ModelSemanticAnalysisOutput with extracted entities, relations,
            semantic features, and metadata.
        """
        # Extract parameters from input
        content = input_data.code_snippet
        language = input_data.context.get("source_language", "python")

        # Call the pure handler function
        result = analyze_semantics(
            content=content,
            language=language,
            include_call_graph=True,
            include_import_graph=True,
        )

        # Convert handler TypedDicts to Pydantic models
        entities = [
            _convert_entity_dict_to_model(entity)
            for entity in result["entities"]
        ]
        relations = [
            _convert_relation_dict_to_model(relation)
            for relation in result["relations"]
        ]

        # Build metadata
        metadata: SemanticAnalysisMetadataDict = {
            "status": "completed",
            "algorithm_version": ANALYSIS_VERSION_STR,
            "processing_time_ms": result["metadata"].get("processing_time_ms", 0.0),
            "input_length": result["metadata"].get("input_length", len(content)),
            "input_line_count": result["metadata"].get("input_line_count", 0),
        }

        # Add correlation ID if provided in context
        correlation_id = input_data.context.get("correlation_id")
        if correlation_id:
            metadata["correlation_id"] = correlation_id

        return ModelSemanticAnalysisOutput(
            success=result["success"],
            parse_ok=result["parse_ok"],
            entities=entities,
            relations=relations,
            warnings=result["warnings"],
            # Cast handler's SemanticFeaturesDict to model's SemanticFeaturesDict
            # Both have identical fields but different total= settings
            semantic_features=cast(SemanticFeaturesDict, result["semantic_features"]),
            embeddings=[],  # Embeddings require external service, not handled here
            similarity_scores={},  # Similarity requires embeddings
            metadata=metadata,
        )


# =============================================================================
# Helper Functions (Pure)
# =============================================================================


def _convert_entity_dict_to_model(entity: EntityDict) -> ModelSemanticEntity:
    """Convert handler EntityDict to Pydantic ModelSemanticEntity.

    Args:
        entity: EntityDict from handler.

    Returns:
        ModelSemanticEntity Pydantic model.
    """
    # Map entity_type string to enum
    entity_type_str = entity["entity_type"]
    try:
        entity_type = EnumSemanticEntityType(entity_type_str)
    except ValueError:
        logger.warning(
            "Unknown entity type '%s' for entity '%s', defaulting to FUNCTION",
            entity_type_str,
            entity["name"],
        )
        entity_type = EnumSemanticEntityType.FUNCTION

    return ModelSemanticEntity(
        name=entity["name"],
        entity_type=entity_type,
        line_start=entity["line_start"],
        line_end=entity["line_end"],
        decorators=entity["decorators"],
        docstring=entity["docstring"],
        # Cast TypedDict union to dict[str, Any] for Pydantic model compatibility
        metadata=cast(dict[str, Any], entity["metadata"]),
    )


def _convert_relation_dict_to_model(relation: RelationDict) -> ModelSemanticRelation:
    """Convert handler RelationDict to Pydantic ModelSemanticRelation.

    Args:
        relation: RelationDict from handler.

    Returns:
        ModelSemanticRelation Pydantic model.
    """
    # Map relation_type string to enum
    relation_type_str = relation["relation_type"]
    try:
        relation_type = EnumSemanticRelationType(relation_type_str)
    except ValueError:
        logger.warning(
            "Unknown relation type '%s' for relation '%s' -> '%s', defaulting to REFERENCES",
            relation_type_str,
            relation["source"],
            relation["target"],
        )
        relation_type = EnumSemanticRelationType.REFERENCES

    return ModelSemanticRelation(
        source=relation["source"],
        target=relation["target"],
        relation_type=relation_type,
        confidence=relation["confidence"],
    )


__all__ = ["NodeSemanticAnalysisCompute"]
