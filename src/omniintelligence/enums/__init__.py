"""Canonical enums for OmniIntelligence.

This package contains type-safe enumerations used throughout
the intelligence system for FSM operations, operation types,
entity types, and other categorical values.
"""

from omniintelligence.enums.enum_code_analysis import (
    EnumAnalysisErrorCode,
    EnumAnalysisOperationType,
    EnumCodeAnalysisEventType,
)
from omniintelligence.enums.enum_domain_taxonomy import (
    DOMAIN_TAXONOMY_VERSION,
    EnumDomainTaxonomy,
)
from omniintelligence.enums.enum_entity import EnumEntityType, EnumRelationshipType
from omniintelligence.enums.enum_fsm import EnumFSMType
from omniintelligence.enums.enum_operation import (
    EnumIntelligenceOperationType,
    EnumOrchestratorWorkflowType,
)
from omniintelligence.enums.enum_pattern_lifecycle import EnumPatternLifecycleStatus

__all__ = [
    "DOMAIN_TAXONOMY_VERSION",
    "EnumAnalysisErrorCode",
    "EnumAnalysisOperationType",
    "EnumCodeAnalysisEventType",
    "EnumDomainTaxonomy",
    "EnumEntityType",
    "EnumFSMType",
    "EnumIntelligenceOperationType",
    "EnumOrchestratorWorkflowType",
    "EnumPatternLifecycleStatus",
    "EnumRelationshipType",
]
