"""Handler for semantic analysis compute node.

This module provides the main handler function for semantic analysis computation.
It bridges the pure analyze_semantics function (which returns TypedDicts) to the
node's Pydantic input/output models.

Design Decisions:
    - All error handling and logging is contained in this handler
    - The node becomes a thin shell that delegates to this handler
    - Enum conversion failures use safe defaults with warnings (not exceptions)
    - Handler owns all business logic, node owns only delegation

Usage:
    from omniintelligence.nodes.node_semantic_analysis_compute.handlers import (
        handle_semantic_analysis_compute,
    )

    output = handle_semantic_analysis_compute(input_data)
"""

from __future__ import annotations

import logging
from typing import Any, cast  # any-ok: cast to dict[str, Any] needed for Pydantic model compatibility with TypedDict

from omniintelligence.nodes.node_semantic_analysis_compute.handlers.handler_semantic_analysis import (
    ANALYSIS_VERSION_STR,
    analyze_semantics,
)
from omniintelligence.nodes.node_semantic_analysis_compute.handlers.protocols import (
    EntityDict,
    RelationDict,
)
from omniintelligence.nodes.node_semantic_analysis_compute.models import (
    EnumSemanticEntityType,
    EnumSemanticRelationType,
    ModelSemanticAnalysisInput,
    ModelSemanticAnalysisOutput,
    ModelSemanticEntity,
    ModelSemanticRelation,
    SemanticAnalysisMetadataDict,
    SemanticFeaturesDict,
)

logger = logging.getLogger(__name__)


def handle_semantic_analysis_compute(
    input_data: ModelSemanticAnalysisInput,
) -> ModelSemanticAnalysisOutput:
    """Compute semantic analysis from input and return typed output.

    This is the main handler function for semantic analysis. It:
    1. Extracts parameters from the input model
    2. Calls the pure analyze_semantics function
    3. Converts TypedDict results to Pydantic models
    4. Handles all error cases with logging

    Args:
        input_data: Typed input model containing code snippet and context.

    Returns:
        ModelSemanticAnalysisOutput with extracted entities, relations,
        semantic features, and metadata.

    Note:
        This function handles all error cases internally. Unknown enum values
        are mapped to safe defaults with warnings logged.
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
    entities = [_convert_entity_dict_to_model(entity) for entity in result["entities"]]
    relations = [
        _convert_relation_dict_to_model(relation) for relation in result["relations"]
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


def _convert_entity_dict_to_model(entity: EntityDict) -> ModelSemanticEntity:
    """Convert handler EntityDict to Pydantic ModelSemanticEntity.

    Args:
        entity: EntityDict from handler.

    Returns:
        ModelSemanticEntity Pydantic model.

    Note:
        Unknown entity types are mapped to FUNCTION with a warning logged.
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

    Note:
        Unknown relation types are mapped to REFERENCES with a warning logged.
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


__all__ = ["handle_semantic_analysis_compute"]
