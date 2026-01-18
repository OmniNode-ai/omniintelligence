"""
Intelligence Contracts - Input models and operation enums for intelligence operations.

DEPRECATED: This module is kept for backwards compatibility.
Please import from omniintelligence._legacy.models and omniintelligence.enums instead:

    # Preferred imports
    from omniintelligence._legacy.enums import EnumIntelligenceOperationType
    from omniintelligence._legacy.models import ModelIntelligenceInput

    # Deprecated import (still works)
    from omniintelligence._legacy.contracts import (
        EnumIntelligenceOperationType,
        ModelIntelligenceInput,
    )

Operation Categories:
- Quality Assessment (4): Code/document quality analysis, ONEX compliance
- Performance (5): Baseline establishment, optimization, trend monitoring
- Document Freshness (6): Freshness analysis, refresh operations
- Pattern Learning (7): Pattern matching, analytics, cache management
- Vector Operations (5): Semantic search, indexing, optimization
- Pattern Traceability (4): Lineage tracking, execution logs
- Autonomous Learning (7): Pattern ingestion, prediction, safety scoring
"""

# Re-export from canonical locations
from omniintelligence._legacy.enums import EnumIntelligenceOperationType
from omniintelligence._legacy.models.model_intelligence_input import ModelIntelligenceInput

__all__ = [
    "EnumIntelligenceOperationType",
    "ModelIntelligenceInput",
]
