"""
Intelligence Operation Output Model.

Domain output model for Intelligence Adapter Effect Node operations.
Provides structured responses for all intelligence service operations including
quality assessment, ONEX compliance validation, pattern detection, and optimization.

This model follows ONEX patterns from omninode_bridge database adapter outputs
and ensures consistent response structure across all intelligence operations.

Created: 2025-10-21
Reference: omninode_bridge/nodes/database_adapter_effect/v1_0_0/models/outputs/
"""

from datetime import UTC, datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelPatternDetection(BaseModel):
    """
    Detected pattern structure for intelligence operations.

    Attributes:
        pattern_type: Type/category of detected pattern
        pattern_name: Human-readable pattern name
        confidence: Pattern detection confidence (0.0-1.0)
        description: Pattern description and context
        location: Source location (file path, line numbers, etc.)
        severity: Pattern severity (info, warning, error, critical)
        recommendation: Suggested action or improvement
    """

    pattern_type: str = Field(
        ...,
        description="Pattern category (architectural, quality, security, etc.)",
        examples=["architectural", "quality", "security", "performance"],
    )

    pattern_name: str = Field(
        ...,
        description="Human-readable pattern name",
        examples=["ONEX_EFFECT_NODE", "ANTI_PATTERN_GOD_CLASS", "SQL_INJECTION"],
    )

    confidence: float = Field(
        ...,
        description="Pattern detection confidence score",
        ge=0.0,
        le=1.0,
    )

    description: str = Field(
        ...,
        description="Pattern description and context",
    )

    location: Optional[str] = Field(
        None,
        description="Source location (file:line or function name)",
    )

    severity: Literal["info", "warning", "error", "critical"] = Field(
        default="info",
        description="Pattern severity level",
    )

    recommendation: Optional[str] = Field(
        None,
        description="Suggested action or improvement",
    )


class ModelIntelligenceMetrics(BaseModel):
    """
    Detailed execution metrics for intelligence operations.

    Tracks service orchestration timing, cache performance, and
    resource utilization during intelligence gathering.

    Attributes:
        rag_service_ms: Time spent in RAG service calls
        vector_service_ms: Time spent in vector search (Qdrant)
        knowledge_service_ms: Time spent in knowledge graph (Memgraph)
        cache_hit: Whether result was served from cache
        cache_key: Cache key used (if applicable)
        services_invoked: List of backend services called
        total_api_calls: Total number of API calls made
    """

    rag_service_ms: Optional[int] = Field(
        None,
        description="RAG service execution time in milliseconds",
        ge=0,
    )

    vector_service_ms: Optional[int] = Field(
        None,
        description="Vector search execution time in milliseconds",
        ge=0,
    )

    knowledge_service_ms: Optional[int] = Field(
        None,
        description="Knowledge graph execution time in milliseconds",
        ge=0,
    )

    cache_hit: bool = Field(
        default=False,
        description="Whether response was served from cache",
    )

    cache_key: Optional[str] = Field(
        None,
        description="Cache key used for this operation",
    )

    services_invoked: list[str] = Field(
        default_factory=list,
        description="List of backend services called",
        examples=[["intelligence", "search", "qdrant"]],
    )

    total_api_calls: int = Field(
        default=0,
        description="Total number of backend API calls",
        ge=0,
    )


class ModelIntelligenceOutput(BaseModel):
    """
    Output from Intelligence Adapter Effect Node operations.

    This model is returned by all intelligence operation handlers and provides
    consistent structure for success/failure reporting, execution metrics,
    ONEX compliance scoring, and intelligent recommendations.

    ONEX Compliance:
        - Follows SUFFIX-based naming (ModelIntelligenceOutput)
        - Uses structured Field() descriptions
        - Includes comprehensive examples
        - Preserves UUID types for strong typing
        - Supports serialization via to_dict()

    Response Pattern:
        Intelligence operations execute in this flow:
        1. Validate input and prepare request
        2. Orchestrate parallel service calls (RAG, Vector, Knowledge)
        3. Check distributed cache (Valkey) for cached results
        4. Analyze and synthesize intelligence from multiple sources
        5. Calculate quality scores and ONEX compliance
        6. Return structured output with metrics and recommendations

    Attributes:
        success: Whether the intelligence operation completed successfully
        operation_type: Type of intelligence operation performed
        correlation_id: UUID preserved from input for end-to-end tracking
        processing_time_ms: Total processing time in milliseconds
        quality_score: Overall quality assessment (0.0-1.0, None if not applicable)
        onex_compliance: ONEX architectural compliance score (0.0-1.0, None if N/A)
        complexity_score: Code complexity score (0.0-1.0, None if N/A)
        issues: List of detected issues requiring attention
        recommendations: List of improvement recommendations
        patterns: Detected patterns (architectural, quality, security, etc.)
        result_data: Operation-specific result data
        metrics: Detailed execution metrics (service timing, cache stats)
        error_code: Machine-readable error code (None on success)
        error_message: Human-readable error description (None on success)
        retry_allowed: Whether operation can be safely retried
        timestamp: Operation completion timestamp (UTC)
        metadata: Additional extensible metadata

    Usage Examples:
        >>> # Success response from quality assessment
        >>> output = ModelIntelligenceOutput(
        ...     success=True,
        ...     operation_type="assess_code_quality",
        ...     correlation_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        ...     processing_time_ms=1234,
        ...     quality_score=0.87,
        ...     onex_compliance=0.92,
        ...     complexity_score=0.65,
        ...     issues=["Missing docstring in function 'process_data'"],
        ...     recommendations=[
        ...         "Add type hints to improve maintainability",
        ...         "Consider extracting complex logic into separate functions"
        ...     ],
        ...     patterns=[
        ...         ModelPatternDetection(
        ...             pattern_type="architectural",
        ...             pattern_name="ONEX_EFFECT_NODE",
        ...             confidence=0.95,
        ...             description="Proper Effect node implementation detected",
        ...             severity="info"
        ...         )
        ...     ],
        ... )
        >>> assert output.success is True
        >>> assert 0.0 <= output.quality_score <= 1.0

        >>> # Error response with retry capability
        >>> error_output = ModelIntelligenceOutput(
        ...     success=False,
        ...     operation_type="assess_code_quality",
        ...     correlation_id=UUID("550e8400-e29b-41d4-a716-446655440001"),
        ...     processing_time_ms=150,
        ...     error_code="INTELLIGENCE_SERVICE_TIMEOUT",
        ...     error_message="Intelligence service did not respond within 10s timeout",
        ...     retry_allowed=True,
        ... )
        >>> assert error_output.retry_allowed is True

        >>> # Serialization to dict
        >>> result_dict = output.to_dict()
        >>> assert "correlation_id" in result_dict
        >>> assert isinstance(result_dict["correlation_id"], str)
    """

    model_config = ConfigDict(
        # Allow arbitrary types (for UUID, datetime)
        arbitrary_types_allowed=True,
        # JSON schema examples for documentation and testing
        json_schema_extra={
            "examples": [
                {
                    "success": True,
                    "operation_type": "assess_code_quality",
                    "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
                    "processing_time_ms": 1234,
                    "quality_score": 0.87,
                    "onex_compliance": 0.92,
                    "complexity_score": 0.65,
                    "issues": [
                        "Missing docstring in function 'process_data'",
                        "Function 'calculate' exceeds complexity threshold (15 > 10)",
                    ],
                    "recommendations": [
                        "Add comprehensive docstrings to all public functions",
                        "Consider extracting complex logic into smaller functions",
                        "Add type hints to improve IDE support and maintainability",
                    ],
                    "patterns": [
                        {
                            "pattern_type": "architectural",
                            "pattern_name": "ONEX_EFFECT_NODE",
                            "confidence": 0.95,
                            "description": "Proper Effect node implementation with execute_effect method",
                            "location": "src/nodes/effect/node_api_effect.py:42",
                            "severity": "info",
                            "recommendation": None,
                        },
                        {
                            "pattern_type": "quality",
                            "pattern_name": "ANTI_PATTERN_GOD_CLASS",
                            "confidence": 0.78,
                            "description": "Class has too many responsibilities (12 methods)",
                            "location": "src/service/orchestrator.py:15",
                            "severity": "warning",
                            "recommendation": "Consider splitting into smaller, focused classes",
                        },
                    ],
                    "result_data": {
                        "lines_of_code": 250,
                        "functions_analyzed": 18,
                        "classes_analyzed": 3,
                    },
                    "metrics": {
                        "rag_service_ms": 300,
                        "vector_service_ms": 250,
                        "knowledge_service_ms": 450,
                        "cache_hit": False,
                        "cache_key": "quality:assess:abc123",
                        "services_invoked": ["intelligence", "search", "qdrant"],
                        "total_api_calls": 3,
                    },
                    "error_code": None,
                    "error_message": None,
                    "retry_allowed": False,
                    "timestamp": "2025-10-21T10:00:00.000Z",
                    "metadata": {
                        "language": "python",
                        "file_path": "src/api/endpoints.py",
                        "onex_version": "1.0.0",
                    },
                },
                {
                    "success": False,
                    "operation_type": "assess_code_quality",
                    "correlation_id": "550e8400-e29b-41d4-a716-446655440001",
                    "processing_time_ms": 150,
                    "quality_score": None,
                    "onex_compliance": None,
                    "complexity_score": None,
                    "issues": [],
                    "recommendations": [],
                    "patterns": None,
                    "result_data": None,
                    "metrics": {
                        "cache_hit": False,
                        "services_invoked": ["intelligence"],
                        "total_api_calls": 1,
                    },
                    "error_code": "INTELLIGENCE_SERVICE_TIMEOUT",
                    "error_message": "Intelligence service did not respond within 10s timeout",
                    "retry_allowed": True,
                    "timestamp": "2025-10-21T10:00:05.000Z",
                    "metadata": {
                        "service": "intelligence",
                        "timeout_ms": 10000,
                        "attempt": 1,
                    },
                },
                {
                    "success": True,
                    "operation_type": "perform_rag_query",
                    "correlation_id": "550e8400-e29b-41d4-a716-446655440002",
                    "processing_time_ms": 856,
                    "quality_score": None,
                    "onex_compliance": None,
                    "complexity_score": None,
                    "issues": [],
                    "recommendations": [
                        "Consider using vector search for better semantic matching",
                        "Related patterns found in 3 other projects",
                    ],
                    "patterns": None,
                    "result_data": {
                        "query": "ONEX Effect node patterns",
                        "total_results": 42,
                        "top_confidence": 0.94,
                        "sources": ["rag_service", "vector_search", "knowledge_graph"],
                    },
                    "metrics": {
                        "rag_service_ms": 300,
                        "vector_service_ms": 250,
                        "knowledge_service_ms": 450,
                        "cache_hit": True,
                        "cache_key": "research:rag:onex_effect_patterns",
                        "services_invoked": ["cache"],
                        "total_api_calls": 1,
                    },
                    "error_code": None,
                    "error_message": None,
                    "retry_allowed": False,
                    "timestamp": "2025-10-21T10:01:00.000Z",
                    "metadata": {
                        "cache_ttl_seconds": 300,
                        "warm_cache": True,
                    },
                },
            ]
        },
    )

    # Core response fields
    success: bool = Field(
        ...,
        description="Operation success status",
    )

    operation_type: str = Field(
        ...,
        description="Type of intelligence operation performed",
        examples=[
            "assess_code_quality",
            "check_architectural_compliance",
            "identify_optimization_opportunities",
            "analyze_document_freshness",
            "perform_rag_query",
        ],
    )

    correlation_id: UUID = Field(
        ...,
        description="Request correlation ID preserved from input for end-to-end tracking",
    )

    processing_time_ms: int = Field(
        ...,
        description="Total processing time in milliseconds",
        ge=0,
    )

    # Intelligence-specific scoring fields
    quality_score: Optional[float] = Field(
        default=None,
        description="Overall quality assessment score (0.0=poor, 1.0=excellent)",
        ge=0.0,
        le=1.0,
    )

    onex_compliance: Optional[float] = Field(
        default=None,
        description="ONEX architectural compliance score (0.0=non-compliant, 1.0=fully compliant)",
        ge=0.0,
        le=1.0,
    )

    complexity_score: Optional[float] = Field(
        default=None,
        description="Code complexity score (0.0=simple, 1.0=highly complex)",
        ge=0.0,
        le=1.0,
    )

    # Analysis results
    issues: list[str] = Field(
        default_factory=list,
        description="List of detected issues requiring attention",
    )

    recommendations: list[str] = Field(
        default_factory=list,
        description="List of actionable improvement recommendations",
    )

    patterns: Optional[list[ModelPatternDetection]] = Field(
        default=None,
        description="Detected patterns (architectural, quality, security, performance)",
    )

    # Operation-specific data
    result_data: Optional[dict[str, Any]] = Field(
        default=None,
        description="Operation-specific result data (structure varies by operation)",
    )

    # Execution metrics
    metrics: Optional[ModelIntelligenceMetrics] = Field(
        default=None,
        description="Detailed execution metrics for performance tracking",
    )

    # Error handling
    error_code: Optional[str] = Field(
        default=None,
        description="Machine-readable error code (None on success)",
        examples=[
            "INTELLIGENCE_SERVICE_TIMEOUT",
            "INVALID_INPUT_SYNTAX",
            "ONEX_COMPLIANCE_FAILED",
            "CACHE_CONNECTION_ERROR",
        ],
    )

    error_message: Optional[str] = Field(
        default=None,
        description="Human-readable error description (None on success)",
    )

    retry_allowed: bool = Field(
        default=False,
        description="Whether this operation can be safely retried",
    )

    # Audit trail
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Operation completion timestamp (UTC, ISO 8601)",
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional extensible metadata for domain-specific requirements",
    )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert output model to dictionary with JSON-serializable types.

        Converts UUIDs to strings and datetime to ISO 8601 format for
        API responses, event payloads, and logging.

        Returns:
            Dictionary with all fields, UUIDs as strings, datetime as ISO 8601

        Example:
            >>> output = ModelIntelligenceOutput(
            ...     success=True,
            ...     operation_type="assess_code_quality",
            ...     correlation_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            ...     processing_time_ms=1234,
            ...     quality_score=0.87,
            ... )
            >>> result = output.to_dict()
            >>> assert result["correlation_id"] == "550e8400-e29b-41d4-a716-446655440000"
            >>> assert result["quality_score"] == 0.87
        """
        return {
            "success": self.success,
            "operation_type": self.operation_type,
            "correlation_id": str(self.correlation_id),
            "processing_time_ms": self.processing_time_ms,
            "quality_score": self.quality_score,
            "onex_compliance": self.onex_compliance,
            "complexity_score": self.complexity_score,
            "issues": self.issues,
            "recommendations": self.recommendations,
            "patterns": (
                [p.model_dump() for p in self.patterns] if self.patterns else None
            ),
            "result_data": self.result_data,
            "metrics": self.metrics.model_dump() if self.metrics else None,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "retry_allowed": self.retry_allowed,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_api_response(
        cls,
        api_response: dict[str, Any],
        operation_type: str,
        correlation_id: UUID,
        processing_time_ms: int,
    ) -> "ModelIntelligenceOutput":
        """
        Create output model from Intelligence Service API response.

        Transforms raw API responses from intelligence service endpoints
        into strongly-typed ModelIntelligenceOutput instances.

        Args:
            api_response: Raw API response dictionary
            operation_type: Intelligence operation type
            correlation_id: Request correlation ID (preserved from input)
            processing_time_ms: Total processing time

        Returns:
            ModelIntelligenceOutput instance with parsed response data

        Example:
            >>> api_response = {
            ...     "quality_score": 0.87,
            ...     "onex_compliance": 0.92,
            ...     "issues": ["Missing docstrings"],
            ...     "recommendations": ["Add type hints"],
            ...     "patterns": [
            ...         {
            ...             "pattern_type": "architectural",
            ...             "pattern_name": "ONEX_EFFECT_NODE",
            ...             "confidence": 0.95,
            ...             "description": "Proper Effect node detected",
            ...             "severity": "info"
            ...         }
            ...     ]
            ... }
            >>> output = ModelIntelligenceOutput.from_api_response(
            ...     api_response=api_response,
            ...     operation_type="assess_code_quality",
            ...     correlation_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            ...     processing_time_ms=1234,
            ... )
            >>> assert output.success is True
            >>> assert output.quality_score == 0.87
        """
        # Parse patterns if present
        patterns = None
        if api_response.get("patterns"):
            patterns = [
                ModelPatternDetection(**pattern) for pattern in api_response["patterns"]
            ]

        # Parse metrics if present
        metrics = None
        if api_response.get("metrics"):
            metrics = ModelIntelligenceMetrics(**api_response["metrics"])

        return cls(
            success=api_response.get("success", False),
            operation_type=operation_type,
            correlation_id=correlation_id,
            processing_time_ms=processing_time_ms,
            quality_score=api_response.get("quality_score"),
            onex_compliance=api_response.get("onex_compliance"),
            complexity_score=api_response.get("complexity_score"),
            issues=api_response.get("issues", []),
            recommendations=api_response.get("recommendations", []),
            patterns=patterns,
            result_data=api_response.get("result_data"),
            metrics=metrics,
            error_code=api_response.get("error_code"),
            error_message=api_response.get("error_message"),
            retry_allowed=api_response.get("retry_allowed", False),
            metadata=api_response.get("metadata", {}),
        )

    @classmethod
    def create_error(
        cls,
        operation_type: str,
        correlation_id: UUID,
        processing_time_ms: int,
        error_code: str,
        error_message: str,
        retry_allowed: bool = False,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "ModelIntelligenceOutput":
        """
        Create error response output.

        Convenience method for creating error responses with consistent
        structure across all intelligence operations.

        Args:
            operation_type: Intelligence operation that failed
            correlation_id: Request correlation ID
            processing_time_ms: Time until failure
            error_code: Machine-readable error code
            error_message: Human-readable error description
            retry_allowed: Whether operation can be retried
            metadata: Additional error context

        Returns:
            ModelIntelligenceOutput instance representing failure

        Example:
            >>> error = ModelIntelligenceOutput.create_error(
            ...     operation_type="assess_code_quality",
            ...     correlation_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            ...     processing_time_ms=150,
            ...     error_code="INTELLIGENCE_SERVICE_TIMEOUT",
            ...     error_message="Service did not respond within 10s",
            ...     retry_allowed=True,
            ...     metadata={"service": "intelligence", "timeout_ms": 10000},
            ... )
            >>> assert error.success is False
            >>> assert error.retry_allowed is True
        """
        return cls(
            success=False,
            operation_type=operation_type,
            correlation_id=correlation_id,
            processing_time_ms=processing_time_ms,
            error_code=error_code,
            error_message=error_message,
            retry_allowed=retry_allowed,
            metadata=metadata or {},
        )
