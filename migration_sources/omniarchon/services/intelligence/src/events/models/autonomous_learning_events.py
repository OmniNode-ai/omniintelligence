"""
Autonomous Learning Event Contracts - ONEX Compliant Kafka Event Schemas

Event schemas for Autonomous Learning operations (7 total):
1. Pattern Ingestion (POST /patterns/ingest)
2. Pattern Success Query (GET /patterns/success)
3. Agent Prediction (POST /predict/agent)
4. Time Prediction (POST /predict/time)
5. Safety Score Calculation (GET /calculate/safety)
6. Statistics (GET /stats)
7. Health Check (GET /health)

Each operation has 3 event types: REQUESTED, COMPLETED, FAILED

ONEX Compliance:
- Model-based naming: ModelAutonomous{Operation}{Type}Payload
- Strong typing with Pydantic v2
- Event envelope integration with ModelEventEnvelope
- Kafka topic routing following event bus architecture
- Serialization/deserialization helpers
- Comprehensive validation

Created: 2025-10-22
Reference: intelligence_adapter_events.py, EVENT_BUS_ARCHITECTURE.md
"""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

# ModelEventEnvelope imported locally in methods to avoid circular import issue
from pydantic import BaseModel, Field, field_validator

# Import from local event base to avoid circular imports

# Type-only import for type hints


class EnumAutonomousEventType(str, Enum):
    """Event types for autonomous learning operations."""

    # Pattern Ingestion
    PATTERN_INGEST_REQUESTED = "PATTERN_INGEST_REQUESTED"
    PATTERN_INGEST_COMPLETED = "PATTERN_INGEST_COMPLETED"
    PATTERN_INGEST_FAILED = "PATTERN_INGEST_FAILED"

    # Pattern Success Query
    PATTERN_SUCCESS_REQUESTED = "PATTERN_SUCCESS_REQUESTED"
    PATTERN_SUCCESS_COMPLETED = "PATTERN_SUCCESS_COMPLETED"
    PATTERN_SUCCESS_FAILED = "PATTERN_SUCCESS_FAILED"

    # Agent Prediction
    AGENT_PREDICT_REQUESTED = "AGENT_PREDICT_REQUESTED"
    AGENT_PREDICT_COMPLETED = "AGENT_PREDICT_COMPLETED"
    AGENT_PREDICT_FAILED = "AGENT_PREDICT_FAILED"

    # Time Prediction
    TIME_PREDICT_REQUESTED = "TIME_PREDICT_REQUESTED"
    TIME_PREDICT_COMPLETED = "TIME_PREDICT_COMPLETED"
    TIME_PREDICT_FAILED = "TIME_PREDICT_FAILED"

    # Safety Score Calculation
    SAFETY_SCORE_REQUESTED = "SAFETY_SCORE_REQUESTED"
    SAFETY_SCORE_COMPLETED = "SAFETY_SCORE_COMPLETED"
    SAFETY_SCORE_FAILED = "SAFETY_SCORE_FAILED"

    # Statistics
    STATS_REQUESTED = "STATS_REQUESTED"
    STATS_COMPLETED = "STATS_COMPLETED"
    STATS_FAILED = "STATS_FAILED"

    # Health Check
    HEALTH_REQUESTED = "HEALTH_REQUESTED"
    HEALTH_COMPLETED = "HEALTH_COMPLETED"
    HEALTH_FAILED = "HEALTH_FAILED"


class EnumAutonomousErrorCode(str, Enum):
    """Error codes for failed autonomous operations."""

    INVALID_INPUT = "INVALID_INPUT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    PREDICTION_ERROR = "PREDICTION_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
    PATTERN_NOT_FOUND = "PATTERN_NOT_FOUND"


# ============================================================================
# Pattern Ingestion Events
# ============================================================================


class ModelAutonomousPatternsIngestRequestPayload(BaseModel):
    """Payload for PATTERN_INGEST_REQUESTED event."""

    execution_pattern: dict[str, Any] = Field(
        ...,
        description="Execution pattern data to ingest",
        examples=[
            {
                "execution_id": "exec-123",
                "task_characteristics": {"task_type": "code_generation"},
                "execution_details": {"agent_used": "agent-api-architect"},
                "outcome": {"success": True, "duration_ms": 285000},
            }
        ],
    )

    project_id: Optional[str] = Field(
        None,
        description="Project identifier for context",
    )


class ModelAutonomousPatternsIngestCompletedPayload(BaseModel):
    """Payload for PATTERN_INGEST_COMPLETED event."""

    pattern_id: str = Field(..., description="Created/updated pattern ID")
    pattern_name: str = Field(..., description="Pattern name")
    is_new_pattern: bool = Field(..., description="Whether pattern is new")
    success_rate: float = Field(..., ge=0.0, le=1.0)
    total_executions: int = Field(..., ge=0)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelAutonomousPatternsIngestFailedPayload(BaseModel):
    """Payload for PATTERN_INGEST_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumAutonomousErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Pattern Success Query Events
# ============================================================================


class ModelAutonomousPatternsSuccessRequestPayload(BaseModel):
    """Payload for PATTERN_SUCCESS_REQUESTED event."""

    min_success_rate: float = Field(default=0.8, ge=0.0, le=1.0)
    task_type: Optional[str] = Field(None)
    limit: int = Field(default=20, ge=1, le=100)


class ModelAutonomousPatternsSuccessCompletedPayload(BaseModel):
    """Payload for PATTERN_SUCCESS_COMPLETED event."""

    patterns: list[dict[str, Any]] = Field(..., description="Success patterns")
    count: int = Field(..., ge=0)
    filters_applied: dict[str, Any] = Field(default_factory=dict)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelAutonomousPatternsSuccessFailedPayload(BaseModel):
    """Payload for PATTERN_SUCCESS_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumAutonomousErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Agent Prediction Events
# ============================================================================


class ModelAutonomousAgentPredictRequestPayload(BaseModel):
    """Payload for AGENT_PREDICT_REQUESTED event."""

    task_characteristics: Optional[dict[str, Any]] = Field(
        None,
        description="Task characteristics for prediction",
    )
    context: Optional[dict[str, Any]] = Field(None, description="Task context")
    requirements: Optional[dict[str, Any]] = Field(
        None, description="Task requirements"
    )
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)

    @field_validator("task_characteristics", "context", "requirements", mode="before")
    @classmethod
    def validate_optional_dict(cls, v: Any, info) -> Optional[dict[str, Any]]:
        """
        Validate optional dict fields to prevent None access errors.

        Returns None if value is None, otherwise validates it's a dict.
        This prevents AttributeError when accessing dict methods on None values.

        Expected schema (when present):
        - task_characteristics: {"task_type": str, "complexity": float, ...}
        - context: {"domain": str, "previous_agent": str, ...}
        - requirements: {"constraints": list, "goals": list, ...}
        """
        if v is None:
            return None
        if not isinstance(v, dict):
            field_name = info.field_name
            raise ValueError(
                f"{field_name} must be a dict or None, got {type(v).__name__}"
            )
        return v


class ModelAutonomousAgentPredictCompletedPayload(BaseModel):
    """Payload for AGENT_PREDICT_COMPLETED event."""

    recommended_agent: str = Field(..., description="Recommended agent name")
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    confidence_level: str = Field(...)
    reasoning: str = Field(...)
    alternative_agents: list[dict[str, Any]] = Field(default_factory=list)
    expected_success_rate: float = Field(..., ge=0.0, le=1.0)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelAutonomousAgentPredictFailedPayload(BaseModel):
    """Payload for AGENT_PREDICT_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumAutonomousErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Time Prediction Events
# ============================================================================


class ModelAutonomousTimePredictRequestPayload(BaseModel):
    """Payload for TIME_PREDICT_REQUESTED event."""

    task_characteristics: Optional[dict[str, Any]] = Field(None)
    task_description: Optional[str] = Field(None, description="Description of the task")
    agent: str = Field(..., description="Agent that will execute task")
    complexity: Optional[str] = Field(None, description="Task complexity level")

    @field_validator("task_characteristics", mode="before")
    @classmethod
    def validate_optional_dict(cls, v: Any, info) -> Optional[dict[str, Any]]:
        """
        Validate optional dict field to prevent None access errors.

        Expected schema (when present):
        - task_characteristics: {"task_type": str, "estimated_lines": int, ...}
        """
        if v is None:
            return None
        if not isinstance(v, dict):
            field_name = info.field_name
            raise ValueError(
                f"{field_name} must be a dict or None, got {type(v).__name__}"
            )
        return v


class ModelAutonomousTimePredictCompletedPayload(BaseModel):
    """Payload for TIME_PREDICT_COMPLETED event."""

    estimated_duration_ms: int = Field(..., ge=0)
    p25_duration_ms: int = Field(..., ge=0)
    p75_duration_ms: int = Field(..., ge=0)
    p95_duration_ms: int = Field(..., ge=0)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    time_breakdown: dict[str, int] = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelAutonomousTimePredictFailedPayload(BaseModel):
    """Payload for TIME_PREDICT_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumAutonomousErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Safety Score Calculation Events
# ============================================================================


class ModelAutonomousSafetyScoreRequestPayload(BaseModel):
    """Payload for SAFETY_SCORE_REQUESTED event."""

    task_type: str = Field(...)
    complexity: Optional[float] = Field(None, ge=0.0, le=1.0)
    change_scope: Optional[str] = Field(None)
    context: Optional[dict[str, Any]] = Field(None, description="Task context")
    agent: Optional[str] = Field(None)

    @field_validator("context", mode="before")
    @classmethod
    def validate_optional_dict(cls, v: Any, info) -> Optional[dict[str, Any]]:
        """
        Validate optional dict field to prevent None access errors.

        Expected schema (when present):
        - context: {"file_paths": list[str], "dependencies": list[str], ...}
        """
        if v is None:
            return None
        if not isinstance(v, dict):
            field_name = info.field_name
            raise ValueError(
                f"{field_name} must be a dict or None, got {type(v).__name__}"
            )
        return v


class ModelAutonomousSafetyScoreCompletedPayload(BaseModel):
    """Payload for SAFETY_SCORE_COMPLETED event."""

    safety_score: float = Field(..., ge=0.0, le=1.0)
    safety_rating: str = Field(...)
    can_execute_autonomously: bool = Field(...)
    requires_human_review: bool = Field(...)
    risk_factors: list[dict[str, Any]] = Field(default_factory=list)
    safety_checks_required: list[str] = Field(default_factory=list)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelAutonomousSafetyScoreFailedPayload(BaseModel):
    """Payload for SAFETY_SCORE_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumAutonomousErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Statistics Events
# ============================================================================


class ModelAutonomousStatsRequestPayload(BaseModel):
    """Payload for STATS_REQUESTED event."""

    # No required fields for stats request
    pass


class ModelAutonomousStatsCompletedPayload(BaseModel):
    """Payload for STATS_COMPLETED event."""

    total_patterns: int = Field(..., ge=0)
    total_agents: int = Field(..., ge=0)
    average_success_rate: float = Field(..., ge=0.0, le=1.0)
    total_executions: int = Field(..., ge=0)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelAutonomousStatsFailedPayload(BaseModel):
    """Payload for STATS_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumAutonomousErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Health Check Events
# ============================================================================


class ModelAutonomousHealthRequestPayload(BaseModel):
    """Payload for HEALTH_REQUESTED event."""

    # No required fields for health request
    pass


class ModelAutonomousHealthCompletedPayload(BaseModel):
    """Payload for HEALTH_COMPLETED event."""

    status: str = Field(...)
    service: str = Field(...)
    version: str = Field(...)
    uptime_seconds: int = Field(..., ge=0)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelAutonomousHealthFailedPayload(BaseModel):
    """Payload for HEALTH_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumAutonomousErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Event Envelope Helpers
# ============================================================================


class AutonomousLearningEventHelpers:
    """Helper methods for creating and managing Autonomous Learning events."""

    SERVICE_PREFIX = "archon-intelligence"
    DOMAIN = "autonomous"
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
        """Create event envelope for any autonomous learning event."""
        correlation_id = correlation_id or uuid4()

        # Local import to avoid circular dependency
        from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

        envelope = ModelEventEnvelope(
            payload=payload if isinstance(payload, dict) else payload.model_dump(),
            correlation_id=correlation_id,
            source_tool="omninode-intelligence",
            metadata={
                "event_type": f"omninode.{AutonomousLearningEventHelpers.DOMAIN}.{AutonomousLearningEventHelpers.PATTERN}.{event_type}.{AutonomousLearningEventHelpers.VERSION}",
                "service": AutonomousLearningEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "autonomous-learning-1",
                "causation_id": str(causation_id) if causation_id else None,
            },
        )

        return envelope.model_dump()

    @staticmethod
    def get_kafka_topic(
        event_type: EnumAutonomousEventType, environment: str = "development"
    ) -> str:
        """Generate Kafka topic name for event type."""
        env_prefix = "dev" if environment == "development" else environment
        event_suffix = event_type.value.replace("_", "-").lower()
        return f"{env_prefix}.{AutonomousLearningEventHelpers.SERVICE_PREFIX}.{AutonomousLearningEventHelpers.DOMAIN}.{event_suffix}.{AutonomousLearningEventHelpers.VERSION}"


# ============================================================================
# Convenience Functions
# ============================================================================


def create_pattern_ingest_requested_event(
    execution_pattern: dict[str, Any],
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """Convenience function to create PATTERN_INGEST_REQUESTED event."""
    payload = ModelAutonomousPatternsIngestRequestPayload(
        execution_pattern=execution_pattern
    )
    return AutonomousLearningEventHelpers.create_event_envelope(
        "autonomous.patterns-ingest.requested", payload, correlation_id
    )


def create_agent_predict_requested_event(
    task_characteristics: dict[str, Any],
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """Convenience function to create AGENT_PREDICT_REQUESTED event."""
    payload = ModelAutonomousAgentPredictRequestPayload(
        task_characteristics=task_characteristics
    )
    return AutonomousLearningEventHelpers.create_event_envelope(
        "autonomous.predict-agent.requested", payload, correlation_id
    )


def create_safety_score_requested_event(
    task_type: str,
    complexity: float,
    change_scope: str,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """Convenience function to create SAFETY_SCORE_REQUESTED event."""
    payload = ModelAutonomousSafetyScoreRequestPayload(
        task_type=task_type, complexity=complexity, change_scope=change_scope
    )
    return AutonomousLearningEventHelpers.create_event_envelope(
        "autonomous.safety-score.requested", payload, correlation_id
    )
