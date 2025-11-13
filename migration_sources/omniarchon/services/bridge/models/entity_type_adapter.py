"""
Entity Type Adapter for Bridge Service

Provides mapping between bridge service EntityType and the unified EntityType system.
This ensures compatibility until the container can be properly updated.
"""

from enum import Enum
from typing import Any, List


class LegacyBridgeEntityType(str, Enum):
    """Legacy bridge service entity types"""

    SOURCE = "source"
    PROJECT = "project"
    PAGE = "page"
    CODE_EXAMPLE = "code_example"
    TASK = "task"
    DOCUMENT = "document"


# Try to import unified EntityType, fall back to legacy if not available
try:
    import os
    import sys

    sys.path.insert(
        0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared", "models")
    )
    from entity_types import EntityType as UnifiedEntityType

    UNIFIED_TYPES_AVAILABLE = True
except ImportError:
    # Fallback: Create a compatible unified type locally
    class UnifiedEntityType(str, Enum):
        """Fallback unified entity type for bridge service"""

        SOURCE = "source"
        PROJECT = "project"
        PAGE = "page"
        CODE_EXAMPLE = "code_example"
        TASK = "task"
        DOCUMENT = "document"
        # Additional types for compatibility
        FUNCTION = "function"
        CLASS = "class"
        METHOD = "method"
        MODULE = "module"
        INTERFACE = "interface"
        COMPONENT = "component"
        API_ENDPOINT = "api_endpoint"
        SERVICE = "service"
        CONFIG_SETTING = "config_setting"
        CONCEPT = "concept"
        PATTERN = "pattern"
        VARIABLE = "variable"
        CONSTANT = "constant"
        ENTITY = "entity"

    UNIFIED_TYPES_AVAILABLE = False


class BridgeEntityTypeAdapter:
    """Adapter for converting between bridge and unified entity types."""

    @staticmethod
    def legacy_to_unified(legacy_type: LegacyBridgeEntityType) -> UnifiedEntityType:
        """Convert legacy bridge EntityType to unified EntityType."""
        # Direct mapping since they use the same string values
        mapping = {
            LegacyBridgeEntityType.SOURCE: UnifiedEntityType.SOURCE,
            LegacyBridgeEntityType.PROJECT: UnifiedEntityType.PROJECT,
            LegacyBridgeEntityType.PAGE: UnifiedEntityType.PAGE,
            LegacyBridgeEntityType.CODE_EXAMPLE: UnifiedEntityType.CODE_EXAMPLE,
            LegacyBridgeEntityType.TASK: UnifiedEntityType.TASK,
            LegacyBridgeEntityType.DOCUMENT: UnifiedEntityType.DOCUMENT,
        }
        return mapping.get(legacy_type, UnifiedEntityType.ENTITY)

    @staticmethod
    def unified_to_legacy(unified_type: UnifiedEntityType) -> LegacyBridgeEntityType:
        """Convert unified EntityType to legacy bridge EntityType."""
        mapping = {
            UnifiedEntityType.SOURCE: LegacyBridgeEntityType.SOURCE,
            UnifiedEntityType.PROJECT: LegacyBridgeEntityType.PROJECT,
            UnifiedEntityType.PAGE: LegacyBridgeEntityType.PAGE,
            UnifiedEntityType.CODE_EXAMPLE: LegacyBridgeEntityType.CODE_EXAMPLE,
            UnifiedEntityType.TASK: LegacyBridgeEntityType.TASK,
            UnifiedEntityType.DOCUMENT: LegacyBridgeEntityType.DOCUMENT,
        }
        # For unified types not supported by bridge, default to DOCUMENT
        return mapping.get(unified_type, LegacyBridgeEntityType.DOCUMENT)

    @staticmethod
    def get_bridge_compatible_types() -> List[LegacyBridgeEntityType]:
        """Get all entity types supported by the bridge service."""
        return [
            LegacyBridgeEntityType.SOURCE,
            LegacyBridgeEntityType.PROJECT,
            LegacyBridgeEntityType.PAGE,
            LegacyBridgeEntityType.CODE_EXAMPLE,
            LegacyBridgeEntityType.TASK,
            LegacyBridgeEntityType.DOCUMENT,
        ]

    @staticmethod
    def normalize_for_sync(entity_types: List[Any]) -> List[LegacyBridgeEntityType]:
        """Normalize a list of entity types for bridge sync operations."""
        normalized = []

        for entity_type in entity_types:
            if isinstance(entity_type, str):
                # Try to convert string to appropriate enum
                try:
                    # Try as LegacyBridgeEntityType first
                    normalized.append(LegacyBridgeEntityType(entity_type))
                except ValueError:
                    try:
                        # Try as UnifiedEntityType and convert
                        unified = UnifiedEntityType(entity_type)
                        legacy = BridgeEntityTypeAdapter.unified_to_legacy(unified)
                        normalized.append(legacy)
                    except ValueError:
                        # Default to DOCUMENT for unknown types
                        normalized.append(LegacyBridgeEntityType.DOCUMENT)
            elif hasattr(entity_type, "value"):
                # It's already an enum
                if isinstance(entity_type, LegacyBridgeEntityType):
                    normalized.append(entity_type)
                else:
                    # Assume it's a unified type and convert
                    try:
                        legacy = BridgeEntityTypeAdapter.unified_to_legacy(entity_type)
                        normalized.append(legacy)
                    except:
                        normalized.append(LegacyBridgeEntityType.DOCUMENT)

        return normalized


def get_entity_type_for_bridge() -> type:
    """Get the appropriate EntityType class for the bridge service."""
    if UNIFIED_TYPES_AVAILABLE:
        return UnifiedEntityType
    else:
        return LegacyBridgeEntityType


# Export the appropriate EntityType for the bridge service
EntityType = get_entity_type_for_bridge()
