# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Code entity model extracted from Python AST parsing."""

from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MethodDescriptor(TypedDict, total=False):
    """AST-derived method descriptor persisted as JSONB."""

    name: str
    args: list[str]
    return_type: str | None
    decorators: list[str]


class FieldDescriptor(TypedDict, total=False):
    """AST-derived Pydantic field descriptor persisted as JSONB."""

    name: str
    type: str | None
    default: str | None


class ModelCodeEntity(BaseModel):
    """A structural code entity extracted from a Python source file.

    Represents classes, protocols, Pydantic models, functions, imports,
    and module-level constants discovered via AST parsing.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        aliases = {
            "entity_id": "id",
            "name": "entity_name",
            "file_path": "source_path",
            "line_start": "line_number",
        }
        for legacy_key, canonical_key in aliases.items():
            if legacy_key in normalized and canonical_key not in normalized:
                normalized[canonical_key] = normalized.pop(legacy_key)
            else:
                normalized.pop(legacy_key, None)
        normalized.pop("line_end", None)
        normalized.pop("source_code", None)
        methods = normalized.get("methods")
        if isinstance(methods, list):
            normalized["methods"] = [
                {"name": method} if isinstance(method, str) else method
                for method in methods
            ]
        if "qualified_name" not in normalized and "entity_name" in normalized:
            source_path = str(normalized.get("source_path", "")).removesuffix(".py")
            module_name = source_path.replace("/", ".")
            normalized["qualified_name"] = (
                f"{module_name}.{normalized['entity_name']}"
                if module_name
                else str(normalized["entity_name"])
            )
        return normalized

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
    methods: list[MethodDescriptor] = Field(
        default_factory=list,
        description="Method descriptors: [{name, args, return_type, decorators}]",
    )
    fields: list[FieldDescriptor] = Field(
        default_factory=list,
        description="Field descriptors for models: [{name, type, default}]",
    )
    decorators: list[str] = Field(
        default_factory=list, description="Decorator expressions"
    )
    docstring: str | None = Field(default=None, description="Docstring of the entity")
    signature: str | None = Field(default=None, description="Function signature string")
    file_hash: str = Field(description="SHA256 hash of the source file")
    source_language: str = Field(
        default="python",
        description="Source language: python, typescript, javascript, etc.",
    )
    confidence: float = Field(
        default=1.0,
        description="Extraction confidence: 1.0 for AST, 0.7 for regex",
    )

    @property
    def entity_id(self) -> str:
        return self.id

    @property
    def name(self) -> str:
        return self.entity_name

    @property
    def file_path(self) -> str:
        return self.source_path

    @property
    def line_start(self) -> int | None:
        return self.line_number
