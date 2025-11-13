"""
Quality Assessment Event Contracts - ONEX Compliant Kafka Event Schemas

Event schemas for Quality Assessment operations:
- CODE_ASSESSMENT_REQUESTED/COMPLETED/FAILED: Code quality analysis
- DOCUMENT_ASSESSMENT_REQUESTED/COMPLETED/FAILED: Document quality analysis
- COMPLIANCE_CHECK_REQUESTED/COMPLETED/FAILED: ONEX compliance validation

ONEX Compliance:
- Model-based naming: ModelQualityAssessment{Type}Payload
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
from typing import Any, Optional
from uuid import UUID, uuid4

# ModelEventEnvelope imported locally in methods to avoid circular import issue
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Type-only import for type hints


class EnumQualityAssessmentEventType(str, Enum):
    """Event types for quality assessment operations."""

    # Code Assessment Events
    CODE_ASSESSMENT_REQUESTED = "CODE_ASSESSMENT_REQUESTED"
    CODE_ASSESSMENT_COMPLETED = "CODE_ASSESSMENT_COMPLETED"
    CODE_ASSESSMENT_FAILED = "CODE_ASSESSMENT_FAILED"

    # Document Assessment Events
    DOCUMENT_ASSESSMENT_REQUESTED = "DOCUMENT_ASSESSMENT_REQUESTED"
    DOCUMENT_ASSESSMENT_COMPLETED = "DOCUMENT_ASSESSMENT_COMPLETED"
    DOCUMENT_ASSESSMENT_FAILED = "DOCUMENT_ASSESSMENT_FAILED"

    # Compliance Check Events
    COMPLIANCE_CHECK_REQUESTED = "COMPLIANCE_CHECK_REQUESTED"
    COMPLIANCE_CHECK_COMPLETED = "COMPLIANCE_CHECK_COMPLETED"
    COMPLIANCE_CHECK_FAILED = "COMPLIANCE_CHECK_FAILED"


class EnumQualityAssessmentErrorCode(str, Enum):
    """Error codes for failed quality assessment operations."""

    INVALID_INPUT = "INVALID_INPUT"
    UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"
    PARSING_ERROR = "PARSING_ERROR"
    TIMEOUT = "TIMEOUT"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INSUFFICIENT_CONTENT = "INSUFFICIENT_CONTENT"


# ============================================================================
# Code Assessment Event Payloads
# ============================================================================


class ModelCodeAssessmentRequestPayload(BaseModel):
    """
    Payload for CODE_ASSESSMENT_REQUESTED event.

    Attributes:
        content: Code content to assess
        source_path: Path to source file
        language: Programming language
        include_patterns: Include pattern analysis
        include_compliance: Include ONEX compliance check
        project_id: Optional project identifier
        user_id: Optional user identifier
    """

    content: str = Field(
        ...,
        description="Code content to assess",
        min_length=1,
        examples=["def hello():\n    pass"],
    )

    source_path: str = Field(
        default="",
        description="Path to source file",
        examples=["src/api/endpoints.py"],
    )

    language: str = Field(
        default="python",
        description="Programming language",
        examples=["python", "typescript", "rust", "go"],
    )

    include_patterns: bool = Field(
        default=True,
        description="Include pattern analysis",
    )

    include_compliance: bool = Field(
        default=True,
        description="Include ONEX compliance check",
    )

    project_id: Optional[str] = Field(
        None,
        description="Project identifier for context",
        examples=["project-123", "omniarchon"],
    )

    user_id: Optional[str] = Field(
        None,
        description="User identifier for authorization",
        examples=["user-456"],
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Ensure content is not empty or whitespace."""
        if not v or not v.strip():
            raise ValueError("content cannot be empty or whitespace")
        return v

    model_config = ConfigDict(frozen=False)


class ModelCodeAssessmentCompletedPayload(BaseModel):
    """
    Payload for CODE_ASSESSMENT_COMPLETED event.

    Attributes:
        source_path: File path analyzed
        quality_score: Overall quality score (0.0-1.0)
        architectural_compliance: ONEX compliance score (0.0-1.0)
        complexity_score: Code complexity score (0.0-1.0)
        maintainability_score: Maintainability score (0.0-1.0)
        patterns_count: Number of patterns detected
        issues_count: Number of issues identified
        recommendations_count: Number of recommendations
        processing_time_ms: Processing time in milliseconds
        cache_hit: Whether result was cached
    """

    source_path: str = Field(
        ...,
        description="File path analyzed",
        examples=["src/api/endpoints.py"],
    )

    quality_score: float = Field(
        ...,
        description="Overall quality score (0.0-1.0)",
        ge=0.0,
        le=1.0,
        examples=[0.87, 0.92],
    )

    architectural_compliance: float = Field(
        ...,
        description="ONEX compliance score (0.0-1.0)",
        ge=0.0,
        le=1.0,
        examples=[0.92, 0.88],
    )

    complexity_score: Optional[float] = Field(
        None,
        description="Code complexity score (0.0-1.0, lower is better)",
        ge=0.0,
        le=1.0,
        examples=[0.45, 0.62],
    )

    maintainability_score: Optional[float] = Field(
        None,
        description="Maintainability score (0.0-1.0, higher is better)",
        ge=0.0,
        le=1.0,
        examples=[0.78, 0.85],
    )

    patterns_count: int = Field(
        default=0,
        description="Number of patterns detected",
        ge=0,
        examples=[5, 12],
    )

    issues_count: int = Field(
        default=0,
        description="Number of issues identified",
        ge=0,
        examples=[3, 0],
    )

    recommendations_count: int = Field(
        default=0,
        description="Number of recommendations",
        ge=0,
        examples=[5, 2],
    )

    processing_time_ms: float = Field(
        ...,
        description="Processing time in milliseconds",
        ge=0.0,
        examples=[1234.5, 567.8],
    )

    cache_hit: bool = Field(
        default=False,
        description="Whether result was cached",
    )

    model_config = ConfigDict(frozen=True)


class ModelCodeAssessmentFailedPayload(BaseModel):
    """
    Payload for CODE_ASSESSMENT_FAILED event.

    Attributes:
        source_path: File path that failed
        error_message: Human-readable error description
        error_code: Machine-readable error code
        retry_allowed: Whether retry is allowed
        retry_count: Number of retries attempted
        processing_time_ms: Time before failure
        error_details: Additional error context
        suggested_action: Recommended action
    """

    source_path: str = Field(
        ...,
        description="File path that failed",
        examples=["src/broken/invalid.py"],
    )

    error_message: str = Field(
        ...,
        description="Human-readable error description",
        min_length=1,
        examples=["Failed to parse Python code: unexpected EOF"],
    )

    error_code: EnumQualityAssessmentErrorCode = Field(
        ...,
        description="Machine-readable error code",
    )

    retry_allowed: bool = Field(
        ...,
        description="Whether retry is allowed",
    )

    retry_count: int = Field(
        default=0,
        description="Number of retries attempted",
        ge=0,
    )

    processing_time_ms: float = Field(
        ...,
        description="Time before failure in milliseconds",
        ge=0.0,
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional error context",
    )

    suggested_action: Optional[str] = Field(
        None,
        description="Recommended action",
        examples=["Verify source code syntax is valid"],
    )

    model_config = ConfigDict(frozen=True)


class ModelDocumentAssessmentRequestPayload(BaseModel):
    """
    Payload for DOCUMENT_ASSESSMENT_REQUESTED event.

    Attributes:
        content: Document content to analyze
        document_type: Type of document
        check_completeness: Check completeness
        include_recommendations: Include recommendations
        project_id: Optional project identifier
        user_id: Optional user identifier
    """

    content: str = Field(
        ...,
        description="Document content to analyze",
        min_length=1,
        examples=["# Title\n\nContent here"],
    )

    document_type: str = Field(
        default="markdown",
        description="Type of document",
        examples=["markdown", "rst", "text"],
    )

    check_completeness: bool = Field(
        default=True,
        description="Check completeness",
    )

    include_recommendations: bool = Field(
        default=True,
        description="Include recommendations",
    )

    project_id: Optional[str] = Field(
        None,
        description="Project identifier",
    )

    user_id: Optional[str] = Field(
        None,
        description="User identifier",
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Ensure content is not empty."""
        if not v or not v.strip():
            raise ValueError("content cannot be empty")
        return v

    model_config = ConfigDict(frozen=False)


class ModelDocumentAssessmentCompletedPayload(BaseModel):
    """
    Payload for DOCUMENT_ASSESSMENT_COMPLETED event.

    Attributes:
        quality_score: Overall quality score (0.0-1.0)
        completeness_score: Completeness score (0.0-1.0)
        structure_score: Structure score (0.0-1.0)
        clarity_score: Clarity score (0.0-1.0)
        word_count: Total word count
        section_count: Number of sections
        recommendations_count: Number of recommendations
        processing_time_ms: Processing time
        cache_hit: Whether cached
    """

    quality_score: float = Field(
        ...,
        description="Overall quality score (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )

    completeness_score: float = Field(
        ...,
        description="Completeness score (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )

    structure_score: float = Field(
        ...,
        description="Structure score (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )

    clarity_score: float = Field(
        ...,
        description="Clarity score (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )

    word_count: int = Field(
        ...,
        description="Total word count",
        ge=0,
    )

    section_count: int = Field(
        ...,
        description="Number of sections",
        ge=0,
    )

    recommendations_count: int = Field(
        default=0,
        description="Number of recommendations",
        ge=0,
    )

    processing_time_ms: float = Field(
        ...,
        description="Processing time in milliseconds",
        ge=0.0,
    )

    cache_hit: bool = Field(
        default=False,
        description="Whether cached",
    )

    model_config = ConfigDict(frozen=True)


class ModelDocumentAssessmentFailedPayload(BaseModel):
    """
    Payload for DOCUMENT_ASSESSMENT_FAILED event.

    Attributes:
        error_message: Human-readable error
        error_code: Machine-readable error code
        retry_allowed: Whether retry allowed
        retry_count: Retry attempts
        processing_time_ms: Time before failure
        error_details: Error context
        suggested_action: Recommended action
    """

    error_message: str = Field(
        ...,
        description="Human-readable error",
        min_length=1,
    )

    error_code: EnumQualityAssessmentErrorCode = Field(
        ...,
        description="Machine-readable error code",
    )

    retry_allowed: bool = Field(
        ...,
        description="Whether retry allowed",
    )

    retry_count: int = Field(
        default=0,
        description="Retry attempts",
        ge=0,
    )

    processing_time_ms: float = Field(
        ...,
        description="Time before failure",
        ge=0.0,
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Error context",
    )

    suggested_action: Optional[str] = Field(
        None,
        description="Recommended action",
    )

    model_config = ConfigDict(frozen=True)


class ModelComplianceCheckRequestPayload(BaseModel):
    """
    Payload for COMPLIANCE_CHECK_REQUESTED event.

    Attributes:
        content: Code content to check
        architecture_type: Architecture type (onex, clean, etc.)
        project_id: Optional project identifier
        user_id: Optional user identifier
    """

    content: str = Field(
        ...,
        description="Code content to check",
        min_length=1,
    )

    architecture_type: str = Field(
        default="onex",
        description="Architecture type",
        examples=["onex", "clean", "hexagonal"],
    )

    project_id: Optional[str] = Field(
        None,
        description="Project identifier",
    )

    user_id: Optional[str] = Field(
        None,
        description="User identifier",
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Ensure content is not empty."""
        if not v or not v.strip():
            raise ValueError("content cannot be empty")
        return v

    model_config = ConfigDict(frozen=False)


class ModelComplianceCheckCompletedPayload(BaseModel):
    """
    Payload for COMPLIANCE_CHECK_COMPLETED event.

    Attributes:
        compliance_score: Overall compliance score (0.0-1.0)
        violations_count: Number of violations
        recommendations_count: Number of recommendations
        architecture_type: Architecture type checked
        processing_time_ms: Processing time
        cache_hit: Whether cached
    """

    compliance_score: float = Field(
        ...,
        description="Overall compliance score (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )

    violations_count: int = Field(
        default=0,
        description="Number of violations",
        ge=0,
    )

    recommendations_count: int = Field(
        default=0,
        description="Number of recommendations",
        ge=0,
    )

    architecture_type: str = Field(
        ...,
        description="Architecture type checked",
    )

    processing_time_ms: float = Field(
        ...,
        description="Processing time in milliseconds",
        ge=0.0,
    )

    cache_hit: bool = Field(
        default=False,
        description="Whether cached",
    )

    model_config = ConfigDict(frozen=True)


class ModelComplianceCheckFailedPayload(BaseModel):
    """
    Payload for COMPLIANCE_CHECK_FAILED event.

    Attributes:
        error_message: Human-readable error
        error_code: Machine-readable error code
        retry_allowed: Whether retry allowed
        retry_count: Retry attempts
        processing_time_ms: Time before failure
        error_details: Error context
        suggested_action: Recommended action
    """

    error_message: str = Field(
        ...,
        description="Human-readable error",
        min_length=1,
    )

    error_code: EnumQualityAssessmentErrorCode = Field(
        ...,
        description="Machine-readable error code",
    )

    retry_allowed: bool = Field(
        ...,
        description="Whether retry allowed",
    )

    retry_count: int = Field(
        default=0,
        description="Retry attempts",
        ge=0,
    )

    processing_time_ms: float = Field(
        ...,
        description="Time before failure",
        ge=0.0,
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Error context",
    )

    suggested_action: Optional[str] = Field(
        None,
        description="Recommended action",
    )

    model_config = ConfigDict(frozen=True)


class QualityAssessmentEventHelpers:
    """
    Helper methods for creating and managing Quality Assessment events.

    Provides factory methods to create properly-formed event envelopes
    with correct topic routing, correlation tracking, and serialization.
    """

    SERVICE_PREFIX = "archon-intelligence"
    DOMAIN = "quality"
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
        Create event envelope for any quality assessment event.

        Args:
            event_type: Event type suffix (e.g., "code_assessment_requested")
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
                "event_type": f"omninode.{QualityAssessmentEventHelpers.DOMAIN}.{QualityAssessmentEventHelpers.PATTERN}.{event_type}.{QualityAssessmentEventHelpers.VERSION}",
                "service": QualityAssessmentEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "intelligence-quality-1",
                "causation_id": str(causation_id) if causation_id else None,
            },
        )

        return envelope.model_dump()

    @staticmethod
    def get_kafka_topic(
        event_type: EnumQualityAssessmentEventType, environment: str = "development"
    ) -> str:
        """
        Generate Kafka topic name for event type.

        Topic Format: {env}.{service}.{domain}.{event_type}.{version}

        Args:
            event_type: Type of quality assessment event
            environment: Environment (development, staging, production)

        Returns:
            Kafka topic name
        """
        env_prefix = "dev" if environment == "development" else environment
        event_suffix = event_type.value.replace("_", "-").lower()
        return f"{env_prefix}.{QualityAssessmentEventHelpers.SERVICE_PREFIX}.{QualityAssessmentEventHelpers.DOMAIN}.{event_suffix}.{QualityAssessmentEventHelpers.VERSION}"
