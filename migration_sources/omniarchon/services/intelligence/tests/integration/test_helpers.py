#!/usr/bin/env python3
"""
Test helper utilities for integration tests.

Provides reusable utility functions for:
- Response validation
- Timestamp handling
- Pagination assertions
- Test data factories
- Common assertion patterns

Author: Archon Intelligence Team
Date: 2025-10-16
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ============================================================================
# Response Validation Utilities
# ============================================================================


def assert_response_schema(
    response_data: dict, expected_fields: List[str], strict: bool = False
):
    """
    Assert response contains expected fields.

    Args:
        response_data: Response data dictionary to validate
        expected_fields: List of field names that must be present
        strict: If True, fail if extra fields are present (default: False)

    Raises:
        AssertionError: If required fields are missing or extra fields present (strict mode)

    Example:
        assert_response_schema(
            response.json(),
            expected_fields=["quality_score", "compliance_score", "violations"]
        )
    """
    missing_fields = [field for field in expected_fields if field not in response_data]

    assert not missing_fields, f"Missing required fields: {', '.join(missing_fields)}"

    if strict:
        extra_fields = [
            field for field in response_data.keys() if field not in expected_fields
        ]
        assert (
            not extra_fields
        ), f"Unexpected extra fields in strict mode: {', '.join(extra_fields)}"


def assert_response_types(response_data: dict, field_types: Dict[str, type]):
    """
    Assert response fields have correct types.

    Args:
        response_data: Response data dictionary to validate
        field_types: Dict mapping field names to expected types

    Raises:
        AssertionError: If field types don't match expectations

    Example:
        assert_response_types(
            response.json(),
            field_types={
                "quality_score": float,
                "violations": list,
                "timestamp": str
            }
        )
    """
    for field, expected_type in field_types.items():
        if field in response_data:
            actual_type = type(response_data[field])
            assert actual_type == expected_type, (
                f"Field '{field}' has incorrect type: "
                f"expected {expected_type.__name__}, got {actual_type.__name__}"
            )


def assert_response_complete(
    response_data: dict, required_fields: List[str], field_types: Dict[str, type]
):
    """
    Comprehensive response validation (schema + types).

    Combines assert_response_schema and assert_response_types for convenience.

    Example:
        assert_response_complete(
            response.json(),
            required_fields=["status", "data", "timestamp"],
            field_types={"status": str, "data": dict, "timestamp": str}
        )
    """
    assert_response_schema(response_data, required_fields)
    assert_response_types(response_data, field_types)


# ============================================================================
# Timestamp Validation Utilities
# ============================================================================


def assert_timestamp_format(timestamp_str: str):
    """
    Assert timestamp is valid ISO 8601 format.

    Args:
        timestamp_str: Timestamp string to validate

    Raises:
        AssertionError: If timestamp is not valid ISO 8601

    Example:
        assert_timestamp_format("2025-10-16T12:30:45.123456Z")
        assert_timestamp_format("2025-10-16T12:30:45+00:00")
    """
    try:
        # Handle both 'Z' and '+00:00' timezone formats
        cleaned_timestamp = timestamp_str.replace("Z", "+00:00")
        datetime.fromisoformat(cleaned_timestamp)
    except (ValueError, AttributeError) as e:
        raise AssertionError(
            f"Invalid ISO 8601 timestamp format: {timestamp_str}"
        ) from e


def assert_timestamp_recent(timestamp_str: str, max_age_seconds: int = 60):
    """
    Assert timestamp is recent (within max_age_seconds).

    Args:
        timestamp_str: Timestamp string to validate
        max_age_seconds: Maximum age in seconds (default: 60)

    Raises:
        AssertionError: If timestamp is too old

    Example:
        # Assert timestamp is within last minute
        assert_timestamp_recent(response["timestamp"], max_age_seconds=60)
    """
    assert_timestamp_format(timestamp_str)

    cleaned_timestamp = timestamp_str.replace("Z", "+00:00")
    timestamp = datetime.fromisoformat(cleaned_timestamp)
    now = datetime.now(timestamp.tzinfo)

    age_seconds = (now - timestamp).total_seconds()

    assert age_seconds <= max_age_seconds, (
        f"Timestamp too old: {age_seconds:.1f}s ago " f"(max: {max_age_seconds}s)"
    )


# ============================================================================
# Pagination Validation Utilities
# ============================================================================


def assert_pagination(response_data: dict):
    """
    Assert response has valid pagination structure.

    Expected fields:
    - total: Total number of items
    - page: Current page number
    - page_size: Items per page
    - results: Array of results

    Args:
        response_data: Response data with pagination

    Raises:
        AssertionError: If pagination structure is invalid

    Example:
        assert_pagination(response.json())
    """
    required_fields = ["total", "page", "page_size", "results"]
    assert_response_schema(response_data, required_fields)

    # Validate types
    assert isinstance(
        response_data["total"], int
    ), f"total should be int, got {type(response_data['total'])}"
    assert isinstance(
        response_data["page"], int
    ), f"page should be int, got {type(response_data['page'])}"
    assert isinstance(
        response_data["page_size"], int
    ), f"page_size should be int, got {type(response_data['page_size'])}"
    assert isinstance(
        response_data["results"], list
    ), f"results should be list, got {type(response_data['results'])}"

    # Validate values
    assert response_data["total"] >= 0, "total should be non-negative"
    assert response_data["page"] >= 1, "page should be >= 1"
    assert response_data["page_size"] > 0, "page_size should be positive"

    # Validate results length
    expected_max_results = min(
        response_data["page_size"],
        max(
            0,
            response_data["total"]
            - (response_data["page"] - 1) * response_data["page_size"],
        ),
    )
    actual_results = len(response_data["results"])
    assert (
        actual_results <= expected_max_results
    ), f"results length ({actual_results}) exceeds expected max ({expected_max_results})"


def assert_pagination_bounds(
    response_data: dict, expected_page: int, expected_page_size: int
):
    """
    Assert pagination matches expected page and page_size.

    Example:
        assert_pagination_bounds(response.json(), expected_page=2, expected_page_size=50)
    """
    assert_pagination(response_data)
    assert (
        response_data["page"] == expected_page
    ), f"Expected page {expected_page}, got {response_data['page']}"
    assert (
        response_data["page_size"] == expected_page_size
    ), f"Expected page_size {expected_page_size}, got {response_data['page_size']}"


# ============================================================================
# Test Data Factory Functions
# ============================================================================


def create_test_pattern(**overrides) -> Dict[str, Any]:
    """
    Factory function for test pattern data.

    Args:
        **overrides: Override default pattern fields

    Returns:
        Dict with pattern data

    Example:
        pattern = create_test_pattern(
            pattern_id="custom_001",
            success=True,
            confidence_score=0.95
        )
    """
    default = {
        "pattern_id": f"test_pattern_{uuid.uuid4().hex[:8]}",
        "pattern_type": "code_generation",
        "context": {"language": "python", "complexity": "medium"},
        "execution_trace": "test_trace_data",
        "success": True,
        "confidence_score": 0.85,
        "metadata": {"created_at": datetime.now(timezone.utc).isoformat()},
    }
    return {**default, **overrides}


def create_test_quality_snapshot(**overrides) -> Dict[str, Any]:
    """
    Factory function for test quality snapshot data.

    Example:
        snapshot = create_test_quality_snapshot(
            quality_score=0.92,
            violations=[]
        )
    """
    default = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project_id": "test_project",
        "file_path": "src/test.py",
        "quality_score": 0.85,
        "compliance_score": 0.90,
        "violations": [],
        "warnings": [],
        "correlation_id": str(uuid.uuid4()),
    }
    return {**default, **overrides}


def create_test_performance_measurement(**overrides) -> Dict[str, Any]:
    """
    Factory function for test performance measurement data.

    Example:
        measurement = create_test_performance_measurement(
            operation="api_call",
            duration_ms=125.0
        )
    """
    default = {
        "operation": "test_operation",
        "duration_ms": 100.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "success": True,
        "correlation_id": str(uuid.uuid4()),
    }
    return {**default, **overrides}


def create_test_execution_log(**overrides) -> Dict[str, Any]:
    """
    Factory function for test agent execution log data.

    Example:
        log = create_test_execution_log(
            agent_name="test_agent",
            success=True
        )
    """
    default = {
        "execution_id": str(uuid.uuid4()),
        "agent_name": "test_agent",
        "pattern_id": "test_pattern",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_ms": 150.0,
        "success": True,
        "error_message": None,
    }
    return {**default, **overrides}


# ============================================================================
# API Response Utilities
# ============================================================================


def assert_success_response(response_data: dict):
    """
    Assert API response indicates success.

    Checks for common success indicators:
    - status field = "success"
    - OR success field = True
    - OR absence of error field

    Example:
        assert_success_response(response.json())
    """
    has_status_success = (
        "status" in response_data and response_data["status"] == "success"
    )
    has_success_true = "success" in response_data and response_data["success"] is True
    has_no_error = "error" not in response_data

    assert (
        has_status_success or has_success_true or has_no_error
    ), f"Response does not indicate success: {response_data}"


def assert_error_response(
    response_data: dict, expected_error_substring: Optional[str] = None
):
    """
    Assert API response indicates error.

    Args:
        response_data: Response data to validate
        expected_error_substring: Optional substring that should appear in error message

    Example:
        assert_error_response(
            response.json(),
            expected_error_substring="Invalid input"
        )
    """
    has_error = "error" in response_data or (
        "status" in response_data and response_data["status"] == "error"
    )

    assert has_error, f"Response does not indicate error: {response_data}"

    if expected_error_substring:
        error_message = response_data.get("error") or response_data.get("message", "")
        assert expected_error_substring in error_message, (
            f"Expected error substring '{expected_error_substring}' "
            f"not found in: {error_message}"
        )


# ============================================================================
# Score Validation Utilities
# ============================================================================


def assert_score_in_range(score: float, min_score: float = 0.0, max_score: float = 1.0):
    """
    Assert score is within valid range [min_score, max_score].

    Args:
        score: Score value to validate
        min_score: Minimum valid score (default: 0.0)
        max_score: Maximum valid score (default: 1.0)

    Raises:
        AssertionError: If score is out of range

    Example:
        assert_score_in_range(response["quality_score"], 0.0, 1.0)
        assert_score_in_range(response["confidence"], 0.0, 1.0)
    """
    assert isinstance(
        score, (int, float)
    ), f"Score should be numeric, got {type(score)}"
    assert (
        min_score <= score <= max_score
    ), f"Score {score} is out of range [{min_score}, {max_score}]"


def assert_scores_present(response_data: dict, score_fields: List[str]):
    """
    Assert all expected score fields are present and valid.

    Args:
        response_data: Response data to validate
        score_fields: List of score field names

    Example:
        assert_scores_present(
            response.json(),
            score_fields=["quality_score", "compliance_score", "confidence_score"]
        )
    """
    for field in score_fields:
        assert field in response_data, f"Missing score field: {field}"
        assert_score_in_range(response_data[field])


# ============================================================================
# Correlation ID Utilities
# ============================================================================


def assert_correlation_id_valid(correlation_id: str):
    """
    Assert correlation ID is a valid UUID.

    Example:
        assert_correlation_id_valid(response["correlation_id"])
    """
    try:
        uuid.UUID(correlation_id)
    except (ValueError, AttributeError) as e:
        raise AssertionError(f"Invalid correlation ID format: {correlation_id}") from e


def assert_correlation_id_preserved(
    request_correlation_id: str, response_correlation_id: str
):
    """
    Assert correlation ID is preserved from request to response.

    Example:
        assert_correlation_id_preserved(
            request_data["correlation_id"],
            response.json()["correlation_id"]
        )
    """
    assert_correlation_id_valid(request_correlation_id)
    assert_correlation_id_valid(response_correlation_id)
    assert request_correlation_id == response_correlation_id, (
        f"Correlation ID not preserved: "
        f"request={request_correlation_id}, response={response_correlation_id}"
    )


# ============================================================================
# Batch Operation Utilities
# ============================================================================


def assert_batch_results(
    results: List[Any],
    expected_count: int,
    all_success: bool = True,
    check_unique_ids: bool = False,
):
    """
    Assert batch operation results meet expectations.

    Args:
        results: List of result items
        expected_count: Expected number of results
        all_success: If True, assert all results succeeded (default: True)
        check_unique_ids: If True, verify all IDs are unique (default: False)

    Example:
        assert_batch_results(
            response["results"],
            expected_count=100,
            all_success=True,
            check_unique_ids=True
        )
    """
    assert (
        len(results) == expected_count
    ), f"Expected {expected_count} results, got {len(results)}"

    if all_success:
        failed_indices = [
            i for i, result in enumerate(results) if not result.get("success", True)
        ]
        assert (
            not failed_indices
        ), f"Expected all results to succeed, but failed at indices: {failed_indices}"

    if check_unique_ids:
        ids = [result.get("id") or result.get("pattern_id") for result in results]
        unique_ids = set(filter(None, ids))
        assert (
            len(unique_ids) == expected_count
        ), f"Expected {expected_count} unique IDs, got {len(unique_ids)}"
