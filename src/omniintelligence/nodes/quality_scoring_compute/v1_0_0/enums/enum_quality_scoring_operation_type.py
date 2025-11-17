"""Operation types for QualityScoring Compute Node"""
from enum import Enum

class EnumQualityScoringOperationType(str, Enum):
    """Operation types supported by quality_scoring compute node."""
    COMPUTE_SCORE = "COMPUTE_SCORE"
    CHECK_COMPLIANCE = "CHECK_COMPLIANCE"
    CALCULATE_METRICS = "CALCULATE_METRICS"
    HEALTH_CHECK = "HEALTH_CHECK"

    def is_computational(self) -> bool:
        return self != EnumQualityScoringOperationType.HEALTH_CHECK
