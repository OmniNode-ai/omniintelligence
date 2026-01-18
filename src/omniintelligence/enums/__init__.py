"""Canonical enums for OmniIntelligence.

This package contains type-safe enumerations used throughout
the intelligence system for FSM operations, operation types,
entity types, and other categorical values.
"""

from omniintelligence.enums.enum_entity import EnumEntityType, EnumRelationshipType
from omniintelligence.enums.enum_fsm import EnumFSMType
from omniintelligence.enums.enum_operation import (
    EnumIntelligenceOperationType,
    EnumOrchestratorWorkflowType,
)

__all__ = [
    "EnumEntityType",
    "EnumFSMType",
    "EnumIntelligenceOperationType",
    "EnumOrchestratorWorkflowType",
    "EnumRelationshipType",
]
