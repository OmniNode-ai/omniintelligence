"""
Intelligence Adapter Event Contracts - ONEX Compliant Kafka Event Schemas

Event schemas for Intelligence Adapter Effect Node operations:
- CODE_ANALYSIS_REQUESTED: Triggered when code analysis is requested
- CODE_ANALYSIS_COMPLETED: Triggered when code analysis completes successfully
- CODE_ANALYSIS_FAILED: Triggered when code analysis fails

ONEX Compliance:
- Model-based naming: ModelCodeAnalysis{Type}Payload
- Strong typing with Pydantic v2
- Event envelope integration with ModelEventEnvelope
- Kafka topic routing following event bus architecture
- Serialization/deserialization helpers
- Comprehensive validation

Created: 2025-10-21
Reference: EVENT_BUS_ARCHITECTURE.md, omninode_bridge event patterns
"""

from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EnumCodeAnalysisEventType(str, Enum):
    """Event types for code analysis operations."""

    CODE_ANALYSIS_REQUESTED = "CODE_ANALYSIS_REQUESTED"
    CODE_ANALYSIS_COMPLETED = "CODE_ANALYSIS_COMPLETED"
    CODE_ANALYSIS_FAILED = "CODE_ANALYSIS_FAILED"


class EnumAnalysisOperationType(str, Enum):
    """Type of analysis operation being performed."""

    # Legacy quality assessment operations
    QUALITY_ASSESSMENT = "QUALITY_ASSESSMENT"
    ONEX_COMPLIANCE = "ONEX_COMPLIANCE"
    ARCHITECTURAL_COMPLIANCE = "ARCHITECTURAL_COMPLIANCE"
    COMPREHENSIVE_ANALYSIS = "COMPREHENSIVE_ANALYSIS"

    # Intelligence request operations (manifest_injector spec)
    PATTERN_EXTRACTION = "PATTERN_EXTRACTION"
    INFRASTRUCTURE_SCAN = "INFRASTRUCTURE_SCAN"
    MODEL_DISCOVERY = "MODEL_DISCOVERY"
    SCHEMA_DISCOVERY = "SCHEMA_DISCOVERY"


class EnumAnalysisErrorCode(str, Enum):
    """Error codes for failed analysis operations."""

    # Legacy error codes
    INVALID_INPUT = "INVALID_INPUT"
    UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"
    PARSING_ERROR = "PARSING_ERROR"
    TIMEOUT = "TIMEOUT"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # Intelligence request error codes (manifest_injector spec)
    PATTERN_QUERY_FAILED = "PATTERN_QUERY_FAILED"
    INFRASTRUCTURE_SCAN_FAILED = "INFRASTRUCTURE_SCAN_FAILED"
    MODEL_DISCOVERY_FAILED = "MODEL_DISCOVERY_FAILED"
    SCHEMA_DISCOVERY_FAILED = "SCHEMA_DISCOVERY_FAILED"
    BACKEND_UNAVAILABLE = "BACKEND_UNAVAILABLE"
    INVALID_OPERATION = "INVALID_OPERATION"


# ============================================================================
# Event Payload Models
# ============================================================================


class ModelCodeAnalysisRequestPayload(BaseModel):
    """
    Payload for CODE_ANALYSIS_REQUESTED event.

    Captures all parameters needed to perform code analysis including
    source identification, content, language, and optional configuration.

    Attributes:
        source_path: File path or identifier for the code being analyzed
        content: Optional code content (if not reading from source_path)
        language: Programming language (python, typescript, rust, etc.)
        operation_type: Type of analysis to perform
        options: Additional analysis options (depth, include_metrics, etc.)
        project_id: Optional project identifier for context
        user_id: Optional user identifier for authorization
    """

    source_path: str = Field(
        ...,
        description="File path or identifier for code being analyzed",
        examples=["src/api/endpoints.py", "lib/utils/parser.ts"],
        min_length=1,
    )

    content: Optional[str] = Field(
        default=None,
        description="Code content to analyze (if not reading from source_path)",
        examples=["def hello():\n    pass"],
    )

    language: Optional[str] = Field(
        default=None,
        description="Programming language (python, typescript, rust, etc.)",
        examples=["python", "typescript", "rust", "go"],
    )

    operation_type: EnumAnalysisOperationType = Field(
        default=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
        description="Type of analysis operation to perform",
    )

    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional analysis options",
        examples=[
            {
                "include_metrics": True,
                "depth": "comprehensive",
                "quality_threshold": 0.8,
                "enable_caching": True,
            }
        ],
    )

    project_id: Optional[str] = Field(
        default=None,
        description="Project identifier for context and historical analysis",
        examples=["project-123", "omniarchon"],
    )

    user_id: Optional[str] = Field(
        default=None,
        description="User identifier for authorization and audit",
        examples=["user-456", "auth0|abc123"],
    )

    @field_validator("source_path")
    @classmethod
    def validate_source_path(cls, v: str) -> str:
        """Ensure source_path is not empty or whitespace."""
        if not v or not v.strip():
            raise ValueError("source_path cannot be empty or whitespace")
        return v.strip()

    model_config = ConfigDict(
        frozen=False,
        json_schema_extra={
            "examples": [
                {
                    "source_path": "src/services/intelligence/quality_service.py",
                    "content": None,
                    "language": "python",
                    "operation_type": "COMPREHENSIVE_ANALYSIS",
                    "options": {
                        "include_metrics": True,
                        "depth": "comprehensive",
                        "quality_threshold": 0.8,
                    },
                    "project_id": "omniarchon",
                    "user_id": "system",
                }
            ]
        },
    )


class ModelCodeAnalysisCompletedPayload(BaseModel):
    """
    Payload for CODE_ANALYSIS_COMPLETED event.

    Captures analysis results including quality scores, compliance metrics,
    identified issues, and recommendations.

    Attributes:
        source_path: File path that was analyzed
        quality_score: Overall quality score (0.0-1.0)
        onex_compliance: ONEX architectural compliance score (0.0-1.0)
        issues_count: Number of issues identified
        recommendations_count: Number of recommendations provided
        processing_time_ms: Time taken to complete analysis in milliseconds
        operation_type: Type of analysis that was performed
        complexity_score: Optional code complexity score
        maintainability_score: Optional maintainability score
        results_summary: Summary of analysis results
        cache_hit: Whether result was served from cache
    """

    source_path: str = Field(
        ...,
        description="File path that was analyzed",
        examples=["src/api/endpoints.py"],
    )

    quality_score: float = Field(
        ...,
        description="Overall quality score (0.0-1.0)",
        ge=0.0,
        le=1.0,
        examples=[0.87, 0.92, 0.65],
    )

    onex_compliance: float = Field(
        ...,
        description="ONEX architectural compliance score (0.0-1.0)",
        ge=0.0,
        le=1.0,
        examples=[0.92, 0.88, 0.75],
    )

    issues_count: int = Field(
        ...,
        description="Number of issues identified",
        ge=0,
        examples=[3, 0, 12],
    )

    recommendations_count: int = Field(
        ...,
        description="Number of recommendations provided",
        ge=0,
        examples=[5, 2, 8],
    )

    processing_time_ms: float = Field(
        ...,
        description="Time taken to complete analysis in milliseconds",
        ge=0.0,
        examples=[1234.5, 567.8, 2345.6],
    )

    operation_type: EnumAnalysisOperationType = Field(
        ...,
        description="Type of analysis that was performed",
    )

    complexity_score: Optional[float] = Field(
        default=None,
        description="Code complexity score (0.0-1.0, lower is better)",
        ge=0.0,
        le=1.0,
        examples=[0.45, 0.62, 0.38],
    )

    maintainability_score: Optional[float] = Field(
        default=None,
        description="Maintainability score (0.0-1.0, higher is better)",
        ge=0.0,
        le=1.0,
        examples=[0.78, 0.85, 0.69],
    )

    results_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of analysis results with key findings",
        examples=[
            {
                "total_lines": 245,
                "cyclomatic_complexity": 12,
                "cognitive_complexity": 18,
                "pattern_matches": ["onex_effect_pattern", "async_transaction"],
                "anti_patterns": ["god_class"],
            }
        ],
    )

    cache_hit: bool = Field(
        default=False,
        description="Whether result was served from cache",
    )

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "source_path": "src/services/intelligence/quality_service.py",
                    "quality_score": 0.87,
                    "onex_compliance": 0.92,
                    "issues_count": 3,
                    "recommendations_count": 5,
                    "processing_time_ms": 1234.5,
                    "operation_type": "COMPREHENSIVE_ANALYSIS",
                    "complexity_score": 0.45,
                    "maintainability_score": 0.78,
                    "results_summary": {
                        "total_lines": 245,
                        "cyclomatic_complexity": 12,
                        "pattern_matches": ["onex_effect_pattern"],
                    },
                    "cache_hit": False,
                }
            ]
        },
    )


class ModelCodeAnalysisFailedPayload(BaseModel):
    """
    Payload for CODE_ANALYSIS_FAILED event.

    Captures failure information including error details, operation context,
    and retry eligibility.

    Attributes:
        operation_type: Type of analysis that failed
        source_path: File path that failed analysis
        error_message: Human-readable error description
        error_code: Machine-readable error code
        retry_allowed: Whether the operation can be retried
        retry_count: Number of retries attempted
        processing_time_ms: Time taken before failure in milliseconds
        error_details: Additional error context and stack trace
        suggested_action: Recommended action to resolve the error
    """

    operation_type: EnumAnalysisOperationType = Field(
        ...,
        description="Type of analysis operation that failed",
    )

    source_path: str = Field(
        ...,
        description="File path that failed analysis",
        examples=["src/broken/invalid_syntax.py"],
    )

    error_message: str = Field(
        ...,
        description="Human-readable error description",
        examples=[
            "Failed to parse Python code: unexpected EOF",
            "Analysis timeout after 30 seconds",
            "Unsupported language: brainfuck",
        ],
        min_length=1,
    )

    error_code: EnumAnalysisErrorCode = Field(
        ...,
        description="Machine-readable error code",
    )

    retry_allowed: bool = Field(
        ...,
        description="Whether the operation can be retried",
        examples=[True, False],
    )

    retry_count: int = Field(
        default=0,
        description="Number of retries attempted",
        ge=0,
        examples=[0, 1, 2, 3],
    )

    processing_time_ms: float = Field(
        ...,
        description="Time taken before failure in milliseconds",
        ge=0.0,
        examples=[456.7, 30000.0, 123.4],
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional error context and stack trace",
        examples=[
            {
                "exception_type": "SyntaxError",
                "line_number": 42,
                "column": 15,
                "stack_trace": "...",
            }
        ],
    )

    suggested_action: Optional[str] = Field(
        default=None,
        description="Recommended action to resolve the error",
        examples=[
            "Verify source code syntax is valid",
            "Retry with increased timeout",
            "Check language is supported",
        ],
    )

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "operation_type": "QUALITY_ASSESSMENT",
                    "source_path": "src/broken/invalid_syntax.py",
                    "error_message": "Failed to parse Python code: unexpected EOF",
                    "error_code": "PARSING_ERROR",
                    "retry_allowed": False,
                    "retry_count": 0,
                    "processing_time_ms": 456.7,
                    "error_details": {
                        "exception_type": "SyntaxError",
                        "line_number": 42,
                    },
                    "suggested_action": "Verify source code syntax is valid",
                }
            ]
        },
    )


# ============================================================================
# Intelligence Request Payload Models (manifest_injector spec)
# ============================================================================


class ModelPatternExtractionPayload(BaseModel):
    """
    Payload for PATTERN_EXTRACTION operation response.

    Returns available code generation patterns from Qdrant vector database.

    Attributes:
        patterns: List of code generation patterns
        query_time_ms: Time taken to complete query in milliseconds
        total_count: Total number of patterns found
    """

    patterns: list[dict[str, Any]] = Field(
        ...,
        description="List of code generation patterns",
        examples=[
            [
                {
                    "name": "CRUD Pattern",
                    "file_path": "path/to/node_crud_effect.py",
                    "description": "Create, Read, Update, Delete operations",
                    "node_types": ["EFFECT", "REDUCER"],
                    "confidence": 0.95,
                    "use_cases": ["Database operations", "API endpoints"],
                    "metadata": {
                        "complexity": "medium",
                        "last_updated": "2025-10-26T12:00:00Z",
                    },
                }
            ]
        ],
    )

    query_time_ms: float = Field(
        ...,
        description="Time taken to complete query in milliseconds",
        ge=0.0,
        examples=[150.0, 250.0, 500.0],
    )

    total_count: int = Field(
        ...,
        description="Total number of patterns found",
        ge=0,
        examples=[4, 12, 0],
    )

    model_config = ConfigDict(frozen=True)


class ModelInfrastructureScanPayload(BaseModel):
    """
    Payload for INFRASTRUCTURE_SCAN operation response.

    Returns current infrastructure topology (databases, Kafka topics, Docker services).

    Attributes:
        postgresql: PostgreSQL database information
        kafka: Kafka/Redpanda information
        qdrant: Qdrant vector database information
        docker_services: Docker services information
        archon_mcp: Archon MCP service information
        query_time_ms: Time taken to complete scan in milliseconds
    """

    postgresql: Optional[dict[str, Any]] = Field(
        None,
        description="PostgreSQL database information",
        examples=[
            {
                "host": "192.168.86.200",
                "port": 5436,
                "database": "omninode_bridge",
                "status": "connected",
                "tables": [
                    {
                        "name": "agent_routing_decisions",
                        "row_count": 1234,
                        "size_mb": 5.2,
                    }
                ],
                "table_count": 34,
            }
        ],
    )

    kafka: Optional[dict[str, Any]] = Field(
        None,
        description="Kafka/Redpanda information (see config.kafka_helper for context-aware defaults)",
        examples=[
            {
                "bootstrap_servers": "192.168.86.200:29092",  # Example - actual config from config.kafka_helper
                "status": "connected",
                "topics": [
                    {
                        "name": "agent-routing-decisions",
                        "partitions": 3,
                        "replication_factor": 1,
                        "message_count": 5678,
                    }
                ],
                "topic_count": 97,
            }
        ],
    )

    qdrant: Optional[dict[str, Any]] = Field(
        None,
        description="Qdrant vector database information",
        examples=[
            {
                "endpoint": "localhost:6333",
                "status": "connected",
                "collections": [
                    {
                        "name": "code_generation_patterns",
                        "vector_size": 1536,
                        "point_count": 234,
                    }
                ],
                "collection_count": 4,
            }
        ],
    )

    docker_services: Optional[list[dict[str, Any]]] = Field(
        None,
        description="Docker services information",
        examples=[
            [
                {
                    "name": "archon-intelligence",
                    "status": "running",
                    "port": 8053,
                    "health": "healthy",
                }
            ]
        ],
    )

    archon_mcp: Optional[dict[str, Any]] = Field(
        None,
        description="Archon MCP service information",
        examples=[
            {
                "endpoint": "http://localhost:8051",
                "status": "healthy",
                "health_data": {"status": "ok"},
            }
        ],
    )

    query_time_ms: float = Field(
        ...,
        description="Time taken to complete scan in milliseconds",
        ge=0.0,
        examples=[250.0, 500.0, 1000.0],
    )

    model_config = ConfigDict(frozen=True)


class ModelDiscoveryPayload(BaseModel):
    """
    Payload for MODEL_DISCOVERY operation response.

    Returns available AI models and ONEX data models.

    Attributes:
        ai_models: AI model providers and configurations
        onex_models: ONEX node types and contracts
        intelligence_models: Intelligence context models
        query_time_ms: Time taken to complete discovery in milliseconds
    """

    ai_models: Optional[dict[str, Any]] = Field(
        None,
        description="AI model providers and configurations",
        examples=[
            {
                "providers": [
                    {
                        "name": "Anthropic",
                        "models": ["claude-sonnet-4", "claude-opus-4"],
                        "status": "available",
                        "rate_limit": "Check API dashboard",
                    }
                ],
                "quorum_config": {
                    "total_weight": 7.5,
                    "consensus_thresholds": {
                        "auto_apply": 0.80,
                        "suggest_with_review": 0.60,
                    },
                },
            }
        ],
    )

    onex_models: Optional[dict[str, Any]] = Field(
        None,
        description="ONEX node types and contracts",
        examples=[
            {
                "node_types": [
                    {
                        "name": "EFFECT",
                        "naming_pattern": "Node<Name>Effect",
                        "file_pattern": "node_*_effect.py",
                        "execute_method": "async def execute_effect(self, contract: ModelContractEffect) -> Any",
                        "count": 45,
                    }
                ],
                "contracts": [
                    "ModelContractEffect",
                    "ModelContractCompute",
                    "ModelContractReducer",
                    "ModelContractOrchestrator",
                ],
            }
        ],
    )

    intelligence_models: Optional[list[dict[str, Any]]] = Field(
        None,
        description="Intelligence context models",
        examples=[
            [
                {
                    "file": "agents/lib/models/intelligence_context.py",
                    "class": "IntelligenceContext",
                    "description": "RAG-gathered intelligence for template generation",
                }
            ]
        ],
    )

    query_time_ms: float = Field(
        ...,
        description="Time taken to complete discovery in milliseconds",
        ge=0.0,
        examples=[100.0, 200.0, 500.0],
    )

    model_config = ConfigDict(frozen=True)


class ModelSchemaDiscoveryPayload(BaseModel):
    """
    Payload for SCHEMA_DISCOVERY operation response.

    Returns database schemas and table definitions.

    Attributes:
        tables: List of database tables with schema information
        total_tables: Total number of tables found
        query_time_ms: Time taken to complete discovery in milliseconds
    """

    tables: list[dict[str, Any]] = Field(
        ...,
        description="List of database tables with schema information",
        examples=[
            [
                {
                    "name": "agent_routing_decisions",
                    "schema": "public",
                    "columns": [
                        {
                            "name": "id",
                            "type": "UUID",
                            "nullable": False,
                            "primary_key": True,
                        },
                        {"name": "user_request", "type": "TEXT", "nullable": False},
                        {
                            "name": "confidence_score",
                            "type": "NUMERIC(5,4)",
                            "nullable": False,
                        },
                    ],
                    "row_count": 1234,
                    "size_mb": 5.2,
                }
            ]
        ],
    )

    total_tables: int = Field(
        ...,
        description="Total number of tables found",
        ge=0,
        examples=[15, 20, 30],
    )

    query_time_ms: float = Field(
        ...,
        description="Time taken to complete discovery in milliseconds",
        ge=0.0,
        examples=[200.0, 300.0, 500.0],
    )

    model_config = ConfigDict(frozen=True)


class IntelligenceAdapterEventHelpers:
    """
    Helper methods for creating and managing Intelligence Adapter events.

    Provides factory methods to create properly-formed event envelopes
    with correct topic routing, correlation tracking, and serialization.
    """

    # Topic routing configuration
    SERVICE_PREFIX = "archon-intelligence"
    DOMAIN = "intelligence"
    PATTERN = "event"
    VERSION = "v1"

    @staticmethod
    def create_analysis_requested_event(
        payload: ModelCodeAnalysisRequestPayload,
        correlation_id: Optional[UUID] = None,
        source_instance: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create CODE_ANALYSIS_REQUESTED event envelope.

        Args:
            payload: Request payload with analysis parameters
            correlation_id: Optional correlation ID for tracking
            source_instance: Optional source instance identifier

        Returns:
            Event envelope dictionary ready for Kafka publishing
        """
        # Local import to avoid circular dependency
        from omniintelligence.models.model_event_envelope import (
            ModelEventEnvelope,
            ModelEventSource,
        )

        correlation_id = correlation_id or uuid4()

        source = ModelEventSource(
            service=IntelligenceAdapterEventHelpers.SERVICE_PREFIX,
            instance_id=source_instance or "intelligence-adapter-1",
        )

        envelope = ModelEventEnvelope(
            event_type=f"omninode.{IntelligenceAdapterEventHelpers.DOMAIN}.{IntelligenceAdapterEventHelpers.PATTERN}.code_analysis_requested.{IntelligenceAdapterEventHelpers.VERSION}",
            payload=payload.model_dump(),
            correlation_id=correlation_id,
            source=source,
        )

        return envelope.to_dict()

    @staticmethod
    def create_analysis_completed_event(
        payload: ModelCodeAnalysisCompletedPayload,
        correlation_id: UUID,
        causation_id: Optional[UUID] = None,
        source_instance: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create CODE_ANALYSIS_COMPLETED event envelope.

        Args:
            payload: Completion payload with analysis results
            correlation_id: Correlation ID from original request
            causation_id: Optional event ID that caused this event
            source_instance: Optional source instance identifier

        Returns:
            Event envelope dictionary ready for Kafka publishing
        """
        # Local import to avoid circular dependency
        from omniintelligence.models.model_event_envelope import (
            ModelEventEnvelope,
            ModelEventSource,
        )

        source = ModelEventSource(
            service=IntelligenceAdapterEventHelpers.SERVICE_PREFIX,
            instance_id=source_instance or "intelligence-adapter-1",
        )

        envelope = ModelEventEnvelope(
            event_type=f"omninode.{IntelligenceAdapterEventHelpers.DOMAIN}.{IntelligenceAdapterEventHelpers.PATTERN}.code_analysis_completed.{IntelligenceAdapterEventHelpers.VERSION}",
            payload=payload.model_dump(),
            correlation_id=correlation_id,
            causation_id=causation_id,
            source=source,
        )

        return envelope.to_dict()

    @staticmethod
    def create_analysis_failed_event(
        payload: ModelCodeAnalysisFailedPayload,
        correlation_id: UUID,
        causation_id: Optional[UUID] = None,
        source_instance: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create CODE_ANALYSIS_FAILED event envelope.

        Args:
            payload: Failure payload with error details
            correlation_id: Correlation ID from original request
            causation_id: Optional event ID that caused this event
            source_instance: Optional source instance identifier

        Returns:
            Event envelope dictionary ready for Kafka publishing
        """
        # Local import to avoid circular dependency
        from omniintelligence.models.model_event_envelope import (
            ModelEventEnvelope,
            ModelEventSource,
        )

        source = ModelEventSource(
            service=IntelligenceAdapterEventHelpers.SERVICE_PREFIX,
            instance_id=source_instance or "intelligence-adapter-1",
        )

        envelope = ModelEventEnvelope(
            event_type=f"omninode.{IntelligenceAdapterEventHelpers.DOMAIN}.{IntelligenceAdapterEventHelpers.PATTERN}.code_analysis_failed.{IntelligenceAdapterEventHelpers.VERSION}",
            payload=payload.model_dump(),
            correlation_id=correlation_id,
            causation_id=causation_id,
            source=source,
        )

        return envelope.to_dict()

    @staticmethod
    def get_kafka_topic(
        event_type: EnumCodeAnalysisEventType, environment: str = "development"
    ) -> str:
        """
        Generate Kafka topic name for event type.

        Topic Format: {env}.{service}.{domain}.{event_type}.{version}

        Args:
            event_type: Type of code analysis event
            environment: Environment (development, staging, production)

        Returns:
            Kafka topic name
        """
        env_prefix = "dev" if environment == "development" else environment
        event_suffix = event_type.value.replace("_", "-").lower()

        return f"{env_prefix}.{IntelligenceAdapterEventHelpers.SERVICE_PREFIX}.{IntelligenceAdapterEventHelpers.DOMAIN}.{event_suffix}.{IntelligenceAdapterEventHelpers.VERSION}"

    @staticmethod
    def deserialize_event(event_dict: dict[str, Any]) -> tuple[str, BaseModel]:
        """
        Deserialize event envelope and extract typed payload.

        Args:
            event_dict: Event envelope dictionary from Kafka

        Returns:
            Tuple of (event_type, typed_payload_model)

        Raises:
            ValueError: If event_type is unknown or payload is invalid
        """
        event_type = event_dict.get("event_type", "")

        # Extract payload
        payload_data = event_dict.get("payload", {})

        # Determine event type and deserialize payload
        if "code_analysis_requested" in event_type:
            request_payload = ModelCodeAnalysisRequestPayload(**payload_data)
            return (EnumCodeAnalysisEventType.CODE_ANALYSIS_REQUESTED.value, request_payload)

        if "code_analysis_completed" in event_type:
            completed_payload = ModelCodeAnalysisCompletedPayload(**payload_data)
            return (EnumCodeAnalysisEventType.CODE_ANALYSIS_COMPLETED.value, completed_payload)

        if "code_analysis_failed" in event_type:
            failed_payload = ModelCodeAnalysisFailedPayload(**payload_data)
            return (EnumCodeAnalysisEventType.CODE_ANALYSIS_FAILED.value, failed_payload)

        raise ValueError(f"Unknown event type: {event_type}")


# ============================================================================
# Convenience Functions
# ============================================================================


def create_request_event(
    source_path: str,
    content: Optional[str] = None,
    language: Optional[str] = None,
    operation_type: EnumAnalysisOperationType = EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
    options: Optional[dict[str, Any]] = None,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """
    Convenience function to create CODE_ANALYSIS_REQUESTED event.

    Args:
        source_path: File path or identifier
        content: Optional code content
        language: Optional programming language
        operation_type: Type of analysis operation
        options: Additional analysis options
        correlation_id: Optional correlation ID

    Returns:
        Event envelope dictionary ready for publishing
    """
    payload = ModelCodeAnalysisRequestPayload(
        source_path=source_path,
        content=content,
        language=language,
        operation_type=operation_type,
        options=options or {},
    )

    return IntelligenceAdapterEventHelpers.create_analysis_requested_event(
        payload=payload,
        correlation_id=correlation_id,
    )


def create_completed_event(
    source_path: str,
    quality_score: float,
    onex_compliance: float,
    issues_count: int,
    recommendations_count: int,
    processing_time_ms: float,
    operation_type: EnumAnalysisOperationType,
    correlation_id: UUID,
    results_summary: Optional[dict[str, Any]] = None,
    cache_hit: bool = False,
) -> dict[str, Any]:
    """
    Convenience function to create CODE_ANALYSIS_COMPLETED event.

    Args:
        source_path: File path analyzed
        quality_score: Overall quality score (0.0-1.0)
        onex_compliance: ONEX compliance score (0.0-1.0)
        issues_count: Number of issues found
        recommendations_count: Number of recommendations
        processing_time_ms: Processing time in milliseconds
        operation_type: Type of analysis performed
        correlation_id: Correlation ID from request
        results_summary: Optional results summary
        cache_hit: Whether result was cached

    Returns:
        Event envelope dictionary ready for publishing
    """
    payload = ModelCodeAnalysisCompletedPayload(
        source_path=source_path,
        quality_score=quality_score,
        onex_compliance=onex_compliance,
        issues_count=issues_count,
        recommendations_count=recommendations_count,
        processing_time_ms=processing_time_ms,
        operation_type=operation_type,
        results_summary=results_summary or {},
        cache_hit=cache_hit,
    )

    return IntelligenceAdapterEventHelpers.create_analysis_completed_event(
        payload=payload,
        correlation_id=correlation_id,
    )


def create_failed_event(
    operation_type: EnumAnalysisOperationType,
    source_path: str,
    error_message: str,
    error_code: EnumAnalysisErrorCode,
    correlation_id: UUID,
    retry_allowed: bool = True,
    processing_time_ms: float = 0.0,
    error_details: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Convenience function to create CODE_ANALYSIS_FAILED event.

    Args:
        operation_type: Type of analysis that failed
        source_path: File path that failed
        error_message: Human-readable error message
        error_code: Machine-readable error code
        correlation_id: Correlation ID from request
        retry_allowed: Whether retry is allowed
        processing_time_ms: Processing time before failure
        error_details: Optional error details

    Returns:
        Event envelope dictionary ready for publishing
    """
    payload = ModelCodeAnalysisFailedPayload(
        operation_type=operation_type,
        source_path=source_path,
        error_message=error_message,
        error_code=error_code,
        retry_allowed=retry_allowed,
        processing_time_ms=processing_time_ms,
        error_details=error_details or {},
    )

    return IntelligenceAdapterEventHelpers.create_analysis_failed_event(
        payload=payload,
        correlation_id=correlation_id,
    )


__all__ = [
    "EnumAnalysisErrorCode",
    "EnumAnalysisOperationType",
    # Enums
    "EnumCodeAnalysisEventType",
    # Helpers
    "IntelligenceAdapterEventHelpers",
    "ModelCodeAnalysisCompletedPayload",
    "ModelCodeAnalysisFailedPayload",
    # Event Payload Models
    "ModelCodeAnalysisRequestPayload",
    "ModelDiscoveryPayload",
    "ModelInfrastructureScanPayload",
    # Intelligence Payload Models
    "ModelPatternExtractionPayload",
    "ModelSchemaDiscoveryPayload",
    "create_completed_event",
    "create_failed_event",
    # Convenience functions
    "create_request_event",
]
