"""Semantic entity type enum for code analysis."""

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


__all__ = ["EnumSemanticEntityType"]
