"""
Intelligence Contracts - Input models and operation enums for intelligence operations.

This module provides the core contract definitions for intelligence operations:
- EnumIntelligenceOperationType: Operation type enumeration (45+ operations)
- ModelIntelligenceInput: Primary input model for intelligence requests

Operation Categories:
- Quality Assessment (4): Code/document quality analysis, ONEX compliance
- Performance (5): Baseline establishment, optimization, trend monitoring
- Document Freshness (6): Freshness analysis, refresh operations
- Pattern Learning (7): Pattern matching, analytics, cache management
- Vector Operations (5): Semantic search, indexing, optimization
- Pattern Traceability (4): Lineage tracking, execution logs
- Autonomous Learning (7): Pattern ingestion, prediction, safety scoring

Usage:
    from omniintelligence.contracts import (
        EnumIntelligenceOperationType,
        ModelIntelligenceInput,
    )

    # Create an intelligence input
    input_data = ModelIntelligenceInput(
        operation_type=EnumIntelligenceOperationType.ASSESS_CODE_QUALITY.value,
        content="def hello(): pass",
        source_path="src/api.py",
        language="python",
    )
"""

from omniintelligence.contracts.enum_intelligence_operation_type import (
    EnumIntelligenceOperationType,
)
from omniintelligence.contracts.model_intelligence_input import (
    ModelIntelligenceInput,
)

__all__ = [
    "EnumIntelligenceOperationType",
    "ModelIntelligenceInput",
]
