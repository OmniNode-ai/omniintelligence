"""
Search Event Contracts - ONEX Compliant Kafka Event Schemas

Event schemas for Search Handler operations:
- SEARCH_REQUESTED: Triggered when search is requested
- SEARCH_COMPLETED: Triggered when search completes successfully
- SEARCH_FAILED: Triggered when search fails

ONEX Compliance:
- Model-based naming: ModelSearch{Type}Payload
- Strong typing with Pydantic v2
- Event envelope integration with ModelEventEnvelope
- Kafka topic routing following event bus architecture
- Serialization/deserialization helpers
- Comprehensive validation

Created: 2025-10-22
Reference: EVENT_HANDLER_CONTRACTS.md, intelligence_adapter_events.py
"""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

# ModelEventEnvelope imported locally in methods to avoid circular import issue
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Import from local event base to avoid circular imports

# Type-only import for type hints


class EnumSearchEventType(str, Enum):
    """Event types for search operations."""

    SEARCH_REQUESTED = "SEARCH_REQUESTED"
    SEARCH_COMPLETED = "SEARCH_COMPLETED"
    SEARCH_FAILED = "SEARCH_FAILED"


class EnumSearchType(str, Enum):
    """Type of search to perform."""

    SEMANTIC = "SEMANTIC"  # RAG-based semantic search
    VECTOR = "VECTOR"  # Pure vector similarity search
    KNOWLEDGE_GRAPH = "KNOWLEDGE_GRAPH"  # Entity/relationship search
    HYBRID = "HYBRID"  # All sources combined with ranking


class EnumSearchErrorCode(str, Enum):
    """Error codes for search failures."""

    INVALID_QUERY = "INVALID_QUERY"
    NO_RESULTS = "NO_RESULTS"
    RAG_SERVICE_ERROR = "RAG_SERVICE_ERROR"
    VECTOR_SERVICE_ERROR = "VECTOR_SERVICE_ERROR"
    KNOWLEDGE_GRAPH_ERROR = "KNOWLEDGE_GRAPH_ERROR"
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# ============================================================================
# Event Payload Models
# ============================================================================


class ModelSearchRequestPayload(BaseModel):
    """
    Payload for SEARCH_REQUESTED event.

    Captures all parameters needed to perform search including
    query, search type, filters, and configuration options.

    Attributes:
        query: Search query text
        search_type: Type of search to perform (SEMANTIC, VECTOR, KNOWLEDGE_GRAPH, HYBRID)
        project_id: Optional project filter
        max_results: Maximum results to return
        filters: Search filters (language, quality_score, etc.)
        quality_weight: Weight for quality-based ranking (0.0-1.0)
        include_context: Include surrounding code context in results
        enable_caching: Whether to use cached results if available
        user_id: Optional user identifier for personalization
    """

    query: str = Field(
        ...,
        description="Search query text",
        examples=["authentication patterns", "async transaction handling"],
        min_length=1,
    )

    search_type: EnumSearchType = Field(
        default=EnumSearchType.HYBRID,
        description="Type of search to perform",
    )

    project_id: Optional[str] = Field(
        None,
        description="Optional project filter",
        examples=["omniarchon", "project-123"],
    )

    max_results: int = Field(
        default=10,
        description="Maximum results to return",
        ge=1,
        le=100,
    )

    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Search filters (language, quality_score, etc.)",
        examples=[
            {
                "language": "python",
                "min_quality_score": 0.7,
                "file_patterns": ["src/**/*.py"],
            }
        ],
    )

    quality_weight: Optional[float] = Field(
        None,
        description="Weight for quality-based ranking (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )

    include_context: bool = Field(
        default=True,
        description="Include surrounding code context in results",
    )

    enable_caching: bool = Field(
        default=True,
        description="Whether to use cached results if available",
    )

    user_id: Optional[str] = Field(
        None,
        description="User identifier for personalization and audit",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Ensure query is not empty or whitespace."""
        if not v or not v.strip():
            raise ValueError("query cannot be empty or whitespace")
        return v.strip()

    model_config = ConfigDict(
        frozen=False,
        json_schema_extra={
            "examples": [
                {
                    "query": "ONEX Effect Node patterns",
                    "search_type": "HYBRID",
                    "project_id": "omniarchon",
                    "max_results": 10,
                    "filters": {
                        "language": "python",
                        "min_quality_score": 0.7,
                    },
                    "quality_weight": 0.3,
                    "include_context": True,
                    "enable_caching": True,
                    "user_id": "system",
                }
            ]
        },
    )


class ModelSearchResultItem(BaseModel):
    """
    Single search result item.

    Attributes:
        source_path: File path of result
        score: Relevance score (0.0-1.0)
        content: Matched content or excerpt
        metadata: Additional metadata (language, quality_score, etc.)
    """

    source_path: str = Field(
        ...,
        description="File path of result",
        examples=["src/api/endpoints.py"],
    )

    score: float = Field(
        ...,
        description="Relevance score (0.0-1.0)",
        ge=0.0,
        le=1.0,
        examples=[0.92, 0.85, 0.78],
    )

    content: str = Field(
        ...,
        description="Matched content or excerpt",
        examples=["class NodeApiEffect(NodeEffect): ..."],
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
        examples=[
            {
                "language": "python",
                "quality_score": 0.87,
                "onex_compliance": 0.92,
                "entity_type": "function",
            }
        ],
    )

    model_config = ConfigDict(frozen=True)


class ModelSearchCompletedPayload(BaseModel):
    """
    Payload for SEARCH_COMPLETED event.

    Captures search results including ranked items, sources queried,
    and performance metrics.

    Attributes:
        query: Original search query
        search_type: Type of search performed
        total_results: Total number of results found
        results: Search results
        sources_queried: Sources queried (rag, vector, knowledge_graph)
        processing_time_ms: Total search time in milliseconds
        service_timings: Breakdown of search time by service
        cache_hit: Whether results were served from cache
        aggregation_strategy: How results were aggregated
    """

    query: str = Field(
        ...,
        description="Original search query",
    )

    search_type: EnumSearchType = Field(
        ...,
        description="Type of search performed",
    )

    total_results: int = Field(
        ...,
        description="Total number of results found",
        ge=0,
    )

    results: list[ModelSearchResultItem] = Field(
        ...,
        description="Search results",
    )

    sources_queried: list[str] = Field(
        ...,
        description="Sources queried (rag, vector, knowledge_graph)",
        examples=[["rag", "vector", "knowledge_graph"]],
    )

    processing_time_ms: float = Field(
        ...,
        description="Total search time in milliseconds",
        ge=0.0,
    )

    service_timings: dict[str, float] = Field(
        default_factory=dict,
        description="Breakdown of search time by service",
        examples=[
            {
                "rag_search_ms": 234.5,
                "vector_search_ms": 123.4,
                "knowledge_graph_ms": 89.3,
                "ranking_ms": 45.2,
            }
        ],
    )

    cache_hit: bool = Field(
        default=False,
        description="Whether results were served from cache",
    )

    aggregation_strategy: Optional[str] = Field(
        None,
        description="How results were aggregated (weighted, ranked, etc.)",
    )

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "query": "ONEX Effect Node patterns",
                    "search_type": "HYBRID",
                    "total_results": 5,
                    "results": [
                        {
                            "source_path": "src/nodes/node_effect.py",
                            "score": 0.92,
                            "content": "class NodeEffect(BaseNode): ...",
                            "metadata": {"language": "python", "quality_score": 0.87},
                        }
                    ],
                    "sources_queried": ["rag", "vector", "knowledge_graph"],
                    "processing_time_ms": 1234.5,
                    "service_timings": {
                        "rag_search_ms": 456.7,
                        "vector_search_ms": 234.5,
                        "knowledge_graph_ms": 345.6,
                        "ranking_ms": 197.7,
                    },
                    "cache_hit": False,
                    "aggregation_strategy": "weighted_score",
                }
            ]
        },
    )


class ModelSearchFailedPayload(BaseModel):
    """
    Payload for SEARCH_FAILED event.

    Captures failure information including error details, partial results,
    and retry eligibility.

    Attributes:
        query: Search query that failed
        search_type: Type of search attempted
        error_message: Human-readable error description
        error_code: Machine-readable error code
        failed_services: Services that failed
        retry_allowed: Whether the operation can be retried
        retry_count: Number of retries attempted
        processing_time_ms: Time taken before failure
        partial_results: Partial results if some services succeeded
        error_details: Additional error context
        suggested_action: Recommended action to resolve the error
    """

    query: str = Field(
        ...,
        description="Search query that failed",
    )

    search_type: EnumSearchType = Field(
        ...,
        description="Type of search attempted",
    )

    error_message: str = Field(
        ...,
        description="Human-readable error description",
        min_length=1,
    )

    error_code: EnumSearchErrorCode = Field(
        ...,
        description="Machine-readable error code",
    )

    failed_services: list[str] = Field(
        default_factory=list,
        description="Services that failed",
        examples=[["rag", "vector"]],
    )

    retry_allowed: bool = Field(
        ...,
        description="Whether the operation can be retried",
    )

    retry_count: int = Field(
        default=0,
        description="Number of retries attempted",
        ge=0,
    )

    processing_time_ms: float = Field(
        ...,
        description="Time taken before failure",
        ge=0.0,
    )

    partial_results: Optional[list[ModelSearchResultItem]] = Field(
        None,
        description="Partial results if some services succeeded",
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional error context",
    )

    suggested_action: Optional[str] = Field(
        None,
        description="Recommended action to resolve the error",
    )

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "query": "invalid search query",
                    "search_type": "HYBRID",
                    "error_message": "All search services failed",
                    "error_code": "INTERNAL_ERROR",
                    "failed_services": ["rag", "vector", "knowledge_graph"],
                    "retry_allowed": True,
                    "retry_count": 0,
                    "processing_time_ms": 567.8,
                    "partial_results": None,
                    "error_details": {"exception_type": "ConnectionError"},
                    "suggested_action": "Verify search services are running",
                }
            ]
        },
    )


class SearchEventHelpers:
    """
    Helper methods for creating and managing Search events.

    Provides factory methods to create properly-formed event envelopes
    with correct topic routing, correlation tracking, and serialization.
    """

    # Topic routing configuration
    SERVICE_PREFIX = "archon-intelligence"
    DOMAIN = "intelligence"
    PATTERN = "event"
    VERSION = "v1"

    @staticmethod
    def create_search_requested_event(
        payload: ModelSearchRequestPayload,
        correlation_id: Optional[UUID] = None,
        source_instance: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create SEARCH_REQUESTED event envelope.

        Args:
            payload: Request payload with search parameters
            correlation_id: Optional correlation ID for tracking
            source_instance: Optional source instance identifier

        Returns:
            Event envelope dictionary ready for Kafka publishing
        """
        correlation_id = correlation_id or uuid4()

        # Local import to avoid circular dependency
        from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

        envelope = ModelEventEnvelope(
            payload=payload if isinstance(payload, dict) else payload.model_dump(),
            correlation_id=correlation_id,
            source_tool="omninode-intelligence",
            metadata={
                "event_type": f"omninode.{SearchEventHelpers.DOMAIN}.{SearchEventHelpers.PATTERN}.search_requested.{SearchEventHelpers.VERSION}",
                "service": SearchEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "search-handler-1",
                "causation_id": None,
            },
        )

        return envelope.model_dump()

    @staticmethod
    def create_search_completed_event(
        payload: ModelSearchCompletedPayload,
        correlation_id: UUID,
        causation_id: Optional[UUID] = None,
        source_instance: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create SEARCH_COMPLETED event envelope.

        Args:
            payload: Completion payload with search results
            correlation_id: Correlation ID from original request
            causation_id: Optional event ID that caused this event
            source_instance: Optional source instance identifier

        Returns:
            Event envelope dictionary ready for Kafka publishing
        """
        # Local import to avoid circular dependency
        from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

        envelope = ModelEventEnvelope(
            payload=payload if isinstance(payload, dict) else payload.model_dump(),
            correlation_id=correlation_id,
            source_tool="omninode-intelligence",
            metadata={
                "event_type": f"omninode.{SearchEventHelpers.DOMAIN}.{SearchEventHelpers.PATTERN}.search_completed.{SearchEventHelpers.VERSION}",
                "service": SearchEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "search-handler-1",
                "causation_id": str(causation_id) if causation_id else None,
            },
        )

        return envelope.model_dump()

    @staticmethod
    def create_search_failed_event(
        payload: ModelSearchFailedPayload,
        correlation_id: UUID,
        causation_id: Optional[UUID] = None,
        source_instance: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create SEARCH_FAILED event envelope.

        Args:
            payload: Failure payload with error details
            correlation_id: Correlation ID from original request
            causation_id: Optional event ID that caused this event
            source_instance: Optional source instance identifier

        Returns:
            Event envelope dictionary ready for Kafka publishing
        """
        # Local import to avoid circular dependency
        from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

        envelope = ModelEventEnvelope(
            payload=payload if isinstance(payload, dict) else payload.model_dump(),
            correlation_id=correlation_id,
            source_tool="omninode-intelligence",
            metadata={
                "event_type": f"omninode.{SearchEventHelpers.DOMAIN}.{SearchEventHelpers.PATTERN}.search_failed.{SearchEventHelpers.VERSION}",
                "service": SearchEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "search-handler-1",
                "causation_id": str(causation_id) if causation_id else None,
            },
        )

        return envelope.model_dump()

    @staticmethod
    def get_kafka_topic(
        event_type: EnumSearchEventType, environment: str = "development"
    ) -> str:
        """
        Generate Kafka topic name for event type.

        Topic Format: {env}.{service}.{domain}.{event_type}.{version}

        Args:
            event_type: Type of search event
            environment: Environment (development, staging, production)

        Returns:
            Kafka topic name
        """
        env_prefix = "dev" if environment == "development" else environment
        event_suffix = event_type.value.replace("_", "-").lower()

        return f"{env_prefix}.{SearchEventHelpers.SERVICE_PREFIX}.{SearchEventHelpers.DOMAIN}.{event_suffix}.{SearchEventHelpers.VERSION}"

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
        if "search_requested" in event_type:
            payload = ModelSearchRequestPayload(**payload_data)
            return (EnumSearchEventType.SEARCH_REQUESTED.value, payload)

        elif "search_completed" in event_type:
            payload = ModelSearchCompletedPayload(**payload_data)
            return (EnumSearchEventType.SEARCH_COMPLETED.value, payload)

        elif "search_failed" in event_type:
            payload = ModelSearchFailedPayload(**payload_data)
            return (EnumSearchEventType.SEARCH_FAILED.value, payload)

        else:
            raise ValueError(f"Unknown event type: {event_type}")


# ============================================================================
# Convenience Functions
# ============================================================================


def create_request_event(
    query: str,
    search_type: EnumSearchType = EnumSearchType.HYBRID,
    project_id: Optional[str] = None,
    max_results: int = 10,
    filters: Optional[dict[str, Any]] = None,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """
    Convenience function to create SEARCH_REQUESTED event.

    Args:
        query: Search query text
        search_type: Type of search to perform
        project_id: Optional project filter
        max_results: Maximum results to return
        filters: Optional search filters
        correlation_id: Optional correlation ID

    Returns:
        Event envelope dictionary ready for publishing
    """
    payload = ModelSearchRequestPayload(
        query=query,
        search_type=search_type,
        project_id=project_id,
        max_results=max_results,
        filters=filters or {},
    )

    return SearchEventHelpers.create_search_requested_event(
        payload=payload,
        correlation_id=correlation_id,
    )


def create_completed_event(
    query: str,
    search_type: EnumSearchType,
    total_results: int,
    results: list[ModelSearchResultItem],
    sources_queried: list[str],
    processing_time_ms: float,
    correlation_id: UUID,
    service_timings: Optional[dict[str, float]] = None,
    cache_hit: bool = False,
    aggregation_strategy: Optional[str] = None,
) -> dict[str, Any]:
    """
    Convenience function to create SEARCH_COMPLETED event.

    Args:
        query: Original search query
        search_type: Type of search performed
        total_results: Total number of results
        results: Search results
        sources_queried: Sources queried
        processing_time_ms: Processing time in milliseconds
        correlation_id: Correlation ID from request
        service_timings: Optional service timings breakdown
        cache_hit: Whether result was cached
        aggregation_strategy: How results were aggregated

    Returns:
        Event envelope dictionary ready for publishing
    """
    payload = ModelSearchCompletedPayload(
        query=query,
        search_type=search_type,
        total_results=total_results,
        results=results,
        sources_queried=sources_queried,
        processing_time_ms=processing_time_ms,
        service_timings=service_timings or {},
        cache_hit=cache_hit,
        aggregation_strategy=aggregation_strategy,
    )

    return SearchEventHelpers.create_search_completed_event(
        payload=payload,
        correlation_id=correlation_id,
    )


def create_failed_event(
    query: str,
    search_type: EnumSearchType,
    error_message: str,
    error_code: EnumSearchErrorCode,
    correlation_id: UUID,
    failed_services: Optional[list[str]] = None,
    retry_allowed: bool = True,
    processing_time_ms: float = 0.0,
    partial_results: Optional[list[ModelSearchResultItem]] = None,
    error_details: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Convenience function to create SEARCH_FAILED event.

    Args:
        query: Search query that failed
        search_type: Type of search attempted
        error_message: Human-readable error message
        error_code: Machine-readable error code
        correlation_id: Correlation ID from request
        failed_services: Services that failed
        retry_allowed: Whether retry is allowed
        processing_time_ms: Processing time before failure
        partial_results: Partial results if available
        error_details: Optional error details

    Returns:
        Event envelope dictionary ready for publishing
    """
    payload = ModelSearchFailedPayload(
        query=query,
        search_type=search_type,
        error_message=error_message,
        error_code=error_code,
        failed_services=failed_services or [],
        retry_allowed=retry_allowed,
        processing_time_ms=processing_time_ms,
        partial_results=partial_results,
        error_details=error_details or {},
    )

    return SearchEventHelpers.create_search_failed_event(
        payload=payload,
        correlation_id=correlation_id,
    )
