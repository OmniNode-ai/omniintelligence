"""
Quality Trends Event Contracts - ONEX Compliant Kafka Event Schemas

Event schemas for Quality Trends operations (7 total):
1. Snapshot Recording (POST /snapshot)
2. Project Trend Query (GET /project/{project_id}/trend)
3. File Trend Query (GET /project/{project_id}/file/{file_path}/trend)
4. File History Query (GET /project/{project_id}/file/{file_path}/history)
5. Regression Detection (POST /detect-regression)
6. Statistics (GET /stats)
7. Clear Snapshots (DELETE /project/{project_id}/snapshots)

Each operation has 3 event types: REQUESTED, COMPLETED, FAILED

ONEX Compliance:
- Model-based naming: ModelQualityTrends{Operation}{Type}Payload
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


class EnumQualityTrendsEventType(str, Enum):
    """Event types for quality trends operations."""

    # Snapshot Recording
    SNAPSHOT_REQUESTED = "SNAPSHOT_REQUESTED"
    SNAPSHOT_COMPLETED = "SNAPSHOT_COMPLETED"
    SNAPSHOT_FAILED = "SNAPSHOT_FAILED"

    # Project Trend
    PROJECT_TREND_REQUESTED = "PROJECT_TREND_REQUESTED"
    PROJECT_TREND_COMPLETED = "PROJECT_TREND_COMPLETED"
    PROJECT_TREND_FAILED = "PROJECT_TREND_FAILED"

    # File Trend
    FILE_TREND_REQUESTED = "FILE_TREND_REQUESTED"
    FILE_TREND_COMPLETED = "FILE_TREND_COMPLETED"
    FILE_TREND_FAILED = "FILE_TREND_FAILED"

    # File History
    FILE_HISTORY_REQUESTED = "FILE_HISTORY_REQUESTED"
    FILE_HISTORY_COMPLETED = "FILE_HISTORY_COMPLETED"
    FILE_HISTORY_FAILED = "FILE_HISTORY_FAILED"

    # Regression Detection
    DETECT_REGRESSION_REQUESTED = "DETECT_REGRESSION_REQUESTED"
    DETECT_REGRESSION_COMPLETED = "DETECT_REGRESSION_COMPLETED"
    DETECT_REGRESSION_FAILED = "DETECT_REGRESSION_FAILED"

    # Statistics
    STATS_REQUESTED = "STATS_REQUESTED"
    STATS_COMPLETED = "STATS_COMPLETED"
    STATS_FAILED = "STATS_FAILED"

    # Clear Snapshots
    CLEAR_REQUESTED = "CLEAR_REQUESTED"
    CLEAR_COMPLETED = "CLEAR_COMPLETED"
    CLEAR_FAILED = "CLEAR_FAILED"


class EnumQualityTrendsErrorCode(str, Enum):
    """Error codes for failed quality trends operations."""

    INVALID_INPUT = "INVALID_INPUT"
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    DATABASE_ERROR = "DATABASE_ERROR"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# ============================================================================
# Snapshot Recording Events
# ============================================================================


class ModelQualityTrendsSnapshotRequestPayload(BaseModel):
    """Payload for SNAPSHOT_REQUESTED event."""

    project_id: str = Field(...)
    file_path: str = Field(...)
    quality_score: float = Field(..., ge=0.0, le=1.0)
    onex_compliance_score: float = Field(..., ge=0.0, le=1.0)
    violations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    correlation_id: str = Field(...)


class ModelQualityTrendsSnapshotCompletedPayload(BaseModel):
    """Payload for SNAPSHOT_COMPLETED event."""

    project_id: str = Field(...)
    file_path: str = Field(...)
    quality_score: float = Field(..., ge=0.0, le=1.0)
    snapshot_id: str = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelQualityTrendsSnapshotFailedPayload(BaseModel):
    """Payload for SNAPSHOT_FAILED event."""

    project_id: str = Field(...)
    file_path: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumQualityTrendsErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Project Trend Events
# ============================================================================


class ModelQualityTrendsProjectTrendRequestPayload(BaseModel):
    """Payload for PROJECT_TREND_REQUESTED event."""

    project_id: str = Field(...)
    time_window_days: int = Field(default=30, ge=1, le=365)


class ModelQualityTrendsProjectTrendCompletedPayload(BaseModel):
    """Payload for PROJECT_TREND_COMPLETED event."""

    project_id: str = Field(...)
    trend: str = Field(...)  # improving/declining/stable/insufficient_data
    current_quality: Optional[float] = Field(None, ge=0.0, le=1.0)
    avg_quality: Optional[float] = Field(None, ge=0.0, le=1.0)
    slope: Optional[float] = Field(None)
    snapshots_count: int = Field(..., ge=0)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelQualityTrendsProjectTrendFailedPayload(BaseModel):
    """Payload for PROJECT_TREND_FAILED event."""

    project_id: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumQualityTrendsErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# File Trend Events
# ============================================================================


class ModelQualityTrendsFileTrendRequestPayload(BaseModel):
    """Payload for FILE_TREND_REQUESTED event."""

    project_id: str = Field(...)
    file_path: str = Field(...)
    time_window_days: int = Field(default=30, ge=1, le=365)


class ModelQualityTrendsFileTrendCompletedPayload(BaseModel):
    """Payload for FILE_TREND_COMPLETED event."""

    project_id: str = Field(...)
    file_path: str = Field(...)
    trend: str = Field(...)
    current_quality: Optional[float] = Field(None, ge=0.0, le=1.0)
    avg_quality: Optional[float] = Field(None, ge=0.0, le=1.0)
    slope: Optional[float] = Field(None)
    snapshots_count: int = Field(..., ge=0)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelQualityTrendsFileTrendFailedPayload(BaseModel):
    """Payload for FILE_TREND_FAILED event."""

    project_id: str = Field(...)
    file_path: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumQualityTrendsErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# File History Events
# ============================================================================


class ModelQualityTrendsFileHistoryRequestPayload(BaseModel):
    """Payload for FILE_HISTORY_REQUESTED event."""

    project_id: str = Field(...)
    file_path: str = Field(...)
    limit: int = Field(default=50, ge=1, le=200)


class ModelQualityTrendsFileHistoryCompletedPayload(BaseModel):
    """Payload for FILE_HISTORY_COMPLETED event."""

    project_id: str = Field(...)
    file_path: str = Field(...)
    history: list[dict[str, Any]] = Field(...)
    snapshots_count: int = Field(..., ge=0)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelQualityTrendsFileHistoryFailedPayload(BaseModel):
    """Payload for FILE_HISTORY_FAILED event."""

    project_id: str = Field(...)
    file_path: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumQualityTrendsErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Regression Detection Events
# ============================================================================


class ModelQualityTrendsDetectRegressionRequestPayload(BaseModel):
    """Payload for DETECT_REGRESSION_REQUESTED event."""

    project_id: str = Field(...)
    current_score: float = Field(..., ge=0.0, le=1.0)
    threshold: float = Field(default=0.1, ge=0.0, le=1.0)


class ModelQualityTrendsDetectRegressionCompletedPayload(BaseModel):
    """Payload for DETECT_REGRESSION_COMPLETED event."""

    project_id: str = Field(...)
    regression_detected: bool = Field(...)
    current_score: float = Field(..., ge=0.0, le=1.0)
    avg_recent_score: float = Field(..., ge=0.0, le=1.0)
    difference: float = Field(...)
    threshold: float = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelQualityTrendsDetectRegressionFailedPayload(BaseModel):
    """Payload for DETECT_REGRESSION_FAILED event."""

    project_id: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumQualityTrendsErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Statistics Events
# ============================================================================


class ModelQualityTrendsStatsRequestPayload(BaseModel):
    """Payload for STATS_REQUESTED event."""

    # No required fields
    pass


class ModelQualityTrendsStatsCompletedPayload(BaseModel):
    """Payload for STATS_COMPLETED event."""

    total_snapshots: int = Field(..., ge=0)
    service_status: str = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelQualityTrendsStatsFailedPayload(BaseModel):
    """Payload for STATS_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumQualityTrendsErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Clear Snapshots Events
# ============================================================================


class ModelQualityTrendsClearRequestPayload(BaseModel):
    """Payload for CLEAR_REQUESTED event."""

    project_id: str = Field(...)


class ModelQualityTrendsClearCompletedPayload(BaseModel):
    """Payload for CLEAR_COMPLETED event."""

    project_id: str = Field(...)
    cleared_snapshots: int = Field(..., ge=0)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelQualityTrendsClearFailedPayload(BaseModel):
    """Payload for CLEAR_FAILED event."""

    project_id: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumQualityTrendsErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Event Envelope Helpers
# ============================================================================


class QualityTrendsEventHelpers:
    """Helper methods for creating and managing Quality Trends events."""

    SERVICE_PREFIX = "archon-intelligence"
    DOMAIN = "quality-trends"
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
        """Create event envelope for any quality trends event."""
        correlation_id = correlation_id or uuid4()

        # Local import to avoid circular dependency
        from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

        envelope = ModelEventEnvelope(
            payload=payload if isinstance(payload, dict) else payload.model_dump(),
            correlation_id=correlation_id,
            source_tool="omninode-intelligence",
            metadata={
                "event_type": f"omninode.{QualityTrendsEventHelpers.DOMAIN}.{QualityTrendsEventHelpers.PATTERN}.{event_type}.{QualityTrendsEventHelpers.VERSION}",
                "service": QualityTrendsEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "quality-trends-1",
                "causation_id": str(causation_id) if causation_id else None,
            },
        )

        return envelope.model_dump()

    @staticmethod
    def get_kafka_topic(
        event_type: EnumQualityTrendsEventType, environment: str = "development"
    ) -> str:
        """Generate Kafka topic name for event type."""
        env_prefix = "dev" if environment == "development" else environment
        event_suffix = event_type.value.replace("_", "-").lower()
        return f"{env_prefix}.{QualityTrendsEventHelpers.SERVICE_PREFIX}.{QualityTrendsEventHelpers.DOMAIN}.{event_suffix}.{QualityTrendsEventHelpers.VERSION}"


# ============================================================================
# Convenience Functions
# ============================================================================


def create_snapshot_requested_event(
    project_id: str,
    file_path: str,
    quality_score: float,
    onex_compliance_score: float,
    correlation_id_str: str,
    violations: Optional[list[str]] = None,
    warnings: Optional[list[str]] = None,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """Convenience function to create SNAPSHOT_REQUESTED event."""
    payload = ModelQualityTrendsSnapshotRequestPayload(
        project_id=project_id,
        file_path=file_path,
        quality_score=quality_score,
        onex_compliance_score=onex_compliance_score,
        violations=violations or [],
        warnings=warnings or [],
        correlation_id=correlation_id_str,
    )
    return QualityTrendsEventHelpers.create_event_envelope(
        "quality-trends.snapshot.requested", payload, correlation_id
    )


def create_detect_regression_requested_event(
    project_id: str,
    current_score: float,
    threshold: float = 0.1,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """Convenience function to create DETECT_REGRESSION_REQUESTED event."""
    payload = ModelQualityTrendsDetectRegressionRequestPayload(
        project_id=project_id, current_score=current_score, threshold=threshold
    )
    return QualityTrendsEventHelpers.create_event_envelope(
        "quality-trends.detect-regression.requested", payload, correlation_id
    )
