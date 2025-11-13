"""
Freshness Database Event Contracts - ONEX Compliant Event Schemas

Event schemas for Freshness Database operations via event bus:
- DB_QUERY_REQUESTED: Triggered when database query is requested
- DB_QUERY_COMPLETED: Triggered when query completes successfully
- DB_QUERY_FAILED: Triggered when query fails

ONEX Compliance:
- Model-based naming: ModelDbQuery{Type}Payload
- Strong typing with Pydantic v2
- Event envelope integration with ModelEventEnvelope
- Kafka topic routing following event bus architecture
- Comprehensive validation

Created: 2025-10-22
Purpose: Event-driven PostgreSQL integration for document freshness system
Reference: search_events.py, EVENT_HANDLER_CONTRACTS.md
"""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

# ModelEventEnvelope imported locally in methods to avoid circular import issue
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Import from local event base to avoid circular imports

# Type-only import for type hints


class EnumDbQueryEventType(str, Enum):
    """Event types for database query operations."""

    DB_QUERY_REQUESTED = "DB_QUERY_REQUESTED"
    DB_QUERY_COMPLETED = "DB_QUERY_COMPLETED"
    DB_QUERY_FAILED = "DB_QUERY_FAILED"


class EnumDbFetchMode(str, Enum):
    """Database fetch modes."""

    ALL = "all"  # Fetch all rows
    ONE = "one"  # Fetch single row
    MANY = "many"  # Fetch many rows (with limit)
    EXECUTE = "execute"  # Execute without fetching


class EnumDbQueryErrorCode(str, Enum):
    """Error codes for database query failures."""

    INVALID_QUERY = "INVALID_QUERY"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    TIMEOUT = "TIMEOUT"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    TABLE_NOT_FOUND = "TABLE_NOT_FOUND"
    CONSTRAINT_VIOLATION = "CONSTRAINT_VIOLATION"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# ============================================================================
# Event Payload Models
# ============================================================================


class ModelDbQueryRequestPayload(BaseModel):
    """
    Payload for DB_QUERY_REQUESTED event.

    Captures all parameters needed to execute a database query including
    SQL query, parameters, fetch mode, and configuration options.

    Attributes:
        query: SQL query to execute
        params: Query parameters (for prepared statements)
        fetch_mode: Fetch mode (all, one, many, execute)
        limit: Optional limit for 'many' fetch mode
        timeout_seconds: Optional query timeout in seconds
        table_name: Optional table name for auditing
        operation_type: Optional operation type (SELECT, INSERT, UPDATE, DELETE)
    """

    query: str = Field(
        ...,
        description="SQL query to execute",
        examples=[
            "SELECT * FROM document_freshness WHERE document_id = $1",
            "INSERT INTO document_freshness (document_id, file_path) VALUES ($1, $2)",
        ],
        min_length=1,
    )

    params: Optional[list[Any]] = Field(
        None,
        description="Query parameters for prepared statements",
        examples=[
            ["doc-123"],
            ["doc-456", "/path/to/file.py"],
        ],
    )

    fetch_mode: EnumDbFetchMode = Field(
        default=EnumDbFetchMode.ALL,
        description="Fetch mode for query results",
    )

    limit: Optional[int] = Field(
        None,
        description="Result limit for 'many' fetch mode",
        ge=1,
        le=10000,
    )

    timeout_seconds: Optional[float] = Field(
        None,
        description="Query timeout in seconds",
        ge=0.1,
        le=60.0,
    )

    table_name: Optional[str] = Field(
        None,
        description="Table name for auditing and logging",
        examples=["document_freshness", "freshness_scores_history"],
    )

    operation_type: Optional[str] = Field(
        None,
        description="Operation type (SELECT, INSERT, UPDATE, DELETE)",
        examples=["SELECT", "INSERT", "UPDATE", "DELETE"],
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
                    "query": "SELECT * FROM document_freshness WHERE freshness_level = $1",
                    "params": ["stale"],
                    "fetch_mode": "all",
                    "limit": None,
                    "timeout_seconds": 5.0,
                    "table_name": "document_freshness",
                    "operation_type": "SELECT",
                }
            ]
        },
    )


class ModelDbQueryCompletedPayload(BaseModel):
    """
    Payload for DB_QUERY_COMPLETED event.

    Captures query results including data, row count, and performance metrics.

    Attributes:
        query: Original SQL query executed
        fetch_mode: Fetch mode used
        row_count: Number of rows returned/affected
        data: Query result data (rows as dicts)
        execution_time_ms: Query execution time in milliseconds
        table_name: Table name (if provided)
        operation_type: Operation type (if provided)
    """

    query: str = Field(
        ...,
        description="Original SQL query executed",
    )

    fetch_mode: EnumDbFetchMode = Field(
        ...,
        description="Fetch mode used",
    )

    row_count: int = Field(
        ...,
        description="Number of rows returned or affected",
        ge=0,
    )

    data: Optional[list[dict[str, Any]]] = Field(
        None,
        description="Query result data (rows as dictionaries)",
    )

    execution_time_ms: float = Field(
        ...,
        description="Query execution time in milliseconds",
        ge=0.0,
    )

    table_name: Optional[str] = Field(
        None,
        description="Table name (if provided)",
    )

    operation_type: Optional[str] = Field(
        None,
        description="Operation type (if provided)",
    )

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "query": "SELECT * FROM document_freshness WHERE freshness_level = $1",
                    "fetch_mode": "all",
                    "row_count": 42,
                    "data": [
                        {
                            "document_id": "doc-123",
                            "file_path": "/path/to/file.py",
                            "freshness_score": 0.85,
                        }
                    ],
                    "execution_time_ms": 45.2,
                    "table_name": "document_freshness",
                    "operation_type": "SELECT",
                }
            ]
        },
    )


class ModelDbQueryFailedPayload(BaseModel):
    """
    Payload for DB_QUERY_FAILED event.

    Captures failure information including error details and retry eligibility.

    Attributes:
        query: SQL query that failed
        fetch_mode: Fetch mode attempted
        error_message: Human-readable error description
        error_code: Machine-readable error code
        retry_allowed: Whether the operation can be retried
        retry_count: Number of retries attempted
        execution_time_ms: Time taken before failure
        error_details: Additional error context (stack trace, etc.)
        table_name: Table name (if provided)
        operation_type: Operation type (if provided)
    """

    query: str = Field(
        ...,
        description="SQL query that failed",
    )

    fetch_mode: EnumDbFetchMode = Field(
        ...,
        description="Fetch mode attempted",
    )

    error_message: str = Field(
        ...,
        description="Human-readable error description",
        min_length=1,
    )

    error_code: EnumDbQueryErrorCode = Field(
        ...,
        description="Machine-readable error code",
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

    execution_time_ms: float = Field(
        ...,
        description="Time taken before failure",
        ge=0.0,
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional error context",
    )

    table_name: Optional[str] = Field(
        None,
        description="Table name (if provided)",
    )

    operation_type: Optional[str] = Field(
        None,
        description="Operation type (if provided)",
    )

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "query": "SELECT * FROM nonexistent_table",
                    "fetch_mode": "all",
                    "error_message": "Table 'nonexistent_table' does not exist",
                    "error_code": "TABLE_NOT_FOUND",
                    "retry_allowed": False,
                    "retry_count": 0,
                    "execution_time_ms": 12.3,
                    "error_details": {"exception_type": "UndefinedTableError"},
                    "table_name": "nonexistent_table",
                    "operation_type": "SELECT",
                }
            ]
        },
    )


class DbQueryEventHelpers:
    """
    Helper methods for creating and managing database query events.

    Provides factory methods to create properly-formed event envelopes
    with correct topic routing, correlation tracking, and serialization.
    """

    # Topic routing configuration
    SERVICE_PREFIX = "archon-intelligence"
    DOMAIN = "freshness"
    PATTERN = "event"
    VERSION = "v1"

    @staticmethod
    def create_db_query_requested_event(
        payload: ModelDbQueryRequestPayload,
        correlation_id: Optional[UUID] = None,
        source_instance: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create DB_QUERY_REQUESTED event envelope.

        Args:
            payload: Request payload with query parameters
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
                "event_type": f"omninode.{DbQueryEventHelpers.DOMAIN}.{DbQueryEventHelpers.PATTERN}.db_query_requested.{DbQueryEventHelpers.VERSION}",
                "service": DbQueryEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "freshness-db-1",
                "causation_id": None,
            },
        )

        return envelope.model_dump()

    @staticmethod
    def create_db_query_completed_event(
        payload: ModelDbQueryCompletedPayload,
        correlation_id: UUID,
        causation_id: Optional[UUID] = None,
        source_instance: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create DB_QUERY_COMPLETED event envelope.

        Args:
            payload: Completion payload with query results
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
                "event_type": f"omninode.{DbQueryEventHelpers.DOMAIN}.{DbQueryEventHelpers.PATTERN}.db_query_completed.{DbQueryEventHelpers.VERSION}",
                "service": DbQueryEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "freshness-db-handler-1",
                "causation_id": str(causation_id) if causation_id else None,
            },
        )

        return envelope.model_dump()

    @staticmethod
    def create_db_query_failed_event(
        payload: ModelDbQueryFailedPayload,
        correlation_id: UUID,
        causation_id: Optional[UUID] = None,
        source_instance: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create DB_QUERY_FAILED event envelope.

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
                "event_type": f"omninode.{DbQueryEventHelpers.DOMAIN}.{DbQueryEventHelpers.PATTERN}.db_query_failed.{DbQueryEventHelpers.VERSION}",
                "service": DbQueryEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "freshness-db-handler-1",
                "causation_id": str(causation_id) if causation_id else None,
            },
        )

        return envelope.model_dump()

    @staticmethod
    def get_kafka_topic(
        event_type: EnumDbQueryEventType, environment: str = "development"
    ) -> str:
        """
        Generate Kafka topic name for event type.

        Topic Format: {env}.{service}.{domain}.{event_type}.{version}

        Args:
            event_type: Type of database query event
            environment: Environment (development, staging, production)

        Returns:
            Kafka topic name
        """
        env_prefix = "dev" if environment == "development" else environment
        event_suffix = event_type.value.replace("_", "-").lower()

        return f"{env_prefix}.{DbQueryEventHelpers.SERVICE_PREFIX}.{DbQueryEventHelpers.DOMAIN}.{event_suffix}.{DbQueryEventHelpers.VERSION}"


# ============================================================================
# Convenience Functions
# ============================================================================


def create_query_request_event(
    query: str,
    params: Optional[list[Any]] = None,
    fetch_mode: EnumDbFetchMode = EnumDbFetchMode.ALL,
    limit: Optional[int] = None,
    correlation_id: Optional[UUID] = None,
    table_name: Optional[str] = None,
    operation_type: Optional[str] = None,
) -> dict[str, Any]:
    """
    Convenience function to create DB_QUERY_REQUESTED event.

    Args:
        query: SQL query to execute
        params: Optional query parameters
        fetch_mode: Fetch mode (all, one, many, execute)
        limit: Optional limit for 'many' fetch mode
        correlation_id: Optional correlation ID
        table_name: Optional table name
        operation_type: Optional operation type

    Returns:
        Event envelope dictionary ready for publishing
    """
    payload = ModelDbQueryRequestPayload(
        query=query,
        params=params,
        fetch_mode=fetch_mode,
        limit=limit,
        table_name=table_name,
        operation_type=operation_type,
    )

    return DbQueryEventHelpers.create_db_query_requested_event(
        payload=payload,
        correlation_id=correlation_id,
    )


def create_query_completed_event(
    query: str,
    fetch_mode: EnumDbFetchMode,
    row_count: int,
    execution_time_ms: float,
    correlation_id: UUID,
    data: Optional[list[dict[str, Any]]] = None,
    table_name: Optional[str] = None,
    operation_type: Optional[str] = None,
) -> dict[str, Any]:
    """
    Convenience function to create DB_QUERY_COMPLETED event.

    Args:
        query: Original SQL query
        fetch_mode: Fetch mode used
        row_count: Number of rows returned/affected
        execution_time_ms: Execution time in milliseconds
        correlation_id: Correlation ID from request
        data: Optional query result data
        table_name: Optional table name
        operation_type: Optional operation type

    Returns:
        Event envelope dictionary ready for publishing
    """
    payload = ModelDbQueryCompletedPayload(
        query=query,
        fetch_mode=fetch_mode,
        row_count=row_count,
        data=data,
        execution_time_ms=execution_time_ms,
        table_name=table_name,
        operation_type=operation_type,
    )

    return DbQueryEventHelpers.create_db_query_completed_event(
        payload=payload,
        correlation_id=correlation_id,
    )


def create_query_failed_event(
    query: str,
    fetch_mode: EnumDbFetchMode,
    error_message: str,
    error_code: EnumDbQueryErrorCode,
    correlation_id: UUID,
    retry_allowed: bool = True,
    execution_time_ms: float = 0.0,
    error_details: Optional[dict[str, Any]] = None,
    table_name: Optional[str] = None,
    operation_type: Optional[str] = None,
) -> dict[str, Any]:
    """
    Convenience function to create DB_QUERY_FAILED event.

    Args:
        query: SQL query that failed
        fetch_mode: Fetch mode attempted
        error_message: Human-readable error message
        error_code: Machine-readable error code
        correlation_id: Correlation ID from request
        retry_allowed: Whether retry is allowed
        execution_time_ms: Execution time before failure
        error_details: Optional error details
        table_name: Optional table name
        operation_type: Optional operation type

    Returns:
        Event envelope dictionary ready for publishing
    """
    payload = ModelDbQueryFailedPayload(
        query=query,
        fetch_mode=fetch_mode,
        error_message=error_message,
        error_code=error_code,
        retry_allowed=retry_allowed,
        execution_time_ms=execution_time_ms,
        error_details=error_details or {},
        table_name=table_name,
        operation_type=operation_type,
    )

    return DbQueryEventHelpers.create_db_query_failed_event(
        payload=payload,
        correlation_id=correlation_id,
    )
