"""Semantic relation type enum for code analysis."""

from __future__ import annotations

from enum import Enum


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


__all__ = ["EnumSemanticRelationType"]
