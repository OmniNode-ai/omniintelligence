"""
Pattern Traceability Event Contracts - ONEX Compliant Kafka Event Schemas

Event schemas for Pattern Traceability operations (11 operations × 3 event types = 33 events):
- TRACK_REQUESTED/COMPLETED/FAILED
- TRACK_BATCH_REQUESTED/COMPLETED/FAILED
- LINEAGE_REQUESTED/COMPLETED/FAILED
- EVOLUTION_REQUESTED/COMPLETED/FAILED
- EXECUTION_LOGS_REQUESTED/COMPLETED/FAILED
- EXECUTION_SUMMARY_REQUESTED/COMPLETED/FAILED
- ANALYTICS_REQUESTED/COMPLETED/FAILED
- ANALYTICS_COMPUTE_REQUESTED/COMPLETED/FAILED
- FEEDBACK_ANALYZE_REQUESTED/COMPLETED/FAILED
- FEEDBACK_APPLY_REQUESTED/COMPLETED/FAILED
- HEALTH_REQUESTED/COMPLETED/FAILED

ONEX Compliance:
- Model-based naming: ModelTraceability{Operation}{Type}Payload
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


class EnumTraceabilityEventType(str, Enum):
    """Event types for traceability operations."""

    # Track operation
    TRACK_REQUESTED = "TRACK_REQUESTED"
    TRACK_COMPLETED = "TRACK_COMPLETED"
    TRACK_FAILED = "TRACK_FAILED"

    # Track batch operation
    TRACK_BATCH_REQUESTED = "TRACK_BATCH_REQUESTED"
    TRACK_BATCH_COMPLETED = "TRACK_BATCH_COMPLETED"
    TRACK_BATCH_FAILED = "TRACK_BATCH_FAILED"

    # Lineage operation
    LINEAGE_REQUESTED = "LINEAGE_REQUESTED"
    LINEAGE_COMPLETED = "LINEAGE_COMPLETED"
    LINEAGE_FAILED = "LINEAGE_FAILED"

    # Evolution operation
    EVOLUTION_REQUESTED = "EVOLUTION_REQUESTED"
    EVOLUTION_COMPLETED = "EVOLUTION_COMPLETED"
    EVOLUTION_FAILED = "EVOLUTION_FAILED"

    # Execution logs operation
    EXECUTION_LOGS_REQUESTED = "EXECUTION_LOGS_REQUESTED"
    EXECUTION_LOGS_COMPLETED = "EXECUTION_LOGS_COMPLETED"
    EXECUTION_LOGS_FAILED = "EXECUTION_LOGS_FAILED"

    # Execution summary operation
    EXECUTION_SUMMARY_REQUESTED = "EXECUTION_SUMMARY_REQUESTED"
    EXECUTION_SUMMARY_COMPLETED = "EXECUTION_SUMMARY_COMPLETED"
    EXECUTION_SUMMARY_FAILED = "EXECUTION_SUMMARY_FAILED"

    # Analytics operation
    ANALYTICS_REQUESTED = "ANALYTICS_REQUESTED"
    ANALYTICS_COMPLETED = "ANALYTICS_COMPLETED"
    ANALYTICS_FAILED = "ANALYTICS_FAILED"

    # Analytics compute operation
    ANALYTICS_COMPUTE_REQUESTED = "ANALYTICS_COMPUTE_REQUESTED"
    ANALYTICS_COMPUTE_COMPLETED = "ANALYTICS_COMPUTE_COMPLETED"
    ANALYTICS_COMPUTE_FAILED = "ANALYTICS_COMPUTE_FAILED"

    # Feedback analyze operation
    FEEDBACK_ANALYZE_REQUESTED = "FEEDBACK_ANALYZE_REQUESTED"
    FEEDBACK_ANALYZE_COMPLETED = "FEEDBACK_ANALYZE_COMPLETED"
    FEEDBACK_ANALYZE_FAILED = "FEEDBACK_ANALYZE_FAILED"

    # Feedback apply operation
    FEEDBACK_APPLY_REQUESTED = "FEEDBACK_APPLY_REQUESTED"
    FEEDBACK_APPLY_COMPLETED = "FEEDBACK_APPLY_COMPLETED"
    FEEDBACK_APPLY_FAILED = "FEEDBACK_APPLY_FAILED"

    # Health operation
    HEALTH_REQUESTED = "HEALTH_REQUESTED"
    HEALTH_COMPLETED = "HEALTH_COMPLETED"
    HEALTH_FAILED = "HEALTH_FAILED"


class EnumTraceabilityErrorCode(str, Enum):
    """Error codes for failed traceability operations."""

    INVALID_INPUT = "INVALID_INPUT"
    PATTERN_NOT_FOUND = "PATTERN_NOT_FOUND"
    DATABASE_ERROR = "DATABASE_ERROR"
    TIMEOUT = "TIMEOUT"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    LINEAGE_INCOMPLETE = "LINEAGE_INCOMPLETE"


# ============================================================================
# Event Payload Models - Track Operation
# ============================================================================


class ModelTrackRequestPayload(BaseModel):
    """Payload for TRACK_REQUESTED event."""

    pattern_id: str = Field(..., min_length=1)
    pattern_type: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_location: Optional[str] = None

    model_config = ConfigDict(frozen=False)


class ModelTrackCompletedPayload(BaseModel):
    """Payload for TRACK_COMPLETED event."""

    pattern_id: str = Field(...)
    tracked: bool = Field(...)
    lineage_id: str = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelTrackFailedPayload(BaseModel):
    """Payload for TRACK_FAILED event."""

    pattern_id: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumTraceabilityErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ModelTrackBatchRequestPayload(BaseModel):
    """Payload for TRACK_BATCH_REQUESTED event."""

    patterns: list[dict[str, Any]] = Field(..., min_length=1)
    batch_metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=False)


class ModelTrackBatchCompletedPayload(BaseModel):
    """Payload for TRACK_BATCH_COMPLETED event."""

    total_patterns: int = Field(..., ge=0)
    tracked_count: int = Field(..., ge=0)
    failed_count: int = Field(..., ge=0)
    lineage_ids: list[str] = Field(default_factory=list)
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelTrackBatchFailedPayload(BaseModel):
    """Payload for TRACK_BATCH_FAILED event."""

    total_patterns: int = Field(..., ge=0)
    error_message: str = Field(..., min_length=1)
    error_code: EnumTraceabilityErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ModelLineageRequestPayload(BaseModel):
    """Payload for LINEAGE_REQUESTED event."""

    pattern_id: str = Field(..., min_length=1)
    depth: Optional[int] = Field(default=None, ge=1)
    include_metadata: bool = Field(default=True)

    model_config = ConfigDict(frozen=False)


class ModelLineageCompletedPayload(BaseModel):
    """Payload for LINEAGE_COMPLETED event."""

    pattern_id: str = Field(...)
    lineage_chain: list[dict[str, Any]] = Field(default_factory=list)
    depth: int = Field(..., ge=0)
    total_ancestors: int = Field(..., ge=0)
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelLineageFailedPayload(BaseModel):
    """Payload for LINEAGE_FAILED event."""

    pattern_id: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumTraceabilityErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ModelEvolutionRequestPayload(BaseModel):
    """Payload for EVOLUTION_REQUESTED event."""

    pattern_id: str = Field(..., min_length=1)
    time_window_hours: Optional[int] = Field(None, ge=1)
    include_metrics: bool = Field(default=True)

    model_config = ConfigDict(frozen=False)


class ModelEvolutionCompletedPayload(BaseModel):
    """Payload for EVOLUTION_COMPLETED event."""

    pattern_id: str = Field(...)
    evolution_stages: list[dict[str, Any]] = Field(default_factory=list)
    total_versions: int = Field(..., ge=0)
    time_span_hours: float = Field(..., ge=0.0)
    metrics: dict[str, Any] = Field(default_factory=dict)
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelEvolutionFailedPayload(BaseModel):
    """Payload for EVOLUTION_FAILED event."""

    pattern_id: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumTraceabilityErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ModelExecutionLogsRequestPayload(BaseModel):
    """Payload for EXECUTION_LOGS_REQUESTED event."""

    agent_name: Optional[str] = None
    time_window_hours: Optional[int] = Field(None, ge=1)
    limit: Optional[int] = Field(None, ge=1)
    include_details: bool = Field(default=True)

    model_config = ConfigDict(frozen=False)


class ModelExecutionLogsCompletedPayload(BaseModel):
    """Payload for EXECUTION_LOGS_COMPLETED event."""

    logs: list[dict[str, Any]] = Field(default_factory=list)
    total_count: int = Field(..., ge=0)
    time_window_hours: Optional[int] = None
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelExecutionLogsFailedPayload(BaseModel):
    """Payload for EXECUTION_LOGS_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumTraceabilityErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ModelExecutionSummaryRequestPayload(BaseModel):
    """Payload for EXECUTION_SUMMARY_REQUESTED event."""

    agent_name: Optional[str] = None
    time_window_hours: Optional[int] = Field(None, ge=1)
    include_breakdown: bool = Field(default=True)

    model_config = ConfigDict(frozen=False)


class ModelExecutionSummaryCompletedPayload(BaseModel):
    """Payload for EXECUTION_SUMMARY_COMPLETED event."""

    total_executions: int = Field(..., ge=0)
    success_count: int = Field(..., ge=0)
    failure_count: int = Field(..., ge=0)
    average_duration_ms: float = Field(..., ge=0.0)
    breakdown: dict[str, Any] = Field(default_factory=dict)
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelExecutionSummaryFailedPayload(BaseModel):
    """Payload for EXECUTION_SUMMARY_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumTraceabilityErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ModelAnalyticsRequestPayload(BaseModel):
    """Payload for ANALYTICS_REQUESTED event."""

    pattern_id: str = Field(..., min_length=1)
    metrics: list[str] = Field(default_factory=list)
    time_window_hours: Optional[int] = Field(None, ge=1)

    model_config = ConfigDict(frozen=False)


class ModelAnalyticsCompletedPayload(BaseModel):
    """Payload for ANALYTICS_COMPLETED event."""

    pattern_id: str = Field(...)
    analytics: dict[str, Any] = Field(default_factory=dict)
    usage_count: int = Field(..., ge=0)
    success_rate: float = Field(..., ge=0.0, le=1.0)
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelAnalyticsFailedPayload(BaseModel):
    """Payload for ANALYTICS_FAILED event."""

    pattern_id: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumTraceabilityErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ModelAnalyticsComputeRequestPayload(BaseModel):
    """Payload for ANALYTICS_COMPUTE_REQUESTED event."""

    correlation_field: str = Field(..., min_length=1)
    aggregation_type: str = Field(default="count")
    time_window_hours: Optional[int] = Field(None, ge=1)

    model_config = ConfigDict(frozen=False)


class ModelAnalyticsComputeCompletedPayload(BaseModel):
    """Payload for ANALYTICS_COMPUTE_COMPLETED event."""

    correlation_field: str = Field(...)
    results: dict[str, Any] = Field(default_factory=dict)
    total_records: int = Field(..., ge=0)
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelAnalyticsComputeFailedPayload(BaseModel):
    """Payload for ANALYTICS_COMPUTE_FAILED event."""

    correlation_field: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumTraceabilityErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ModelFeedbackAnalyzeRequestPayload(BaseModel):
    """Payload for FEEDBACK_ANALYZE_REQUESTED event."""

    pattern_id: str = Field(..., min_length=1)
    feedback_data: dict[str, Any] = Field(default_factory=dict)
    analysis_depth: str = Field(default="standard")

    model_config = ConfigDict(frozen=False)


class ModelFeedbackAnalyzeCompletedPayload(BaseModel):
    """Payload for FEEDBACK_ANALYZE_COMPLETED event."""

    pattern_id: str = Field(...)
    analysis_results: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelFeedbackAnalyzeFailedPayload(BaseModel):
    """Payload for FEEDBACK_ANALYZE_FAILED event."""

    pattern_id: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumTraceabilityErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ModelFeedbackApplyRequestPayload(BaseModel):
    """Payload for FEEDBACK_APPLY_REQUESTED event."""

    pattern_id: str = Field(..., min_length=1)
    feedback_type: str = Field(..., min_length=1)
    feedback_data: dict[str, Any] = Field(default_factory=dict)
    auto_update: bool = Field(default=False)

    model_config = ConfigDict(frozen=False)


class ModelFeedbackApplyCompletedPayload(BaseModel):
    """Payload for FEEDBACK_APPLY_COMPLETED event."""

    pattern_id: str = Field(...)
    applied: bool = Field(...)
    changes: dict[str, Any] = Field(default_factory=dict)
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelFeedbackApplyFailedPayload(BaseModel):
    """Payload for FEEDBACK_APPLY_FAILED event."""

    pattern_id: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumTraceabilityErrorCode
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

    status: str = Field(...)
    checks: dict[str, Any] = Field(default_factory=dict)
    uptime_seconds: float = Field(..., ge=0.0)
    processing_time_ms: float = Field(..., ge=0.0)

    model_config = ConfigDict(frozen=True)


class ModelHealthFailedPayload(BaseModel):
    """Payload for HEALTH_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumTraceabilityErrorCode
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class TraceabilityEventHelpers:
    """Helper methods for creating and managing Traceability events."""

    SERVICE_PREFIX = "archon-intelligence"
    DOMAIN = "traceability"
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
                "event_type": f"omninode.{TraceabilityEventHelpers.DOMAIN}.{TraceabilityEventHelpers.PATTERN}.{event_type}.{TraceabilityEventHelpers.VERSION}",
                "service": TraceabilityEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "intelligence-traceability-1",
                "causation_id": str(causation_id) if causation_id else None,
            },
        )

        return envelope.model_dump()

    @staticmethod
    def get_kafka_topic(event_type: str, environment: str = "development") -> str:
        """Generate Kafka topic name for event type."""
        env_prefix = "dev" if environment == "development" else environment
        event_suffix = event_type.replace("_", "-").lower()
        return f"{env_prefix}.{TraceabilityEventHelpers.SERVICE_PREFIX}.{TraceabilityEventHelpers.DOMAIN}.{event_suffix}.{TraceabilityEventHelpers.VERSION}"
