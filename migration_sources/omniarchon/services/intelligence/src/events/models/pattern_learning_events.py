"""
Pattern Learning Event Contracts - ONEX Compliant Kafka Event Schemas

Event schemas for Pattern Learning operations (7 operations × 3 event types = 21 events):
- PATTERN_MATCH_REQUESTED/COMPLETED/FAILED
- HYBRID_SCORE_REQUESTED/COMPLETED/FAILED
- SEMANTIC_ANALYZE_REQUESTED/COMPLETED/FAILED
- METRICS_REQUESTED/COMPLETED/FAILED
- CACHE_STATS_REQUESTED/COMPLETED/FAILED
- CACHE_CLEAR_REQUESTED/COMPLETED/FAILED
- HEALTH_REQUESTED/COMPLETED/FAILED

ONEX Compliance:
- Model-based naming: ModelPattern{Operation}{Type}Payload
- Strong typing with Pydantic v2
- Event envelope integration with ModelEventEnvelope
- Kafka topic routing following event bus architecture
- Serialization/deserialization helpers
- Comprehensive validation

Created: 2025-10-22
Reference: EVENT_BUS_ARCHITECTURE.md, intelligence_adapter_events.py
"""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

# ModelEventEnvelope imported locally in methods to avoid circular import issue
from pydantic import BaseModel, ConfigDict, Field

# Import from local event base to avoid circular imports

# Type-only import for type hints


class EnumPatternLearningEventType(str, Enum):
    """Event types for pattern learning operations."""

    # Pattern match operation
    PATTERN_MATCH_REQUESTED = "PATTERN_MATCH_REQUESTED"
    PATTERN_MATCH_COMPLETED = "PATTERN_MATCH_COMPLETED"
    PATTERN_MATCH_FAILED = "PATTERN_MATCH_FAILED"

    # Hybrid score operation
    HYBRID_SCORE_REQUESTED = "HYBRID_SCORE_REQUESTED"
    HYBRID_SCORE_COMPLETED = "HYBRID_SCORE_COMPLETED"
    HYBRID_SCORE_FAILED = "HYBRID_SCORE_FAILED"

    # Semantic analyze operation
    SEMANTIC_ANALYZE_REQUESTED = "SEMANTIC_ANALYZE_REQUESTED"
    SEMANTIC_ANALYZE_COMPLETED = "SEMANTIC_ANALYZE_COMPLETED"
    SEMANTIC_ANALYZE_FAILED = "SEMANTIC_ANALYZE_FAILED"

    # Metrics operation
    METRICS_REQUESTED = "METRICS_REQUESTED"
    METRICS_COMPLETED = "METRICS_COMPLETED"
    METRICS_FAILED = "METRICS_FAILED"

    # Cache stats operation
    CACHE_STATS_REQUESTED = "CACHE_STATS_REQUESTED"
    CACHE_STATS_COMPLETED = "CACHE_STATS_COMPLETED"
    CACHE_STATS_FAILED = "CACHE_STATS_FAILED"

    # Cache clear operation
    CACHE_CLEAR_REQUESTED = "CACHE_CLEAR_REQUESTED"
    CACHE_CLEAR_COMPLETED = "CACHE_CLEAR_COMPLETED"
    CACHE_CLEAR_FAILED = "CACHE_CLEAR_FAILED"

    # Health operation
    HEALTH_REQUESTED = "HEALTH_REQUESTED"
    HEALTH_COMPLETED = "HEALTH_COMPLETED"
    HEALTH_FAILED = "HEALTH_FAILED"


class EnumPatternLearningErrorCode(str, Enum):
    """Error codes for failed pattern learning operations."""

    INVALID_INPUT = "INVALID_INPUT"
    PATTERN_NOT_FOUND = "PATTERN_NOT_FOUND"
    EMBEDDING_ERROR = "EMBEDDING_ERROR"
    CACHE_ERROR = "CACHE_ERROR"
    TIMEOUT = "TIMEOUT"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


# ============================================================================
# Event Payload Models - Pattern Match Operation
# ============================================================================


class ModelPatternMatchRequestPayload(BaseModel):
    """Payload for PATTERN_MATCH_REQUESTED event."""

    query_pattern: str = Field(
        ..., min_length=1, description="Pattern to match against"
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context for matching",
    )
    top_k: Optional[int] = Field(default=10, ge=1, le=100)
    similarity_threshold: Optional[float] = Field(default=0.7, ge=0.0, le=1.0)

    model_config = ConfigDict(frozen=False)


class ModelPatternMatchCompletedPayload(BaseModel):
    """Payload for PATTERN_MATCH_COMPLETED event."""

    query_pattern: str = Field(...)
    matches: list[dict[str, Any]] = Field(default_factory=list)
    match_count: int = Field(..., ge=0)
    highest_similarity: float = Field(..., ge=0.0, le=1.0)
    processing_time_ms: float = Field(..., ge=0.0)
    cache_hit: bool = Field(default=False)

    model_config = ConfigDict(frozen=True)


class ModelPatternMatchFailedPayload(BaseModel):
    """Payload for PATTERN_MATCH_FAILED event."""

    query_pattern: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumPatternLearningErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ModelHybridScoreRequestPayload(BaseModel):
    """Payload for HYBRID_SCORE_REQUESTED event."""

    pattern_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    semantic_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    keyword_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    structural_weight: float = Field(default=0.2, ge=0.0, le=1.0)

    model_config = ConfigDict(frozen=False)


class ModelHybridScoreCompletedPayload(BaseModel):
    """Payload for HYBRID_SCORE_COMPLETED event."""

    pattern_id: str = Field(...)
    hybrid_score: float = Field(..., ge=0.0, le=1.0)
    semantic_score: float = Field(..., ge=0.0, le=1.0)
    keyword_score: float = Field(..., ge=0.0, le=1.0)
    structural_score: float = Field(..., ge=0.0, le=1.0)
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelHybridScoreFailedPayload(BaseModel):
    """Payload for HYBRID_SCORE_FAILED event."""

    pattern_id: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumPatternLearningErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ModelSemanticAnalyzeRequestPayload(BaseModel):
    """Payload for SEMANTIC_ANALYZE_REQUESTED event."""

    text: str = Field(..., min_length=1)
    analysis_type: str = Field(default="comprehensive")
    include_embeddings: bool = Field(default=False)

    model_config = ConfigDict(frozen=False)


class ModelSemanticAnalyzeCompletedPayload(BaseModel):
    """Payload for SEMANTIC_ANALYZE_COMPLETED event."""

    text: str = Field(...)
    semantic_features: dict[str, Any] = Field(default_factory=dict)
    embeddings: Optional[list[float]] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelSemanticAnalyzeFailedPayload(BaseModel):
    """Payload for SEMANTIC_ANALYZE_FAILED event."""

    text_preview: str = Field(..., description="First 100 chars of text")
    error_message: str = Field(..., min_length=1)
    error_code: EnumPatternLearningErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ModelMetricsRequestPayload(BaseModel):
    """Payload for METRICS_REQUESTED event."""

    time_window_hours: Optional[int] = Field(None, ge=1)
    include_breakdown: bool = Field(default=True)

    model_config = ConfigDict(frozen=False)


class ModelMetricsCompletedPayload(BaseModel):
    """Payload for METRICS_COMPLETED event."""

    total_patterns: int = Field(..., ge=0)
    total_matches: int = Field(..., ge=0)
    average_similarity: float = Field(..., ge=0.0, le=1.0)
    cache_hit_rate: float = Field(..., ge=0.0, le=1.0)
    breakdown: dict[str, Any] = Field(default_factory=dict)
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelMetricsFailedPayload(BaseModel):
    """Payload for METRICS_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumPatternLearningErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ModelCacheStatsRequestPayload(BaseModel):
    """Payload for CACHE_STATS_REQUESTED event."""

    include_entries: bool = Field(default=False)

    model_config = ConfigDict(frozen=False)


class ModelCacheStatsCompletedPayload(BaseModel):
    """Payload for CACHE_STATS_COMPLETED event."""

    total_entries: int = Field(..., ge=0)
    cache_size_bytes: int = Field(..., ge=0)
    hit_rate: float = Field(..., ge=0.0, le=1.0)
    miss_rate: float = Field(..., ge=0.0, le=1.0)
    eviction_count: int = Field(..., ge=0)
    entries: Optional[list[dict[str, Any]]] = None
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelCacheStatsFailedPayload(BaseModel):
    """Payload for CACHE_STATS_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumPatternLearningErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ModelCacheClearRequestPayload(BaseModel):
    """Payload for CACHE_CLEAR_REQUESTED event."""

    pattern: Optional[str] = Field(
        None, description="Optional pattern to clear specific entries"
    )
    clear_all: bool = Field(default=False)

    model_config = ConfigDict(frozen=False)


class ModelCacheClearCompletedPayload(BaseModel):
    """Payload for CACHE_CLEAR_COMPLETED event."""

    cleared_count: int = Field(..., ge=0)
    pattern: Optional[str] = None
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelCacheClearFailedPayload(BaseModel):
    """Payload for CACHE_CLEAR_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumPatternLearningErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ModelHealthRequestPayload(BaseModel):
    """Payload for HEALTH_REQUESTED event."""

    include_detailed_checks: bool = Field(default=False)

    model_config = ConfigDict(frozen=False)


class ModelHealthCompletedPayload(BaseModel):
    """Payload for HEALTH_COMPLETED event."""

    status: str = Field(..., description="Overall health status")
    checks: dict[str, Any] = Field(default_factory=dict)
    uptime_seconds: float = Field(..., ge=0.0)
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelHealthFailedPayload(BaseModel):
    """Payload for HEALTH_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumPatternLearningErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class PatternLearningEventHelpers:
    """Helper methods for creating and managing Pattern Learning events."""

    SERVICE_PREFIX = "archon-intelligence"
    DOMAIN = "pattern-learning"
    PATTERN = "event"
    VERSION = "v1"

    @staticmethod
    def create_event_envelope(
        event_type: str,
        payload: BaseModel,
        correlation_id: Optional[UUID] = None,
        causation_id: Optional[UUID] = None,
        source_instance: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create event envelope with proper topic routing."""
        correlation_id = correlation_id or uuid4()

        # Local import to avoid circular dependency
        from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

        envelope = ModelEventEnvelope(
            payload=payload if isinstance(payload, dict) else payload.model_dump(),
            correlation_id=correlation_id,
            source_tool="omninode-intelligence",
            metadata={
                "event_type": f"omninode.{PatternLearningEventHelpers.DOMAIN}.{PatternLearningEventHelpers.PATTERN}.{event_type}.{PatternLearningEventHelpers.VERSION}",
                "service": PatternLearningEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "intelligence-pattern-learning-1",
                "causation_id": str(causation_id) if causation_id else None,
            },
        )

        return envelope.model_dump()

    @staticmethod
    def get_kafka_topic(event_type: str, environment: str = "development") -> str:
        """Generate Kafka topic name for event type."""
        env_prefix = "dev" if environment == "development" else environment
        event_suffix = event_type.replace("_", "-").lower()
        return f"{env_prefix}.{PatternLearningEventHelpers.SERVICE_PREFIX}.{PatternLearningEventHelpers.DOMAIN}.{event_suffix}.{PatternLearningEventHelpers.VERSION}"
