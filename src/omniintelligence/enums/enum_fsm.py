"""FSM-related enums for OmniIntelligence.

This module contains canonical FSM type enumerations for the intelligence system.
These enums provide type safety for FSM operations in reducer and orchestrator nodes.

ONEX Compliance:
    - Enum-based naming: Enum{Category}
    - String-based enum for JSON serialization
    - Integration with Pydantic models
"""

from enum import Enum


class EnumFSMType(str, Enum):
    """FSM types handled by the intelligence reducer.

    This enum defines the three primary FSM workflows supported by
    the intelligence reducer node.

    Attributes:
        INGESTION: Document ingestion workflow (RECEIVED -> PROCESSING -> INDEXED)
        PATTERN_LEARNING: Pattern learning workflow (4-phase: Foundation -> Matching -> Validation -> Traceability)
        QUALITY_ASSESSMENT: Quality assessment workflow (RAW -> ASSESSING -> SCORED -> STORED)

    Example:
        >>> from omniintelligence.enums import EnumFSMType
        >>> fsm_type = EnumFSMType.INGESTION
        >>> assert fsm_type.value == "INGESTION"
    """

    INGESTION = "INGESTION"
    PATTERN_LEARNING = "PATTERN_LEARNING"
    QUALITY_ASSESSMENT = "QUALITY_ASSESSMENT"


__all__ = ["EnumFSMType"]
