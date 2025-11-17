"""Operation types for SemanticAnalysis Compute Node"""
from enum import Enum

class EnumSemanticAnalysisOperationType(str, Enum):
    """Operation types supported by semantic_analysis compute node."""
    ANALYZE_SEMANTICS = "ANALYZE_SEMANTICS"
    EXTRACT_FEATURES = "EXTRACT_FEATURES"
    COMPUTE_COMPLEXITY = "COMPUTE_COMPLEXITY"
    HEALTH_CHECK = "HEALTH_CHECK"

    def is_computational(self) -> bool:
        return self != EnumSemanticAnalysisOperationType.HEALTH_CHECK
