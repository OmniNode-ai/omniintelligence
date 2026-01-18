"""Canonical enums for OmniIntelligence.

This package contains type-safe enumerations used throughout
the intelligence system for FSM operations, operation types,
and other categorical values.
"""

from omniintelligence.enums.enum_fsm import EnumFSMType
from omniintelligence.enums.enum_operation import (
    EnumIntelligenceOperationType,
    EnumOrchestratorWorkflowType,
)

__all__ = [
    "EnumFSMType",
    "EnumIntelligenceOperationType",
    "EnumOrchestratorWorkflowType",
]
