"""Operation types for EntityExtraction Compute Node"""
from enum import Enum

class EnumEntityExtractionOperationType(str, Enum):
    """Operation types supported by entity_extraction compute node."""
    EXTRACT_ENTITIES = "EXTRACT_ENTITIES"
    PARSE_CODE = "PARSE_CODE"
    ANALYZE_AST = "ANALYZE_AST"
    HEALTH_CHECK = "HEALTH_CHECK"

    def is_computational(self) -> bool:
        return self != EnumEntityExtractionOperationType.HEALTH_CHECK
