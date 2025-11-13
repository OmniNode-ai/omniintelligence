"""
Performance Analytics Event Contracts - ONEX Compliant Kafka Event Schemas

Event schemas for Performance Analytics operations (6 total):
1. Baselines Query (GET /baselines)
2. Operation Metrics Query (GET /operations/{operation}/metrics)
3. Optimization Opportunities Query (GET /optimization-opportunities)
4. Anomaly Check (POST /operations/{operation}/anomaly-check)
5. Trends Query (GET /trends)
6. Health Check (GET /health)

Each operation has 3 event types: REQUESTED, COMPLETED, FAILED

ONEX Compliance:
- Model-based naming: ModelPerfAnalytics{Operation}{Type}Payload
- Strong typing with Pydantic v2
- Event envelope integration with ModelEventEnvelope
- Kafka topic routing following event bus architecture

Created: 2025-10-22
Reference: intelligence_adapter_events.py, EVENT_BUS_ARCHITECTURE.md
"""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

# ModelEventEnvelope imported locally in methods to avoid circular import issue
from pydantic import BaseModel, Field

# Import from local event base to avoid circular imports

# Type-only import for type hints


class EnumPerfAnalyticsEventType(str, Enum):
    """Event types for performance analytics operations."""

    # Baselines
    BASELINES_REQUESTED = "BASELINES_REQUESTED"
    BASELINES_COMPLETED = "BASELINES_COMPLETED"
    BASELINES_FAILED = "BASELINES_FAILED"

    # Operation Metrics
    METRICS_REQUESTED = "METRICS_REQUESTED"
    METRICS_COMPLETED = "METRICS_COMPLETED"
    METRICS_FAILED = "METRICS_FAILED"

    # Optimization Opportunities
    OPPORTUNITIES_REQUESTED = "OPPORTUNITIES_REQUESTED"
    OPPORTUNITIES_COMPLETED = "OPPORTUNITIES_COMPLETED"
    OPPORTUNITIES_FAILED = "OPPORTUNITIES_FAILED"

    # Anomaly Check
    ANOMALY_CHECK_REQUESTED = "ANOMALY_CHECK_REQUESTED"
    ANOMALY_CHECK_COMPLETED = "ANOMALY_CHECK_COMPLETED"
    ANOMALY_CHECK_FAILED = "ANOMALY_CHECK_FAILED"

    # Trends
    TRENDS_REQUESTED = "TRENDS_REQUESTED"
    TRENDS_COMPLETED = "TRENDS_COMPLETED"
    TRENDS_FAILED = "TRENDS_FAILED"

    # Health Check
    HEALTH_REQUESTED = "HEALTH_REQUESTED"
    HEALTH_COMPLETED = "HEALTH_COMPLETED"
    HEALTH_FAILED = "HEALTH_FAILED"


class EnumPerfAnalyticsErrorCode(str, Enum):
    """Error codes for failed performance analytics operations."""

    INVALID_INPUT = "INVALID_INPUT"
    OPERATION_NOT_FOUND = "OPERATION_NOT_FOUND"
    NO_BASELINE_DATA = "NO_BASELINE_DATA"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    DATABASE_ERROR = "DATABASE_ERROR"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# Alias for backward compatibility with tests
EnumPerformanceAnalyticsEventType = EnumPerfAnalyticsEventType


# ============================================================================
# Baselines Events
# ============================================================================


class ModelPerfAnalyticsBaselinesRequestPayload(BaseModel):
    """Payload for BASELINES_REQUESTED event."""

    operation: Optional[str] = Field(None, description="Filter by specific operation")


class ModelPerfAnalyticsBaselinesCompletedPayload(BaseModel):
    """Payload for BASELINES_COMPLETED event."""

    baselines: dict[str, dict[str, Any]] = Field(...)
    total_operations: int = Field(..., ge=0)
    total_measurements: int = Field(..., ge=0)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelPerfAnalyticsBaselinesFailedPayload(BaseModel):
    """Payload for BASELINES_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumPerfAnalyticsErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Operation Metrics Events
# ============================================================================


class ModelPerfAnalyticsMetricsRequestPayload(BaseModel):
    """Payload for METRICS_REQUESTED event."""

    operation: str = Field(...)
    recent_count: int = Field(default=10, ge=1, le=100)


class ModelPerfAnalyticsMetricsCompletedPayload(BaseModel):
    """Payload for METRICS_COMPLETED event."""

    operation: str = Field(...)
    baseline: dict[str, Any] = Field(...)
    recent_measurements: list[dict[str, Any]] = Field(...)
    trend: str = Field(...)  # improving/declining/stable
    anomaly_count_24h: int = Field(..., ge=0)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelPerfAnalyticsMetricsFailedPayload(BaseModel):
    """Payload for METRICS_FAILED event."""

    operation: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumPerfAnalyticsErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Optimization Opportunities Events
# ============================================================================


class ModelPerfAnalyticsOpportunitiesRequestPayload(BaseModel):
    """Payload for OPPORTUNITIES_REQUESTED event."""

    min_roi: float = Field(default=1.0, ge=0.0)
    max_effort: str = Field(default="high")


class ModelPerfAnalyticsOpportunitiesCompletedPayload(BaseModel):
    """Payload for OPPORTUNITIES_COMPLETED event."""

    opportunities: list[dict[str, Any]] = Field(...)
    total_opportunities: int = Field(..., ge=0)
    avg_roi: float = Field(..., ge=0.0)
    total_potential_improvement: float = Field(..., ge=0.0)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelPerfAnalyticsOpportunitiesFailedPayload(BaseModel):
    """Payload for OPPORTUNITIES_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumPerfAnalyticsErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Anomaly Check Events
# ============================================================================


class ModelPerfAnalyticsAnomalyCheckRequestPayload(BaseModel):
    """Payload for ANOMALY_CHECK_REQUESTED event."""

    operation: str = Field(...)
    duration_ms: float = Field(..., ge=0.0)


class ModelPerfAnalyticsAnomalyCheckCompletedPayload(BaseModel):
    """Payload for ANOMALY_CHECK_COMPLETED event."""

    operation: str = Field(...)
    anomaly_detected: bool = Field(...)
    z_score: float = Field(...)
    current_duration_ms: float = Field(..., ge=0.0)
    baseline_mean: float = Field(..., ge=0.0)
    baseline_p95: float = Field(..., ge=0.0)
    deviation_percentage: float = Field(...)
    severity: str = Field(...)  # normal/medium/high/critical
    processing_time_ms: float = Field(..., ge=0.0)


class ModelPerfAnalyticsAnomalyCheckFailedPayload(BaseModel):
    """Payload for ANOMALY_CHECK_FAILED event."""

    operation: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumPerfAnalyticsErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Trends Events
# ============================================================================


class ModelPerfAnalyticsTrendsRequestPayload(BaseModel):
    """Payload for TRENDS_REQUESTED event."""

    time_window: str = Field(default="24h")  # 24h/7d/30d


class ModelPerfAnalyticsTrendsCompletedPayload(BaseModel):
    """Payload for TRENDS_COMPLETED event."""

    time_window: str = Field(...)
    operations: dict[str, dict[str, Any]] = Field(...)
    overall_health: str = Field(...)  # excellent/good/warning/critical
    processing_time_ms: float = Field(..., ge=0.0)


class ModelPerfAnalyticsTrendsFailedPayload(BaseModel):
    """Payload for TRENDS_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumPerfAnalyticsErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Health Check Events
# ============================================================================


class ModelPerfAnalyticsHealthRequestPayload(BaseModel):
    """Payload for HEALTH_REQUESTED event."""

    # No required fields
    pass


class ModelPerfAnalyticsHealthCompletedPayload(BaseModel):
    """Payload for HEALTH_COMPLETED event."""

    status: str = Field(...)
    baseline_service: str = Field(...)
    optimization_analyzer: str = Field(...)
    total_operations_tracked: int = Field(..., ge=0)
    total_measurements: int = Field(..., ge=0)
    uptime_seconds: int = Field(..., ge=0)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelPerfAnalyticsHealthFailedPayload(BaseModel):
    """Payload for HEALTH_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumPerfAnalyticsErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Backward Compatibility Aliases
# ============================================================================

# Aliases for full naming convention (for tests and external imports)
ModelPerformanceAnalyticsBaselinesFailedPayload = (
    ModelPerfAnalyticsBaselinesFailedPayload
)
ModelPerformanceAnalyticsMetricsFailedPayload = ModelPerfAnalyticsMetricsFailedPayload
ModelPerformanceAnalyticsOpportunitiesFailedPayload = (
    ModelPerfAnalyticsOpportunitiesFailedPayload
)
ModelPerformanceAnalyticsAnomalyCheckFailedPayload = (
    ModelPerfAnalyticsAnomalyCheckFailedPayload
)


# ============================================================================
# Event Envelope Helpers
# ============================================================================


class PerformanceAnalyticsEventHelpers:
    """Helper methods for creating and managing Performance Analytics events."""

    SERVICE_PREFIX = "archon-intelligence"
    DOMAIN = "perf-analytics"
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
        """Create event envelope for any performance analytics event."""
        correlation_id = correlation_id or uuid4()

        # Local import to avoid circular dependency
        from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

        envelope = ModelEventEnvelope(
            payload=payload if isinstance(payload, dict) else payload.model_dump(),
            correlation_id=correlation_id,
            source_tool="omninode-intelligence",
            metadata={
                "event_type": f"omninode.{PerformanceAnalyticsEventHelpers.DOMAIN}.{PerformanceAnalyticsEventHelpers.PATTERN}.{event_type}.{PerformanceAnalyticsEventHelpers.VERSION}",
                "service": PerformanceAnalyticsEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "perf-analytics-1",
                "causation_id": str(causation_id) if causation_id else None,
            },
        )

        return envelope.model_dump()

    @staticmethod
    def get_kafka_topic(
        event_type: EnumPerfAnalyticsEventType, environment: str = "development"
    ) -> str:
        """Generate Kafka topic name for event type."""
        env_prefix = "dev" if environment == "development" else environment
        event_suffix = event_type.value.replace("_", "-").lower()
        return f"{env_prefix}.{PerformanceAnalyticsEventHelpers.SERVICE_PREFIX}.{PerformanceAnalyticsEventHelpers.DOMAIN}.{event_suffix}.{PerformanceAnalyticsEventHelpers.VERSION}"


# ============================================================================
# Convenience Functions
# ============================================================================


def create_baselines_requested_event(
    operation: Optional[str] = None,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """Convenience function to create BASELINES_REQUESTED event."""
    payload = ModelPerfAnalyticsBaselinesRequestPayload(operation=operation)
    return PerformanceAnalyticsEventHelpers.create_event_envelope(
        "perf-analytics.baselines.requested", payload, correlation_id
    )


def create_metrics_requested_event(
    operation: str,
    recent_count: int = 10,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """Convenience function to create METRICS_REQUESTED event."""
    payload = ModelPerfAnalyticsMetricsRequestPayload(
        operation=operation, recent_count=recent_count
    )
    return PerformanceAnalyticsEventHelpers.create_event_envelope(
        "perf-analytics.metrics.requested", payload, correlation_id
    )


def create_anomaly_check_requested_event(
    operation: str,
    duration_ms: float,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """Convenience function to create ANOMALY_CHECK_REQUESTED event."""
    payload = ModelPerfAnalyticsAnomalyCheckRequestPayload(
        operation=operation, duration_ms=duration_ms
    )
    return PerformanceAnalyticsEventHelpers.create_event_envelope(
        "perf-analytics.anomaly-check.requested", payload, correlation_id
    )


def create_opportunities_requested_event(
    min_roi: float = 1.0,
    max_effort: str = "high",
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """Convenience function to create OPPORTUNITIES_REQUESTED event."""
    payload = ModelPerfAnalyticsOpportunitiesRequestPayload(
        min_roi=min_roi, max_effort=max_effort
    )
    return PerformanceAnalyticsEventHelpers.create_event_envelope(
        "perf-analytics.opportunities.requested", payload, correlation_id
    )
