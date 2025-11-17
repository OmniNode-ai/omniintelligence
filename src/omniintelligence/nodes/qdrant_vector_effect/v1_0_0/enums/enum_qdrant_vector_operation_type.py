"""Operation types for QdrantVector Effect Node"""
from enum import Enum

class EnumQdrantVectorOperationType(str, Enum):
    """Operation types supported by qdrant_vector effect node."""
    INDEX_VECTOR = "INDEX_VECTOR"
    SEARCH_VECTORS = "SEARCH_VECTORS"
    UPDATE_VECTOR = "UPDATE_VECTOR"
    DELETE_VECTOR = "DELETE_VECTOR"
    HEALTH_CHECK = "HEALTH_CHECK"

    def is_system(self) -> bool:
        return self == EnumQdrantVectorOperationType.HEALTH_CHECK
