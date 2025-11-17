"""Operation types for IntelligenceApi Effect Node"""
from enum import Enum

class EnumIntelligenceApiOperationType(str, Enum):
    """Operation types supported by intelligence_api effect node."""
    GET_REQUEST = "GET_REQUEST"
    POST_REQUEST = "POST_REQUEST"
    PUT_REQUEST = "PUT_REQUEST"
    DELETE_REQUEST = "DELETE_REQUEST"
    HEALTH_CHECK = "HEALTH_CHECK"

    def is_system(self) -> bool:
        return self == EnumIntelligenceApiOperationType.HEALTH_CHECK
