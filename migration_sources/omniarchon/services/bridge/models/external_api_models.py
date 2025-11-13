"""
Pydantic models for external API response validation.

This module provides strict validation for all external API responses
to prevent crashes from malformed data. All external API calls should
validate responses through these models before processing.

Security: Prevents injection attacks and crashes from malformed external data.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ============================================================================
# Intelligence Service API Response Models
# ============================================================================


class IntelligenceEntityResponse(BaseModel):
    """
    Validated response model for individual entity from intelligence service.

    Used by: /extract/code, /extract/document endpoints
    Security: Validates all required fields and types before processing
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    entity_id: str = Field(..., min_length=1, description="Unique entity identifier")
    entity_type: str = Field(
        ..., min_length=1, description="Entity type (e.g., 'document', 'code')"
    )
    name: str = Field(..., description="Entity name")
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0"
    )
    properties: Dict[str, Any] = Field(
        default_factory=dict, description="Additional entity properties"
    )

    @field_validator("entity_id", "entity_type", "name")
    @classmethod
    def validate_non_empty_strings(cls, v: str, info) -> str:
        """Ensure critical string fields are not empty or whitespace-only."""
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} cannot be empty or whitespace")
        return v.strip()


class IntelligenceExtractionResponse(BaseModel):
    """
    Validated response for entity extraction endpoints.

    Endpoints: POST /extract/code, POST /extract/document
    Security: Validates array structure and entity consistency
    """

    model_config = ConfigDict(extra="allow")  # Allow additional fields for flexibility

    entities: List[IntelligenceEntityResponse] = Field(
        default_factory=list, description="Extracted entities"
    )
    entities_extracted: Optional[int] = Field(
        None, ge=0, description="Count of entities extracted"
    )
    status: Optional[str] = Field(None, description="Operation status")
    message: Optional[str] = Field(None, description="Status message")

    @field_validator("entities_extracted")
    @classmethod
    def validate_count_consistency(cls, v: Optional[int], info) -> Optional[int]:
        """Validate entity count matches array length if provided."""
        if v is not None and "entities" in info.data:
            entities_list = info.data["entities"]
            if v != len(entities_list):
                raise ValueError(
                    f"entities_extracted ({v}) does not match entities array length ({len(entities_list)})"
                )
        return v


class IntelligenceDocumentProcessingResponse(BaseModel):
    """
    Validated response for document processing endpoint.

    Endpoint: POST /process/document
    Security: Validates comprehensive document processing results
    """

    model_config = ConfigDict(extra="allow")

    entities_extracted: int = Field(
        ..., ge=0, description="Number of entities extracted"
    )
    status: str = Field(..., min_length=1, description="Processing status")
    message: Optional[str] = Field(None, description="Status message")
    document_id: Optional[str] = Field(None, description="Document identifier")
    project_id: Optional[str] = Field(None, description="Project identifier")
    vectorization_status: Optional[str] = Field(
        None, description="Vectorization status"
    )
    error: Optional[str] = Field(None, description="Error message if failed")


class IntelligenceHealthResponse(BaseModel):
    """
    Validated response for intelligence service health check.

    Endpoint: GET /health
    Security: Validates service availability status
    """

    model_config = ConfigDict(extra="allow")

    status: str = Field(
        ..., description="Service status (healthy, degraded, unhealthy)"
    )
    service: Optional[str] = Field(None, description="Service name")
    version: Optional[str] = Field(None, description="Service version")
    uptime_seconds: Optional[float] = Field(None, ge=0.0, description="Service uptime")

    @field_validator("status")
    @classmethod
    def validate_status_value(cls, v: str) -> str:
        """Validate status is one of expected values."""
        valid_statuses = {"healthy", "degraded", "unhealthy", "ok"}
        if v.lower() not in valid_statuses:
            raise ValueError(
                f"Invalid status '{v}'. Must be one of: {', '.join(valid_statuses)}"
            )
        return v.lower()


# ============================================================================
# Supabase/PostgreSQL Response Models
# ============================================================================


class SupabaseQueryResultData(BaseModel):
    """
    Validated wrapper for Supabase query result data.

    Security: Validates result structure before model conversion
    """

    model_config = ConfigDict(extra="allow")

    data: List[Dict[str, Any]] = Field(
        default_factory=list, description="Query result rows"
    )
    count: Optional[int] = Field(None, ge=0, description="Total count if requested")
    error: Optional[Dict[str, Any]] = Field(
        None, description="Error information if query failed"
    )

    @field_validator("count")
    @classmethod
    def validate_count_consistency(cls, v: Optional[int], info) -> Optional[int]:
        """Validate count matches data length if both present."""
        if v is not None and "data" in info.data:
            data_len = len(info.data["data"])
            # Count may be total rows while data is paginated, so only check if equal or count > data
            if v < data_len:
                raise ValueError(
                    f"count ({v}) cannot be less than data length ({data_len})"
                )
        return v


class SupabaseRowData(BaseModel):
    """
    Base validated model for Supabase row data.

    Security: Validates common fields present in all Supabase entities
    """

    model_config = ConfigDict(extra="allow")  # Allow entity-specific fields

    id: Union[str, int] = Field(..., description="Primary key")
    created_at: str = Field(
        ..., description="Creation timestamp (ISO format)"
    )  # Validate as string first
    updated_at: Optional[str] = Field(None, description="Update timestamp (ISO format)")

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_timestamp_format(cls, v: Optional[str], info) -> Optional[str]:
        """Validate timestamp is valid ISO format."""
        if v is None:
            return None
        try:
            # Validate it's parseable (but keep as string for flexibility)
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            return v
        except (ValueError, AttributeError) as e:
            raise ValueError(
                f"Invalid timestamp format for {info.field_name}: {v}. Must be ISO format."
            ) from e


# ============================================================================
# Memgraph/Neo4j Response Models
# ============================================================================


class MemgraphRecordValue(BaseModel):
    """
    Validated model for individual Memgraph/Neo4j record value.

    Security: Validates Cypher query result structure
    """

    model_config = ConfigDict(extra="allow")

    # Memgraph records can contain various types, so we keep this flexible
    # but validate that required fields are present in specific contexts


class MemgraphQueryResult(BaseModel):
    """
    Validated wrapper for Memgraph query results.

    Security: Validates graph query result structure before processing
    """

    model_config = ConfigDict(extra="allow")

    records: List[Dict[str, Any]] = Field(
        default_factory=list, description="Query result records"
    )
    summary: Optional[Dict[str, Any]] = Field(
        None, description="Query execution summary"
    )

    @field_validator("records")
    @classmethod
    def validate_records_structure(
        cls, v: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Validate each record is a dictionary."""
        for idx, record in enumerate(v):
            if not isinstance(record, dict):
                raise ValueError(
                    f"Record at index {idx} must be a dictionary, got {type(record)}"
                )
        return v


class MemgraphSingleRecordResult(BaseModel):
    """
    Validated model for single record results from Memgraph.

    Used for: Entity creation, relationship creation, single node queries
    Security: Validates single-record operations
    """

    model_config = ConfigDict(extra="allow")

    record: Optional[Dict[str, Any]] = Field(
        None, description="Single record result (None if no result)"
    )

    @field_validator("record")
    @classmethod
    def validate_record_structure(
        cls, v: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Validate record is dictionary if present."""
        if v is not None and not isinstance(v, dict):
            raise ValueError(f"Record must be a dictionary, got {type(v)}")
        return v


# ============================================================================
# Validation Error Response Models
# ============================================================================


class ValidationErrorDetail(BaseModel):
    """
    Detailed validation error information.

    Security: Provides structured error information without exposing internals
    """

    field: str = Field(..., description="Field that failed validation")
    error: str = Field(..., description="Error message")
    value: Optional[Any] = Field(
        None, description="Invalid value (redacted if sensitive)"
    )
    error_type: str = Field(..., description="Type of validation error")


class ExternalAPIValidationError(BaseModel):
    """
    Comprehensive external API validation error response.

    Security: Standardized error format for all validation failures
    """

    success: bool = Field(default=False, description="Always False for errors")
    error_type: str = Field(
        ..., description="Type of error (validation, network, timeout)"
    )
    message: str = Field(..., description="Human-readable error message")
    service: str = Field(
        ...,
        description="External service that failed (e.g., 'intelligence', 'supabase')",
    )
    endpoint: Optional[str] = Field(None, description="API endpoint that was called")
    status_code: Optional[int] = Field(
        None, description="HTTP status code if applicable"
    )
    validation_errors: List[ValidationErrorDetail] = Field(
        default_factory=list, description="Detailed validation errors"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Error timestamp"
    )

    @field_validator("error_type")
    @classmethod
    def validate_error_type(cls, v: str) -> str:
        """Validate error type is one of expected values."""
        valid_types = {
            "validation",
            "network",
            "timeout",
            "service_unavailable",
            "malformed_response",
            "authentication",
        }
        if v not in valid_types:
            raise ValueError(
                f"Invalid error_type '{v}'. Must be one of: {', '.join(valid_types)}"
            )
        return v


# ============================================================================
# Utility Functions for Validation
# ============================================================================


def validate_intelligence_response(
    response_data: Dict[str, Any], endpoint: str
) -> Union[
    IntelligenceExtractionResponse,
    IntelligenceDocumentProcessingResponse,
    IntelligenceHealthResponse,
]:
    """
    Validate intelligence service response based on endpoint.

    Args:
        response_data: Raw response dictionary from intelligence service
        endpoint: API endpoint that was called (e.g., '/extract/code')

    Returns:
        Validated Pydantic model instance

    Raises:
        ValueError: If response data fails validation
    """
    try:
        if endpoint in ["/extract/code", "/extract/document"]:
            return IntelligenceExtractionResponse.model_validate(response_data)
        elif endpoint == "/process/document":
            return IntelligenceDocumentProcessingResponse.model_validate(response_data)
        elif endpoint == "/health":
            return IntelligenceHealthResponse.model_validate(response_data)
        else:
            raise ValueError(f"Unknown intelligence service endpoint: {endpoint}")
    except Exception as e:
        raise ValueError(
            f"Intelligence service response validation failed for {endpoint}: {str(e)}"
        ) from e


def validate_supabase_result(
    result_data: Any, expected_fields: Optional[List[str]] = None
) -> SupabaseQueryResultData:
    """
    Validate Supabase query result structure.

    Args:
        result_data: Raw result from Supabase query
        expected_fields: Optional list of expected fields in each row

    Returns:
        Validated SupabaseQueryResultData instance

    Raises:
        ValueError: If result data fails validation
    """
    try:
        # Handle both direct result objects and dictionaries
        if hasattr(result_data, "data"):
            data_dict = {"data": result_data.data}
            if hasattr(result_data, "count"):
                data_dict["count"] = result_data.count
            if hasattr(result_data, "error"):
                data_dict["error"] = result_data.error
        elif isinstance(result_data, dict):
            data_dict = result_data
        else:
            raise ValueError(f"Unexpected result type: {type(result_data)}")

        validated = SupabaseQueryResultData.model_validate(data_dict)

        # Optionally validate expected fields are present
        if expected_fields and validated.data:
            for row in validated.data:
                missing_fields = [f for f in expected_fields if f not in row]
                if missing_fields:
                    raise ValueError(
                        f"Missing expected fields in Supabase result: {missing_fields}"
                    )

        return validated
    except Exception as e:
        raise ValueError(f"Supabase result validation failed: {str(e)}") from e


def validate_memgraph_result(
    records: List[Any], expected_keys: Optional[List[str]] = None
) -> MemgraphQueryResult:
    """
    Validate Memgraph query results.

    Args:
        records: Raw records from Memgraph query
        expected_keys: Optional list of expected keys in each record

    Returns:
        Validated MemgraphQueryResult instance

    Raises:
        ValueError: If result data fails validation
    """
    try:
        # Convert records to dictionaries if needed
        records_dicts = []
        for record in records:
            if isinstance(record, dict):
                records_dicts.append(record)
            elif hasattr(record, "data"):
                # Neo4j Record object
                records_dicts.append(dict(record.data()))
            else:
                raise ValueError(f"Unexpected record type: {type(record)}")

        validated = MemgraphQueryResult(records=records_dicts)

        # Optionally validate expected keys are present
        if expected_keys and validated.records:
            for idx, record in enumerate(validated.records):
                missing_keys = [k for k in expected_keys if k not in record]
                if missing_keys:
                    raise ValueError(
                        f"Missing expected keys in record {idx}: {missing_keys}"
                    )

        return validated
    except Exception as e:
        raise ValueError(f"Memgraph result validation failed: {str(e)}") from e
