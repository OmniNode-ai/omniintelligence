"""
Intent type enums for omniintelligence.

Contains intent types for communication between nodes.
"""

from enum import Enum


class EnumIntentType(str, Enum):
    """Intent types for communication between nodes."""
    STATE_UPDATE = "STATE_UPDATE"
    WORKFLOW_TRIGGER = "WORKFLOW_TRIGGER"
    EVENT_PUBLISH = "EVENT_PUBLISH"
    CACHE_INVALIDATE = "CACHE_INVALIDATE"
    RESOURCE_ALLOCATION = "RESOURCE_ALLOCATION"
    ERROR_NOTIFICATION = "ERROR_NOTIFICATION"


__all__ = [
    "EnumIntentType",
]
