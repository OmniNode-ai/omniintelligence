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

from omniintelligence.models.events import (
    ModelCodeAnalysisCompletedPayload,
    ModelCodeAnalysisFailedPayload,
    ModelCodeAnalysisRequestPayload,
)
from omniintelligence.models.model_entity import ModelEntity
from omniintelligence.models.model_intelligence_input import (
    IntelligenceMetadataDict,
    IntelligenceOptionsDict,
    ModelIntelligenceInput,
    PerformanceContextDict,
)
from omniintelligence.models.model_intelligence_output import (
    AnalysisResultsDict,
    ModelIntelligenceOutput,
    OutputMetadataDict,
)
from omniintelligence.models.model_pattern_match import (
    ModelPatternMatch,
    PatternMatchMetadataDict,
)
from omniintelligence.models.model_relationship import ModelRelationship
from omniintelligence.models.model_search_result import (
    ModelSearchResult,
    SearchResultMetadataDict,
)
from omniintelligence.models.repository import (
    ModelDomainCandidate,
    ModelExistsResult,
    ModelIdResult,
    ModelLearnedPatternRow,
    ModelPatternForInjection,
    ModelTimestampResult,
    ModelVersionResult,
)

__all__ = [
    "AnalysisResultsDict",
    "IntelligenceMetadataDict",
    "IntelligenceOptionsDict",
    "ModelCodeAnalysisCompletedPayload",
    "ModelCodeAnalysisFailedPayload",
    "ModelCodeAnalysisRequestPayload",
    "ModelDomainCandidate",
    "ModelEntity",
    "ModelExistsResult",
    "ModelIdResult",
    "ModelIntelligenceInput",
    "ModelIntelligenceOutput",
    "ModelLearnedPatternRow",
    "ModelPatternForInjection",
    "ModelPatternMatch",
    "ModelRelationship",
    "ModelSearchResult",
    "ModelTimestampResult",
    "ModelVersionResult",
    "OutputMetadataDict",
    "PatternMatchMetadataDict",
    "PerformanceContextDict",
    "SearchResultMetadataDict",
]
