"""
Entity and relationship type enums for omniintelligence.

Contains entity types and relationship types for knowledge graph.
"""

from enum import Enum


class EnumEntityType(str, Enum):
    """Entity types for knowledge graph."""
    DOCUMENT = "DOCUMENT"
    CLASS = "CLASS"
    FUNCTION = "FUNCTION"
    MODULE = "MODULE"
    PACKAGE = "PACKAGE"
    VARIABLE = "VARIABLE"
    CONSTANT = "CONSTANT"
    INTERFACE = "INTERFACE"
    TYPE = "TYPE"
    PATTERN = "PATTERN"
    PROJECT = "PROJECT"
    FILE = "FILE"
    DEPENDENCY = "DEPENDENCY"
    TEST = "TEST"
    CONFIGURATION = "CONFIGURATION"


class EnumRelationshipType(str, Enum):
    """Relationship types for knowledge graph."""
    CONTAINS = "CONTAINS"
    IMPORTS = "IMPORTS"
    DEPENDS_ON = "DEPENDS_ON"
    IMPLEMENTS = "IMPLEMENTS"
    EXTENDS = "EXTENDS"
    CALLS = "CALLS"
    REFERENCES = "REFERENCES"
    DEFINES = "DEFINES"
    USES = "USES"
    MATCHES_PATTERN = "MATCHES_PATTERN"
    SIMILAR_TO = "SIMILAR_TO"


__all__ = [
    "EnumEntityType",
    "EnumRelationshipType",
]
