"""
Cache scope enums for omniintelligence.

Contains cache scope types.
"""

from enum import Enum


class EnumCacheScope(str, Enum):
    """Cache scope types."""
    GLOBAL = "GLOBAL"
    WORKFLOW = "WORKFLOW"
    OPERATION = "OPERATION"
    ENTITY = "ENTITY"


__all__ = [
    "EnumCacheScope",
]
