"""Operation types for RelationshipDetection Compute Node"""
from enum import Enum

class EnumRelationshipDetectionOperationType(str, Enum):
    """Operation types supported by relationship_detection compute node."""
    DETECT_RELATIONSHIPS = "DETECT_RELATIONSHIPS"
    ANALYZE_DEPENDENCIES = "ANALYZE_DEPENDENCIES"
    BUILD_GRAPH = "BUILD_GRAPH"
    HEALTH_CHECK = "HEALTH_CHECK"

    def is_computational(self) -> bool:
        return self != EnumRelationshipDetectionOperationType.HEALTH_CHECK
