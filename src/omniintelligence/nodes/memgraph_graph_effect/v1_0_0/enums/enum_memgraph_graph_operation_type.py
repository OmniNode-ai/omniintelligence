"""Operation types for MemgraphGraph Effect Node"""
from enum import Enum

class EnumMemgraphGraphOperationType(str, Enum):
    """Operation types supported by memgraph_graph effect node."""
    CREATE_NODE = "CREATE_NODE"
    CREATE_RELATIONSHIP = "CREATE_RELATIONSHIP"
    QUERY_GRAPH = "QUERY_GRAPH"
    DELETE_NODE = "DELETE_NODE"
    HEALTH_CHECK = "HEALTH_CHECK"

    def is_system(self) -> bool:
        return self == EnumMemgraphGraphOperationType.HEALTH_CHECK
