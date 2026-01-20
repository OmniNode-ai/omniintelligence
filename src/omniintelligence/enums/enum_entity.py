"""Entity and relationship type enums for OmniIntelligence.

Canonical entity types and relationship types for knowledge graph operations.
"""

from enum import Enum


class EnumEntityType(str, Enum):
    """Entity types for knowledge graph.

    These types categorize code and document entities for analysis,
    storage in vector databases, and graph relationships.
    """

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
    """Relationship types for knowledge graph.

    These types define the edges between entities in the knowledge graph,
    enabling traversal and relationship-based queries.
    """

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
