"""
Bridge Intelligence Event Contracts - ONEX Compliant Kafka Event Schemas

Event schemas for Bridge Intelligence operations:
- GENERATE_INTELLIGENCE_REQUESTED/COMPLETED/FAILED: Generate OmniNode metadata intelligence
- BRIDGE_HEALTH_REQUESTED/COMPLETED/FAILED: Check bridge service health status
- CAPABILITIES_REQUESTED/COMPLETED/FAILED: Retrieve bridge service capabilities

ONEX Compliance:
- Model-based naming: ModelBridge{Operation}{Type}Payload
- Strong typing with Pydantic v2
- Event envelope integration with ModelEventEnvelope
- Kafka topic routing following event bus architecture
- Serialization/deserialization helpers
- Comprehensive validation

Created: 2025-10-22
Purpose: Phase 4 - Bridge & Utility Events Implementation
Reference: EVENT_BUS_ARCHITECTURE.md, intelligence_adapter_events.py pattern
"""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

# ModelEventEnvelope imported locally in methods to avoid circular import issue
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Import from local event base to avoid circular imports

# Type-only import for type hints


# ============================================================================
# Enums
# ============================================================================


class EnumBridgeEventType(str, Enum):
    """Event types for bridge intelligence operations."""

    # Generate Intelligence
    GENERATE_INTELLIGENCE_REQUESTED = "GENERATE_INTELLIGENCE_REQUESTED"
    GENERATE_INTELLIGENCE_COMPLETED = "GENERATE_INTELLIGENCE_COMPLETED"
    GENERATE_INTELLIGENCE_FAILED = "GENERATE_INTELLIGENCE_FAILED"

    # Health Check
    BRIDGE_HEALTH_REQUESTED = "BRIDGE_HEALTH_REQUESTED"
    BRIDGE_HEALTH_COMPLETED = "BRIDGE_HEALTH_COMPLETED"
    BRIDGE_HEALTH_FAILED = "BRIDGE_HEALTH_FAILED"

    # Capabilities
    CAPABILITIES_REQUESTED = "CAPABILITIES_REQUESTED"
    CAPABILITIES_COMPLETED = "CAPABILITIES_COMPLETED"
    CAPABILITIES_FAILED = "CAPABILITIES_FAILED"


class EnumBridgeOperationType(str, Enum):
    """Type of bridge intelligence operation."""

    METADATA_GENERATION = "METADATA_GENERATION"
    HEALTH_CHECK = "HEALTH_CHECK"
    CAPABILITY_QUERY = "CAPABILITY_QUERY"


class EnumBridgeErrorCode(str, Enum):
    """Error codes for bridge operations."""

    INVALID_INPUT = "INVALID_INPUT"
    BRIDGE_SERVICE_UNAVAILABLE = "BRIDGE_SERVICE_UNAVAILABLE"
    METADATA_GENERATION_FAILED = "METADATA_GENERATION_FAILED"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"


# ============================================================================
# Generate Intelligence Event Payloads
# ============================================================================


class ModelBridgeGenerateIntelligenceRequestPayload(BaseModel):
    """
    Payload for GENERATE_INTELLIGENCE_REQUESTED event.

    Attributes:
        source_path: File path for metadata generation
        content: Code/document content to analyze
        language: Programming language (optional, auto-detected if not provided)
        metadata_options: Options for metadata generation
        project_id: Optional project identifier
        user_id: Optional user identifier
    """

    source_path: str = Field(
        ...,
        description="File path for metadata generation",
        examples=["src/services/api.py", "docs/README.md"],
        min_length=1,
    )

    content: str = Field(
        ...,
        description="Code/document content to analyze",
        min_length=1,
    )

    language: Optional[str] = Field(
        None,
        description="Programming language (auto-detected if not provided)",
        examples=["python", "typescript", "markdown"],
    )

    metadata_options: dict[str, Any] = Field(
        default_factory=dict,
        description="Options for metadata generation",
        examples=[{"include_blake3_hash": True, "extract_dependencies": True}],
    )

    project_id: Optional[str] = Field(
        None,
        description="Project identifier for context",
        examples=["project-123"],
    )

    user_id: Optional[str] = Field(
        None,
        description="User identifier for audit",
        examples=["user-456"],
    )

    @field_validator("source_path", "content")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Ensure fields are not empty or whitespace."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace")
        return v.strip()

    model_config = ConfigDict(frozen=False)


class ModelBridgeGenerateIntelligenceCompletedPayload(BaseModel):
    """
    Payload for GENERATE_INTELLIGENCE_COMPLETED event.

    Attributes:
        source_path: File path analyzed
        metadata: Generated OmniNode metadata
        blake3_hash: BLAKE3 content hash
        intelligence_score: Intelligence quality score (0.0-1.0)
        processing_time_ms: Processing time in milliseconds
        cache_hit: Whether result was cached
    """

    source_path: str = Field(..., description="File path analyzed")

    metadata: dict[str, Any] = Field(
        ...,
        description="Generated OmniNode metadata",
        examples=[
            {
                "file_type": "python",
                "entity_count": 15,
                "dependency_count": 8,
                "complexity_metrics": {},
            }
        ],
    )

    blake3_hash: str = Field(
        ...,
        description="BLAKE3 content hash for deduplication",
        examples=["abc123def456..."],
        min_length=64,
        max_length=64,
    )

    intelligence_score: float = Field(
        ...,
        description="Intelligence quality score (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )

    processing_time_ms: float = Field(
        ..., description="Processing time in milliseconds", ge=0.0
    )

    cache_hit: bool = Field(default=False, description="Whether result was cached")

    model_config = ConfigDict(frozen=True)


class ModelBridgeGenerateIntelligenceFailedPayload(BaseModel):
    """
    Payload for GENERATE_INTELLIGENCE_FAILED event.

    Attributes:
        source_path: File path that failed
        error_message: Human-readable error description
        error_code: Machine-readable error code
        retry_allowed: Whether retry is allowed
        processing_time_ms: Time taken before failure
        error_details: Additional error context
    """

    source_path: str = Field(..., description="File path that failed")

    error_message: str = Field(
        ..., description="Human-readable error description", min_length=1
    )

    error_code: EnumBridgeErrorCode = Field(
        ..., description="Machine-readable error code"
    )

    retry_allowed: bool = Field(..., description="Whether retry is allowed")

    processing_time_ms: float = Field(
        ..., description="Time taken before failure", ge=0.0
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict, description="Additional error context"
    )

    model_config = ConfigDict(frozen=True)


class ModelBridgeHealthRequestPayload(BaseModel):
    """
    Payload for BRIDGE_HEALTH_REQUESTED event.

    Attributes:
        include_dependencies: Include dependency health checks
        timeout_ms: Timeout for health check in milliseconds
    """

    include_dependencies: bool = Field(
        default=True, description="Include dependency health checks"
    )

    timeout_ms: int = Field(
        default=5000,
        description="Timeout for health check in milliseconds",
        ge=100,
        le=30000,
    )

    model_config = ConfigDict(frozen=False)


class ModelBridgeHealthCompletedPayload(BaseModel):
    """
    Payload for BRIDGE_HEALTH_COMPLETED event.

    Attributes:
        status: Health status (healthy, degraded, unhealthy)
        uptime_seconds: Service uptime in seconds
        version: Service version
        dependencies: Dependency health status
        processing_time_ms: Processing time in milliseconds
    """

    status: str = Field(
        ...,
        description="Health status",
        examples=["healthy", "degraded", "unhealthy"],
    )

    uptime_seconds: float = Field(..., description="Service uptime in seconds", ge=0.0)

    version: str = Field(..., description="Service version", examples=["1.0.0"])

    dependencies: dict[str, Any] = Field(
        default_factory=dict,
        description="Dependency health status",
        examples=[{"database": "healthy", "cache": "healthy"}],
    )

    processing_time_ms: float = Field(
        ..., description="Processing time in milliseconds", ge=0.0
    )

    model_config = ConfigDict(frozen=True)


class ModelBridgeHealthFailedPayload(BaseModel):
    """
    Payload for BRIDGE_HEALTH_FAILED event.

    Attributes:
        error_message: Error description
        error_code: Error code
        retry_allowed: Whether retry is allowed
        processing_time_ms: Time taken before failure
    """

    error_message: str = Field(..., description="Error description", min_length=1)

    error_code: EnumBridgeErrorCode = Field(..., description="Error code")

    retry_allowed: bool = Field(..., description="Whether retry is allowed")

    processing_time_ms: float = Field(
        ..., description="Time taken before failure", ge=0.0
    )

    model_config = ConfigDict(frozen=True)


class ModelBridgeCapabilitiesRequestPayload(BaseModel):
    """
    Payload for CAPABILITIES_REQUESTED event.

    Attributes:
        include_versions: Include version information
        include_limits: Include rate limits and quotas
    """

    include_versions: bool = Field(
        default=True, description="Include version information"
    )

    include_limits: bool = Field(
        default=True, description="Include rate limits and quotas"
    )

    model_config = ConfigDict(frozen=False)


class ModelBridgeCapabilitiesCompletedPayload(BaseModel):
    """
    Payload for CAPABILITIES_COMPLETED event.

    Attributes:
        capabilities: Service capabilities list
        supported_languages: Supported programming languages
        metadata_features: Available metadata features
        version_info: Version information
        rate_limits: Rate limits and quotas
        processing_time_ms: Processing time in milliseconds
    """

    capabilities: list[str] = Field(
        ...,
        description="Service capabilities list",
        examples=[
            [
                "metadata_generation",
                "blake3_hashing",
                "deduplication",
                "kafka_events",
            ]
        ],
    )

    supported_languages: list[str] = Field(
        ...,
        description="Supported programming languages",
        examples=[["python", "typescript", "rust", "go"]],
    )

    metadata_features: list[str] = Field(
        ...,
        description="Available metadata features",
        examples=[["entity_extraction", "dependency_analysis", "complexity_metrics"]],
    )

    version_info: dict[str, str] = Field(
        default_factory=dict,
        description="Version information",
        examples=[{"service": "1.0.0", "api": "v1"}],
    )

    rate_limits: dict[str, Any] = Field(
        default_factory=dict,
        description="Rate limits and quotas",
        examples=[{"requests_per_minute": 60, "max_content_size_mb": 10}],
    )

    processing_time_ms: float = Field(
        ..., description="Processing time in milliseconds", ge=0.0
    )

    model_config = ConfigDict(frozen=True)


class ModelBridgeCapabilitiesFailedPayload(BaseModel):
    """
    Payload for CAPABILITIES_FAILED event.

    Attributes:
        error_message: Error description
        error_code: Error code
        retry_allowed: Whether retry is allowed
        processing_time_ms: Time taken before failure
    """

    error_message: str = Field(..., description="Error description", min_length=1)

    error_code: EnumBridgeErrorCode = Field(..., description="Error code")

    retry_allowed: bool = Field(..., description="Whether retry is allowed")

    processing_time_ms: float = Field(
        ..., description="Time taken before failure", ge=0.0
    )

    model_config = ConfigDict(frozen=True)


class BridgeIntelligenceEventHelpers:
    """Helper methods for creating Bridge Intelligence events."""

    SERVICE_PREFIX = "archon-intelligence"
    DOMAIN = "bridge"
    PATTERN = "event"
    VERSION = "v1"

    @staticmethod
    def _create_envelope(
        event_type: str,
        payload: BaseModel,
        correlation_id: UUID,
        causation_id: Optional[UUID] = None,
        source_instance: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create event envelope with fallback for missing imports."""
        # Local import to avoid circular dependency
        from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

        envelope = ModelEventEnvelope(
            payload=payload if isinstance(payload, dict) else payload.model_dump(),
            correlation_id=correlation_id,
            source_tool="omninode-intelligence",
            metadata={
                "event_type": event_type,
                "service": BridgeIntelligenceEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "intelligence-bridge-1",
                "causation_id": str(causation_id) if causation_id else None,
            },
        )
        return envelope.model_dump()

    @staticmethod
    def get_kafka_topic(
        event_type: EnumBridgeEventType, environment: str = "development"
    ) -> str:
        """Generate Kafka topic name for event type."""
        env_prefix = "dev" if environment == "development" else environment
        event_suffix = event_type.value.replace("_", "-").lower()

        return f"{env_prefix}.{BridgeIntelligenceEventHelpers.SERVICE_PREFIX}.{BridgeIntelligenceEventHelpers.DOMAIN}.{event_suffix}.{BridgeIntelligenceEventHelpers.VERSION}"


# ============================================================================
# Convenience Functions
# ============================================================================


def create_generate_intelligence_request(
    source_path: str,
    content: str,
    language: Optional[str] = None,
    metadata_options: Optional[dict[str, Any]] = None,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """Create GENERATE_INTELLIGENCE_REQUESTED event."""
    payload = ModelBridgeGenerateIntelligenceRequestPayload(
        source_path=source_path,
        content=content,
        language=language,
        metadata_options=metadata_options or {},
    )

    correlation_id = correlation_id or uuid4()
    event_type = f"omninode.{BridgeIntelligenceEventHelpers.DOMAIN}.{BridgeIntelligenceEventHelpers.PATTERN}.generate_intelligence_requested.{BridgeIntelligenceEventHelpers.VERSION}"

    return BridgeIntelligenceEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )


def create_generate_intelligence_completed(
    source_path: str,
    metadata: dict[str, Any],
    blake3_hash: str,
    intelligence_score: float,
    processing_time_ms: float,
    correlation_id: UUID,
    cache_hit: bool = False,
) -> dict[str, Any]:
    """Create GENERATE_INTELLIGENCE_COMPLETED event."""
    payload = ModelBridgeGenerateIntelligenceCompletedPayload(
        source_path=source_path,
        metadata=metadata,
        blake3_hash=blake3_hash,
        intelligence_score=intelligence_score,
        processing_time_ms=processing_time_ms,
        cache_hit=cache_hit,
    )

    event_type = f"omninode.{BridgeIntelligenceEventHelpers.DOMAIN}.{BridgeIntelligenceEventHelpers.PATTERN}.generate_intelligence_completed.{BridgeIntelligenceEventHelpers.VERSION}"

    return BridgeIntelligenceEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )


def create_generate_intelligence_failed(
    source_path: str,
    error_message: str,
    error_code: EnumBridgeErrorCode,
    correlation_id: UUID,
    retry_allowed: bool = True,
    processing_time_ms: float = 0.0,
    error_details: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Create GENERATE_INTELLIGENCE_FAILED event."""
    payload = ModelBridgeGenerateIntelligenceFailedPayload(
        source_path=source_path,
        error_message=error_message,
        error_code=error_code,
        retry_allowed=retry_allowed,
        processing_time_ms=processing_time_ms,
        error_details=error_details or {},
    )

    event_type = f"omninode.{BridgeIntelligenceEventHelpers.DOMAIN}.{BridgeIntelligenceEventHelpers.PATTERN}.generate_intelligence_failed.{BridgeIntelligenceEventHelpers.VERSION}"

    return BridgeIntelligenceEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )


def create_health_request(
    include_dependencies: bool = True,
    timeout_ms: int = 5000,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """Create BRIDGE_HEALTH_REQUESTED event."""
    payload = ModelBridgeHealthRequestPayload(
        include_dependencies=include_dependencies, timeout_ms=timeout_ms
    )

    correlation_id = correlation_id or uuid4()
    event_type = f"omninode.{BridgeIntelligenceEventHelpers.DOMAIN}.{BridgeIntelligenceEventHelpers.PATTERN}.bridge_health_requested.{BridgeIntelligenceEventHelpers.VERSION}"

    return BridgeIntelligenceEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )


def create_health_completed(
    status: str,
    uptime_seconds: float,
    version: str,
    processing_time_ms: float,
    correlation_id: UUID,
    dependencies: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Create BRIDGE_HEALTH_COMPLETED event."""
    payload = ModelBridgeHealthCompletedPayload(
        status=status,
        uptime_seconds=uptime_seconds,
        version=version,
        dependencies=dependencies or {},
        processing_time_ms=processing_time_ms,
    )

    event_type = f"omninode.{BridgeIntelligenceEventHelpers.DOMAIN}.{BridgeIntelligenceEventHelpers.PATTERN}.bridge_health_completed.{BridgeIntelligenceEventHelpers.VERSION}"

    return BridgeIntelligenceEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )


def create_health_failed(
    error_message: str,
    error_code: EnumBridgeErrorCode,
    correlation_id: UUID,
    retry_allowed: bool = True,
    processing_time_ms: float = 0.0,
) -> dict[str, Any]:
    """Create BRIDGE_HEALTH_FAILED event."""
    payload = ModelBridgeHealthFailedPayload(
        error_message=error_message,
        error_code=error_code,
        retry_allowed=retry_allowed,
        processing_time_ms=processing_time_ms,
    )

    event_type = f"omninode.{BridgeIntelligenceEventHelpers.DOMAIN}.{BridgeIntelligenceEventHelpers.PATTERN}.bridge_health_failed.{BridgeIntelligenceEventHelpers.VERSION}"

    return BridgeIntelligenceEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )


def create_capabilities_request(
    include_versions: bool = True,
    include_limits: bool = True,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """Create CAPABILITIES_REQUESTED event."""
    payload = ModelBridgeCapabilitiesRequestPayload(
        include_versions=include_versions, include_limits=include_limits
    )

    correlation_id = correlation_id or uuid4()
    event_type = f"omninode.{BridgeIntelligenceEventHelpers.DOMAIN}.{BridgeIntelligenceEventHelpers.PATTERN}.capabilities_requested.{BridgeIntelligenceEventHelpers.VERSION}"

    return BridgeIntelligenceEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )


def create_capabilities_completed(
    capabilities: list[str],
    supported_languages: list[str],
    metadata_features: list[str],
    processing_time_ms: float,
    correlation_id: UUID,
    version_info: Optional[dict[str, str]] = None,
    rate_limits: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Create CAPABILITIES_COMPLETED event."""
    payload = ModelBridgeCapabilitiesCompletedPayload(
        capabilities=capabilities,
        supported_languages=supported_languages,
        metadata_features=metadata_features,
        version_info=version_info or {},
        rate_limits=rate_limits or {},
        processing_time_ms=processing_time_ms,
    )

    event_type = f"omninode.{BridgeIntelligenceEventHelpers.DOMAIN}.{BridgeIntelligenceEventHelpers.PATTERN}.capabilities_completed.{BridgeIntelligenceEventHelpers.VERSION}"

    return BridgeIntelligenceEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )


def create_capabilities_failed(
    error_message: str,
    error_code: EnumBridgeErrorCode,
    correlation_id: UUID,
    retry_allowed: bool = True,
    processing_time_ms: float = 0.0,
) -> dict[str, Any]:
    """Create CAPABILITIES_FAILED event."""
    payload = ModelBridgeCapabilitiesFailedPayload(
        error_message=error_message,
        error_code=error_code,
        retry_allowed=retry_allowed,
        processing_time_ms=processing_time_ms,
    )

    event_type = f"omninode.{BridgeIntelligenceEventHelpers.DOMAIN}.{BridgeIntelligenceEventHelpers.PATTERN}.capabilities_failed.{BridgeIntelligenceEventHelpers.VERSION}"

    return BridgeIntelligenceEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )
