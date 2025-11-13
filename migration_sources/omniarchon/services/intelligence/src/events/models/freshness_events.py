"""
Document Freshness Event Contracts - ONEX Compliant Kafka Event Schemas

Event schemas for Document Freshness operations (9 operations × 3 event types = 27 events):
- FRESHNESS_ANALYZE_REQUESTED/COMPLETED/FAILED
- FRESHNESS_STALE_REQUESTED/COMPLETED/FAILED
- FRESHNESS_REFRESH_REQUESTED/COMPLETED/FAILED
- FRESHNESS_STATS_REQUESTED/COMPLETED/FAILED
- FRESHNESS_DOCUMENT_REQUESTED/COMPLETED/FAILED
- FRESHNESS_CLEANUP_REQUESTED/COMPLETED/FAILED
- FRESHNESS_DOCUMENT_UPDATE_REQUESTED/COMPLETED/FAILED
- FRESHNESS_EVENT_STATS_REQUESTED/COMPLETED/FAILED
- FRESHNESS_ANALYSES_REQUESTED/COMPLETED/FAILED

ONEX Compliance:
- Model-based naming: ModelFreshness{Operation}{Type}Payload
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
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Import from local event base to avoid circular imports

# Type-only import for type hints


class EnumFreshnessEventType(str, Enum):
    """Event types for freshness operations."""

    # Analyze operation
    FRESHNESS_ANALYZE_REQUESTED = "FRESHNESS_ANALYZE_REQUESTED"
    FRESHNESS_ANALYZE_COMPLETED = "FRESHNESS_ANALYZE_COMPLETED"
    FRESHNESS_ANALYZE_FAILED = "FRESHNESS_ANALYZE_FAILED"

    # Stale operation
    FRESHNESS_STALE_REQUESTED = "FRESHNESS_STALE_REQUESTED"
    FRESHNESS_STALE_COMPLETED = "FRESHNESS_STALE_COMPLETED"
    FRESHNESS_STALE_FAILED = "FRESHNESS_STALE_FAILED"

    # Refresh operation
    FRESHNESS_REFRESH_REQUESTED = "FRESHNESS_REFRESH_REQUESTED"
    FRESHNESS_REFRESH_COMPLETED = "FRESHNESS_REFRESH_COMPLETED"
    FRESHNESS_REFRESH_FAILED = "FRESHNESS_REFRESH_FAILED"

    # Stats operation
    FRESHNESS_STATS_REQUESTED = "FRESHNESS_STATS_REQUESTED"
    FRESHNESS_STATS_COMPLETED = "FRESHNESS_STATS_COMPLETED"
    FRESHNESS_STATS_FAILED = "FRESHNESS_STATS_FAILED"

    # Document operation
    FRESHNESS_DOCUMENT_REQUESTED = "FRESHNESS_DOCUMENT_REQUESTED"
    FRESHNESS_DOCUMENT_COMPLETED = "FRESHNESS_DOCUMENT_COMPLETED"
    FRESHNESS_DOCUMENT_FAILED = "FRESHNESS_DOCUMENT_FAILED"

    # Cleanup operation
    FRESHNESS_CLEANUP_REQUESTED = "FRESHNESS_CLEANUP_REQUESTED"
    FRESHNESS_CLEANUP_COMPLETED = "FRESHNESS_CLEANUP_COMPLETED"
    FRESHNESS_CLEANUP_FAILED = "FRESHNESS_CLEANUP_FAILED"

    # Document update operation
    FRESHNESS_DOCUMENT_UPDATE_REQUESTED = "FRESHNESS_DOCUMENT_UPDATE_REQUESTED"
    FRESHNESS_DOCUMENT_UPDATE_COMPLETED = "FRESHNESS_DOCUMENT_UPDATE_COMPLETED"
    FRESHNESS_DOCUMENT_UPDATE_FAILED = "FRESHNESS_DOCUMENT_UPDATE_FAILED"

    # Event stats operation
    FRESHNESS_EVENT_STATS_REQUESTED = "FRESHNESS_EVENT_STATS_REQUESTED"
    FRESHNESS_EVENT_STATS_COMPLETED = "FRESHNESS_EVENT_STATS_COMPLETED"
    FRESHNESS_EVENT_STATS_FAILED = "FRESHNESS_EVENT_STATS_FAILED"

    # Analyses operation
    FRESHNESS_ANALYSES_REQUESTED = "FRESHNESS_ANALYSES_REQUESTED"
    FRESHNESS_ANALYSES_COMPLETED = "FRESHNESS_ANALYSES_COMPLETED"
    FRESHNESS_ANALYSES_FAILED = "FRESHNESS_ANALYSES_FAILED"


class EnumFreshnessErrorCode(str, Enum):
    """Error codes for failed freshness operations."""

    INVALID_INPUT = "INVALID_INPUT"
    DOCUMENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"
    DATABASE_ERROR = "DATABASE_ERROR"
    TIMEOUT = "TIMEOUT"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    STALE_THRESHOLD_ERROR = "STALE_THRESHOLD_ERROR"


# ============================================================================
# Event Payload Models - Analyze Operation
# ============================================================================


class ModelFreshnessAnalyzeRequestPayload(BaseModel):
    """Payload for FRESHNESS_ANALYZE_REQUESTED event."""

    document_paths: list[str] = Field(
        ...,
        description="Document paths to analyze for freshness",
        min_length=1,
    )

    project_id: Optional[str] = Field(
        None,
        description="Optional project identifier for filtering",
    )

    model_config = ConfigDict(frozen=False)


class ModelFreshnessAnalyzeCompletedPayload(BaseModel):
    """Payload for FRESHNESS_ANALYZE_COMPLETED event."""

    analyzed_count: int = Field(..., ge=0)
    stale_count: int = Field(..., ge=0)
    fresh_count: int = Field(..., ge=0)
    results: dict[str, Any] = Field(default_factory=dict)
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelFreshnessAnalyzeFailedPayload(BaseModel):
    """Payload for FRESHNESS_ANALYZE_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumFreshnessErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ModelFreshnessStaleRequestPayload(BaseModel):
    """Payload for FRESHNESS_STALE_REQUESTED event."""

    threshold_days: Optional[int] = Field(None, ge=1)
    project_id: Optional[str] = None
    limit: Optional[int] = Field(None, ge=1)

    model_config = ConfigDict(frozen=False)


class ModelFreshnessStaleCompletedPayload(BaseModel):
    """Payload for FRESHNESS_STALE_COMPLETED event."""

    stale_documents: list[dict[str, Any]] = Field(default_factory=list)
    total_count: int = Field(..., ge=0)
    threshold_days: int = Field(..., ge=1)
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelFreshnessStaleFailedPayload(BaseModel):
    """Payload for FRESHNESS_STALE_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumFreshnessErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ModelFreshnessRefreshRequestPayload(BaseModel):
    """Payload for FRESHNESS_REFRESH_REQUESTED event."""

    document_paths: list[str] = Field(..., min_length=1)
    force_refresh: bool = Field(default=False)
    quality_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)

    model_config = ConfigDict(frozen=False)


class ModelFreshnessRefreshCompletedPayload(BaseModel):
    """Payload for FRESHNESS_REFRESH_COMPLETED event."""

    refreshed_count: int = Field(..., ge=0)
    failed_count: int = Field(..., ge=0)
    skipped_count: int = Field(..., ge=0)
    results: dict[str, Any] = Field(default_factory=dict)
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelFreshnessRefreshFailedPayload(BaseModel):
    """Payload for FRESHNESS_REFRESH_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumFreshnessErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ModelFreshnessStatsRequestPayload(BaseModel):
    """Payload for FRESHNESS_STATS_REQUESTED event."""

    project_id: Optional[str] = None
    include_breakdown: bool = Field(default=True)

    model_config = ConfigDict(frozen=False)


class ModelFreshnessStatsCompletedPayload(BaseModel):
    """Payload for FRESHNESS_STATS_COMPLETED event."""

    total_documents: int = Field(..., ge=0)
    stale_documents: int = Field(..., ge=0)
    fresh_documents: int = Field(..., ge=0)
    average_age_days: float = Field(..., ge=0.0)
    breakdown: dict[str, Any] = Field(default_factory=dict)
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelFreshnessStatsFailedPayload(BaseModel):
    """Payload for FRESHNESS_STATS_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumFreshnessErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ModelFreshnessDocumentRequestPayload(BaseModel):
    """Payload for FRESHNESS_DOCUMENT_REQUESTED event."""

    document_path: str = Field(..., min_length=1)
    include_history: bool = Field(default=False)

    model_config = ConfigDict(frozen=False)


class ModelFreshnessDocumentCompletedPayload(BaseModel):
    """Payload for FRESHNESS_DOCUMENT_COMPLETED event."""

    document_path: str = Field(...)
    is_stale: bool = Field(...)
    age_days: float = Field(..., ge=0.0)
    last_modified: str = Field(...)
    freshness_score: float = Field(..., ge=0.0, le=1.0)
    history: Optional[list[dict[str, Any]]] = None
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelFreshnessDocumentFailedPayload(BaseModel):
    """Payload for FRESHNESS_DOCUMENT_FAILED event."""

    document_path: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumFreshnessErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ModelFreshnessCleanupRequestPayload(BaseModel):
    """Payload for FRESHNESS_CLEANUP_REQUESTED event."""

    older_than_days: int = Field(..., ge=1)
    project_id: Optional[str] = None
    dry_run: bool = Field(default=False)

    model_config = ConfigDict(frozen=False)


class ModelFreshnessCleanupCompletedPayload(BaseModel):
    """Payload for FRESHNESS_CLEANUP_COMPLETED event."""

    deleted_count: int = Field(..., ge=0)
    skipped_count: int = Field(..., ge=0)
    dry_run: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelFreshnessCleanupFailedPayload(BaseModel):
    """Payload for FRESHNESS_CLEANUP_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumFreshnessErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ModelFreshnessDocumentUpdateRequestPayload(BaseModel):
    """Payload for FRESHNESS_DOCUMENT_UPDATE_REQUESTED event."""

    document_path: str = Field(..., min_length=1)
    event_type: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=False)


class ModelFreshnessDocumentUpdateCompletedPayload(BaseModel):
    """Payload for FRESHNESS_DOCUMENT_UPDATE_COMPLETED event."""

    document_path: str = Field(...)
    event_type: str = Field(...)
    updated: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelFreshnessDocumentUpdateFailedPayload(BaseModel):
    """Payload for FRESHNESS_DOCUMENT_UPDATE_FAILED event."""

    document_path: str = Field(...)
    event_type: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumFreshnessErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ModelFreshnessEventStatsRequestPayload(BaseModel):
    """Payload for FRESHNESS_EVENT_STATS_REQUESTED event."""

    time_window_hours: Optional[int] = Field(None, ge=1)
    event_type_filter: Optional[str] = None

    model_config = ConfigDict(frozen=False)


class ModelFreshnessEventStatsCompletedPayload(BaseModel):
    """Payload for FRESHNESS_EVENT_STATS_COMPLETED event."""

    total_events: int = Field(..., ge=0)
    events_by_type: dict[str, int] = Field(default_factory=dict)
    time_window_hours: int = Field(..., ge=1)
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelFreshnessEventStatsFailedPayload(BaseModel):
    """Payload for FRESHNESS_EVENT_STATS_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumFreshnessErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ModelFreshnessAnalysesRequestPayload(BaseModel):
    """Payload for FRESHNESS_ANALYSES_REQUESTED event."""

    project_id: Optional[str] = None
    limit: Optional[int] = Field(None, ge=1)
    offset: Optional[int] = Field(None, ge=0)

    model_config = ConfigDict(frozen=False)


class ModelFreshnessAnalysesCompletedPayload(BaseModel):
    """Payload for FRESHNESS_ANALYSES_COMPLETED event."""

    analyses: list[dict[str, Any]] = Field(default_factory=list)
    total_count: int = Field(..., ge=0)
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelFreshnessAnalysesFailedPayload(BaseModel):
    """Payload for FRESHNESS_ANALYSES_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumFreshnessErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class FreshnessEventHelpers:
    """Helper methods for creating and managing Freshness events."""

    SERVICE_PREFIX = "archon-intelligence"
    DOMAIN = "freshness"
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
                "event_type": f"omninode.{FreshnessEventHelpers.DOMAIN}.{FreshnessEventHelpers.PATTERN}.{event_type}.{FreshnessEventHelpers.VERSION}",
                "service": FreshnessEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "intelligence-freshness-1",
                "causation_id": str(causation_id) if causation_id else None,
            },
        )

        return envelope.model_dump()

    @staticmethod
    def get_kafka_topic(event_type: str, environment: str = "development") -> str:
        """Generate Kafka topic name for event type."""
        env_prefix = "dev" if environment == "development" else environment
        event_suffix = event_type.replace("_", "-").lower()
        return f"{env_prefix}.{FreshnessEventHelpers.SERVICE_PREFIX}.{FreshnessEventHelpers.DOMAIN}.{event_suffix}.{FreshnessEventHelpers.VERSION}"
