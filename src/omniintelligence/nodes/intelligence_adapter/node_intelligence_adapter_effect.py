"""
Node Intelligence Adapter Effect - ONEX Effect Node with Kafka Event Integration.

This Effect node provides:
- Code analysis operations via Archon intelligence services
- Kafka event subscription for CODE_ANALYSIS_REQUESTED events
- Event publishing for CODE_ANALYSIS_COMPLETED/FAILED events
- Consumer lifecycle management
- Distributed tracing and correlation tracking
- Error handling with DLQ routing

ONEX Compliance:
- Suffix-based naming: NodeIntelligenceAdapterEffect
- Effect pattern: async execute_effect() method
- Strong typing with Pydantic models
- Correlation ID preservation
- Comprehensive error handling via OnexError

Event Flow:
1. Subscribe to dev.archon-intelligence.intelligence.code-analysis-requested.v1
2. Consume events in background loop
3. Route to analyze_code() operation
4. Publish CODE_ANALYSIS_COMPLETED or CODE_ANALYSIS_FAILED events
5. Commit offsets after successful processing

Architecture Note:
    This adapter currently handles multiple operation types (quality assessment,
    pattern detection, performance analysis). A future consideration is to split
    this into smaller, focused adapters. See ARCHITECTURE.md in this directory
    for detailed analysis and implementation roadmap.

Created: 2025-10-21
Reference: EVENT_BUS_ARCHITECTURE.md, intelligence_adapter_events.py, ARCHITECTURE.md
"""

import asyncio
import contextlib
import logging
import os
import time
from collections.abc import Awaitable, Callable
from datetime import UTC
from enum import Enum
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from omniintelligence.enums import EnumIntelligenceOperationType

from pydantic import BaseModel, Field

# ONEX base class and protocols
from omnibase_core.models.container.model_onex_container import ModelONEXContainer
from omnibase_core.nodes import NodeEffect
from omnibase_core.protocols.event_bus import (
    ProtocolEventMessage,
    ProtocolKafkaEventBusAdapter,
)

# Centralized configuration
try:
    from config import settings as parent_settings

    _DEFAULT_KAFKA_SERVERS = parent_settings.kafka_bootstrap_servers
except ImportError:
    # Allow fallback ONLY if explicitly enabled via environment variable
    if os.getenv("OMNIINTELLIGENCE_ALLOW_DEFAULT_KAFKA", "").lower() == "true":
        _DEFAULT_KAFKA_SERVERS = "omninode-bridge-redpanda:9092"
    else:
        raise RuntimeError(
            "Failed to import Kafka configuration. "
            "Set KAFKA_BOOTSTRAP_SERVERS environment variable or "
            "set OMNIINTELLIGENCE_ALLOW_DEFAULT_KAFKA=true to use defaults."
        )

# Canonical models and enums
from omniintelligence.enums import EnumIntelligenceOperationType
from omniintelligence.models import ModelIntelligenceInput, ModelIntelligenceOutput
from omniintelligence.models.model_intelligence_input import IntelligenceMetadataDict, IntelligenceOptionsDict
from omniintelligence.models.model_intelligence_output import AnalysisResultsDict, OutputMetadataDict

# Handlers for operation-specific transformations
from omniintelligence.nodes.intelligence_adapter.handlers import (
    AnyHandlerResponse,
    PatternHandlerResponse,
    PerformanceHandlerResponse,
    QualityHandlerResponse,
    ValidatedHandlerResponse,
    transform_pattern_response,
    transform_performance_response,
    transform_quality_response,
    validate_handler_result,
)

# =============================================================================
# Local Stub Implementations for Effect Node Self-Containment
# =============================================================================
# These stubs replace removed legacy dependencies (omninode_bridge clients).
# They provide type compatibility while keeping this Effect node self-contained.
#
# Design Decision: Stubs are intentional for the following reasons:
#   1. Effect nodes should manage their own I/O - no external client dependencies
#   2. Configuration is read via os.getenv() at initialization (Effect pattern)
#   3. Full client implementations would duplicate logic now in this node
#
# If external service integration is needed, implement via:
#   - New Effect nodes (e.g., NodeExternalApiEffect)
#   - Orchestrator coordination between nodes
#   - See ARCHITECTURE.md for decomposition options
# =============================================================================


class ModelIntelligenceConfig(BaseModel):
    """Configuration for intelligence service connections.

    This is a lightweight config model that reads from environment variables.
    Used by Effect nodes where os.getenv() is acceptable at initialization.
    """

    base_url: str = Field(default="http://localhost:8080")
    timeout_seconds: int = Field(default=30)
    max_retries: int = Field(default=3)
    circuit_breaker_enabled: bool = Field(default=True)
    retry_delay_ms: int = Field(default=1000)

    @classmethod
    def from_environment_variable(cls) -> "ModelIntelligenceConfig":
        return cls(
            base_url=os.getenv("INTELLIGENCE_SERVICE_URL", "http://localhost:8080"),
            timeout_seconds=int(os.getenv("INTELLIGENCE_TIMEOUT", "30")),
            max_retries=int(os.getenv("INTELLIGENCE_MAX_RETRIES", "3")),
            circuit_breaker_enabled=os.getenv(
                "INTELLIGENCE_CIRCUIT_BREAKER_ENABLED", "true"
            ).lower()
            == "true",
            retry_delay_ms=int(os.getenv("INTELLIGENCE_RETRY_DELAY_MS", "1000")),
        )


class HealthResponse(BaseModel):
    """Health check response model for service status.

    Used by IntelligenceServiceClient.check_health() to report service status.
    In stub mode, returns status="ok" with service_version="stub".
    """

    status: str = Field(default="ok")
    service_version: str = Field(default="stub")


class IntelligenceServiceClient:
    """Stub client for testing and development when real intelligence service is unavailable.

    This stub client provides safe default responses for all intelligence operations,
    allowing tests and development workflows to proceed without a running backend service.

    Stub Behavior:
        - All methods return valid ModelIntelligenceOutput with success=True
        - A warning is logged on first use of any stub method
        - Responses are marked with "[STUB]" prefix in recommendations
        - Quality scores default to 1.0 (passing), patterns_detected is empty

    Production Safety:
        - Set OMNIINTELLIGENCE_FAIL_ON_STUB=true to raise RuntimeError if stub is used
        - This prevents accidental use of stub client in production environments

    Usage:
        This stub is intended for:
        - Unit testing without external dependencies
        - Local development without running intelligence services
        - Integration tests where intelligence results are mocked

        For production, use the real IntelligenceServiceClient from omninode_bridge.

    Example:
        >>> client = IntelligenceServiceClient()
        >>> await client.connect()
        >>> result = await client.assess_code_quality(source_path="test.py", content="...")
        >>> assert result.success is True  # Stub always succeeds
        >>> assert "[STUB]" in result.recommendations[0]  # Clearly marked as stub
    """

    # Class-level flag to track if warning has been logged
    _stub_warning_logged: bool = False

    def __init__(
        self,
        config: ModelIntelligenceConfig | None = None,
        *,
        base_url: str | None = None,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        circuit_breaker_enabled: bool = True,
    ):
        """Initialize stub client with config or kwargs for compatibility.

        Args:
            config: Optional ModelIntelligenceConfig for configuration.
            base_url: Base URL for the intelligence service (stored but not used by stub).
            timeout_seconds: Request timeout in seconds (stored but not used by stub).
            max_retries: Maximum retry attempts (stored but not used by stub).
            circuit_breaker_enabled: Whether circuit breaker is enabled (stored but not used).
        """
        self._logger = logging.getLogger(__name__)
        if config is not None:
            self.config = config
        else:
            self.config = ModelIntelligenceConfig(
                base_url=base_url or "http://localhost:8080",
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
                circuit_breaker_enabled=circuit_breaker_enabled,
            )

    def _check_production_safety(self, method_name: str) -> None:
        """Check if stub usage should fail in production mode.

        Raises:
            RuntimeError: If OMNIINTELLIGENCE_FAIL_ON_STUB=true and stub method is called.
        """
        if os.getenv("OMNIINTELLIGENCE_FAIL_ON_STUB", "").lower() == "true":
            raise RuntimeError(
                f"IntelligenceServiceClient stub method '{method_name}' called in production mode. "
                "Set OMNIINTELLIGENCE_FAIL_ON_STUB=false or use real IntelligenceServiceClient."
            )

    def _log_stub_warning(self, method_name: str) -> None:
        """Log a warning that stub is being used (once per session)."""
        if not IntelligenceServiceClient._stub_warning_logged:
            self._logger.warning(
                "[STUB] IntelligenceServiceClient is a stub implementation. "
                "For production use, configure the real intelligence service client. "
                f"First stub method called: {method_name}"
            )
            IntelligenceServiceClient._stub_warning_logged = True
        else:
            self._logger.debug(f"[STUB] IntelligenceServiceClient.{method_name} called")

    def _create_stub_response(
        self,
        operation_type: "EnumIntelligenceOperationType",
        method_name: str,
        correlation_id: str | None = None,
    ) -> ModelIntelligenceOutput:
        """Create a valid stub response for the given operation type.

        Args:
            operation_type: The type of intelligence operation.
            method_name: Name of the method for logging/tracking.
            correlation_id: Optional correlation ID to preserve in response.

        Returns:
            ModelIntelligenceOutput with stub values indicating success.
        """

        return ModelIntelligenceOutput(
            success=True,
            operation_type=operation_type,
            quality_score=1.0,  # Default to passing score
            analysis_results={
                "onex_compliance_score": 1.0,
                "complexity_score": 0.0,
                "maintainability_score": 1.0,
            },
            patterns_detected=[],  # No patterns detected by stub
            recommendations=[
                f"[STUB] This response is from IntelligenceServiceClient stub ({method_name}). "
                "For actual analysis, use the real intelligence service."
            ],
            onex_compliant=True,  # Default to compliant
            correlation_id=correlation_id,
            metadata={
                "processing_time_ms": 0,
                "source_file": "stub",
            },
        )

    async def connect(self) -> None:
        """Connect to the intelligence service (stub - does nothing)."""
        self._log_stub_warning("connect")
        self._check_production_safety("connect")

    async def check_health(self) -> HealthResponse:
        """Check health (stub - returns healthy)."""
        self._log_stub_warning("check_health")
        self._check_production_safety("check_health")
        return HealthResponse(status="ok", service_version="stub")

    async def analyze_code(
        self,
        *_args: Any,
        correlation_id: str | None = None,
        **kwargs: Any,
    ) -> ModelIntelligenceOutput:
        """Analyze code (stub - returns default successful response).

        This stub method returns a valid ModelIntelligenceOutput indicating success.
        The response is clearly marked as coming from a stub implementation.

        Args:
            *args: Ignored positional arguments for compatibility.
            correlation_id: Optional correlation ID to preserve in response.
            **kwargs: Ignored keyword arguments for compatibility.

        Returns:
            ModelIntelligenceOutput with stub values.
        """
        from omniintelligence.enums import EnumIntelligenceOperationType as OpType

        self._log_stub_warning("analyze_code")
        self._check_production_safety("analyze_code")
        return self._create_stub_response(
            OpType.ASSESS_CODE_QUALITY,
            "analyze_code",
            correlation_id=correlation_id or kwargs.get("correlation_id"),
        )

    async def assess_code_quality(
        self,
        *_args: Any,
        correlation_id: str | None = None,
        **kwargs: Any,
    ) -> ModelIntelligenceOutput:
        """Assess code quality (stub - returns default successful response).

        This stub method returns a valid ModelIntelligenceOutput indicating success.
        The response is clearly marked as coming from a stub implementation.

        Args:
            *args: Ignored positional arguments for compatibility.
            correlation_id: Optional correlation ID to preserve in response.
            **kwargs: Ignored keyword arguments for compatibility.

        Returns:
            ModelIntelligenceOutput with stub values.
        """
        from omniintelligence.enums import EnumIntelligenceOperationType as OpType

        self._log_stub_warning("assess_code_quality")
        self._check_production_safety("assess_code_quality")
        return self._create_stub_response(
            OpType.ASSESS_CODE_QUALITY,
            "assess_code_quality",
            correlation_id=correlation_id or kwargs.get("correlation_id"),
        )

    async def analyze_performance(
        self,
        *_args: Any,
        correlation_id: str | None = None,
        **kwargs: Any,
    ) -> ModelIntelligenceOutput:
        """Analyze performance (stub - returns default successful response).

        This stub method returns a valid ModelIntelligenceOutput indicating success.
        The response is clearly marked as coming from a stub implementation.

        Args:
            *args: Ignored positional arguments for compatibility.
            correlation_id: Optional correlation ID to preserve in response.
            **kwargs: Ignored keyword arguments for compatibility.

        Returns:
            ModelIntelligenceOutput with stub values.
        """
        from omniintelligence.enums import EnumIntelligenceOperationType as OpType

        self._log_stub_warning("analyze_performance")
        self._check_production_safety("analyze_performance")
        return self._create_stub_response(
            OpType.ESTABLISH_PERFORMANCE_BASELINE,
            "analyze_performance",
            correlation_id=correlation_id or kwargs.get("correlation_id"),
        )

    async def detect_patterns(
        self,
        *_args: Any,
        correlation_id: str | None = None,
        **kwargs: Any,
    ) -> ModelIntelligenceOutput:
        """Detect patterns (stub - returns default successful response).

        This stub method returns a valid ModelIntelligenceOutput indicating success.
        The response is clearly marked as coming from a stub implementation.

        Args:
            *args: Ignored positional arguments for compatibility.
            correlation_id: Optional correlation ID to preserve in response.
            **kwargs: Ignored keyword arguments for compatibility.

        Returns:
            ModelIntelligenceOutput with stub values.
        """
        from omniintelligence.enums import EnumIntelligenceOperationType as OpType

        self._log_stub_warning("detect_patterns")
        self._check_production_safety("detect_patterns")
        return self._create_stub_response(
            OpType.PATTERN_MATCH,
            "detect_patterns",
            correlation_id=correlation_id or kwargs.get("correlation_id"),
        )

    async def close(self) -> None:
        """Close the client connection (stub - does nothing)."""
        self._log_stub_warning("close")
        # No production safety check for close - always allow cleanup


class EventPublisher:
    """Event publisher for testing without Kafka.

    Logs publish requests instead of sending to Kafka. Used when:
    - Running tests without Kafka infrastructure
    - Local development without event bus
    - Debugging event payloads
    """

    def __init__(self, *_args: Any, **_kwargs: Any):
        self._logger = logging.getLogger(__name__)

    async def publish(self, topic: str, payload: Any, **_kwargs: Any) -> None:
        self._logger.info(f"[STUB] Would publish to {topic}: {type(payload).__name__}")

    async def close(self) -> None:
        pass


# UUID pattern for correlation_id validation
UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"


# =============================================================================
# Request Models for Intelligence Operations
# =============================================================================
# These models define the input structure for intelligence service requests.
# They are used both by the stub client and can be used with real implementations.
# =============================================================================


class ModelQualityAssessmentRequest(BaseModel):
    """Request model for code quality assessment operations."""

    source_path: str = Field(default="", min_length=0)
    content: str = Field(default="", min_length=0)
    options: dict[str, Any] = Field(default_factory=dict)
    language: str = Field(default="python")
    include_recommendations: bool = Field(default=True)
    min_quality_threshold: float = Field(default=0.0, ge=0.0, le=1.0)


class ModelPatternDetectionRequest(BaseModel):
    """Request model for pattern detection operations."""

    source_path: str = Field(default="", min_length=0)
    content: str = Field(default="", min_length=0)
    patterns: list[str] = Field(default_factory=list)
    pattern_categories: list[str] = Field(default_factory=list)
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    include_recommendations: bool = Field(default=True)


class ModelPerformanceAnalysisRequest(BaseModel):
    """Request model for performance analysis operations."""

    source_path: str = Field(default="", min_length=0)
    content: str = Field(default="", min_length=0)
    code_content: str = Field(default="", min_length=0)
    metrics: list[str] = Field(default_factory=list)
    operation_name: str = Field(default="")
    context: dict[str, Any] = Field(default_factory=dict)
    include_opportunities: bool = Field(default=True)
    target_percentile: int = Field(default=95, ge=1, le=100)


# =============================================================================
# Enums and Event Models for Code Analysis
# =============================================================================


class EnumAnalysisErrorCode(str, Enum):
    """Analysis error codes."""

    UNKNOWN = "unknown"
    TIMEOUT = "timeout"
    INVALID_INPUT = "invalid_input"
    SERVICE_ERROR = "service_error"
    INTERNAL_ERROR = "internal_error"
    SERVICE_UNAVAILABLE = "service_unavailable"


class EnumAnalysisOperationType(str, Enum):
    """Analysis operation types."""

    QUALITY_ASSESSMENT = "quality_assessment"
    PATTERN_DETECTION = "pattern_detection"
    PERFORMANCE_ANALYSIS = "performance_analysis"
    COMPREHENSIVE_ANALYSIS = "comprehensive_analysis"
    ONEX_COMPLIANCE = "onex_compliance"
    PATTERN_EXTRACTION = "pattern_extraction"
    ARCHITECTURAL_COMPLIANCE = "architectural_compliance"


class EnumCodeAnalysisEventType(str, Enum):
    """Code analysis event types."""

    REQUESTED = "requested"
    COMPLETED = "completed"
    FAILED = "failed"
    # Aliases for compatibility with code using CODE_ANALYSIS_* prefixed names
    CODE_ANALYSIS_REQUESTED = "code_analysis_requested"
    CODE_ANALYSIS_COMPLETED = "code_analysis_completed"
    CODE_ANALYSIS_FAILED = "code_analysis_failed"


class ModelCodeAnalysisRequestPayload(BaseModel):
    """Event payload for code analysis requests."""

    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for distributed tracing (UUID format)",
        pattern=UUID_PATTERN,
    )
    source_path: str = Field(default="", min_length=0)
    content: str = Field(default="", min_length=0)
    operation_type: EnumAnalysisOperationType | None = Field(
        default=None,
        description="Type of analysis operation to perform",
    )
    language: str = Field(default="python", description="Programming language of the content")
    options: dict[str, Any] = Field(default_factory=dict, description="Operation options")
    project_id: str | None = Field(default=None, description="Project identifier")
    user_id: str | None = Field(default=None, description="User identifier")


class ModelCodeAnalysisCompletedPayload(BaseModel):
    """Event payload for completed analysis."""

    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for distributed tracing (UUID format)",
        pattern=UUID_PATTERN,
    )
    result: dict[str, Any] = Field(default_factory=dict)
    source_path: str = Field(default="", description="Path to the analyzed source")
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Quality score")
    onex_compliance: float = Field(
        default=0.0, ge=0.0, le=1.0, description="ONEX compliance score"
    )
    issues_count: int = Field(default=0, ge=0, description="Number of issues found")
    recommendations_count: int = Field(
        default=0, ge=0, description="Number of recommendations"
    )
    processing_time_ms: float = Field(default=0.0, ge=0.0, description="Processing time in ms")
    operation_type: EnumAnalysisOperationType | None = Field(
        default=None, description="Type of analysis performed"
    )
    complexity_score: float | None = Field(default=None, description="Complexity score")
    maintainability_score: float | None = Field(
        default=None, description="Maintainability score"
    )
    results_summary: dict[str, Any] = Field(
        default_factory=dict, description="Summary of results"
    )
    cache_hit: bool = Field(default=False, description="Whether result was cached")


class ModelCodeAnalysisFailedPayload(BaseModel):
    """Event payload for failed analysis."""

    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for distributed tracing (UUID format)",
        pattern=UUID_PATTERN,
    )
    error_code: str = Field(default="", min_length=0)
    error_message: str = Field(default="", min_length=0)
    operation_type: EnumAnalysisOperationType | None = Field(
        default=None, description="Type of analysis that failed"
    )
    source_path: str = Field(default="", description="Path to the source that was analyzed")
    retry_allowed: bool = Field(default=True, description="Whether retry is allowed")
    processing_time_ms: float = Field(default=0.0, ge=0.0, description="Processing time in ms")
    error_details: str | None = Field(default=None, description="Detailed error information")
    suggested_action: str | None = Field(default=None, description="Suggested action to resolve")


class IntelligenceAdapterEventHelpers:
    """Utility helpers for Kafka event creation and serialization.

    Provides static methods for:
    - Event deserialization from Kafka messages
    - Topic name resolution for event types
    - Event payload creation for completed/failed events
    """

    # Kafka topic mapping
    _TOPIC_MAP: dict[EnumCodeAnalysisEventType, str] = {
        EnumCodeAnalysisEventType.REQUESTED: "dev.archon-intelligence.intelligence.code-analysis-requested.v1",
        EnumCodeAnalysisEventType.COMPLETED: "dev.archon-intelligence.intelligence.code-analysis-completed.v1",
        EnumCodeAnalysisEventType.FAILED: "dev.archon-intelligence.intelligence.code-analysis-failed.v1",
        EnumCodeAnalysisEventType.CODE_ANALYSIS_REQUESTED: "dev.archon-intelligence.intelligence.code-analysis-requested.v1",
        EnumCodeAnalysisEventType.CODE_ANALYSIS_COMPLETED: "dev.archon-intelligence.intelligence.code-analysis-completed.v1",
        EnumCodeAnalysisEventType.CODE_ANALYSIS_FAILED: "dev.archon-intelligence.intelligence.code-analysis-failed.v1",
    }

    @staticmethod
    def deserialize_event(raw_event: bytes | str) -> dict[str, Any]:
        """Deserialize a Kafka event from bytes or string."""
        import json

        if isinstance(raw_event, bytes):
            raw_event = raw_event.decode("utf-8")
        return cast(dict[str, Any], json.loads(raw_event))

    @staticmethod
    def extract_typed_payload(
        event_dict: dict[str, Any],
    ) -> tuple[str, ModelCodeAnalysisRequestPayload]:
        """Extract event type and typed payload from event dict.

        Args:
            event_dict: The event envelope dictionary containing event_type and payload.

        Returns:
            Tuple of (event_type_str, typed_payload_model).

        Raises:
            KeyError: If required fields are missing from event_dict.
            ValueError: If payload validation fails.
        """
        event_type = event_dict.get("event_type", "")
        payload_dict = event_dict.get("payload", {})

        # Deserialize payload into the appropriate model based on event type
        # Currently only CODE_ANALYSIS_REQUESTED is supported
        if event_type == EnumCodeAnalysisEventType.CODE_ANALYSIS_REQUESTED.value:
            payload = ModelCodeAnalysisRequestPayload.model_validate(payload_dict)
        else:
            # Default to request payload for unknown event types
            payload = ModelCodeAnalysisRequestPayload.model_validate(payload_dict)

        return event_type, payload

    @staticmethod
    def get_kafka_topic(event_type: EnumCodeAnalysisEventType) -> str:
        """Get the Kafka topic for an event type."""
        return IntelligenceAdapterEventHelpers._TOPIC_MAP.get(
            event_type, f"unknown-topic-{event_type.value}"
        )

    @staticmethod
    def create_completed_event(correlation_id: str, result: Any) -> dict[str, Any]:
        return {"correlation_id": correlation_id, "result": result}

    @staticmethod
    def create_analysis_completed_event(
        payload: ModelCodeAnalysisCompletedPayload,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Create a completion event envelope."""
        from datetime import datetime

        return {
            "event_type": EnumCodeAnalysisEventType.CODE_ANALYSIS_COMPLETED.value,
            "correlation_id": str(correlation_id),
            "causation_id": str(causation_id) if causation_id else None,
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": payload.model_dump(),
        }

    @staticmethod
    def create_failed_event(
        correlation_id: str, error_code: str, error_message: str
    ) -> dict[str, Any]:
        return {
            "correlation_id": correlation_id,
            "error_code": error_code,
            "error_message": error_message,
        }

    @staticmethod
    def create_analysis_failed_event(
        payload: ModelCodeAnalysisFailedPayload,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Create a failure event envelope."""
        from datetime import datetime

        return {
            "event_type": EnumCodeAnalysisEventType.CODE_ANALYSIS_FAILED.value,
            "correlation_id": str(correlation_id),
            "causation_id": str(causation_id) if causation_id else None,
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": payload.model_dump(),
        }


logger = logging.getLogger(__name__)


class ModelKafkaConsumerConfig(BaseModel):
    """
    Configuration for Kafka consumer.

    Attributes:
        bootstrap_servers: Kafka bootstrap servers (comma-separated)
        group_id: Consumer group ID
        topics: List of topics to subscribe to
        auto_offset_reset: Offset reset strategy (earliest, latest)
        enable_auto_commit: Enable auto-commit of offsets
        max_poll_records: Maximum records per poll
        session_timeout_ms: Session timeout in milliseconds
        max_poll_interval_ms: Max time between polls
    """

    bootstrap_servers: str = Field(
        default=_DEFAULT_KAFKA_SERVERS,
        description="Kafka bootstrap servers from centralized config",
    )

    group_id: str = Field(
        default="intelligence_adapter_consumers",
        description="Consumer group ID for load balancing",
    )

    topics: list[str] = Field(
        default_factory=lambda: [
            "dev.archon-intelligence.intelligence.code-analysis-requested.v1"
        ],
        description="Topics to subscribe to",
    )

    auto_offset_reset: str = Field(
        default="latest",
        description="Offset reset strategy (earliest, latest)",
    )

    enable_auto_commit: bool = Field(
        default=False,
        description="Enable auto-commit (False for manual control)",
    )

    max_poll_records: int = Field(
        default=10,
        description="Maximum records to fetch per poll",
    )

    session_timeout_ms: int = Field(
        default=30000,
        description="Session timeout in milliseconds",
    )

    max_poll_interval_ms: int = Field(
        default=300000,
        description="Max time between polls (5 minutes)",
    )


def _extract_error_info(error: Exception | None) -> dict[str, str]:
    """
    Extract standardized error information from an exception.

    This helper function provides consistent error type extraction for DLQ routing
    and error logging throughout the intelligence adapter. It ensures all error
    payloads have a uniform structure.

    Args:
        error: The exception to extract information from, or None.

    Returns:
        Dictionary containing:
        - error_type: The class name of the exception (e.g., "ValueError")
        - error_message: The string representation of the error
        - error_module: The module where the exception class is defined
          (e.g., "builtins" for ValueError, "omnibase_core.errors" for OnexError)

    Example:
        >>> info = _extract_error_info(ValueError("invalid input"))
        >>> info["error_type"]
        'ValueError'
        >>> info["error_message"]
        'invalid input'
        >>> info["error_module"]
        'builtins'

        >>> info = _extract_error_info(None)
        >>> info["error_type"]
        'NoneType'
    """
    if error is None:
        return {
            "error_type": "NoneType",
            "error_message": "Unknown error (None)",
            "error_module": "builtins",
        }

    return {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "error_module": type(error).__module__,
    }


class NodeIntelligenceAdapterEffect(NodeEffect):
    """
    Intelligence Adapter Effect Node with Protocol-Based Event Integration.

    This ONEX Effect node integrates Archon's intelligence services with
    event-driven architecture via the ProtocolKafkaEventBusAdapter protocol.
    It subscribes to code analysis request events, processes them via
    intelligence services, and publishes completion/failure events.

    **Core Capabilities**:
    - Code quality assessment with ONEX compliance scoring
    - Document quality analysis
    - Pattern extraction and matching
    - Architectural compliance validation
    - Protocol-based event subscription and publishing
    - Distributed tracing with correlation IDs

    **Event Subscription**:
    - Topic: dev.archon-intelligence.intelligence.code-analysis-requested.v1
    - Consumer Group: intelligence_adapter_consumers
    - Offset Strategy: Latest (configurable)
    - Manual offset commit after successful processing

    **Event Publishing**:
    - CODE_ANALYSIS_COMPLETED: On successful analysis
    - CODE_ANALYSIS_FAILED: On analysis failure or error
    - DLQ routing: Unrecoverable errors sent to .dlq topic

    **Lifecycle Management**:
    - initialize(): Start event subscription and background loop
    - shutdown(): Stop subscription, cleanup
    - Graceful error handling with exponential backoff

    **Usage**:
        >>> from uuid import uuid4
        >>> from omniintelligence.models import ModelIntelligenceInput
        >>> from omnibase_core.models.container import ModelONEXContainer
        >>>
        >>> # Create container and event bus adapter
        >>> container = ModelONEXContainer(...)
        >>> event_bus = MyKafkaEventBusAdapter(...)  # implements ProtocolKafkaEventBusAdapter
        >>>
        >>> # Direct operation (non-event)
        >>> node = NodeIntelligenceAdapterEffect(
        ...     container=container,
        ...     event_bus=event_bus,
        ...     service_url="http://localhost:8053"
        ... )
        >>> await node.initialize()
        >>>
        >>> input_data = ModelIntelligenceInput(
        ...     operation_type="assess_code_quality",
        ...     correlation_id=uuid4(),
        ...     content="def hello(): pass",
        ...     source_path="test.py",
        ...     language="python"
        ... )
        >>>
        >>> output = await node.analyze_code(input_data)
        >>> assert output.success
        >>> assert 0.0 <= output.quality_score <= 1.0
        >>>
        >>> # Event-driven operation (automatic)
        >>> # Events are consumed in background loop
        >>> # Results published to Kafka automatically
        >>>
        >>> await node.shutdown()

    **Error Handling**:
    - Event bus errors: Log and retry with backoff
    - Analysis errors: Publish CODE_ANALYSIS_FAILED event
    - Unrecoverable errors: Route to DLQ topic
    - Circuit breaker: Prevent cascading failures

    Attributes:
        service_url: Intelligence service base URL
        event_bus: Protocol-based event bus adapter
        consumer_config: Consumer configuration
        is_running: Consumer running status
        metrics: Operation metrics (events processed, errors, etc.)
    """

    def __init__(
        self,
        container: ModelONEXContainer,
        event_bus: ProtocolKafkaEventBusAdapter | None = None,
        service_url: str = "http://archon-intelligence:8053",
        bootstrap_servers: str = _DEFAULT_KAFKA_SERVERS,
        consumer_config: ModelKafkaConsumerConfig | None = None,
    ):
        """
        Initialize Intelligence Adapter Effect Node.

        Args:
            container: ONEX container for dependency injection
            event_bus: Protocol-based event bus adapter for Kafka operations
            service_url: Intelligence service base URL
            bootstrap_servers: Kafka bootstrap servers (for configuration)
            consumer_config: Optional consumer configuration
        """
        super().__init__(container)
        self._event_bus = event_bus
        self.service_url = service_url
        self.bootstrap_servers = bootstrap_servers
        self.consumer_config = consumer_config or ModelKafkaConsumerConfig(
            bootstrap_servers=bootstrap_servers
        )

        # ONEX-compliant attributes
        self._config: ModelIntelligenceConfig | None = None
        self._client: IntelligenceServiceClient | None = None

        # Event bus infrastructure
        self.event_publisher: EventPublisher | None = None
        self._unsubscribe: Callable[[], Awaitable[None]] | None = None
        self._event_consumption_task: asyncio.Task[None] | None = None

        # Lifecycle state
        self.is_running = False
        self._shutdown_event = asyncio.Event()

        # Statistics tracking (ONEX-compliant _stats attribute)
        self._stats: dict[str, Any] = {
            "total_analyses": 0,
            "successful_analyses": 0,
            "failed_analyses": 0,
            "total_quality_score": 0.0,
            "avg_quality_score": 0.0,
            "success_rate": 0.0,
            "last_analysis_time": None,
        }

        # Event metrics
        self.metrics = {
            "events_consumed": 0,
            "events_processed": 0,
            "events_failed": 0,
            "analysis_completed": 0,
            "analysis_failed": 0,
            "dlq_routed": 0,
            "total_processing_time_ms": 0.0,
            "avg_processing_time_ms": 0.0,
        }

        logger.info(
            f"NodeIntelligenceAdapterEffect initialized | "
            f"node_id={self.node_id} | "
            f"service_url={service_url} | "
            f"kafka={bootstrap_servers}"
        )

    async def initialize(self) -> None:
        """
        Initialize Intelligence Adapter Effect Node.

        This method:
        1. Loads configuration from environment
        2. Creates intelligence service client
        3. Connects to intelligence service
        4. Performs health check
        5. Initializes Kafka consumer (if available)
        6. Initializes event publisher
        7. Starts background event consumption loop

        Raises:
            ModelOnexError: If initialization fails
        """
        from omnibase_core.enums.enum_core_error_code import EnumCoreErrorCode
        from omnibase_core.models.errors.model_onex_error import ModelOnexError

        try:
            # Step 1: Load configuration from environment
            self._config = ModelIntelligenceConfig.from_environment_variable()
            logger.info(
                f"Configuration loaded | base_url={self._config.base_url} | "
                f"timeout={self._config.timeout_seconds}s"
            )

            # Step 2: Create intelligence service client
            self._client = IntelligenceServiceClient(
                base_url=self._config.base_url,
                timeout_seconds=self._config.timeout_seconds,
                max_retries=self._config.max_retries,
                circuit_breaker_enabled=self._config.circuit_breaker_enabled,
            )

            # Step 3: Connect to intelligence service
            await self._client.connect()
            logger.info("Intelligence service client connected")

            # Step 4: Perform health check (warning only if fails)
            try:
                health_response = await self._client.check_health()
                logger.info(
                    f"Intelligence service health check passed | "
                    f"status={health_response.status} | "
                    f"version={health_response.service_version}"
                )
            except (ConnectionError, TimeoutError, OSError) as health_error:
                # Network-related errors during health check are non-fatal
                logger.warning(
                    f"Health check failed (continuing anyway): {health_error}"
                )
            except Exception as health_error:
                # Intentionally broad: health check should never prevent initialization
                # This catches unexpected errors like response parsing failures
                logger.warning(
                    f"Health check failed with unexpected error (continuing anyway): {health_error}"
                )

            # Step 5-7: Initialize event bus infrastructure (if event bus provided)
            if self._event_bus is not None:
                try:
                    await self._initialize_event_bus_infrastructure()
                except (ConnectionError, TimeoutError) as bus_error:
                    # Network errors during initialization are non-fatal
                    logger.warning(
                        f"Event bus initialization failed (continuing without event bus): {bus_error}"
                    )
                except RuntimeError as bus_error:
                    # RuntimeError from our own _initialize_event_bus_infrastructure
                    logger.warning(
                        f"Event bus initialization failed (continuing without event bus): {bus_error}"
                    )
            else:
                logger.warning(
                    "Event bus not provided, skipping event subscription. "
                    "Direct API calls only."
                )

            logger.info(
                f"NodeIntelligenceAdapterEffect initialized | "
                f"node_id={self.node_id} | "
                f"config_loaded=True | "
                f"client_connected=True | "
                f"event_bus_available={self._event_bus is not None}"
            )

        except (ConnectionError, TimeoutError, OSError) as e:
            # Network-related initialization failures
            logger.error(
                f"Failed to initialize Intelligence Adapter (network error): {e}", exc_info=True
            )
            raise ModelOnexError(
                error_code=EnumCoreErrorCode.INITIALIZATION_FAILED,
                message=f"Failed to initialize Intelligence Adapter (network error): {e!s}",
            ) from e
        except asyncio.CancelledError:
            # Task cancellation during initialization - must re-raise to preserve cancellation semantics
            logger.info("Intelligence Adapter initialization cancelled")
            raise
        except ValueError as e:
            # Configuration or validation errors
            logger.error(
                f"Failed to initialize Intelligence Adapter (config error): {e}", exc_info=True
            )
            raise ModelOnexError(
                error_code=EnumCoreErrorCode.INITIALIZATION_FAILED,
                message=f"Failed to initialize Intelligence Adapter (config error): {e!s}",
            ) from e
        except Exception as e:
            # Intentionally broad: top-level catch-all to convert any unexpected error
            # to ModelOnexError for consistent error handling across the ONEX system
            logger.error(
                f"Failed to initialize Intelligence Adapter (unexpected): {e}", exc_info=True
            )
            raise ModelOnexError(
                error_code=EnumCoreErrorCode.INITIALIZATION_FAILED,
                message=f"Failed to initialize Intelligence Adapter: {e!s}",
            ) from e

    async def _initialize_event_bus_infrastructure(self) -> None:
        """
        Initialize event bus subscription using protocol.

        This is a separate method to allow initialization to succeed even
        if event bus is not available (for direct API usage).

        Raises:
            RuntimeError: If event bus initialization fails
        """
        if self.is_running:
            logger.warning("Consumer already running, skipping event bus initialization")
            return

        if self._event_bus is None:
            logger.warning("Event bus not configured, skipping subscription")
            return

        try:
            # Subscribe to topics using protocol
            # Subscribe to the first topic (protocol handles single topic subscription)
            topic = self.consumer_config.topics[0] if self.consumer_config.topics else ""
            if not topic:
                logger.warning("No topics configured, skipping subscription")
                return

            self._unsubscribe = await self._event_bus.subscribe(
                topic=topic,
                group_id=self.consumer_config.group_id,
                on_message=self._handle_event_message,
            )

            logger.info(
                f"Event bus subscribed | "
                f"topic={topic} | "
                f"group_id={self.consumer_config.group_id}"
            )

            # Initialize stub event publisher (for logging/testing)
            self.event_publisher = EventPublisher(
                bootstrap_servers=self.bootstrap_servers,
                service_name="archon-intelligence",
                instance_id=f"intelligence-adapter-{uuid4().hex[:8]}",
                max_retries=3,
                enable_dlq=True,
            )

            logger.info("Event publisher initialized")

            self.is_running = True

            logger.info("Event bus infrastructure initialized and subscription started")

        except (ConnectionError, TimeoutError) as e:
            # Network-related errors during event bus initialization
            logger.error(
                f"Failed to initialize event bus infrastructure (network error): {e}", exc_info=True
            )
            raise RuntimeError(f"Event bus infrastructure initialization failed: {e}") from e
        except Exception as e:
            # Intentionally broad: catch unexpected errors during setup
            # and convert to RuntimeError for consistent handling
            logger.error(
                f"Failed to initialize event bus infrastructure (unexpected): {e}", exc_info=True
            )
            raise RuntimeError(f"Event bus infrastructure initialization failed: {e}") from e

    async def _handle_event_message(self, message: ProtocolEventMessage) -> None:
        """
        Handle incoming event message from protocol subscription.

        This method is called by the event bus when a message is received.
        It processes the message and acknowledges it upon success.

        Args:
            message: Protocol event message from subscription
        """
        self.metrics["events_consumed"] += 1

        try:
            await self._process_event_message(message)
            self.metrics["events_processed"] += 1

            # Acknowledge successful processing
            await message.ack()

        except ValueError as e:
            # Deserialization or validation errors
            self.metrics["events_failed"] += 1
            logger.error(
                f"Failed to process event (validation error) | error={e} | "
                f"topic={message.topic}",
                exc_info=True,
            )
            await self._route_protocol_message_to_dlq(message, e)
            await message.nack()

        except Exception as e:
            # Intentionally broad: any processing error should route to DLQ
            self.metrics["events_failed"] += 1
            logger.error(
                f"Failed to process event | error={e} | "
                f"topic={message.topic}",
                exc_info=True,
            )
            await self._route_protocol_message_to_dlq(message, e)
            await message.nack()

    async def _process_event_message(self, message: ProtocolEventMessage) -> None:
        """
        Process an event message from the protocol subscription.

        Args:
            message: Protocol event message

        Raises:
            ValueError: If message deserialization fails
        """
        import json

        start_time = time.perf_counter()

        # Step 1: Deserialize message
        try:
            message_value = message.value.decode("utf-8")
            event_dict = json.loads(message_value)
        except UnicodeDecodeError as e:
            logger.error(f"Failed to decode message bytes: {e}")
            raise ValueError(f"Message decoding failed (invalid UTF-8): {e}") from e
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message JSON: {e}")
            raise ValueError(f"Message parsing failed (invalid JSON): {e}") from e

        # Step 2: Extract event metadata
        event_type = event_dict.get("event_type", "")
        correlation_id_str = event_dict.get("correlation_id")
        event_id_str = event_dict.get("event_id")

        if not correlation_id_str:
            raise ValueError("Missing correlation_id in event envelope")

        correlation_id = UUID(correlation_id_str)
        causation_id = UUID(event_id_str) if event_id_str else None

        logger.info(
            f"Processing event | event_type={event_type} | "
            f"correlation_id={correlation_id} | "
            f"topic={message.topic}"
        )

        # Step 3: Deserialize payload using event helper
        try:
            event_type_enum, payload = (
                IntelligenceAdapterEventHelpers.extract_typed_payload(event_dict)
            )
        except KeyError as e:
            logger.error(f"Missing field in event payload: {e}")
            raise ValueError(f"Payload deserialization failed (missing field): {e}") from e
        except (TypeError, ValueError) as e:
            logger.error(f"Invalid event payload: {e}")
            raise ValueError(f"Payload deserialization failed (validation error): {e}") from e

        # Step 4: Route based on event type
        if event_type_enum == EnumCodeAnalysisEventType.CODE_ANALYSIS_REQUESTED.value:
            await self._handle_code_analysis_requested(
                payload=payload,
                correlation_id=correlation_id,
                causation_id=causation_id,
                start_time=start_time,
            )
        else:
            logger.warning(f"Unknown event type: {event_type_enum}, skipping")

    async def _route_protocol_message_to_dlq(
        self, message: ProtocolEventMessage, error: Exception | None
    ) -> None:
        """
        Route failed protocol message to Dead Letter Queue.

        Args:
            message: Original protocol message that failed processing
            error: Exception explaining why processing failed
        """
        import json
        import traceback
        from datetime import datetime

        original_topic = message.topic
        dlq_topic = f"{original_topic}.dlq"

        error_info = _extract_error_info(error)

        if self._event_bus is None:
            logger.warning(
                f"Event bus not configured, cannot route to DLQ | "
                f"topic={original_topic} | error={error}"
            )
            self.metrics["dlq_routed"] += 1
            return

        try:
            # Decode original message content
            try:
                original_content = message.value.decode("utf-8")
                try:
                    original_payload = json.loads(original_content)
                except json.JSONDecodeError:
                    original_payload = {"raw_content": original_content}
            except UnicodeDecodeError as decode_error:
                original_payload = {
                    "raw_bytes": message.value.hex() if message.value else None,
                    "decode_error": str(decode_error),
                }

            # Build DLQ payload
            dlq_payload = {
                "original_message": original_payload,
                "error": {
                    "error_type": error_info["error_type"],
                    "error_message": error_info["error_message"],
                    "error_module": error_info["error_module"],
                    "traceback": traceback.format_exc(),
                },
                "original_metadata": {
                    "topic": original_topic,
                    "key": message.key.decode("utf-8") if message.key else None,
                    "headers": message.headers,
                },
                "processing_context": {
                    "node_id": str(self.node_id),
                    "consumer_group": self.consumer_config.group_id,
                    "routed_at": datetime.now(UTC).isoformat(),
                    "service_url": self.service_url,
                },
            }

            # Extract correlation_id from original message if available
            correlation_id = uuid4()
            if isinstance(original_payload, dict):
                correlation_id_str = original_payload.get("correlation_id")
                if correlation_id_str:
                    with contextlib.suppress(ValueError, TypeError):
                        correlation_id = UUID(correlation_id_str)

            # Publish to DLQ using protocol
            await self._publish_event_via_protocol(
                topic=dlq_topic,
                key=message.key,
                value=json.dumps(dlq_payload).encode("utf-8"),
                headers={"event_type": "CODE_ANALYSIS_DLQ"},
            )

            self.metrics["dlq_routed"] += 1

            logger.warning(
                f"Routed message to DLQ | "
                f"dlq_topic={dlq_topic} | "
                f"original_topic={original_topic} | "
                f"correlation_id={correlation_id} | "
                f"error={error}"
            )

        except Exception as e:
            self.metrics["dlq_routed"] += 1
            logger.error(
                f"Failed to route message to DLQ | "
                f"dlq_topic={dlq_topic} | "
                f"original_topic={original_topic} | "
                f"routing_error={e}",
                exc_info=True,
            )

    async def _publish_event_via_protocol(
        self,
        topic: str,
        key: bytes | None,
        value: bytes,
        headers: dict[str, str],
    ) -> None:
        """
        Publish event using protocol-based event bus.

        Args:
            topic: Target topic
            key: Message key
            value: Message value
            headers: Message headers
        """
        if self._event_bus is None:
            logger.warning(f"Event bus not configured, cannot publish to {topic}")
            return

        # Create a simple headers object that satisfies the protocol
        # The actual implementation will depend on the concrete event bus adapter
        await self._event_bus.publish(
            topic=topic,
            key=key,
            value=value,
            headers=cast(Any, headers),  # Cast to satisfy protocol
        )

    async def shutdown(self) -> None:
        """
        Shutdown event subscription and publisher.

        This method:
        1. Signals shutdown to background loop
        2. Waits for in-flight events to complete
        3. Unsubscribes from event bus
        4. Closes event bus connection
        5. Closes event publisher
        6. Cleans up node resources

        Does not raise exceptions - logs warnings on failure.
        """
        if not self.is_running:
            logger.info("Consumer not running, nothing to shutdown")
            return

        logger.info("Shutting down Intelligence Adapter Effect Node...")

        # Step 1: Signal shutdown
        self._shutdown_event.set()

        # Step 2: Wait for consumption loop to finish
        if self._event_consumption_task:
            try:
                await asyncio.wait_for(self._event_consumption_task, timeout=30.0)
            except TimeoutError:
                logger.warning("Event consumption task did not finish in 30s")
                self._event_consumption_task.cancel()
                # Await the cancelled task to suppress CancelledError
                with contextlib.suppress(asyncio.CancelledError):
                    await self._event_consumption_task

        # Step 3: Unsubscribe and close event bus
        if self._unsubscribe:
            try:
                await self._unsubscribe()
                logger.info("Event bus unsubscribed")
            except Exception as e:
                # Intentionally broad: cleanup must never raise, any error is logged only
                logger.warning(f"Error unsubscribing from event bus: {e}")

        if self._event_bus:
            try:
                await self._event_bus.close()
                logger.info("Event bus connection closed")
            except Exception as e:
                # Intentionally broad: cleanup must never raise, any error is logged only
                logger.warning(f"Error closing event bus: {e}")

        # Step 4: Close event publisher
        if self.event_publisher:
            try:
                await self.event_publisher.close()
                logger.info("Event publisher closed")
            except (ConnectionError, TimeoutError, OSError) as e:
                # Network errors during publisher close are expected and non-fatal
                logger.warning(f"Network error closing event publisher: {e}")
            except AttributeError as e:
                # close() method may not exist on the publisher instance
                logger.warning(f"Event publisher has no close method: {e}")
            except Exception as e:
                # Intentionally broad: cleanup must never raise, any error is logged only.
                # Include error type for debugging unexpected issues.
                logger.warning(f"Error closing event publisher ({type(e).__name__}): {e}")

        # Step 5: Clean up node resources
        await self._cleanup_node_resources()

        self.is_running = False

        logger.info(
            f"NodeIntelligenceAdapterEffect shutdown complete | "
            f"final_metrics={self.metrics}"
        )

    async def _cleanup_node_resources(self) -> None:
        """
        Clean up node resources (ONEX-compliant).

        This method:
        1. Closes the intelligence service client
        2. Clears client reference

        Does not raise exceptions - logs warnings on failure.
        """
        if self._client:
            try:
                await self._client.close()
                logger.info("Intelligence service client closed")
            except (ConnectionError, TimeoutError, OSError) as e:
                # Network errors during client close are expected and non-fatal
                logger.warning(f"Network error closing intelligence service client: {e}")
            except AttributeError as e:
                # close() method may not exist on the client instance (e.g., mock client)
                logger.warning(f"Intelligence client has no close method: {e}")
            except Exception as e:
                # Intentionally broad: cleanup must never raise, any error is logged only.
                # Include error type for debugging unexpected issues.
                logger.warning(f"Error closing intelligence service client ({type(e).__name__}): {e}")
            finally:
                self._client = None

    # NOTE: The old _consume_events_loop and _route_event_to_operation methods have been
    # replaced by protocol-based event handling via _handle_event_message and
    # _process_event_message. The protocol's subscribe() method handles the consumption
    # loop internally and calls _handle_event_message for each message.

    async def _handle_code_analysis_requested(
        self,
        payload: ModelCodeAnalysisRequestPayload,
        correlation_id: UUID,
        causation_id: UUID | None,
        start_time: float,
    ) -> None:
        """
        Handle CODE_ANALYSIS_REQUESTED event.

        This method:
        1. Converts event payload to ModelIntelligenceInput
        2. Calls analyze_code() to perform analysis
        3. Publishes CODE_ANALYSIS_COMPLETED on success
        4. Publishes CODE_ANALYSIS_FAILED on error

        Args:
            payload: Request payload from event
            correlation_id: Correlation ID for tracking
            causation_id: Event ID that caused this event
            start_time: Request start time for metrics
        """
        # Initialize input_data before try block to ensure it exists in exception handlers
        input_data: ModelIntelligenceInput | None = None

        try:
            # Step 1: Convert event payload to intelligence input
            # Build metadata dict with only valid IntelligenceMetadataDict keys
            metadata_dict = IntelligenceMetadataDict()
            if payload.user_id is not None:
                metadata_dict["user_id"] = payload.user_id

            input_data = ModelIntelligenceInput(
                operation_type=self._map_operation_type(payload.operation_type),
                correlation_id=str(correlation_id),
                source_path=payload.source_path,
                content=payload.content,
                language=payload.language,
                options=cast(IntelligenceOptionsDict, payload.options),
                metadata=metadata_dict,
            )

            # Step 2: Perform analysis
            output = await self.analyze_code(input_data)

            # Step 3: Calculate processing time
            processing_time_ms = (time.perf_counter() - start_time) * 1000

            # Step 4: Publish completion or failure event
            if output.success:
                await self._publish_analysis_completed_event(
                    output=output,
                    correlation_id=correlation_id,
                    causation_id=causation_id,
                    processing_time_ms=processing_time_ms,
                )
                self.metrics["analysis_completed"] += 1
            else:
                # error_code is in analysis_results (removed from direct fields)
                error_code = output.analysis_results.get("error_code", "INTERNAL_ERROR")
                await self._publish_analysis_failed_event(
                    input_data=input_data,
                    error_message=output.error_message or "Unknown error",
                    error_code=str(error_code),
                    correlation_id=correlation_id,
                    causation_id=causation_id,
                    processing_time_ms=processing_time_ms,
                )
                self.metrics["analysis_failed"] += 1

            # Update metrics
            self.metrics["total_processing_time_ms"] += processing_time_ms
            processed_count = (
                self.metrics["analysis_completed"] + self.metrics["analysis_failed"]
            )
            if processed_count > 0:
                self.metrics["avg_processing_time_ms"] = (
                    self.metrics["total_processing_time_ms"] / processed_count
                )

        except (ConnectionError, TimeoutError) as e:
            # Network-related errors during analysis
            logger.error(
                f"Network error handling CODE_ANALYSIS_REQUESTED | "
                f"correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_analysis_failed_event(
                input_data=input_data,
                error_message=str(e),
                error_code="SERVICE_UNAVAILABLE",
                correlation_id=correlation_id,
                causation_id=causation_id,
                processing_time_ms=processing_time_ms,
            )
            self.metrics["analysis_failed"] += 1
            raise

        except Exception as e:
            # Intentionally broad: any error during analysis must publish a failure event
            # to maintain event-driven consistency (every request gets a response)
            logger.error(
                f"Error handling CODE_ANALYSIS_REQUESTED | "
                f"correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )

            # Publish failure event
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_analysis_failed_event(
                input_data=input_data,
                error_message=str(e),
                error_code="INTERNAL_ERROR",
                correlation_id=correlation_id,
                causation_id=causation_id,
                processing_time_ms=processing_time_ms,
            )
            self.metrics["analysis_failed"] += 1

            raise

    async def _publish_analysis_completed_event(
        self,
        output: ModelIntelligenceOutput,
        correlation_id: UUID,
        causation_id: UUID | None,
        processing_time_ms: float,
    ) -> None:
        """
        Publish CODE_ANALYSIS_COMPLETED event.

        Args:
            output: Analysis output with results
            correlation_id: Correlation ID from request
            causation_id: Event ID that caused this event
            processing_time_ms: Processing time in milliseconds
        """
        try:
            # Create completion payload
            # Note: Field mappings from canonical ModelIntelligenceOutput:
            # - source_path: Use metadata["source_file"] (renamed from source_path)
            # - onex_compliance: Calculate from onex_compliant bool (0.92 if True, 0.0 if False/None)
            # - issues: Merged into recommendations (use 0 for issues_count)
            # - complexity_score: Use analysis_results["complexity_score"]
            # - maintainability_score: Use analysis_results["maintainability_score"]
            # - result_data: Renamed to analysis_results
            # - metrics: Removed (observability layer)
            onex_compliance_score = (
                output.analysis_results.get("onex_compliance_score", 0.92 if output.onex_compliant else 0.0)
                if output.onex_compliant is not None
                else 0.0
            )
            complexity_score = output.analysis_results.get("complexity_score")
            maintainability_score = output.analysis_results.get("maintainability_score")

            payload = ModelCodeAnalysisCompletedPayload(
                source_path=str(output.metadata.get("source_file", "unknown")),
                quality_score=output.quality_score or 0.0,
                onex_compliance=float(onex_compliance_score) if onex_compliance_score else 0.0,
                issues_count=0,  # Issues merged into recommendations in canonical model
                recommendations_count=len(output.recommendations),
                processing_time_ms=processing_time_ms,
                operation_type=self._map_to_event_operation_type(output.operation_type),
                complexity_score=float(complexity_score) if complexity_score is not None else None,
                maintainability_score=float(maintainability_score) if maintainability_score is not None else None,
                results_summary=dict(output.analysis_results) if output.analysis_results else {},
                cache_hit=False,  # metrics removed from canonical model
            )

            # Create event envelope
            event = IntelligenceAdapterEventHelpers.create_analysis_completed_event(
                payload=payload,
                correlation_id=correlation_id,
                causation_id=causation_id,
            )

            # Publish to Kafka
            topic = IntelligenceAdapterEventHelpers.get_kafka_topic(
                EnumCodeAnalysisEventType.CODE_ANALYSIS_COMPLETED
            )

            if self.event_publisher is None:
                logger.warning(
                    f"Event publisher not initialized, skipping publish | "
                    f"correlation_id={correlation_id}"
                )
                return

            await self.event_publisher.publish(
                event_type=event["event_type"],
                payload=event["payload"],
                correlation_id=correlation_id,
                causation_id=causation_id,
                topic=topic,
            )

            logger.info(
                f"Published CODE_ANALYSIS_COMPLETED | "
                f"correlation_id={correlation_id} | "
                f"quality_score={payload.quality_score:.2f} | "
                f"processing_time={processing_time_ms:.2f}ms"
            )

        except (ConnectionError, TimeoutError) as e:
            # Network errors during event publishing
            logger.error(
                f"Failed to publish CODE_ANALYSIS_COMPLETED (publish error) | "
                f"correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )
        except Exception as e:
            # Intentionally broad: event publishing failures should not propagate
            # up the call stack; analysis was successful, just notification failed
            logger.error(
                f"Failed to publish CODE_ANALYSIS_COMPLETED | "
                f"correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )

    async def _publish_analysis_failed_event(
        self,
        input_data: ModelIntelligenceInput | None,
        error_message: str,
        error_code: str,
        correlation_id: UUID,
        causation_id: UUID | None,
        processing_time_ms: float,
    ) -> None:
        """
        Publish CODE_ANALYSIS_FAILED event.

        Args:
            input_data: Original input data (if available)
            error_message: Human-readable error description
            error_code: Machine-readable error code
            correlation_id: Correlation ID from request
            causation_id: Event ID that caused this event
            processing_time_ms: Processing time before failure
        """
        try:
            # Map error code to enum
            try:
                error_code_enum = EnumAnalysisErrorCode(error_code)
            except ValueError:
                error_code_enum = EnumAnalysisErrorCode.INTERNAL_ERROR

            # Safely extract source_path (handles both None input_data and None source_path)
            source_path: str = "unknown"
            if input_data is not None and input_data.source_path is not None:
                source_path = input_data.source_path

            # Create failure payload
            payload = ModelCodeAnalysisFailedPayload(
                operation_type=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
                source_path=source_path,
                error_message=error_message,
                error_code=error_code_enum,
                retry_allowed=True,
                processing_time_ms=processing_time_ms,
                error_details=str(error_message),
                suggested_action="Review error details and retry with valid input",
            )

            # Create event envelope
            event = IntelligenceAdapterEventHelpers.create_analysis_failed_event(
                payload=payload,
                correlation_id=correlation_id,
                causation_id=causation_id,
            )

            # Publish to Kafka
            topic = IntelligenceAdapterEventHelpers.get_kafka_topic(
                EnumCodeAnalysisEventType.CODE_ANALYSIS_FAILED
            )

            if self.event_publisher is None:
                logger.warning(
                    f"Event publisher not initialized, skipping publish | "
                    f"correlation_id={correlation_id}"
                )
                return

            await self.event_publisher.publish(
                event_type=event["event_type"],
                payload=event["payload"],
                correlation_id=correlation_id,
                causation_id=causation_id,
                topic=topic,
            )

            logger.info(
                f"Published CODE_ANALYSIS_FAILED | "
                f"correlation_id={correlation_id} | "
                f"error_code={error_code_enum.value} | "
                f"processing_time={processing_time_ms:.2f}ms"
            )

        except (ConnectionError, TimeoutError) as e:
            # Network errors during event publishing
            logger.error(
                f"Failed to publish CODE_ANALYSIS_FAILED (publish error) | "
                f"correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )
        except Exception as e:
            # Intentionally broad: event publishing failures should not propagate;
            # the analysis already failed, we just can't notify about it
            logger.error(
                f"Failed to publish CODE_ANALYSIS_FAILED | "
                f"correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )

    # NOTE: The old _route_to_dlq method for raw Kafka messages has been replaced by
    # _route_protocol_message_to_dlq which handles ProtocolEventMessage objects.

    # =========================================================================
    # ONEX Effect Pattern Methods
    # =========================================================================

    async def process(self, operation_data: dict[str, Any]) -> Any:
        """
        Process operation (ONEX Effect pattern method).

        This is a generic Effect pattern method that can be mocked in tests
        to test higher-level workflows without actually calling the intelligence service.

        Args:
            operation_data: Dictionary containing operation details

        Returns:
            Result object with operation outcome

        Note: This is primarily for testing and ONEX pattern compliance.
        Production code should use analyze_code() directly.
        """
        # This is a stub method for ONEX Effect pattern compliance
        # Tests can mock this method to test higher-level logic
        # In production, code calls analyze_code() directly
        from types import SimpleNamespace

        return SimpleNamespace(
            result=operation_data,
            processing_time_ms=0.0,
        )

    # =========================================================================
    # Core Analysis Operation (Extended from Agent 1's work)
    # =========================================================================

    async def analyze_code(
        self, input_data: ModelIntelligenceInput
    ) -> ModelIntelligenceOutput:
        """
        Analyze code using Archon intelligence services.

        This method routes intelligence operations to appropriate backend services:
        - Quality Assessment: /assess/code endpoint
        - Document Quality: /assess/document endpoint
        - Pattern Extraction: /patterns/extract endpoint
        - Compliance Checking: /compliance/check endpoint

        Args:
            input_data: Intelligence operation input with correlation tracking

        Returns:
            ModelIntelligenceOutput with analysis results

        Raises:
            ModelOnexError: If node not initialized or analysis fails
        """
        from datetime import datetime

        from omnibase_core.enums.enum_core_error_code import EnumCoreErrorCode
        from omnibase_core.models.errors.model_onex_error import ModelOnexError

        # Check initialization
        if self._config is None or self._client is None:
            raise ModelOnexError(
                error_code=EnumCoreErrorCode.INITIALIZATION_FAILED,
                message="Intelligence Adapter Effect Node not initialized. Call initialize() first.",
            )

        # Type-safe increment of total_analyses
        total = self._stats.get("total_analyses", 0)
        self._stats["total_analyses"] = (int(total) if total is not None else 0) + 1

        # Retry logic configuration
        max_retries = self._config.max_retries if self._config else 3
        retry_count = 0
        last_error: Exception | None = None

        # Extract content and source_path with safe defaults
        content: str = input_data.content or ""
        source_path: str = input_data.source_path or "unknown"

        while retry_count <= max_retries:
            try:
                logger.info(
                    f"Analyzing code | operation={input_data.operation_type} | "
                    f"correlation_id={input_data.correlation_id} | "
                    f"attempt={retry_count + 1}/{max_retries + 1}"
                )

                # Track processing time
                operation_start = time.perf_counter()

                # Route to appropriate backend service based on operation type
                # Use explicit type annotation for raw_result to allow different handler response types
                raw_result: AnyHandlerResponse
                if input_data.operation_type in [
                    EnumIntelligenceOperationType.ASSESS_CODE_QUALITY,
                    EnumIntelligenceOperationType.CHECK_ARCHITECTURAL_COMPLIANCE,
                ]:
                    # Quality assessment endpoint
                    quality_request = ModelQualityAssessmentRequest(
                        content=content,
                        source_path=source_path,
                        language=input_data.language,
                        include_recommendations=True,
                        min_quality_threshold=(
                            input_data.options.get("min_quality_threshold", 0.7)
                            if input_data.options
                            else 0.7
                        ),
                    )
                    quality_response = await self._client.assess_code_quality(
                        quality_request
                    )
                    raw_result = self._transform_quality_response(quality_response)
                    result_data = self._validate_transform_result(
                        raw_result, "assess_code_quality"
                    )

                elif input_data.operation_type == EnumIntelligenceOperationType.ESTABLISH_PERFORMANCE_BASELINE:
                    # Performance baseline endpoint
                    perf_request = ModelPerformanceAnalysisRequest(
                        operation_name=source_path,
                        code_content=content,
                        context=dict(input_data.options) if input_data.options else {},
                        include_opportunities=True,
                        target_percentile=(
                            input_data.options.get("target_percentile", 95)
                            if input_data.options
                            else 95
                        ),
                    )
                    perf_response = await self._client.analyze_performance(perf_request)
                    raw_result = self._transform_performance_response(perf_response)
                    result_data = self._validate_transform_result(
                        raw_result, "analyze_performance"
                    )

                elif input_data.operation_type == EnumIntelligenceOperationType.GET_QUALITY_PATTERNS:
                    # Pattern detection endpoint
                    pattern_categories = (
                        input_data.options.get("pattern_categories")
                        if input_data.options
                        else None
                    )
                    pattern_request = ModelPatternDetectionRequest(
                        content=content,
                        source_path=source_path,
                        pattern_categories=pattern_categories or [],
                        min_confidence=(
                            input_data.options.get("min_confidence", 0.7)
                            if input_data.options
                            else 0.7
                        ),
                        include_recommendations=True,
                    )
                    pattern_response = await self._client.detect_patterns(pattern_request)
                    raw_result = self._transform_pattern_response(pattern_response)
                    result_data = self._validate_transform_result(
                        raw_result, "get_quality_patterns"
                    )

                else:
                    # Default to quality assessment for unknown operation types
                    logger.warning(
                        f"Unknown operation type '{input_data.operation_type}', "
                        f"defaulting to quality assessment"
                    )
                    default_request = ModelQualityAssessmentRequest(
                        content=content,
                        source_path=source_path,
                        language=input_data.language,
                        include_recommendations=True,
                        min_quality_threshold=0.7,
                    )
                    default_response = await self._client.assess_code_quality(
                        default_request
                    )
                    raw_result = self._transform_quality_response(default_response)
                    result_data = self._validate_transform_result(
                        raw_result, "default_quality_assessment"
                    )

                # Calculate actual processing time
                processing_time_ms = int((time.perf_counter() - operation_start) * 1000)

                # Success - clear error and break out of retry loop
                last_error = None
                break

            except (ConnectionError, TimeoutError, OSError) as process_error:
                # Transient network errors - these are retryable
                last_error = process_error
                retry_count += 1

                if retry_count <= max_retries:
                    retry_delay = (
                        self._config.retry_delay_ms / 1000 if self._config else 1.0
                    )
                    logger.warning(
                        f"Process failed with transient error (attempt {retry_count}/{max_retries + 1}), "
                        f"retrying in {retry_delay}s: {process_error}"
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(
                        f"Process failed after {retry_count} attempts (network error): {process_error}"
                    )
                    break

            except ValueError as process_error:
                # Validation errors - not retryable, fail immediately
                last_error = process_error
                logger.error(
                    f"Process failed with validation error (not retrying): {process_error}"
                )
                break

            except asyncio.CancelledError:
                # Task cancellation during analysis - must re-raise to preserve cancellation semantics
                logger.info(
                    f"Code analysis cancelled | operation={input_data.operation_type} | "
                    f"correlation_id={input_data.correlation_id}"
                )
                raise

            except Exception as process_error:
                # Intentionally broad: catch any unexpected error for the retry loop.
                # Unknown errors are treated as potentially transient and retried.
                last_error = process_error
                retry_count += 1

                if retry_count <= max_retries:
                    retry_delay = (
                        self._config.retry_delay_ms / 1000 if self._config else 1.0
                    )
                    logger.warning(
                        f"Process failed (attempt {retry_count}/{max_retries + 1}), "
                        f"retrying in {retry_delay}s: {process_error}"
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(
                        f"Process failed after {retry_count} attempts: {process_error}"
                    )
                    break

        # Check if we exhausted retries
        if last_error is not None:
            # Track failure (type-safe)
            failed = self._stats.get("failed_analyses", 0)
            self._stats["failed_analyses"] = (int(failed) if failed is not None else 0) + 1

            # Update success rate (type-safe)
            total_analyses = self._stats.get("total_analyses", 0)
            if total_analyses and int(total_analyses) > 0:
                successful = self._stats.get("successful_analyses", 0)
                self._stats["success_rate"] = (
                    float(successful or 0) / float(total_analyses)
                )

            logger.error(
                f"Intelligence analysis failed | "
                f"operation={input_data.operation_type} | "
                f"correlation_id={input_data.correlation_id} | "
                f"error={last_error}",
                exc_info=True,
            )

            raise ModelOnexError(
                error_code=EnumCoreErrorCode.OPERATION_FAILED,
                message=f"Intelligence analysis failed: {last_error!s}",
            ) from last_error

        # Build output from process result using canonical ModelIntelligenceOutput fields
        # Field mapping from internal result_data to canonical model:
        # - processing_time_ms -> metadata (removed from direct fields)
        # - onex_compliance (float) -> onex_compliant (bool, threshold > 0.8)
        # - complexity_score -> analysis_results
        # - issues -> merged into recommendations
        # - patterns (objects) -> patterns_detected (list[str])
        # - result_data -> analysis_results
        onex_compliance_score = result_data.get("onex_compliance", 0.0)
        onex_compliant = onex_compliance_score >= 0.8 if onex_compliance_score else None

        # Merge issues into recommendations (canonical model only has recommendations)
        issues = result_data.get("issues", [])
        recommendations = result_data.get("recommendations", [])
        all_recommendations = list(recommendations) + [
            f"[Issue] {issue}" for issue in issues
        ]

        # Convert patterns (objects or dicts) to pattern names (list[str])
        raw_patterns = result_data.get("patterns", [])
        patterns_detected: list[str] = []
        if raw_patterns:
            for pattern in raw_patterns:
                if isinstance(pattern, str):
                    patterns_detected.append(pattern)
                elif isinstance(pattern, dict):
                    # Extract pattern name from dict
                    name = pattern.get("pattern_name") or pattern.get("name", "unknown")
                    patterns_detected.append(str(name))
                elif hasattr(pattern, "pattern_name"):
                    patterns_detected.append(str(pattern.pattern_name))
                elif hasattr(pattern, "name"):
                    patterns_detected.append(str(pattern.name))

        # Build analysis_results from complexity_score and result_data
        # Use AnalysisResultsDict for type safety
        analysis_results_dict = AnalysisResultsDict()
        raw_result_data = result_data.get("result_data") or {}
        if isinstance(raw_result_data, dict):
            # Copy over known fields with proper types
            if "complexity_score" in raw_result_data:
                analysis_results_dict["complexity_score"] = float(raw_result_data["complexity_score"])
        if result_data.get("complexity_score") is not None:
            analysis_results_dict["complexity_score"] = float(result_data["complexity_score"])
        if onex_compliance_score:
            analysis_results_dict["onex_compliance_score"] = float(onex_compliance_score)

        # Build metadata with OutputMetadataDict for type safety
        output_metadata = OutputMetadataDict()
        if input_data.source_path:
            output_metadata["source_file"] = input_data.source_path
        output_metadata["processing_time_ms"] = processing_time_ms

        output = ModelIntelligenceOutput(
            success=result_data.get("success", True),
            operation_type=input_data.operation_type,
            correlation_id=input_data.correlation_id,
            quality_score=result_data.get("quality_score", 0.0),
            onex_compliant=onex_compliant,
            recommendations=all_recommendations,
            patterns_detected=patterns_detected,
            analysis_results=analysis_results_dict,
            metadata=output_metadata,
        )

        # Update statistics for successful analysis (type-safe)
        if output.success:
            successful = self._stats.get("successful_analyses", 0)
            self._stats["successful_analyses"] = (
                int(successful) if successful is not None else 0
            ) + 1
            if output.quality_score is not None:
                total_quality = self._stats.get("total_quality_score", 0.0)
                new_total_quality = (
                    float(total_quality) if total_quality is not None else 0.0
                ) + output.quality_score
                self._stats["total_quality_score"] = new_total_quality
                successful_count = self._stats.get("successful_analyses", 1)
                self._stats["avg_quality_score"] = new_total_quality / float(
                    successful_count if successful_count else 1
                )
        else:
            failed = self._stats.get("failed_analyses", 0)
            self._stats["failed_analyses"] = (
                int(failed) if failed is not None else 0
            ) + 1

        # Update success rate (type-safe)
        total_analyses = self._stats.get("total_analyses", 0)
        if total_analyses and int(total_analyses) > 0:
            successful = self._stats.get("successful_analyses", 0)
            self._stats["success_rate"] = (
                float(successful or 0) / float(total_analyses)
            )

        # Update last analysis time
        self._stats["last_analysis_time"] = datetime.now(UTC).isoformat()

        return output

    # =========================================================================
    # Transformation Methods (ONEX-compliant)
    # =========================================================================

    def _validate_transform_result(
        self,
        result: Any,
        operation_type: str,
    ) -> ValidatedHandlerResponse:
        """
        Validate and normalize handler transform result.

        Delegates to the validate_handler_result helper function which provides
        comprehensive type validation and normalization for all expected keys.

        This method ensures that transform handlers return valid dictionaries with
        expected keys and proper types. Provides defensive defaults if the result
        is None, not a dict, or has missing/invalid keys.

        Args:
            result: Return value from a transform handler
            operation_type: Name of the operation for error messages and logging

        Returns:
            Validated dictionary with guaranteed structure:
            - success: bool (default True)
            - quality_score: float in [0.0, 1.0] (default 0.0)
            - onex_compliance: float in [0.0, 1.0] (default 0.0)
            - complexity_score: float in [0.0, 1.0] (default 0.0)
            - issues: list (default [])
            - recommendations: list (default [])
            - patterns: list (default [])
            - result_data: dict (default {})

        Note:
            Type validation is performed for all fields:
            - success must be a boolean (non-bool values are converted)
            - Numeric fields are validated and clamped to [0.0, 1.0]
            - List fields are validated and converted if needed
            - Dict fields are validated and converted if needed
            - Validation issues are logged for debugging
        """
        return validate_handler_result(result, operation_type, log_issues=True)

    def _convert_to_effect_input(self, input_data: ModelIntelligenceInput) -> Any:
        """
        Convert ModelIntelligenceInput to Effect input format.

        This is a utility method for ONEX Effect pattern compliance, converting
        intelligence input to a generic effect operation format.

        Args:
            input_data: Intelligence operation input

        Returns:
            Object with effect input structure:
            - operation_id: Correlation ID for tracking
            - operation_data: Input data and metadata
            - retry_enabled: Whether retries are enabled
            - circuit_breaker_enabled: Whether circuit breaker is active
        """
        from types import SimpleNamespace

        return SimpleNamespace(
            operation_id=input_data.correlation_id,
            operation_data={
                "operation_type": input_data.operation_type,
                "content": input_data.content,
                "source_path": input_data.source_path,
                "language": input_data.language,
                "options": input_data.options or {},
                "metadata": input_data.metadata or {},
            },
            retry_enabled=self._config.max_retries > 0 if self._config else True,
            circuit_breaker_enabled=(
                self._config.circuit_breaker_enabled if self._config else True
            ),
        )

    def _transform_quality_response(self, response: Any) -> QualityHandlerResponse:
        """Transform quality assessment response to standard format.

        Delegates to the extracted handler for the actual transformation logic.
        This method is kept for backward compatibility and to maintain the
        instance method interface expected by callers.

        Args:
            response: Quality assessment response from intelligence service

        Returns:
            QualityHandlerResponse with standardized quality data.
            See handlers.handler_transform_quality.transform_quality_response
            for full documentation of the return format.
        """
        return transform_quality_response(response)

    def _transform_performance_response(self, response: Any) -> PerformanceHandlerResponse:
        """Transform performance analysis response to standard format.

        Delegates to the extracted handler for the actual transformation logic.
        This method is kept for backward compatibility and to maintain the
        instance method interface expected by callers.

        Args:
            response: Performance analysis response from intelligence service

        Returns:
            PerformanceHandlerResponse with standardized performance data.
            See handlers.handler_transform_performance.transform_performance_response
            for full documentation of the return format.
        """
        return transform_performance_response(response)

    def _transform_pattern_response(self, response: Any) -> PatternHandlerResponse:
        """Transform pattern detection response to standard format.

        Delegates to the pure handler function for transformation logic.

        Args:
            response: Pattern detection response from intelligence service

        Returns:
            PatternHandlerResponse with standardized pattern data:
            - success: Operation success status
            - onex_compliance: ONEX compliance score
            - patterns: Detected patterns
            - issues: Anti-patterns and issues
            - recommendations: Pattern-based recommendations
            - result_data: Additional pattern metadata
        """
        return transform_pattern_response(response)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def _map_operation_type(
        self, event_op_type: EnumAnalysisOperationType | None
    ) -> EnumIntelligenceOperationType:
        """
        Map event operation type to intelligence operation type.

        Args:
            event_op_type: Event operation type enum (or None for default)

        Returns:
            Intelligence operation type enum
        """
        if event_op_type is None:
            return EnumIntelligenceOperationType.ASSESS_CODE_QUALITY
        mapping: dict[EnumAnalysisOperationType, EnumIntelligenceOperationType] = {
            EnumAnalysisOperationType.QUALITY_ASSESSMENT: EnumIntelligenceOperationType.ASSESS_CODE_QUALITY,
            EnumAnalysisOperationType.ONEX_COMPLIANCE: EnumIntelligenceOperationType.CHECK_ARCHITECTURAL_COMPLIANCE,
            EnumAnalysisOperationType.PATTERN_EXTRACTION: EnumIntelligenceOperationType.GET_QUALITY_PATTERNS,
            EnumAnalysisOperationType.ARCHITECTURAL_COMPLIANCE: EnumIntelligenceOperationType.CHECK_ARCHITECTURAL_COMPLIANCE,
            EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS: EnumIntelligenceOperationType.ASSESS_CODE_QUALITY,
        }
        return mapping.get(event_op_type, EnumIntelligenceOperationType.ASSESS_CODE_QUALITY)

    def _map_to_event_operation_type(
        self, operation_type: EnumIntelligenceOperationType
    ) -> EnumAnalysisOperationType:
        """
        Map intelligence operation type to event operation type.

        Args:
            operation_type: Intelligence operation type enum

        Returns:
            Event operation type enum
        """
        mapping: dict[EnumIntelligenceOperationType, EnumAnalysisOperationType] = {
            EnumIntelligenceOperationType.ASSESS_CODE_QUALITY: EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
            EnumIntelligenceOperationType.CHECK_ARCHITECTURAL_COMPLIANCE: EnumAnalysisOperationType.ARCHITECTURAL_COMPLIANCE,
            EnumIntelligenceOperationType.GET_QUALITY_PATTERNS: EnumAnalysisOperationType.PATTERN_EXTRACTION,
        }
        return mapping.get(
            operation_type, EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS
        )

    def get_analysis_stats(self) -> dict[str, Any]:
        """
        Get current analysis statistics (ONEX-compliant).

        Returns:
            Dictionary with analysis statistics including:
            - node_id: Unique node identifier
            - total_analyses: Total analysis operations
            - successful_analyses: Successfully completed analyses
            - failed_analyses: Failed analysis operations
            - avg_quality_score: Average quality score across analyses
            - success_rate: Success rate (0.0 to 1.0)
            - last_analysis_time: Timestamp of last analysis
        """
        return {
            "node_id": str(self.node_id),
            **self._stats,
        }

    def get_metrics(self) -> dict[str, Any]:
        """
        Get current operation metrics.

        Returns:
            Dictionary with metrics including:
            - events_consumed: Total events consumed from Kafka
            - events_processed: Successfully processed events
            - events_failed: Failed event processing
            - analysis_completed: Successful analyses
            - analysis_failed: Failed analyses
            - dlq_routed: Messages routed to DLQ
            - avg_processing_time_ms: Average processing time
        """
        return {
            **self.metrics,
            "is_running": self.is_running,
            "consumer_group": self.consumer_config.group_id,
            "topics_subscribed": self.consumer_config.topics,
        }
