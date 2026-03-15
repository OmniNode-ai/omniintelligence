# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Semantic Entity model for AST-based analysis."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_semantic_analysis_compute.models.enum_semantic_entity_type import (
    EnumSemanticEntityType,
)


class SemanticEntityMetadataDict(TypedDict, total=False):
    """Flattened typed metadata for all semantic entity types.

    Merges keys from SemanticFunctionMetadata, SemanticClassMetadata,
    SemanticImportMetadata, and SemanticConstantMetadata into a single
    TypedDict for Pydantic model compatibility. All fields are optional
    since each entity type populates a different subset.
    """

    # Function metadata
    is_async: bool
    arguments: list[str]
    return_type: str | None

    # Class metadata
    bases: list[str]
    methods: list[str]

    # Import metadata
    source_module: str | None
    imported_name: str | None
    alias: str | None

    # Constant/variable metadata
    type_annotation: str | None
    value_ast_type: str | None


class ModelSemanticEntity(BaseModel):
    """Represents a semantic entity extracted from code via AST analysis.

    An entity is a named code element such as a function, class, import,
    constant, variable, or decorator that has been identified during
    parsing of the source code.
    """

    name: str = Field(
        ...,
        min_length=1,
        description="Name of the entity (e.g., function name, class name)",
    )
    entity_type: EnumSemanticEntityType = Field(
        ...,
        description="Type of the semantic entity",
    )
    line_start: int = Field(
        ...,
        ge=1,
        description="Starting line number in source code (1-indexed)",
    )
    line_end: int = Field(
        ...,
        ge=1,
        description="Ending line number in source code (1-indexed)",
    )
    decorators: list[str] = Field(
        default_factory=list,
        description="List of decorator names applied to this entity",
    )
    docstring: str | None = Field(
        default=None,
        description="Docstring associated with this entity, if present",
    )
    metadata: SemanticEntityMetadataDict = Field(
        default_factory=lambda: SemanticEntityMetadataDict(),
        description="Typed metadata about the entity (e.g., arguments, return type)",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelSemanticEntity", "SemanticEntityMetadataDict"]
