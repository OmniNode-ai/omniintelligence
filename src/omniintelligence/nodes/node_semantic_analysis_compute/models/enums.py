"""Enums for Semantic Analysis Compute Node."""

from __future__ import annotations

from enum import Enum


class EnumSemanticEntityType(str, Enum):
    """Types of semantic entities extracted from code.

    Represents the different kinds of code elements that can be
    identified during AST-based semantic analysis.
    """

    FUNCTION = "function"
    CLASS = "class"
    IMPORT = "import"
    CONSTANT = "constant"
    VARIABLE = "variable"
    DECORATOR = "decorator"


class EnumSemanticRelationType(str, Enum):
    """Types of semantic relations between entities.

    Represents the different kinds of relationships that can exist
    between code entities in the semantic graph.
    """

    IMPORTS = "imports"
    DEFINES = "defines"
    CALLS = "calls"
    INHERITS = "inherits"
    REFERENCES = "references"
    IMPLEMENTS = "implements"


__all__ = [
    "EnumSemanticEntityType",
    "EnumSemanticRelationType",
]
