"""
Shared response formatting utilities for API endpoints.

Provides consistent response structures for success, error, pagination,
and analytics across all API routers. Reduces code duplication and ensures
standardized response formats throughout the Intelligence service.

Design Principles:
- Type-safe with Pydantic models and explicit type hints
- Consistent timestamp formatting (ISO 8601 with Z suffix)
- Flexible metadata support for domain-specific additions
- Performance-focused with minimal overhead (<1ms per call)

Usage:
    from api.utils.response_formatters import success_response, paginated_response

    @router.get("/items")
async def get_items(
page: int = 1,
    correlation_id: Optional[UUID] = None
):
        items = await fetch_items(page)
        total = await count_items()
        return paginated_response(items, total, page, 20)
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypeVar

from pydantic import BaseModel, Field, field_validator

T = TypeVar("T")


# ============================================================================
# Pydantic Models for Response Structures
# ============================================================================


class APIResponse(BaseModel):
    """Base API response model with status and timestamp"""

    status: str
    timestamp: str


class SuccessResponse(APIResponse):
    """Success response with data and optional metadata"""

    status: str = "success"
    data: Any
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("metadata", mode="before")
    @classmethod
    def validate_metadata(cls, v: Any) -> Optional[Dict[str, Any]]:
        """
        Validate optional metadata field to prevent None access errors.

        Expected schema (when present):
        - metadata: {"count": int, "execution_time_ms": float, ...}
        """
        if v is None:
            return None
        if not isinstance(v, dict):
            raise ValueError(f"metadata must be a dict or None, got {type(v).__name__}")
        return v


class PaginationMetadata(BaseModel):
    """Pagination metadata structure"""

    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether next page exists")
    has_prev: bool = Field(..., description="Whether previous page exists")


class PaginatedResponse(SuccessResponse):
    """Paginated response with pagination metadata"""

    pagination: PaginationMetadata


class HealthCheckResponse(BaseModel):
    """Health check response structure"""

    status: str = Field(..., description="Health status: healthy, degraded, unhealthy")
    timestamp: str
    service: str = Field(default="intelligence", description="Service name")
    checks: Optional[Dict[str, Any]] = Field(None, description="Detailed health checks")

    @field_validator("checks", mode="before")
    @classmethod
    def validate_checks(cls, v: Any) -> Optional[Dict[str, Any]]:
        """
        Validate optional checks field to prevent None access errors.

        Expected schema (when present):
        - checks: {"database": {"status": "healthy", ...}, "cache": {"status": "healthy", ...}, ...}
        """
        if v is None:
            return None
        if not isinstance(v, dict):
            raise ValueError(f"checks must be a dict or None, got {type(v).__name__}")
        return v


class ErrorResponse(APIResponse):
    """Error response structure"""

    status: str = "error"
    error: str
    detail: Optional[str] = None
    error_code: Optional[str] = None


# ============================================================================
# Pagination Helper
# ============================================================================


class PaginationParams(BaseModel):
    """Reusable pagination parameters with validation"""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(
        default=20, ge=1, le=100, description="Items per page (1-100)"
    )

    def offset(self) -> int:
        """Calculate database offset from page number"""
        return (self.page - 1) * self.page_size

    def limit(self) -> int:
        """Get limit for database query"""
        return self.page_size

    def calculate_total_pages(self, total_items: int) -> int:
        """Calculate total pages from total items"""
        if self.page_size == 0:
            return 0
        return (total_items + self.page_size - 1) // self.page_size


# ============================================================================
# Response Formatter Functions
# ============================================================================


def _format_timestamp() -> str:
    """
    Generate ISO 8601 timestamp with Z suffix for UTC.

    Returns:
        ISO 8601 formatted timestamp string

    Example:
        >>> _format_timestamp()
        '2025-10-16T12:00:00Z'
    """
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def success_response(
    data: Any, metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create standardized success response.

    Args:
        data: Response data (can be dict, list, or any JSON-serializable type)
        metadata: Optional metadata (e.g., counts, execution times, flags)

    Returns:
        Formatted success response dictionary

    Example:
        >>> success_response({"patterns": [...]}, {"count": 10})
        {
            "status": "success",
            "data": {"patterns": [...]},
            "metadata": {"count": 10},
            "timestamp": "2025-10-16T12:00:00Z"
        }
    """
    response = {"status": "success", "data": data, "timestamp": _format_timestamp()}

    if metadata:
        response["metadata"] = metadata

    return response


def paginated_response(
    data: List[Any],
    total: int,
    page: int,
    page_size: int,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create standardized paginated response.

    Args:
        data: List of items for current page
        total: Total number of items across all pages
        page: Current page number (1-indexed)
        page_size: Items per page
        metadata: Optional additional metadata

    Returns:
        Formatted paginated response with pagination metadata

    Example:
        >>> paginated_response(items, 100, 1, 20)
        {
            "status": "success",
            "data": [...],
            "pagination": {
                "total": 100,
                "page": 1,
                "page_size": 20,
                "total_pages": 5,
                "has_next": True,
                "has_prev": False
            },
            "timestamp": "2025-10-16T12:00:00Z"
        }
    """
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    response = success_response(data, metadata)
    response["pagination"] = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }

    return response


def analytics_response(
    data: Any,
    data_points: Optional[int] = None,
    time_range: Optional[Dict[str, str]] = None,
    computation_time_ms: Optional[float] = None,
    additional_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create standardized analytics response.

    Args:
        data: Analytics data (metrics, statistics, trends)
        data_points: Number of data points analyzed
        time_range: Time range for analysis ({"start": "...", "end": "..."})
        computation_time_ms: Computation time in milliseconds
        additional_metadata: Additional domain-specific metadata

    Returns:
        Formatted analytics response with computation metadata

    Example:
        >>> analytics_response(
        ...     {"patterns": [...]},
        ...     data_points=100,
        ...     time_range={"start": "2025-10-01", "end": "2025-10-16"},
        ...     computation_time_ms=45.3
        ... )
        {
            "status": "success",
            "data": {"patterns": [...]},
            "metadata": {
                "computed_at": "2025-10-16T12:00:00Z",
                "data_points": 100,
                "time_range": {"start": "2025-10-01", "end": "2025-10-16"},
                "computation_time_ms": 45.3
            },
            "timestamp": "2025-10-16T12:00:00Z"
        }
    """
    metadata = {"computed_at": _format_timestamp()}

    if data_points is not None:
        metadata["data_points"] = data_points

    if time_range:
        metadata["time_range"] = time_range

    if computation_time_ms is not None:
        metadata["computation_time_ms"] = round(computation_time_ms, 2)

    # Merge additional metadata if provided
    if additional_metadata:
        metadata.update(additional_metadata)

    return success_response(data, metadata)


def health_response(
    status: str = "healthy",
    checks: Optional[Dict[str, Any]] = None,
    service: str = "intelligence",
) -> Dict[str, Any]:
    """
    Create standardized health check response.

    Args:
        status: Health status (healthy, degraded, unhealthy)
        checks: Optional detailed health checks by component
        service: Service name (default: "intelligence")

    Returns:
        Formatted health response

    Example:
        >>> health_response(
        ...     status="healthy",
        ...     checks={
        ...         "database": "operational",
        ...         "cache": "operational"
        ...     }
        ... )
        {
            "status": "healthy",
            "timestamp": "2025-10-16T12:00:00Z",
            "service": "intelligence",
            "checks": {
                "database": "operational",
                "cache": "operational"
            }
        }
    """
    response = {"status": status, "timestamp": _format_timestamp(), "service": service}

    if checks:
        response["checks"] = checks

    return response


def list_response(
    items: List[Any],
    resource_type: str,
    filters_applied: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create standardized list response.

    Args:
        items: List of items
        resource_type: Type of resource (patterns, projects, documents, etc.)
        filters_applied: Filters that were applied to the query

    Returns:
        Formatted list response with count metadata

    Example:
        >>> list_response(
        ...     items=[{"id": 1}, {"id": 2}],
        ...     resource_type="patterns",
        ...     filters_applied={"type": "architectural"}
        ... )
        {
            "status": "success",
            "data": [{"id": 1}, {"id": 2}],
            "metadata": {
                "count": 2,
                "resource_type": "patterns",
                "filters_applied": {"type": "architectural"}
            },
            "timestamp": "2025-10-16T12:00:00Z"
        }
    """
    metadata = {"count": len(items), "resource_type": resource_type}

    if filters_applied:
        metadata["filters_applied"] = filters_applied

    return success_response(items, metadata)


def error_response(
    error: str,
    detail: Optional[str] = None,
    error_code: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create standardized error response.

    Args:
        error: Error message
        detail: Optional detailed error description
        error_code: Optional error code for client handling
        metadata: Optional additional error context

    Returns:
        Formatted error response

    Example:
        >>> error_response(
        ...     error="Pattern not found",
        ...     detail="Pattern ID does not exist in database",
        ...     error_code="PATTERN_NOT_FOUND"
        ... )
        {
            "status": "error",
            "error": "Pattern not found",
            "detail": "Pattern ID does not exist in database",
            "error_code": "PATTERN_NOT_FOUND",
            "timestamp": "2025-10-16T12:00:00Z"
        }
    """
    response = {"status": "error", "error": error, "timestamp": _format_timestamp()}

    if detail is not None:
        response["detail"] = detail

    if error_code is not None:
        response["error_code"] = error_code

    if metadata:
        response["metadata"] = metadata

    return response


def processing_time_metadata(start_time: float) -> Dict[str, float]:
    """
    Calculate processing time metadata from start time.

    Args:
        start_time: Start time from time.time()

    Returns:
        Dictionary with processing_time_ms

    Example:
        >>> import time
        >>> start = time.time()
        >>> # ... do work ...
        >>> processing_time_metadata(start)
        {"processing_time_ms": 45.32}
    """
    import time

    processing_time_ms = (time.time() - start_time) * 1000
    return {"processing_time_ms": round(processing_time_ms, 2)}


# ============================================================================
# Common Response Patterns
# ============================================================================


def created_response(
    resource: Any, resource_type: str, resource_id: str
) -> Dict[str, Any]:
    """
    Create standardized 201 Created response.

    Args:
        resource: Created resource data
        resource_type: Type of resource created
        resource_id: Unique identifier of created resource

    Returns:
        Formatted creation response

    Example:
        >>> created_response(
        ...     resource={"id": "abc123", "name": "New Pattern"},
        ...     resource_type="pattern",
        ...     resource_id="abc123"
        ... )
        {
            "status": "success",
            "data": {"id": "abc123", "name": "New Pattern"},
            "metadata": {
                "resource_type": "pattern",
                "resource_id": "abc123",
                "created": True
            },
            "timestamp": "2025-10-16T12:00:00Z"
        }
    """
    return success_response(
        resource,
        metadata={
            "resource_type": resource_type,
            "resource_id": resource_id,
            "created": True,
        },
    )


def updated_response(
    resource: Any,
    resource_type: str,
    resource_id: str,
    fields_updated: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Create standardized update response.

    Args:
        resource: Updated resource data
        resource_type: Type of resource updated
        resource_id: Unique identifier of updated resource
        fields_updated: List of field names that were updated

    Returns:
        Formatted update response

    Example:
        >>> updated_response(
        ...     resource={"id": "abc123", "name": "Updated Pattern"},
        ...     resource_type="pattern",
        ...     resource_id="abc123",
        ...     fields_updated=["name", "description"]
        ... )
        {
            "status": "success",
            "data": {"id": "abc123", "name": "Updated Pattern"},
            "metadata": {
                "resource_type": "pattern",
                "resource_id": "abc123",
                "updated": True,
                "fields_updated": ["name", "description"]
            },
            "timestamp": "2025-10-16T12:00:00Z"
        }
    """
    metadata = {
        "resource_type": resource_type,
        "resource_id": resource_id,
        "updated": True,
    }

    if fields_updated:
        metadata["fields_updated"] = fields_updated

    return success_response(resource, metadata)


def deleted_response(resource_type: str, resource_id: str) -> Dict[str, Any]:
    """
    Create standardized deletion response.

    Args:
        resource_type: Type of resource deleted
        resource_id: Unique identifier of deleted resource

    Returns:
        Formatted deletion response

    Example:
        >>> deleted_response("pattern", "abc123")
        {
            "status": "success",
            "data": {
                "resource_type": "pattern",
                "resource_id": "abc123",
                "deleted": True
            },
            "timestamp": "2025-10-16T12:00:00Z"
        }
    """
    return success_response(
        {"resource_type": resource_type, "resource_id": resource_id, "deleted": True}
    )
