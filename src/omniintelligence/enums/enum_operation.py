"""
Operation type enums for omniintelligence.

Contains operation types handled by the intelligence orchestrator.
"""

from enum import Enum


class EnumOperationType(str, Enum):
    """Operation types handled by the intelligence orchestrator."""
    DOCUMENT_INGESTION = "DOCUMENT_INGESTION"
    PATTERN_LEARNING = "PATTERN_LEARNING"
    QUALITY_ASSESSMENT = "QUALITY_ASSESSMENT"
    SEMANTIC_ANALYSIS = "SEMANTIC_ANALYSIS"
    RELATIONSHIP_DETECTION = "RELATIONSHIP_DETECTION"
    VECTORIZATION = "VECTORIZATION"
    ENTITY_EXTRACTION = "ENTITY_EXTRACTION"


__all__ = [
    "EnumOperationType",
]
