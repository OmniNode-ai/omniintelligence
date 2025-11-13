"""
Pattern Analytics Event Contracts - ONEX Compliant Kafka Event Schemas

Event schemas for Pattern Analytics operations (5 total):
1. Success Rates Query (GET /success-rates)
2. Top Patterns Query (GET /top-patterns)
3. Emerging Patterns Query (GET /emerging-patterns)
4. Pattern History Query (GET /pattern/{pattern_id}/history)
5. Health Check (GET /health)

Each operation has 3 event types: REQUESTED, COMPLETED, FAILED

ONEX Compliance:
- Model-based naming: ModelPatternAnalytics{Operation}{Type}Payload
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


class EnumPatternAnalyticsEventType(str, Enum):
    """Event types for pattern analytics operations."""

    # Success Rates
    SUCCESS_RATES_REQUESTED = "SUCCESS_RATES_REQUESTED"
    SUCCESS_RATES_COMPLETED = "SUCCESS_RATES_COMPLETED"
    SUCCESS_RATES_FAILED = "SUCCESS_RATES_FAILED"

    # Top Patterns
    TOP_PATTERNS_REQUESTED = "TOP_PATTERNS_REQUESTED"
    TOP_PATTERNS_COMPLETED = "TOP_PATTERNS_COMPLETED"
    TOP_PATTERNS_FAILED = "TOP_PATTERNS_FAILED"

    # Emerging Patterns
    EMERGING_REQUESTED = "EMERGING_REQUESTED"
    EMERGING_COMPLETED = "EMERGING_COMPLETED"
    EMERGING_FAILED = "EMERGING_FAILED"

    # Pattern History
    HISTORY_REQUESTED = "HISTORY_REQUESTED"
    HISTORY_COMPLETED = "HISTORY_COMPLETED"
    HISTORY_FAILED = "HISTORY_FAILED"

    # Health Check
    HEALTH_REQUESTED = "HEALTH_REQUESTED"
    HEALTH_COMPLETED = "HEALTH_COMPLETED"
    HEALTH_FAILED = "HEALTH_FAILED"


class EnumPatternAnalyticsErrorCode(str, Enum):
    """Error codes for failed pattern analytics operations."""

    INVALID_INPUT = "INVALID_INPUT"
    PATTERN_NOT_FOUND = "PATTERN_NOT_FOUND"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    DATABASE_ERROR = "DATABASE_ERROR"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# ============================================================================
# Success Rates Events
# ============================================================================


class ModelPatternAnalyticsSuccessRatesRequestPayload(BaseModel):
    """Payload for SUCCESS_RATES_REQUESTED event."""

    pattern_type: Optional[str] = Field(None, description="Filter by pattern type")
    min_samples: int = Field(default=5, ge=1, le=1000)
    min_success_rate: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Minimum success rate filter"
    )


class ModelPatternAnalyticsSuccessRatesCompletedPayload(BaseModel):
    """Payload for SUCCESS_RATES_COMPLETED event."""

    patterns: list[dict[str, Any]] = Field(..., description="Pattern success rates")
    summary: dict[str, Any] = Field(..., description="Summary statistics")
    processing_time_ms: float = Field(..., ge=0.0)


class ModelPatternAnalyticsSuccessRatesFailedPayload(BaseModel):
    """Payload for SUCCESS_RATES_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumPatternAnalyticsErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Top Patterns Events
# ============================================================================


class ModelPatternAnalyticsTopPatternsRequestPayload(BaseModel):
    """Payload for TOP_PATTERNS_REQUESTED event."""

    node_type: Optional[str] = Field(None, description="Filter by ONEX node type")
    limit: int = Field(default=10, ge=1, le=100)
    min_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Minimum quality score filter"
    )


class ModelPatternAnalyticsTopPatternsCompletedPayload(BaseModel):
    """Payload for TOP_PATTERNS_COMPLETED event."""

    top_patterns: list[dict[str, Any]] = Field(
        ..., description="Top performing patterns"
    )
    total_patterns: int = Field(..., ge=0)
    filter_criteria: dict[str, Any] = Field(default_factory=dict)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelPatternAnalyticsTopPatternsFailedPayload(BaseModel):
    """Payload for TOP_PATTERNS_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumPatternAnalyticsErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Emerging Patterns Events
# ============================================================================


class ModelPatternAnalyticsEmergingRequestPayload(BaseModel):
    """Payload for EMERGING_REQUESTED event."""

    min_frequency: int = Field(default=5, ge=1, le=1000)
    time_window_hours: int = Field(default=24, ge=1, le=720)
    min_occurrences: Optional[int] = Field(
        None, ge=1, le=10000, description="Minimum occurrences filter"
    )


class ModelPatternAnalyticsEmergingCompletedPayload(BaseModel):
    """Payload for EMERGING_COMPLETED event."""

    emerging_patterns: list[dict[str, Any]] = Field(
        ..., description="Emerging patterns"
    )
    total_emerging: int = Field(..., ge=0)
    time_window_hours: int = Field(..., ge=1)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelPatternAnalyticsEmergingFailedPayload(BaseModel):
    """Payload for EMERGING_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumPatternAnalyticsErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Pattern History Events
# ============================================================================


class ModelPatternAnalyticsHistoryRequestPayload(BaseModel):
    """Payload for HISTORY_REQUESTED event."""

    pattern_id: str = Field(..., description="Pattern identifier")


class ModelPatternAnalyticsHistoryCompletedPayload(BaseModel):
    """Payload for HISTORY_COMPLETED event."""

    pattern_id: str = Field(...)
    pattern_name: str = Field(...)
    feedback_history: list[dict[str, Any]] = Field(...)
    summary: dict[str, Any] = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelPatternAnalyticsHistoryFailedPayload(BaseModel):
    """Payload for HISTORY_FAILED event."""

    pattern_id: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumPatternAnalyticsErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Health Check Events
# ============================================================================


class ModelPatternAnalyticsHealthRequestPayload(BaseModel):
    """Payload for HEALTH_REQUESTED event."""

    # No required fields
    pass


class ModelPatternAnalyticsHealthCompletedPayload(BaseModel):
    """Payload for HEALTH_COMPLETED event."""

    status: str = Field(...)
    service: str = Field(...)
    endpoints: list[str] = Field(default_factory=list)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelPatternAnalyticsHealthFailedPayload(BaseModel):
    """Payload for HEALTH_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumPatternAnalyticsErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Event Envelope Helpers
# ============================================================================


class PatternAnalyticsEventHelpers:
    """Helper methods for creating and managing Pattern Analytics events."""

    SERVICE_PREFIX = "archon-intelligence"
    DOMAIN = "pattern-analytics"
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
        """Create event envelope for any pattern analytics event."""
        correlation_id = correlation_id or uuid4()

        # Local import to avoid circular dependency
        from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

        envelope = ModelEventEnvelope(
            payload=payload if isinstance(payload, dict) else payload.model_dump(),
            correlation_id=correlation_id,
            source_tool="omninode-intelligence",
            metadata={
                "event_type": f"omninode.{PatternAnalyticsEventHelpers.DOMAIN}.{PatternAnalyticsEventHelpers.PATTERN}.{event_type}.{PatternAnalyticsEventHelpers.VERSION}",
                "service": PatternAnalyticsEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "pattern-analytics-1",
                "causation_id": str(causation_id) if causation_id else None,
            },
        )

        return envelope.model_dump()

    @staticmethod
    def get_kafka_topic(
        event_type: EnumPatternAnalyticsEventType, environment: str = "development"
    ) -> str:
        """Generate Kafka topic name for event type."""
        env_prefix = "dev" if environment == "development" else environment
        event_suffix = event_type.value.replace("_", "-").lower()
        return f"{env_prefix}.{PatternAnalyticsEventHelpers.SERVICE_PREFIX}.{PatternAnalyticsEventHelpers.DOMAIN}.{event_suffix}.{PatternAnalyticsEventHelpers.VERSION}"


# ============================================================================
# Convenience Functions
# ============================================================================


def create_success_rates_requested_event(
    pattern_type: Optional[str] = None,
    min_samples: int = 5,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """Convenience function to create SUCCESS_RATES_REQUESTED event."""
    payload = ModelPatternAnalyticsSuccessRatesRequestPayload(
        pattern_type=pattern_type, min_samples=min_samples
    )
    return PatternAnalyticsEventHelpers.create_event_envelope(
        "pattern-analytics.success-rates.requested", payload, correlation_id
    )


def create_top_patterns_requested_event(
    node_type: Optional[str] = None,
    limit: int = 10,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """Convenience function to create TOP_PATTERNS_REQUESTED event."""
    payload = ModelPatternAnalyticsTopPatternsRequestPayload(
        node_type=node_type, limit=limit
    )
    return PatternAnalyticsEventHelpers.create_event_envelope(
        "pattern-analytics.top-patterns.requested", payload, correlation_id
    )


def create_emerging_requested_event(
    min_frequency: int = 5,
    time_window_hours: int = 24,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """Convenience function to create EMERGING_REQUESTED event."""
    payload = ModelPatternAnalyticsEmergingRequestPayload(
        min_frequency=min_frequency, time_window_hours=time_window_hours
    )
    return PatternAnalyticsEventHelpers.create_event_envelope(
        "pattern-analytics.emerging.requested", payload, correlation_id
    )


def create_history_requested_event(
    pattern_id: str,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """Convenience function to create HISTORY_REQUESTED event."""
    payload = ModelPatternAnalyticsHistoryRequestPayload(pattern_id=pattern_id)
    return PatternAnalyticsEventHelpers.create_event_envelope(
        "pattern-analytics.history.requested", payload, correlation_id
    )
