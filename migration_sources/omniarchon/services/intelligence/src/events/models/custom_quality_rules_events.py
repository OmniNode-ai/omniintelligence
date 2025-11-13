"""
Custom Quality Rules Event Contracts - ONEX Compliant Kafka Event Schemas

Event schemas for Custom Quality Rules operations (8 total):
1. Rule Evaluation (POST /evaluate)
2. Get Project Rules (GET /project/{project_id}/rules)
3. Load Configuration (POST /project/{project_id}/load-config)
4. Register Rule (POST /project/{project_id}/rule)
5. Enable Rule (PUT /project/{project_id}/rule/{rule_id}/enable)
6. Disable Rule (PUT /project/{project_id}/rule/{rule_id}/disable)
7. Clear Rules (DELETE /project/{project_id}/rules)
8. Health Check (GET /health)

Each operation has 3 event types: REQUESTED, COMPLETED, FAILED

ONEX Compliance:
- Model-based naming: ModelCustomRules{Operation}{Type}Payload
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


class EnumCustomRulesEventType(str, Enum):
    """Event types for custom quality rules operations."""

    # Rule Evaluation
    EVALUATE_REQUESTED = "EVALUATE_REQUESTED"
    EVALUATE_COMPLETED = "EVALUATE_COMPLETED"
    EVALUATE_FAILED = "EVALUATE_FAILED"

    # Get Rules
    GET_RULES_REQUESTED = "GET_RULES_REQUESTED"
    GET_RULES_COMPLETED = "GET_RULES_COMPLETED"
    GET_RULES_FAILED = "GET_RULES_FAILED"

    # Load Configuration
    LOAD_CONFIG_REQUESTED = "LOAD_CONFIG_REQUESTED"
    LOAD_CONFIG_COMPLETED = "LOAD_CONFIG_COMPLETED"
    LOAD_CONFIG_FAILED = "LOAD_CONFIG_FAILED"

    # Register Rule
    REGISTER_REQUESTED = "REGISTER_REQUESTED"
    REGISTER_COMPLETED = "REGISTER_COMPLETED"
    REGISTER_FAILED = "REGISTER_FAILED"

    # Enable Rule
    ENABLE_REQUESTED = "ENABLE_REQUESTED"
    ENABLE_COMPLETED = "ENABLE_COMPLETED"
    ENABLE_FAILED = "ENABLE_FAILED"

    # Disable Rule
    DISABLE_REQUESTED = "DISABLE_REQUESTED"
    DISABLE_COMPLETED = "DISABLE_COMPLETED"
    DISABLE_FAILED = "DISABLE_FAILED"

    # Clear Rules
    CLEAR_REQUESTED = "CLEAR_REQUESTED"
    CLEAR_COMPLETED = "CLEAR_COMPLETED"
    CLEAR_FAILED = "CLEAR_FAILED"

    # Health Check
    HEALTH_REQUESTED = "HEALTH_REQUESTED"
    HEALTH_COMPLETED = "HEALTH_COMPLETED"
    HEALTH_FAILED = "HEALTH_FAILED"


class EnumCustomRulesErrorCode(str, Enum):
    """Error codes for failed custom rules operations."""

    INVALID_INPUT = "INVALID_INPUT"
    RULE_NOT_FOUND = "RULE_NOT_FOUND"
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    PERMISSION_ERROR = "PERMISSION_ERROR"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# ============================================================================
# Rule Evaluation Events
# ============================================================================


class ModelCustomRulesEvaluateRequestPayload(BaseModel):
    """Payload for EVALUATE_REQUESTED event."""

    project_id: str = Field(...)
    code: str = Field(..., max_length=1_000_000)
    file_path: Optional[str] = Field(None)


class ModelCustomRulesEvaluateCompletedPayload(BaseModel):
    """Payload for EVALUATE_COMPLETED event."""

    custom_score: float = Field(..., ge=0.0, le=1.0)
    violations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    rules_evaluated: int = Field(..., ge=0)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelCustomRulesEvaluateFailedPayload(BaseModel):
    """Payload for EVALUATE_FAILED event."""

    project_id: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumCustomRulesErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Get Project Rules Events
# ============================================================================


class ModelCustomRulesGetRulesRequestPayload(BaseModel):
    """Payload for GET_RULES_REQUESTED event."""

    project_id: str = Field(...)


class ModelCustomRulesGetRulesCompletedPayload(BaseModel):
    """Payload for GET_RULES_COMPLETED event."""

    project_id: str = Field(...)
    rules: list[dict[str, Any]] = Field(...)
    total_rules: int = Field(..., ge=0)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelCustomRulesGetRulesFailedPayload(BaseModel):
    """Payload for GET_RULES_FAILED event."""

    project_id: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumCustomRulesErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Load Configuration Events
# ============================================================================


class ModelCustomRulesLoadConfigRequestPayload(BaseModel):
    """Payload for LOAD_CONFIG_REQUESTED event."""

    project_id: str = Field(...)
    config_path: str = Field(...)


class ModelCustomRulesLoadConfigCompletedPayload(BaseModel):
    """Payload for LOAD_CONFIG_COMPLETED event."""

    project_id: str = Field(...)
    rules_loaded: int = Field(..., ge=0)
    rule_ids: list[str] = Field(...)
    config_path: str = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelCustomRulesLoadConfigFailedPayload(BaseModel):
    """Payload for LOAD_CONFIG_FAILED event."""

    project_id: str = Field(...)
    config_path: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumCustomRulesErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Register Rule Events
# ============================================================================


class ModelCustomRulesRegisterRequestPayload(BaseModel):
    """Payload for REGISTER_REQUESTED event."""

    project_id: str = Field(...)
    rule_id: str = Field(...)
    rule_type: str = Field(...)
    description: str = Field(...)
    severity: str = Field(...)
    weight: float = Field(default=0.1, ge=0.0, le=1.0)


class ModelCustomRulesRegisterCompletedPayload(BaseModel):
    """Payload for REGISTER_COMPLETED event."""

    project_id: str = Field(...)
    rule_id: str = Field(...)
    rule_type: str = Field(...)
    severity: str = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelCustomRulesRegisterFailedPayload(BaseModel):
    """Payload for REGISTER_FAILED event."""

    project_id: str = Field(...)
    rule_id: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumCustomRulesErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Enable Rule Events
# ============================================================================


class ModelCustomRulesEnableRequestPayload(BaseModel):
    """Payload for ENABLE_REQUESTED event."""

    project_id: str = Field(...)
    rule_id: str = Field(...)


class ModelCustomRulesEnableCompletedPayload(BaseModel):
    """Payload for ENABLE_COMPLETED event."""

    project_id: str = Field(...)
    rule_id: str = Field(...)
    enabled: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelCustomRulesEnableFailedPayload(BaseModel):
    """Payload for ENABLE_FAILED event."""

    project_id: str = Field(...)
    rule_id: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumCustomRulesErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Disable Rule Events
# ============================================================================


class ModelCustomRulesDisableRequestPayload(BaseModel):
    """Payload for DISABLE_REQUESTED event."""

    project_id: str = Field(...)
    rule_id: str = Field(...)


class ModelCustomRulesDisableCompletedPayload(BaseModel):
    """Payload for DISABLE_COMPLETED event."""

    project_id: str = Field(...)
    rule_id: str = Field(...)
    enabled: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelCustomRulesDisableFailedPayload(BaseModel):
    """Payload for DISABLE_FAILED event."""

    project_id: str = Field(...)
    rule_id: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumCustomRulesErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Clear Rules Events
# ============================================================================


class ModelCustomRulesClearRequestPayload(BaseModel):
    """Payload for CLEAR_REQUESTED event."""

    project_id: str = Field(...)


class ModelCustomRulesClearCompletedPayload(BaseModel):
    """Payload for CLEAR_COMPLETED event."""

    project_id: str = Field(...)
    rules_cleared: int = Field(..., ge=0)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelCustomRulesClearFailedPayload(BaseModel):
    """Payload for CLEAR_FAILED event."""

    project_id: str = Field(...)
    error_message: str = Field(..., min_length=1)
    error_code: EnumCustomRulesErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Health Check Events
# ============================================================================


class ModelCustomRulesHealthRequestPayload(BaseModel):
    """Payload for HEALTH_REQUESTED event."""

    # No required fields
    pass


class ModelCustomRulesHealthCompletedPayload(BaseModel):
    """Payload for HEALTH_COMPLETED event."""

    status: str = Field(...)
    total_projects: int = Field(..., ge=0)
    total_rules: int = Field(..., ge=0)
    processing_time_ms: float = Field(..., ge=0.0)


class ModelCustomRulesHealthFailedPayload(BaseModel):
    """Payload for HEALTH_FAILED event."""

    error_message: str = Field(..., min_length=1)
    error_code: EnumCustomRulesErrorCode = Field(...)
    retry_allowed: bool = Field(...)
    processing_time_ms: float = Field(..., ge=0.0)
    error_details: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Event Envelope Helpers
# ============================================================================


class CustomRulesEventHelpers:
    """Helper methods for creating and managing Custom Quality Rules events."""

    SERVICE_PREFIX = "archon-intelligence"
    DOMAIN = "custom-rules"
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
        """Create event envelope for any custom rules event."""
        correlation_id = correlation_id or uuid4()

        # Local import to avoid circular dependency
        from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

        envelope = ModelEventEnvelope(
            payload=payload if isinstance(payload, dict) else payload.model_dump(),
            correlation_id=correlation_id,
            source_tool="omninode-intelligence",
            metadata={
                "event_type": f"omninode.{CustomRulesEventHelpers.DOMAIN}.{CustomRulesEventHelpers.PATTERN}.{event_type}.{CustomRulesEventHelpers.VERSION}",
                "service": CustomRulesEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "custom-rules-1",
                "causation_id": str(causation_id) if causation_id else None,
            },
        )

        return envelope.model_dump()

    @staticmethod
    def get_kafka_topic(
        event_type: EnumCustomRulesEventType, environment: str = "development"
    ) -> str:
        """Generate Kafka topic name for event type."""
        env_prefix = "dev" if environment == "development" else environment
        event_suffix = event_type.value.replace("_", "-").lower()
        return f"{env_prefix}.{CustomRulesEventHelpers.SERVICE_PREFIX}.{CustomRulesEventHelpers.DOMAIN}.{event_suffix}.{CustomRulesEventHelpers.VERSION}"


# ============================================================================
# Convenience Functions
# ============================================================================


def create_evaluate_requested_event(
    project_id: str,
    code: str,
    file_path: Optional[str] = None,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """Convenience function to create EVALUATE_REQUESTED event."""
    payload = ModelCustomRulesEvaluateRequestPayload(
        project_id=project_id, code=code, file_path=file_path
    )
    return CustomRulesEventHelpers.create_event_envelope(
        "custom-rules.evaluate.requested", payload, correlation_id
    )


def create_register_requested_event(
    project_id: str,
    rule_id: str,
    rule_type: str,
    description: str,
    severity: str,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """Convenience function to create REGISTER_REQUESTED event."""
    payload = ModelCustomRulesRegisterRequestPayload(
        project_id=project_id,
        rule_id=rule_id,
        rule_type=rule_type,
        description=description,
        severity=severity,
    )
    return CustomRulesEventHelpers.create_event_envelope(
        "custom-rules.register.requested", payload, correlation_id
    )
