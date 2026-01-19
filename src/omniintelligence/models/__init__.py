"""Top-level models for OmniIntelligence.

These models are shared across multiple nodes and provide common
data structures for intelligence operations.

Migration from Legacy (omniarchon):
    These canonical models are intentionally simplified from the legacy
    omniarchon models. Key differences include:

    - ModelIntelligenceInput: Unified input model replacing multiple
      operation-specific request models (ModelQualityAssessmentRequest, etc.)

    - ModelIntelligenceOutput: Simplified output with:
      - correlation_id as Optional[str] (was required UUID)
      - onex_compliant as bool (was onex_compliance float score)
      - patterns_detected as list[str] (was list[ModelPatternDetection])
      - Removed: processing_time_ms, metrics, error_code, retry_allowed, timestamp

    - ModelEntity / ModelRelationship: Typed models for knowledge graph entities
      and relationships, replacing untyped dict-based representations.

    - ModelSearchResult / ModelPatternMatch: Typed models for search results
      and pattern matches, replacing untyped dict-based representations.

    For complete migration guidance, see MIGRATION.md in this directory.
"""

from omniintelligence.models.model_entity import ModelEntity, ModelRelationship
from omniintelligence.models.model_intelligence_input import (
    IntelligenceMetadataDict,
    IntelligenceOptionsDict,
    ModelIntelligenceInput,
    PerformanceContextDict,
)
from omniintelligence.models.model_intelligence_output import ModelIntelligenceOutput
from omniintelligence.models.model_search_result import (
    ModelPatternMatch,
    ModelSearchResult,
)

__all__ = [
    "IntelligenceMetadataDict",
    "IntelligenceOptionsDict",
    "ModelEntity",
    "ModelIntelligenceInput",
    "ModelIntelligenceOutput",
    "ModelPatternMatch",
    "ModelRelationship",
    "ModelSearchResult",
    "PerformanceContextDict",
]
