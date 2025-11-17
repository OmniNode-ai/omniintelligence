"""Operation types for PostgresPattern Effect Node"""
from enum import Enum

class EnumPostgresPatternOperationType(str, Enum):
    """Operation types supported by postgres_pattern effect node."""
    STORE_PATTERN = "STORE_PATTERN"
    QUERY_PATTERN = "QUERY_PATTERN"
    UPDATE_LINEAGE = "UPDATE_LINEAGE"
    GET_TRACE = "GET_TRACE"
    HEALTH_CHECK = "HEALTH_CHECK"

    def is_system(self) -> bool:
        return self == EnumPostgresPatternOperationType.HEALTH_CHECK
