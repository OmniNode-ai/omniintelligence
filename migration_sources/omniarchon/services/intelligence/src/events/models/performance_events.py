"""
Performance Optimization Event Contracts - ONEX Compliant Kafka Event Schemas

Event schemas for Performance Optimization operations:
- BASELINE_REQUESTED/COMPLETED/FAILED: Establish performance baseline
- OPPORTUNITIES_REQUESTED/COMPLETED/FAILED: Get optimization opportunities
- OPTIMIZE_REQUESTED/COMPLETED/FAILED: Apply performance optimization
- REPORT_REQUESTED/COMPLETED/FAILED: Get performance report
- TRENDS_REQUESTED/COMPLETED/FAILED: Get performance trends

ONEX Compliance:
- Model-based naming: ModelPerformance{Type}Payload
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


class EnumPerformanceEventType(str, Enum):
    """Event types for performance optimization operations."""

    # Baseline Events
    BASELINE_REQUESTED = "BASELINE_REQUESTED"
    BASELINE_COMPLETED = "BASELINE_COMPLETED"
    BASELINE_FAILED = "BASELINE_FAILED"

    # Opportunities Events
    OPPORTUNITIES_REQUESTED = "OPPORTUNITIES_REQUESTED"
    OPPORTUNITIES_COMPLETED = "OPPORTUNITIES_COMPLETED"
    OPPORTUNITIES_FAILED = "OPPORTUNITIES_FAILED"

    # Optimize Events
    OPTIMIZE_REQUESTED = "OPTIMIZE_REQUESTED"
    OPTIMIZE_COMPLETED = "OPTIMIZE_COMPLETED"
    OPTIMIZE_FAILED = "OPTIMIZE_FAILED"

    # Report Events
    REPORT_REQUESTED = "REPORT_REQUESTED"
    REPORT_COMPLETED = "REPORT_COMPLETED"
    REPORT_FAILED = "REPORT_FAILED"

    # Trends Events
    TRENDS_REQUESTED = "TRENDS_REQUESTED"
    TRENDS_COMPLETED = "TRENDS_COMPLETED"
    TRENDS_FAILED = "TRENDS_FAILED"


class EnumPerformanceErrorCode(str, Enum):
    """Error codes for failed performance operations."""

    INVALID_INPUT = "INVALID_INPUT"
    TIMEOUT = "TIMEOUT"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    OPERATION_NOT_FOUND = "OPERATION_NOT_FOUND"
    DATABASE_ERROR = "DATABASE_ERROR"


# ============================================================================
# Baseline Event Payloads
# ============================================================================


class ModelBaselineRequestPayload(BaseModel):
    """
    Payload for BASELINE_REQUESTED event.

    Attributes:
        operation_name: Name of operation to baseline
        code_content: Optional code content for immediate analysis
        project_id: Optional project identifier
        user_id: Optional user identifier
    """

    operation_name: str = Field(
        ...,
        description="Name of operation to baseline",
        min_length=1,
    )

    code_content: Optional[str] = Field(
        None,
        description="Optional code content for immediate analysis",
    )

    project_id: Optional[str] = Field(
        None,
        description="Project identifier",
    )

    user_id: Optional[str] = Field(
        None,
        description="User identifier",
    )

    @field_validator("operation_name")
    @classmethod
    def validate_operation_name(cls, v: str) -> str:
        """Ensure operation_name is not empty."""
        if not v or not v.strip():
            raise ValueError("operation_name cannot be empty")
        return v.strip()

    model_config = ConfigDict(frozen=False)


class ModelBaselineCompletedPayload(BaseModel):
    """
    Payload for BASELINE_COMPLETED event.

    Attributes:
        operation_name: Operation name
        average_response_time_ms: Average response time
        p50_ms: 50th percentile
        p95_ms: 95th percentile
        p99_ms: 99th percentile
        std_dev_ms: Standard deviation
        sample_size: Number of measurements
        quality_score: Optional quality score
        complexity_score: Optional complexity score
        source: Data source (cached, code_analysis, real_time)
        processing_time_ms: Processing time
        cache_hit: Whether cached
    """

    operation_name: str = Field(
        ...,
        description="Operation name",
    )

    average_response_time_ms: float = Field(
        ...,
        description="Average response time",
        ge=0.0,
    )

    p50_ms: float = Field(
        ...,
        description="50th percentile",
        ge=0.0,
    )

    p95_ms: float = Field(
        ...,
        description="95th percentile",
        ge=0.0,
    )

    p99_ms: float = Field(
        ...,
        description="99th percentile",
        ge=0.0,
    )

    std_dev_ms: Optional[float] = Field(
        None,
        description="Standard deviation",
        ge=0.0,
    )

    sample_size: int = Field(
        ...,
        description="Number of measurements",
        ge=0,
    )

    quality_score: Optional[float] = Field(
        None,
        description="Optional quality score",
        ge=0.0,
        le=1.0,
    )

    complexity_score: Optional[float] = Field(
        None,
        description="Optional complexity score",
        ge=0.0,
        le=1.0,
    )

    source: str = Field(
        ...,
        description="Data source",
        examples=["cached", "code_analysis", "real_time"],
    )

    processing_time_ms: float = Field(
        ...,
        description="Processing time",
        ge=0.0,
    )

    cache_hit: bool = Field(
        default=False,
        description="Whether cached",
    )

    model_config = ConfigDict(frozen=True)


class ModelBaselineFailedPayload(BaseModel):
    """
    Payload for BASELINE_FAILED event.

    Attributes:
        operation_name: Operation name
        error_message: Error message
        error_code: Error code
        retry_allowed: Retry allowed
        retry_count: Retry count
        processing_time_ms: Processing time
        error_details: Error details
        suggested_action: Suggested action
    """

    operation_name: str = Field(
        ...,
        description="Operation name",
    )

    error_message: str = Field(
        ...,
        description="Error message",
        min_length=1,
    )

    error_code: EnumPerformanceErrorCode = Field(
        ...,
        description="Error code",
    )

    retry_allowed: bool = Field(
        ...,
        description="Retry allowed",
    )

    retry_count: int = Field(
        default=0,
        description="Retry count",
        ge=0,
    )

    processing_time_ms: float = Field(
        ...,
        description="Processing time",
        ge=0.0,
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Error details",
    )

    suggested_action: Optional[str] = Field(
        None,
        description="Suggested action",
    )

    model_config = ConfigDict(frozen=True)


class ModelOpportunitiesRequestPayload(BaseModel):
    """
    Payload for OPPORTUNITIES_REQUESTED event.

    Attributes:
        operation_name: Operation name to analyze
        project_id: Optional project identifier
        user_id: Optional user identifier
    """

    operation_name: str = Field(
        ...,
        description="Operation name to analyze",
        min_length=1,
    )

    project_id: Optional[str] = Field(
        None,
        description="Project identifier",
    )

    user_id: Optional[str] = Field(
        None,
        description="User identifier",
    )

    @field_validator("operation_name")
    @classmethod
    def validate_operation_name(cls, v: str) -> str:
        """Ensure operation_name is not empty."""
        if not v or not v.strip():
            raise ValueError("operation_name cannot be empty")
        return v.strip()

    model_config = ConfigDict(frozen=False)


class ModelOpportunitiesCompletedPayload(BaseModel):
    """
    Payload for OPPORTUNITIES_COMPLETED event.

    Attributes:
        operation_name: Operation name
        opportunities_count: Number of opportunities
        total_potential_improvement_percent: Total improvement potential
        categories: Optimization categories
        processing_time_ms: Processing time
        cache_hit: Whether cached
    """

    operation_name: str = Field(
        ...,
        description="Operation name",
    )

    opportunities_count: int = Field(
        ...,
        description="Number of opportunities",
        ge=0,
    )

    total_potential_improvement_percent: float = Field(
        ...,
        description="Total improvement potential",
        ge=0.0,
    )

    categories: list[str] = Field(
        default_factory=list,
        description="Optimization categories",
        examples=[["caching", "database", "algorithm"]],
    )

    processing_time_ms: float = Field(
        ...,
        description="Processing time",
        ge=0.0,
    )

    cache_hit: bool = Field(
        default=False,
        description="Whether cached",
    )

    model_config = ConfigDict(frozen=True)


class ModelOpportunitiesFailedPayload(BaseModel):
    """
    Payload for OPPORTUNITIES_FAILED event.

    Attributes:
        operation_name: Operation name
        error_message: Error message
        error_code: Error code
        retry_allowed: Retry allowed
        retry_count: Retry count
        processing_time_ms: Processing time
        error_details: Error details
        suggested_action: Suggested action
    """

    operation_name: str = Field(
        ...,
        description="Operation name",
    )

    error_message: str = Field(
        ...,
        description="Error message",
        min_length=1,
    )

    error_code: EnumPerformanceErrorCode = Field(
        ...,
        description="Error code",
    )

    retry_allowed: bool = Field(
        ...,
        description="Retry allowed",
    )

    retry_count: int = Field(
        default=0,
        description="Retry count",
        ge=0,
    )

    processing_time_ms: float = Field(
        ...,
        description="Processing time",
        ge=0.0,
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Error details",
    )

    suggested_action: Optional[str] = Field(
        None,
        description="Suggested action",
    )

    model_config = ConfigDict(frozen=True)


class ModelOptimizeRequestPayload(BaseModel):
    """
    Payload for OPTIMIZE_REQUESTED event.

    Attributes:
        operation_name: Operation name to optimize
        category: Optimization category
        test_duration_minutes: Test duration
        project_id: Optional project identifier
        user_id: Optional user identifier
    """

    operation_name: str = Field(
        ...,
        description="Operation name to optimize",
        min_length=1,
    )

    category: str = Field(
        ...,
        description="Optimization category",
        min_length=1,
    )

    test_duration_minutes: int = Field(
        default=5,
        description="Test duration in minutes",
        ge=1,
        le=60,
    )

    project_id: Optional[str] = Field(
        None,
        description="Project identifier",
    )

    user_id: Optional[str] = Field(
        None,
        description="User identifier",
    )

    @field_validator("operation_name")
    @classmethod
    def validate_operation_name(cls, v: str) -> str:
        """Ensure operation_name is not empty."""
        if not v or not v.strip():
            raise ValueError("operation_name cannot be empty")
        return v.strip()

    model_config = ConfigDict(frozen=False)


class ModelOptimizeCompletedPayload(BaseModel):
    """
    Payload for OPTIMIZE_COMPLETED event.

    Attributes:
        operation_name: Operation name
        category: Optimization category
        improvement_percent: Improvement percentage
        baseline_ms: Baseline response time
        optimized_ms: Optimized response time
        test_duration_minutes: Test duration
        processing_time_ms: Processing time
        success: Whether optimization succeeded
    """

    operation_name: str = Field(
        ...,
        description="Operation name",
    )

    category: str = Field(
        ...,
        description="Optimization category",
    )

    improvement_percent: float = Field(
        ...,
        description="Improvement percentage",
    )

    baseline_ms: float = Field(
        ...,
        description="Baseline response time",
        ge=0.0,
    )

    optimized_ms: float = Field(
        ...,
        description="Optimized response time",
        ge=0.0,
    )

    test_duration_minutes: int = Field(
        ...,
        description="Test duration",
        ge=1,
    )

    processing_time_ms: float = Field(
        ...,
        description="Processing time",
        ge=0.0,
    )

    success: bool = Field(
        ...,
        description="Whether optimization succeeded",
    )

    model_config = ConfigDict(frozen=True)


class ModelOptimizeFailedPayload(BaseModel):
    """
    Payload for OPTIMIZE_FAILED event.

    Attributes:
        operation_name: Operation name
        category: Optimization category
        error_message: Error message
        error_code: Error code
        retry_allowed: Retry allowed
        retry_count: Retry count
        processing_time_ms: Processing time
        error_details: Error details
        suggested_action: Suggested action
    """

    operation_name: str = Field(
        ...,
        description="Operation name",
    )

    category: str = Field(
        ...,
        description="Optimization category",
    )

    error_message: str = Field(
        ...,
        description="Error message",
        min_length=1,
    )

    error_code: EnumPerformanceErrorCode = Field(
        ...,
        description="Error code",
    )

    retry_allowed: bool = Field(
        ...,
        description="Retry allowed",
    )

    retry_count: int = Field(
        default=0,
        description="Retry count",
        ge=0,
    )

    processing_time_ms: float = Field(
        ...,
        description="Processing time",
        ge=0.0,
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Error details",
    )

    suggested_action: Optional[str] = Field(
        None,
        description="Suggested action",
    )

    model_config = ConfigDict(frozen=True)


class ModelReportRequestPayload(BaseModel):
    """
    Payload for REPORT_REQUESTED event.

    Attributes:
        operation_name: Optional operation name filter
        time_window_hours: Time window in hours
        project_id: Optional project identifier
        user_id: Optional user identifier
    """

    operation_name: Optional[str] = Field(
        None,
        description="Optional operation name filter",
    )

    time_window_hours: int = Field(
        default=24,
        description="Time window in hours",
        ge=1,
        le=720,
    )

    project_id: Optional[str] = Field(
        None,
        description="Project identifier",
    )

    user_id: Optional[str] = Field(
        None,
        description="User identifier",
    )

    model_config = ConfigDict(frozen=False)


class ModelReportCompletedPayload(BaseModel):
    """
    Payload for REPORT_COMPLETED event.

    Attributes:
        operations_count: Number of operations analyzed
        total_measurements: Total measurements
        time_window_hours: Time window
        report_summary: Report summary
        processing_time_ms: Processing time
        cache_hit: Whether cached
    """

    operations_count: int = Field(
        ...,
        description="Number of operations analyzed",
        ge=0,
    )

    total_measurements: int = Field(
        ...,
        description="Total measurements",
        ge=0,
    )

    time_window_hours: int = Field(
        ...,
        description="Time window",
        ge=1,
    )

    report_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Report summary",
    )

    processing_time_ms: float = Field(
        ...,
        description="Processing time",
        ge=0.0,
    )

    cache_hit: bool = Field(
        default=False,
        description="Whether cached",
    )

    model_config = ConfigDict(frozen=True)


class ModelReportFailedPayload(BaseModel):
    """
    Payload for REPORT_FAILED event.

    Attributes:
        error_message: Error message
        error_code: Error code
        retry_allowed: Retry allowed
        retry_count: Retry count
        processing_time_ms: Processing time
        error_details: Error details
        suggested_action: Suggested action
    """

    error_message: str = Field(
        ...,
        description="Error message",
        min_length=1,
    )

    error_code: EnumPerformanceErrorCode = Field(
        ...,
        description="Error code",
    )

    retry_allowed: bool = Field(
        ...,
        description="Retry allowed",
    )

    retry_count: int = Field(
        default=0,
        description="Retry count",
        ge=0,
    )

    processing_time_ms: float = Field(
        ...,
        description="Processing time",
        ge=0.0,
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Error details",
    )

    suggested_action: Optional[str] = Field(
        None,
        description="Suggested action",
    )

    model_config = ConfigDict(frozen=True)


class ModelTrendsRequestPayload(BaseModel):
    """
    Payload for TRENDS_REQUESTED event.

    Attributes:
        operation_name: Optional operation name filter
        time_window_hours: Time window in hours
        project_id: Optional project identifier
        user_id: Optional user identifier
    """

    operation_name: Optional[str] = Field(
        None,
        description="Optional operation name filter",
    )

    time_window_hours: int = Field(
        default=168,
        description="Time window in hours (default: 1 week)",
        ge=1,
        le=720,
    )

    project_id: Optional[str] = Field(
        None,
        description="Project identifier",
    )

    user_id: Optional[str] = Field(
        None,
        description="User identifier",
    )

    model_config = ConfigDict(frozen=False)


class ModelTrendsCompletedPayload(BaseModel):
    """
    Payload for TRENDS_COMPLETED event.

    Attributes:
        operations_count: Number of operations
        trends_count: Number of trends identified
        time_window_hours: Time window
        trends_summary: Trends summary
        processing_time_ms: Processing time
        cache_hit: Whether cached
    """

    operations_count: int = Field(
        ...,
        description="Number of operations",
        ge=0,
    )

    trends_count: int = Field(
        ...,
        description="Number of trends identified",
        ge=0,
    )

    time_window_hours: int = Field(
        ...,
        description="Time window",
        ge=1,
    )

    trends_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Trends summary",
    )

    processing_time_ms: float = Field(
        ...,
        description="Processing time",
        ge=0.0,
    )

    cache_hit: bool = Field(
        default=False,
        description="Whether cached",
    )

    model_config = ConfigDict(frozen=True)


class ModelTrendsFailedPayload(BaseModel):
    """
    Payload for TRENDS_FAILED event.

    Attributes:
        error_message: Error message
        error_code: Error code
        retry_allowed: Retry allowed
        retry_count: Retry count
        processing_time_ms: Processing time
        error_details: Error details
        suggested_action: Suggested action
    """

    error_message: str = Field(
        ...,
        description="Error message",
        min_length=1,
    )

    error_code: EnumPerformanceErrorCode = Field(
        ...,
        description="Error code",
    )

    retry_allowed: bool = Field(
        ...,
        description="Retry allowed",
    )

    retry_count: int = Field(
        default=0,
        description="Retry count",
        ge=0,
    )

    processing_time_ms: float = Field(
        ...,
        description="Processing time",
        ge=0.0,
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Error details",
    )

    suggested_action: Optional[str] = Field(
        None,
        description="Suggested action",
    )

    model_config = ConfigDict(frozen=True)


class PerformanceEventHelpers:
    """
    Helper methods for creating and managing Performance events.

    Provides factory methods to create properly-formed event envelopes
    with correct topic routing, correlation tracking, and serialization.
    """

    SERVICE_PREFIX = "archon-intelligence"
    DOMAIN = "performance"
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
        """
        Create event envelope for any performance event.

        Args:
            event_type: Event type suffix
            payload: Event payload model
            correlation_id: Optional correlation ID
            causation_id: Optional causation ID
            source_instance: Optional source instance

        Returns:
            Event envelope dictionary
        """
        correlation_id = correlation_id or uuid4()

        # Local import to avoid circular dependency
        from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

        envelope = ModelEventEnvelope(
            payload=payload if isinstance(payload, dict) else payload.model_dump(),
            correlation_id=correlation_id,
            source_tool="omninode-intelligence",
            metadata={
                "event_type": f"omninode.{PerformanceEventHelpers.DOMAIN}.{PerformanceEventHelpers.PATTERN}.{event_type}.{PerformanceEventHelpers.VERSION}",
                "service": PerformanceEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "intelligence-performance-1",
                "causation_id": str(causation_id) if causation_id else None,
            },
        )

        return envelope.model_dump()

    @staticmethod
    def get_kafka_topic(
        event_type: EnumPerformanceEventType, environment: str = "development"
    ) -> str:
        """
        Generate Kafka topic name for event type.

        Topic Format: {env}.{service}.{domain}.{event_type}.{version}

        Args:
            event_type: Type of performance event
            environment: Environment

        Returns:
            Kafka topic name
        """
        env_prefix = "dev" if environment == "development" else environment
        event_suffix = event_type.value.replace("_", "-").lower()
        return f"{env_prefix}.{PerformanceEventHelpers.SERVICE_PREFIX}.{PerformanceEventHelpers.DOMAIN}.{event_suffix}.{PerformanceEventHelpers.VERSION}"
