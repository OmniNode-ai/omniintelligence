# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Code entity model extracted from Python AST parsing."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ModelCodeEntity(BaseModel):
    """A structural code entity extracted from a Python source file.

    Represents classes, protocols, Pydantic models, functions, imports,
    and module-level constants discovered via AST parsing.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    id: str = Field(description="UUID identifying this entity")
    entity_name: str = Field(description="Simple name of the entity")
    entity_type: str = Field(
        description=(
            "Kind of entity: 'class', 'protocol', 'model', "
            "'function', 'import', 'constant'"
        )
    )
    qualified_name: str = Field(
        description="Fully qualified name, e.g. module.ClassName.method_name"
    )
    source_repo: str = Field(description="Repository the source file belongs to")
    source_path: str = Field(description="Path relative to repo root")
    line_number: int | None = Field(
        default=None, description="Line number in source file"
    )
    bases: list[str] = Field(
        default_factory=list, description="Base class names for classes"
    )
    methods: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Method descriptors: [{name, args, return_type, decorators}]",
    )
    fields: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Field descriptors for models: [{name, type, default}]",
    )
    decorators: list[str] = Field(
        default_factory=list, description="Decorator expressions"
    )
    docstring: str | None = Field(default=None, description="Docstring of the entity")
    signature: str | None = Field(default=None, description="Function signature string")
    file_hash: str = Field(description="SHA256 hash of the source file")
