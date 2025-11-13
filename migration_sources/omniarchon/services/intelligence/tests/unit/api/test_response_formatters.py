"""
Unit tests for API response formatter utilities.

Tests all response formatter functions and models to ensure consistent
response structures across API endpoints.

Coverage:
- success_response: Standard success responses
- paginated_response: Paginated list responses
- analytics_response: Analytics data responses
- health_response: Health check responses
- list_response: List resource responses
- error_response: Error responses
- created_response: Resource creation responses
- updated_response: Resource update responses
- deleted_response: Resource deletion responses
- PaginationParams: Pagination parameter helper
"""

import time
from datetime import datetime, timezone

import pytest
from api.utils.response_formatters import (
    APIResponse,
    ErrorResponse,
    HealthCheckResponse,
    PaginationMetadata,
    PaginationParams,
    SuccessResponse,
    _format_timestamp,
    analytics_response,
    created_response,
    deleted_response,
    error_response,
    health_response,
    list_response,
    paginated_response,
    processing_time_metadata,
    success_response,
    updated_response,
)
from pydantic import ValidationError

# ============================================================================
# Tests for Timestamp Formatting
# ============================================================================


def test_format_timestamp():
    """Test timestamp formatting produces ISO 8601 with Z suffix"""
    timestamp = _format_timestamp()

    # Should be ISO 8601 format
    assert isinstance(timestamp, str)
    assert timestamp.endswith("Z")
    assert "T" in timestamp

    # Should be parseable
    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    assert dt.tzinfo == timezone.utc


# ============================================================================
# Tests for success_response
# ============================================================================


def test_success_response_basic():
    """Test basic success response without metadata"""
    data = {"patterns": [{"id": 1}, {"id": 2}]}
    response = success_response(data)

    assert response["status"] == "success"
    assert response["data"] == data
    assert "timestamp" in response
    assert response["timestamp"].endswith("Z")
    assert "metadata" not in response


def test_success_response_with_metadata():
    """Test success response with metadata"""
    data = {"patterns": []}
    metadata = {"count": 0, "execution_time_ms": 45.3}
    response = success_response(data, metadata)

    assert response["status"] == "success"
    assert response["data"] == data
    assert response["metadata"] == metadata
    assert "timestamp" in response


def test_success_response_with_list_data():
    """Test success response with list as data"""
    data = [{"id": 1}, {"id": 2}, {"id": 3}]
    response = success_response(data)

    assert response["status"] == "success"
    assert response["data"] == data
    assert len(response["data"]) == 3


def test_success_response_with_none_data():
    """Test success response with None data"""
    response = success_response(None)

    assert response["status"] == "success"
    assert response["data"] is None


# ============================================================================
# Tests for paginated_response
# ============================================================================


def test_paginated_response_first_page():
    """Test paginated response for first page"""
    items = [{"id": i} for i in range(20)]
    response = paginated_response(items, total=100, page=1, page_size=20)

    assert response["status"] == "success"
    assert response["data"] == items
    assert response["pagination"]["total"] == 100
    assert response["pagination"]["page"] == 1
    assert response["pagination"]["page_size"] == 20
    assert response["pagination"]["total_pages"] == 5
    assert response["pagination"]["has_next"] is True
    assert response["pagination"]["has_prev"] is False


def test_paginated_response_middle_page():
    """Test paginated response for middle page"""
    items = [{"id": i} for i in range(20)]
    response = paginated_response(items, total=100, page=3, page_size=20)

    assert response["pagination"]["page"] == 3
    assert response["pagination"]["has_next"] is True
    assert response["pagination"]["has_prev"] is True


def test_paginated_response_last_page():
    """Test paginated response for last page"""
    items = [{"id": i} for i in range(20)]
    response = paginated_response(items, total=100, page=5, page_size=20)

    assert response["pagination"]["page"] == 5
    assert response["pagination"]["has_next"] is False
    assert response["pagination"]["has_prev"] is True


def test_paginated_response_partial_page():
    """Test paginated response with partial page"""
    items = [{"id": i} for i in range(7)]
    response = paginated_response(items, total=47, page=3, page_size=20)

    assert response["pagination"]["total"] == 47
    assert response["pagination"]["total_pages"] == 3
    assert len(response["data"]) == 7


def test_paginated_response_empty():
    """Test paginated response with no items"""
    response = paginated_response([], total=0, page=1, page_size=20)

    assert response["data"] == []
    assert response["pagination"]["total"] == 0
    assert response["pagination"]["total_pages"] == 0
    assert response["pagination"]["has_next"] is False
    assert response["pagination"]["has_prev"] is False


def test_paginated_response_with_metadata():
    """Test paginated response with additional metadata"""
    items = [{"id": 1}]
    metadata = {"filters_applied": {"type": "architectural"}}
    response = paginated_response(
        items, total=100, page=1, page_size=20, metadata=metadata
    )

    assert response["metadata"] == metadata
    assert "pagination" in response


# ============================================================================
# Tests for analytics_response
# ============================================================================


def test_analytics_response_basic():
    """Test basic analytics response"""
    data = {"success_rate": 0.95, "avg_score": 0.87}
    response = analytics_response(data)

    assert response["status"] == "success"
    assert response["data"] == data
    assert "computed_at" in response["metadata"]
    assert response["metadata"]["computed_at"].endswith("Z")


def test_analytics_response_with_data_points():
    """Test analytics response with data points"""
    data = {"metrics": []}
    response = analytics_response(data, data_points=100)

    assert response["metadata"]["data_points"] == 100


def test_analytics_response_with_time_range():
    """Test analytics response with time range"""
    data = {"metrics": []}
    time_range = {"start": "2025-10-01T00:00:00Z", "end": "2025-10-16T23:59:59Z"}
    response = analytics_response(data, time_range=time_range)

    assert response["metadata"]["time_range"] == time_range


def test_analytics_response_with_computation_time():
    """Test analytics response with computation time"""
    data = {"metrics": []}
    response = analytics_response(data, computation_time_ms=123.456)

    assert (
        response["metadata"]["computation_time_ms"] == 123.46
    )  # Rounded to 2 decimals


def test_analytics_response_all_parameters():
    """Test analytics response with all parameters"""
    data = {"patterns": []}
    time_range = {"start": "2025-10-01", "end": "2025-10-16"}
    additional = {"confidence": 0.95, "method": "hybrid"}

    response = analytics_response(
        data,
        data_points=250,
        time_range=time_range,
        computation_time_ms=87.3,
        additional_metadata=additional,
    )

    assert response["metadata"]["data_points"] == 250
    assert response["metadata"]["time_range"] == time_range
    assert response["metadata"]["computation_time_ms"] == 87.3
    assert response["metadata"]["confidence"] == 0.95
    assert response["metadata"]["method"] == "hybrid"


# ============================================================================
# Tests for health_response
# ============================================================================


def test_health_response_healthy():
    """Test healthy status response"""
    response = health_response(status="healthy")

    assert response["status"] == "healthy"
    assert response["service"] == "intelligence"
    assert "timestamp" in response


def test_health_response_with_checks():
    """Test health response with component checks"""
    checks = {
        "database": "operational",
        "cache": "operational",
        "external_service": "degraded",
    }
    response = health_response(status="degraded", checks=checks)

    assert response["status"] == "degraded"
    assert response["checks"] == checks


def test_health_response_custom_service():
    """Test health response with custom service name"""
    response = health_response(service="pattern-analytics")

    assert response["service"] == "pattern-analytics"


def test_health_response_unhealthy():
    """Test unhealthy status response"""
    checks = {"database": "error: connection timeout", "cache": "operational"}
    response = health_response(status="unhealthy", checks=checks)

    assert response["status"] == "unhealthy"
    assert "error" in response["checks"]["database"]


# ============================================================================
# Tests for list_response
# ============================================================================


def test_list_response_basic():
    """Test basic list response"""
    items = [{"id": 1}, {"id": 2}]
    response = list_response(items, resource_type="patterns")

    assert response["status"] == "success"
    assert response["data"] == items
    assert response["metadata"]["count"] == 2
    assert response["metadata"]["resource_type"] == "patterns"


def test_list_response_with_filters():
    """Test list response with filters applied"""
    items = [{"id": 1, "type": "architectural"}]
    filters = {"type": "architectural", "min_quality": 0.8}
    response = list_response(items, resource_type="patterns", filters_applied=filters)

    assert response["metadata"]["filters_applied"] == filters


def test_list_response_empty():
    """Test empty list response"""
    response = list_response([], resource_type="patterns")

    assert response["data"] == []
    assert response["metadata"]["count"] == 0


# ============================================================================
# Tests for error_response
# ============================================================================


def test_error_response_basic():
    """Test basic error response"""
    response = error_response("Pattern not found")

    assert response["status"] == "error"
    assert response["error"] == "Pattern not found"
    assert "timestamp" in response


def test_error_response_with_detail():
    """Test error response with detail"""
    response = error_response("Validation failed", detail="Field 'name' is required")

    assert response["error"] == "Validation failed"
    assert response["detail"] == "Field 'name' is required"


def test_error_response_with_error_code():
    """Test error response with error code"""
    response = error_response("Pattern not found", error_code="PATTERN_NOT_FOUND")

    assert response["error_code"] == "PATTERN_NOT_FOUND"


def test_error_response_with_metadata():
    """Test error response with metadata"""
    metadata = {"attempted_id": "abc123", "retry_count": 3}
    response = error_response("Operation failed", metadata=metadata)

    assert response["metadata"] == metadata


# ============================================================================
# Tests for CRUD responses
# ============================================================================


def test_created_response():
    """Test resource creation response"""
    resource = {"id": "abc123", "name": "New Pattern", "type": "architectural"}
    response = created_response(resource, resource_type="pattern", resource_id="abc123")

    assert response["status"] == "success"
    assert response["data"] == resource
    assert response["metadata"]["resource_type"] == "pattern"
    assert response["metadata"]["resource_id"] == "abc123"
    assert response["metadata"]["created"] is True


def test_updated_response():
    """Test resource update response"""
    resource = {"id": "abc123", "name": "Updated Pattern"}
    response = updated_response(
        resource,
        resource_type="pattern",
        resource_id="abc123",
        fields_updated=["name", "description"],
    )

    assert response["status"] == "success"
    assert response["data"] == resource
    assert response["metadata"]["updated"] is True
    assert response["metadata"]["fields_updated"] == ["name", "description"]


def test_updated_response_without_fields():
    """Test resource update response without fields list"""
    resource = {"id": "abc123"}
    response = updated_response(resource, resource_type="pattern", resource_id="abc123")

    assert response["metadata"]["updated"] is True
    assert "fields_updated" not in response["metadata"]


def test_deleted_response():
    """Test resource deletion response"""
    response = deleted_response(resource_type="pattern", resource_id="abc123")

    assert response["status"] == "success"
    assert response["data"]["resource_type"] == "pattern"
    assert response["data"]["resource_id"] == "abc123"
    assert response["data"]["deleted"] is True


# ============================================================================
# Tests for processing_time_metadata
# ============================================================================


def test_processing_time_metadata():
    """Test processing time calculation"""
    start_time = time.time()
    time.sleep(0.01)  # Sleep 10ms
    metadata = processing_time_metadata(start_time)

    assert "processing_time_ms" in metadata
    assert metadata["processing_time_ms"] >= 10.0  # At least 10ms
    assert metadata["processing_time_ms"] < 100.0  # Less than 100ms
    assert isinstance(metadata["processing_time_ms"], float)


# ============================================================================
# Tests for PaginationParams
# ============================================================================


def test_pagination_params_defaults():
    """Test pagination params with defaults"""
    params = PaginationParams()

    assert params.page == 1
    assert params.page_size == 20
    assert params.offset() == 0
    assert params.limit() == 20


def test_pagination_params_custom():
    """Test pagination params with custom values"""
    params = PaginationParams(page=3, page_size=50)

    assert params.page == 3
    assert params.page_size == 50
    assert params.offset() == 100  # (3-1) * 50
    assert params.limit() == 50


def test_pagination_params_calculate_total_pages():
    """Test total pages calculation"""
    params = PaginationParams(page=1, page_size=20)

    assert params.calculate_total_pages(100) == 5
    assert params.calculate_total_pages(101) == 6
    assert params.calculate_total_pages(0) == 0
    assert params.calculate_total_pages(19) == 1


def test_pagination_params_validation():
    """Test pagination params validation"""
    # Valid params
    params = PaginationParams(page=1, page_size=50)
    assert params.page == 1

    # Invalid page (less than 1)
    with pytest.raises(ValidationError):
        PaginationParams(page=0, page_size=20)

    # Invalid page_size (greater than 100)
    with pytest.raises(ValidationError):
        PaginationParams(page=1, page_size=101)

    # Invalid page_size (less than 1)
    with pytest.raises(ValidationError):
        PaginationParams(page=1, page_size=0)


# ============================================================================
# Tests for Pydantic Models
# ============================================================================


def test_api_response_model():
    """Test APIResponse Pydantic model"""
    response = APIResponse(status="success", timestamp="2025-10-16T12:00:00Z")

    assert response.status == "success"
    assert response.timestamp == "2025-10-16T12:00:00Z"


def test_success_response_model():
    """Test SuccessResponse Pydantic model"""
    response = SuccessResponse(
        status="success",
        timestamp="2025-10-16T12:00:00Z",
        data={"patterns": []},
        metadata={"count": 0},
    )

    assert response.status == "success"
    assert response.data == {"patterns": []}
    assert response.metadata == {"count": 0}


def test_pagination_metadata_model():
    """Test PaginationMetadata Pydantic model"""
    metadata = PaginationMetadata(
        total=100, page=1, page_size=20, total_pages=5, has_next=True, has_prev=False
    )

    assert metadata.total == 100
    assert metadata.page == 1
    assert metadata.has_next is True


def test_health_check_response_model():
    """Test HealthCheckResponse Pydantic model"""
    response = HealthCheckResponse(
        status="healthy",
        timestamp="2025-10-16T12:00:00Z",
        service="intelligence",
        checks={"database": "operational"},
    )

    assert response.status == "healthy"
    assert response.checks == {"database": "operational"}


def test_error_response_model():
    """Test ErrorResponse Pydantic model"""
    response = ErrorResponse(
        status="error",
        timestamp="2025-10-16T12:00:00Z",
        error="Pattern not found",
        detail="Pattern ID does not exist",
        error_code="PATTERN_NOT_FOUND",
    )

    assert response.status == "error"
    assert response.error == "Pattern not found"
    assert response.error_code == "PATTERN_NOT_FOUND"


# ============================================================================
# Integration Tests
# ============================================================================


def test_response_consistency():
    """Test that all responses have consistent structure"""
    responses = [
        success_response({"data": "test"}),
        paginated_response([{"id": 1}], 10, 1, 10),
        analytics_response({"metrics": []}),
        health_response(),
        list_response([{"id": 1}], "patterns"),
        error_response("Test error"),
    ]

    # All should have status and timestamp
    for response in responses:
        assert "status" in response
        assert "timestamp" in response
        assert response["timestamp"].endswith("Z")


def test_timestamp_consistency():
    """Test that timestamps are consistent across responses"""
    # Generate multiple responses quickly
    responses = [
        success_response({}),
        paginated_response([], 0, 1, 10),
        analytics_response({}),
    ]

    # All timestamps should be very close (within 1 second)
    timestamps = [
        datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00")) for r in responses
    ]
    time_diffs = [
        (timestamps[i + 1] - timestamps[i]).total_seconds()
        for i in range(len(timestamps) - 1)
    ]

    for diff in time_diffs:
        assert diff < 1.0  # Less than 1 second difference


def test_metadata_merging():
    """Test that metadata merges correctly in analytics response"""
    data = {"test": "data"}
    time_range = {"start": "2025-10-01", "end": "2025-10-16"}
    additional = {"custom_field": "custom_value", "nested": {"key": "value"}}

    response = analytics_response(
        data,
        data_points=100,
        time_range=time_range,
        computation_time_ms=50.5,
        additional_metadata=additional,
    )

    # All metadata should be present
    assert response["metadata"]["data_points"] == 100
    assert response["metadata"]["time_range"] == time_range
    assert response["metadata"]["computation_time_ms"] == 50.5
    assert response["metadata"]["custom_field"] == "custom_value"
    assert response["metadata"]["nested"] == {"key": "value"}


# ============================================================================
# Edge Cases
# ============================================================================


def test_pagination_with_zero_page_size():
    """Test pagination with zero page size (edge case)"""
    response = paginated_response([], total=100, page=1, page_size=0)

    # Should handle gracefully
    assert response["pagination"]["total_pages"] == 0
    assert response["pagination"]["has_next"] is False


def test_large_page_numbers():
    """Test pagination with very large page numbers"""
    response = paginated_response([], total=100, page=999, page_size=20)

    # Should handle gracefully
    assert response["pagination"]["page"] == 999
    assert response["pagination"]["has_next"] is False
    assert response["pagination"]["has_prev"] is True


def test_negative_computation_time():
    """Test analytics with negative computation time (edge case)"""
    response = analytics_response({}, computation_time_ms=-5.0)

    # Should accept and round
    assert response["metadata"]["computation_time_ms"] == -5.0


def test_empty_string_responses():
    """Test responses with empty string values"""
    response = error_response("", detail="")

    assert response["error"] == ""
    assert response["detail"] == ""


def test_none_metadata_values():
    """Test responses with None metadata values"""
    metadata = {"key1": None, "key2": "value"}
    response = success_response({}, metadata=metadata)

    assert response["metadata"]["key1"] is None
    assert response["metadata"]["key2"] == "value"
