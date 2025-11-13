"""
Unified Entity Type System for Archon Services

Provides a standardized EntityType enum and mapping utilities to handle
cross-service communication while maintaining backwards compatibility.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Union


class EntityType(str, Enum):
    """
    Unified entity type system for all Archon services.

    This serves as the single source of truth for entity types across
    the intelligence, search, bridge, and MCP services.
    """

    # Document and Content Types
    DOCUMENT = "document"
    PAGE = "page"
    CODE_EXAMPLE = "code_example"

    # Project Management Types
    PROJECT = "project"
    TASK = "task"
    SOURCE = "source"

    # Code Structure Types
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    MODULE = "module"
    INTERFACE = "interface"
    COMPONENT = "component"

    # System Types
    API_ENDPOINT = "api_endpoint"
    SERVICE = "service"
    CONFIG_SETTING = "config_setting"

    # Knowledge Types
    CONCEPT = "concept"
    PATTERN = "pattern"
    VARIABLE = "variable"
    CONSTANT = "constant"

    # Generic fallback
    ENTITY = "entity"


class IntelligenceEntityType(str, Enum):
    """Legacy intelligence service entity types (UPPERCASE)."""

    FUNCTION = "FUNCTION"
    CLASS = "CLASS"
    METHOD = "METHOD"
    MODULE = "MODULE"
    INTERFACE = "INTERFACE"
    API_ENDPOINT = "API_ENDPOINT"
    SERVICE = "SERVICE"
    COMPONENT = "COMPONENT"
    CONCEPT = "CONCEPT"
    DOCUMENT = "DOCUMENT"
    CODE_EXAMPLE = "CODE_EXAMPLE"
    PATTERN = "PATTERN"
    VARIABLE = "VARIABLE"
    CONSTANT = "CONSTANT"
    CONFIG_SETTING = "CONFIG_SETTING"


class SearchEntityType(str, Enum):
    """Legacy search service entity types (lowercase)."""

    SOURCE = "source"
    PAGE = "page"
    CODE_EXAMPLE = "code_example"
    PROJECT = "project"
    ENTITY = "entity"


# Mapping dictionaries for entity type conversion
UNIFIED_TO_INTELLIGENCE: Dict[EntityType, IntelligenceEntityType] = {
    EntityType.FUNCTION: IntelligenceEntityType.FUNCTION,
    EntityType.CLASS: IntelligenceEntityType.CLASS,
    EntityType.METHOD: IntelligenceEntityType.METHOD,
    EntityType.MODULE: IntelligenceEntityType.MODULE,
    EntityType.INTERFACE: IntelligenceEntityType.INTERFACE,
    EntityType.API_ENDPOINT: IntelligenceEntityType.API_ENDPOINT,
    EntityType.SERVICE: IntelligenceEntityType.SERVICE,
    EntityType.COMPONENT: IntelligenceEntityType.COMPONENT,
    EntityType.CONCEPT: IntelligenceEntityType.CONCEPT,
    EntityType.DOCUMENT: IntelligenceEntityType.DOCUMENT,
    EntityType.CODE_EXAMPLE: IntelligenceEntityType.CODE_EXAMPLE,
    EntityType.PATTERN: IntelligenceEntityType.PATTERN,
    EntityType.VARIABLE: IntelligenceEntityType.VARIABLE,
    EntityType.CONSTANT: IntelligenceEntityType.CONSTANT,
    EntityType.CONFIG_SETTING: IntelligenceEntityType.CONFIG_SETTING,
}

# Mapping from unified EntityType to legacy SearchEntityType
UNIFIED_TO_SEARCH: Dict[EntityType, SearchEntityType] = {
    EntityType.SOURCE: SearchEntityType.SOURCE,
    EntityType.PAGE: SearchEntityType.PAGE,
    EntityType.DOCUMENT: SearchEntityType.PAGE,  # Documents map to pages in search
    EntityType.CODE_EXAMPLE: SearchEntityType.CODE_EXAMPLE,
    EntityType.PROJECT: SearchEntityType.PROJECT,
    # All other types map to generic ENTITY
    EntityType.FUNCTION: SearchEntityType.ENTITY,
    EntityType.CLASS: SearchEntityType.ENTITY,
    EntityType.METHOD: SearchEntityType.ENTITY,
    EntityType.MODULE: SearchEntityType.ENTITY,
    EntityType.INTERFACE: SearchEntityType.ENTITY,
    EntityType.API_ENDPOINT: SearchEntityType.ENTITY,
    EntityType.SERVICE: SearchEntityType.ENTITY,
    EntityType.COMPONENT: SearchEntityType.ENTITY,
    EntityType.CONCEPT: SearchEntityType.ENTITY,
    EntityType.PATTERN: SearchEntityType.ENTITY,
    EntityType.VARIABLE: SearchEntityType.ENTITY,
    EntityType.CONSTANT: SearchEntityType.ENTITY,
    EntityType.CONFIG_SETTING: SearchEntityType.ENTITY,
    EntityType.TASK: SearchEntityType.ENTITY,
    EntityType.ENTITY: SearchEntityType.ENTITY,
}

# Reverse mapping from IntelligenceEntityType to unified EntityType
INTELLIGENCE_TO_UNIFIED: Dict[IntelligenceEntityType, EntityType] = {
    v: k for k, v in UNIFIED_TO_INTELLIGENCE.items()
}

# Reverse mapping from SearchEntityType to unified EntityType
SEARCH_TO_UNIFIED: Dict[SearchEntityType, EntityType] = {
    SearchEntityType.SOURCE: EntityType.SOURCE,
    SearchEntityType.PAGE: EntityType.PAGE,  # Could be PAGE or DOCUMENT
    SearchEntityType.CODE_EXAMPLE: EntityType.CODE_EXAMPLE,
    SearchEntityType.PROJECT: EntityType.PROJECT,
    SearchEntityType.ENTITY: EntityType.ENTITY,
}


class EntityTypeMapper:
    """
    Utility class for mapping between different entity type systems.

    Handles conversion between the unified EntityType and legacy service-specific
    entity types to maintain backwards compatibility during transition.
    """

    @classmethod
    def to_intelligence_type(cls, unified_type: EntityType) -> IntelligenceEntityType:
        """Convert unified EntityType to IntelligenceEntityType."""
        return UNIFIED_TO_INTELLIGENCE.get(unified_type, IntelligenceEntityType.CONCEPT)

    @classmethod
    def to_search_type(cls, unified_type: EntityType) -> SearchEntityType:
        """Convert unified EntityType to SearchEntityType."""
        return UNIFIED_TO_SEARCH.get(unified_type, SearchEntityType.ENTITY)

    @classmethod
    def from_intelligence_type(
        cls, intelligence_type: IntelligenceEntityType
    ) -> EntityType:
        """Convert IntelligenceEntityType to unified EntityType."""
        return INTELLIGENCE_TO_UNIFIED.get(intelligence_type, EntityType.ENTITY)

    @classmethod
    def from_search_type(cls, search_type: SearchEntityType) -> EntityType:
        """Convert SearchEntityType to unified EntityType."""
        return SEARCH_TO_UNIFIED.get(search_type, EntityType.ENTITY)

    @classmethod
    def auto_convert(
        cls,
        entity_type: Union[str, EntityType, IntelligenceEntityType, SearchEntityType],
    ) -> EntityType:
        """
        Automatically convert any entity type string or enum to unified EntityType.

        Args:
            entity_type: String or enum representing an entity type

        Returns:
            Unified EntityType

        Raises:
            ValueError: If the entity type cannot be converted
        """
        if isinstance(entity_type, EntityType):
            return entity_type

        if isinstance(entity_type, IntelligenceEntityType):
            return cls.from_intelligence_type(entity_type)

        if isinstance(entity_type, SearchEntityType):
            return cls.from_search_type(entity_type)

        if isinstance(entity_type, str):
            # Try unified EntityType first
            try:
                return EntityType(entity_type.lower())
            except ValueError:
                pass

            # Try IntelligenceEntityType
            try:
                intelligence_type = IntelligenceEntityType(entity_type.upper())
                return cls.from_intelligence_type(intelligence_type)
            except ValueError:
                pass

            # Try SearchEntityType
            try:
                search_type = SearchEntityType(entity_type.lower())
                return cls.from_search_type(search_type)
            except ValueError:
                pass

        raise ValueError(f"Cannot convert '{entity_type}' to unified EntityType")


# Utility functions for backward compatibility
def normalize_entity_type(
    entity_type: Union[str, EntityType, IntelligenceEntityType, SearchEntityType],
) -> EntityType:
    """Normalize any entity type to unified EntityType."""
    return EntityTypeMapper.auto_convert(entity_type)


def to_service_entity_type(
    unified_type: EntityType, service: str
) -> Union[EntityType, IntelligenceEntityType, SearchEntityType]:
    """
    Convert unified EntityType to service-specific type.

    Args:
        unified_type: Unified entity type
        service: Target service name ('intelligence', 'search', or 'unified')

    Returns:
        Service-specific entity type
    """
    if service.lower() == "intelligence":
        return EntityTypeMapper.to_intelligence_type(unified_type)
    elif service.lower() == "search":
        return EntityTypeMapper.to_search_type(unified_type)
    else:
        return unified_type
