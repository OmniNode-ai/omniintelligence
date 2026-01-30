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
from omniintelligence.enums.enum_injection import (
    COHORT_CONTROL_PERCENTAGE,
    COHORT_TREATMENT_PERCENTAGE,
    HEURISTIC_CONFIDENCE,
    EnumCohort,
    EnumHeuristicMethod,
    EnumInjectionContext,
)
from omniintelligence.enums.enum_operation import (
    EnumIntelligenceOperationType,
    EnumOrchestratorWorkflowType,
)
from omniintelligence.enums.enum_pattern_lifecycle import EnumPatternLifecycleStatus

__all__ = [
    "COHORT_CONTROL_PERCENTAGE",
    "COHORT_TREATMENT_PERCENTAGE",
    "DOMAIN_TAXONOMY_VERSION",
    "HEURISTIC_CONFIDENCE",
    "EnumAnalysisErrorCode",
    "EnumAnalysisOperationType",
    "EnumCodeAnalysisEventType",
    "EnumCohort",
    "EnumDomainTaxonomy",
    "EnumEntityType",
    "EnumFSMType",
    "EnumHeuristicMethod",
    "EnumInjectionContext",
    "EnumIntelligenceOperationType",
    "EnumOrchestratorWorkflowType",
    "EnumPatternLifecycleStatus",
    "EnumRelationshipType",
]
