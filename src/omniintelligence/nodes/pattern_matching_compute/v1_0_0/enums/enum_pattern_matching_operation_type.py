"""Operation types for PatternMatching Compute Node"""
from enum import Enum

class EnumPatternMatchingOperationType(str, Enum):
    """Operation types supported by pattern_matching compute node."""
    MATCH_PATTERN = "MATCH_PATTERN"
    DETECT_PATTERN = "DETECT_PATTERN"
    ANALYZE_SIMILARITY = "ANALYZE_SIMILARITY"
    HEALTH_CHECK = "HEALTH_CHECK"

    def is_computational(self) -> bool:
        return self != EnumPatternMatchingOperationType.HEALTH_CHECK
