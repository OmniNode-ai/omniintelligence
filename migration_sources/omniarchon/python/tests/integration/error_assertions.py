"""
Reusable Error Assertion Helpers for Integration Tests

Provides comprehensive validation utilities for error events, API error responses,
and failure scenarios across all integration tests.

Error Schema Expectations:
-------------------------

1. Event Envelope Error (ModelEventEnvelope with error payload):
   - event_id: UUID (required)
   - event_type: string matching pattern (required)
   - correlation_id: UUID (required)
   - causation_id: Optional UUID
   - timestamp: datetime UTC (required)
   - version: semantic version string (required)
   - source: ModelEventSource (required)
   - metadata: Optional ModelEventMetadata
   - payload: Error payload with:
     * status: "FAILED" (required for error events)
     * error_code: string from CoreErrorCode enum (required)
     * error_message: descriptive string (required)
     * stack_trace: Optional string (for exceptions)
     * error_context: Optional dict (additional metadata)

2. API Error Response (HTTP errors):
   - status_code: HTTP status code (4xx or 5xx)
   - detail: Error message or dict with:
     * error: string message
     * error_code: Optional error code
     * suggestion: Optional suggestion
   - For structured errors:
     * success: false
     * error: dict with type, message, details, suggestion

3. Service Error (Exception-based):
   - exception_type: Exception class name
   - exception_message: str(exception)
   - error_code: Optional CoreErrorCode
   - details: Optional dict with context

Usage:
------
    from tests.integration.error_assertions import ErrorAssertions

    # Validate event envelope error
    ErrorAssertions.assert_error_event(
        event,
        expected_status="FAILED",
        expected_error_code="VALIDATION_ERROR",
        should_have_stack_trace=True
    )

    # Validate API error response
    ErrorAssertions.assert_api_error_response(
        response,
        expected_status_code=500,
        expected_error_message_contains="Database connection failed"
    )

    # Validate exception handling
    ErrorAssertions.assert_exception_handling(
        exception,
        expected_exception_type=ValueError,
        expected_message_contains="Invalid input"
    )
"""

import re
import traceback
from datetime import datetime
from typing import Any, Optional, Type, Union
from uuid import UUID

import pytest


class ErrorAssertions:
    """Comprehensive error validation utilities for integration tests."""

    # Valid error codes from CoreErrorCode enum
    VALID_ERROR_CODES = {
        "AUTHENTICATION_FAILED",
        "AUTHORIZATION_FAILED",
        "VALIDATION_ERROR",
        "INTERNAL_ERROR",
        "SERVICE_UNAVAILABLE",
        "INVALID_REQUEST",
        "RESOURCE_NOT_FOUND",
        "RATE_LIMIT_EXCEEDED",
    }

    # Valid status values for failure scenarios
    VALID_FAILURE_STATUSES = {"FAILED", "failed", "ERROR", "error"}

    # HTTP error status codes
    CLIENT_ERROR_CODES = range(400, 500)
    SERVER_ERROR_CODES = range(500, 600)

    @staticmethod
    def assert_error_event(
        event: dict[str, Any],
        expected_status: str = "FAILED",
        expected_error_code: Optional[str] = None,
        expected_error_message_contains: Optional[str] = None,
        should_have_stack_trace: bool = False,
        should_have_error_context: bool = False,
        validate_envelope_structure: bool = True,
    ) -> None:
        """
        Validate error event structure and content.

        Ensures error events follow ModelEventEnvelope pattern with proper
        error payload fields.

        Args:
            event: Event dictionary to validate
            expected_status: Expected status value (default: "FAILED")
            expected_error_code: Expected error code from CoreErrorCode enum
            expected_error_message_contains: Substring expected in error message
            should_have_stack_trace: Whether stack_trace field should be present
            should_have_error_context: Whether error_context field should be present
            validate_envelope_structure: Whether to validate full envelope structure

        Raises:
            AssertionError: If validation fails with descriptive message
        """
        assert event is not None, "Event should not be None"
        assert isinstance(event, dict), f"Event should be dict, got {type(event)}"

        # Validate envelope structure if requested
        if validate_envelope_structure:
            ErrorAssertions._validate_event_envelope_structure(event)

        # Extract payload (handle both nested and flat structures)
        payload = event.get("payload", event)
        assert payload is not None, "Event payload should not be None"

        # Validate status field
        status = payload.get("status")
        assert status is not None, "Error event must have 'status' field in payload"
        assert (
            status == expected_status
            or status in ErrorAssertions.VALID_FAILURE_STATUSES
        ), f"Expected status '{expected_status}', got '{status}'"

        # Validate error_code field
        error_code = payload.get("error_code")
        assert (
            error_code is not None
        ), "Error event must have 'error_code' field in payload"
        assert isinstance(
            error_code, str
        ), f"error_code should be string, got {type(error_code)}"

        if expected_error_code:
            assert (
                error_code == expected_error_code
            ), f"Expected error_code '{expected_error_code}', got '{error_code}'"
        else:
            # Validate it's a known error code
            assert (
                error_code in ErrorAssertions.VALID_ERROR_CODES
            ), f"Unknown error_code '{error_code}', valid codes: {ErrorAssertions.VALID_ERROR_CODES}"

        # Validate error_message field
        error_message = payload.get("error_message")
        assert (
            error_message is not None
        ), "Error event must have 'error_message' field in payload"
        assert isinstance(
            error_message, str
        ), f"error_message should be string, got {type(error_message)}"
        assert len(error_message) > 0, "error_message should not be empty"

        if expected_error_message_contains:
            assert (
                expected_error_message_contains.lower() in error_message.lower()
            ), f"Expected error_message to contain '{expected_error_message_contains}', got '{error_message}'"

        # Validate stack_trace field if expected
        if should_have_stack_trace:
            stack_trace = payload.get("stack_trace")
            assert (
                stack_trace is not None
            ), "Error event should have 'stack_trace' field for exceptions"
            assert isinstance(
                stack_trace, str
            ), f"stack_trace should be string, got {type(stack_trace)}"
            assert len(stack_trace) > 0, "stack_trace should not be empty"
            # Stack trace should contain traceback indicators
            assert any(
                indicator in stack_trace
                for indicator in ["Traceback", "File ", "line ", "Error:"]
            ), "stack_trace should contain valid traceback information"

        # Validate error_context field if expected
        if should_have_error_context:
            error_context = payload.get("error_context")
            assert (
                error_context is not None
            ), "Error event should have 'error_context' field"
            assert isinstance(
                error_context, dict
            ), f"error_context should be dict, got {type(error_context)}"
            assert len(error_context) > 0, "error_context should not be empty"

    @staticmethod
    def assert_api_error_response(
        response: Any,
        expected_status_code: Optional[int] = None,
        expected_error_message_contains: Optional[str] = None,
        expected_error_type: Optional[str] = None,
        should_have_suggestion: bool = False,
        validate_json_structure: bool = True,
    ) -> None:
        """
        Validate API error response structure and content.

        Ensures API error responses follow consistent format with proper
        error fields.

        Args:
            response: HTTP response object (with status_code and json() method)
            expected_status_code: Expected HTTP status code
            expected_error_message_contains: Substring expected in error message
            expected_error_type: Expected error type (e.g., "validation_error")
            should_have_suggestion: Whether response should include suggestion
            validate_json_structure: Whether to validate JSON structure

        Raises:
            AssertionError: If validation fails with descriptive message
        """
        # Validate status code
        assert hasattr(
            response, "status_code"
        ), "Response should have status_code attribute"

        if expected_status_code:
            assert (
                response.status_code == expected_status_code
            ), f"Expected status_code {expected_status_code}, got {response.status_code}"
        else:
            # Should be an error status code
            assert (
                response.status_code >= 400
            ), f"Expected error status code (>=400), got {response.status_code}"

        # Validate response body structure
        if validate_json_structure:
            assert hasattr(response, "json"), "Response should have json() method"
            data = response.json()
            assert isinstance(
                data, dict
            ), f"Response JSON should be dict, got {type(data)}"

            # Check for error information (multiple formats supported)
            has_error_info = False

            # Format 1: {"detail": "error message"} or {"detail": {"error": "..."}}
            if "detail" in data:
                has_error_info = True
                detail = data["detail"]

                if isinstance(detail, dict):
                    # Structured error detail
                    assert (
                        "error" in detail or "message" in detail
                    ), "Structured detail should have 'error' or 'message' field"

                    error_msg = detail.get("error") or detail.get("message")
                    if expected_error_message_contains:
                        assert (
                            expected_error_message_contains.lower()
                            in str(error_msg).lower()
                        ), (
                            f"Expected error message to contain '{expected_error_message_contains}', "
                            f"got '{error_msg}'"
                        )
                else:
                    # Simple error detail
                    if expected_error_message_contains:
                        assert (
                            expected_error_message_contains.lower()
                            in str(detail).lower()
                        ), (
                            f"Expected error message to contain '{expected_error_message_contains}', "
                            f"got '{detail}'"
                        )

            # Format 2: {"error": {"type": "...", "message": "...", ...}}
            if "error" in data and isinstance(data["error"], dict):
                has_error_info = True
                error = data["error"]

                # Validate error type
                if "type" in error:
                    error_type = error["type"]
                    assert isinstance(
                        error_type, str
                    ), f"error.type should be string, got {type(error_type)}"

                    if expected_error_type:
                        assert (
                            error_type == expected_error_type
                        ), f"Expected error type '{expected_error_type}', got '{error_type}'"

                # Validate error message
                if "message" in error:
                    error_message = error["message"]
                    assert isinstance(
                        error_message, str
                    ), f"error.message should be string, got {type(error_message)}"

                    if expected_error_message_contains:
                        assert (
                            expected_error_message_contains.lower()
                            in error_message.lower()
                        ), (
                            f"Expected error message to contain '{expected_error_message_contains}', "
                            f"got '{error_message}'"
                        )

                # Validate suggestion if expected
                if should_have_suggestion:
                    assert "suggestion" in error, "Error should have 'suggestion' field"
                    suggestion = error["suggestion"]
                    assert isinstance(
                        suggestion, str
                    ), f"suggestion should be string, got {type(suggestion)}"
                    assert len(suggestion) > 0, "suggestion should not be empty"

            # Format 3: {"success": false, "error": ...}
            if "success" in data:
                has_error_info = True
                assert (
                    data["success"] is False
                ), "Error response should have success=false"

            assert (
                has_error_info
            ), "Response should contain error information ('detail', 'error', or 'success' field)"

    @staticmethod
    def assert_exception_handling(
        exception: Exception,
        expected_exception_type: Optional[Type[Exception]] = None,
        expected_message_contains: Optional[str] = None,
        should_have_cause: bool = False,
    ) -> None:
        """
        Validate exception handling and exception properties.

        Ensures exceptions are properly caught and have expected properties.

        Args:
            exception: Exception instance to validate
            expected_exception_type: Expected exception class
            expected_message_contains: Substring expected in exception message
            should_have_cause: Whether exception should have __cause__ set

        Raises:
            AssertionError: If validation fails with descriptive message
        """
        assert exception is not None, "Exception should not be None"
        assert isinstance(
            exception, Exception
        ), f"Should be Exception instance, got {type(exception)}"

        # Validate exception type
        if expected_exception_type:
            assert isinstance(
                exception, expected_exception_type
            ), f"Expected {expected_exception_type.__name__}, got {type(exception).__name__}"

        # Validate exception message
        exception_message = str(exception)
        assert len(exception_message) > 0, "Exception message should not be empty"

        if expected_message_contains:
            assert expected_message_contains.lower() in exception_message.lower(), (
                f"Expected exception message to contain '{expected_message_contains}', "
                f"got '{exception_message}'"
            )

        # Validate exception chaining if expected
        if should_have_cause:
            assert (
                exception.__cause__ is not None
            ), "Exception should have __cause__ set for proper exception chaining"

    @staticmethod
    def assert_rollback_event(
        event: dict[str, Any],
        expected_item_id: Optional[str] = None,
        expected_rollback_reason: Optional[str] = None,
        should_have_original_state: bool = False,
    ) -> None:
        """
        Validate rollback event structure for optimistic update failures.

        Args:
            event: Rollback event dictionary
            expected_item_id: Expected item ID being rolled back
            expected_rollback_reason: Expected reason for rollback
            should_have_original_state: Whether event should include original state

        Raises:
            AssertionError: If validation fails
        """
        assert event is not None, "Rollback event should not be None"
        assert isinstance(event, dict), f"Event should be dict, got {type(event)}"

        # Get event data (handle nested structure)
        data = event.get("data", event)

        # Validate rollback flag (can be 'rollback' or 'rollback_to_server')
        has_rollback_field = "rollback" in data or "rollback_to_server" in data
        assert (
            has_rollback_field
        ), "Rollback event must have 'rollback' or 'rollback_to_server' field"

        rollback_value = data.get("rollback") or data.get("rollback_to_server")
        assert rollback_value is True, "rollback field should be True"

        # Validate item ID
        if expected_item_id:
            item_id = data.get("item_id")
            assert item_id is not None, "Rollback event should have 'item_id' field"
            assert (
                item_id == expected_item_id
            ), f"Expected item_id '{expected_item_id}', got '{item_id}'"

        # Validate rollback reason
        rollback_reason = (
            data.get("error") or data.get("conflict_reason") or data.get("reason")
        )
        assert (
            rollback_reason is not None
        ), "Rollback event should have reason/error field"
        assert isinstance(
            rollback_reason, str
        ), f"Rollback reason should be string, got {type(rollback_reason)}"

        if expected_rollback_reason:
            assert expected_rollback_reason.lower() in rollback_reason.lower(), (
                f"Expected rollback reason to contain '{expected_rollback_reason}', "
                f"got '{rollback_reason}'"
            )

        # Validate original state if expected
        if should_have_original_state:
            original_state = data.get("server_state") or data.get("original_state")
            assert (
                original_state is not None
            ), "Rollback event should have original state"
            assert isinstance(
                original_state, dict
            ), f"Original state should be dict, got {type(original_state)}"

    @staticmethod
    def _validate_event_envelope_structure(event: dict[str, Any]) -> None:
        """
        Validate event follows ModelEventEnvelope structure.

        Internal helper for comprehensive envelope validation.
        """
        # Required fields
        assert "event_id" in event, "Event must have 'event_id' field"
        assert "event_type" in event, "Event must have 'event_type' field"
        assert "correlation_id" in event, "Event must have 'correlation_id' field"
        assert "timestamp" in event, "Event must have 'timestamp' field"
        assert "version" in event, "Event must have 'version' field"
        assert "source" in event, "Event must have 'source' field"
        assert "payload" in event, "Event must have 'payload' field"

        # Validate event_id format (UUID)
        event_id = event["event_id"]
        ErrorAssertions._validate_uuid_field(event_id, "event_id")

        # Validate event_type format
        event_type = event["event_type"]
        assert isinstance(
            event_type, str
        ), f"event_type should be string, got {type(event_type)}"
        # Should match pattern: omninode.{domain}.{pattern}.{operation}.v{version}
        pattern = r"^omninode\.[a-z_]+\.(request|response|event|audit)\.[a-z_]+\.v\d+$"
        assert re.match(
            pattern, event_type
        ), f"event_type '{event_type}' should match pattern '{pattern}'"

        # Validate correlation_id format (UUID)
        correlation_id = event["correlation_id"]
        ErrorAssertions._validate_uuid_field(correlation_id, "correlation_id")

        # Validate timestamp format (ISO 8601)
        timestamp = event["timestamp"]
        ErrorAssertions._validate_timestamp_field(timestamp)

        # Validate version format (semantic versioning)
        version = event["version"]
        assert isinstance(
            version, str
        ), f"version should be string, got {type(version)}"
        version_pattern = r"^\d+\.\d+\.\d+$"
        assert re.match(
            version_pattern, version
        ), f"version '{version}' should match semantic versioning pattern"

        # Validate source structure
        source = event["source"]
        assert isinstance(source, dict), f"source should be dict, got {type(source)}"
        assert "service" in source, "source must have 'service' field"
        assert "instance_id" in source, "source must have 'instance_id' field"

    @staticmethod
    def _validate_uuid_field(value: Any, field_name: str) -> None:
        """Validate field is valid UUID format."""
        if isinstance(value, str):
            # Try parsing as UUID
            try:
                UUID(value)
            except ValueError:
                pytest.fail(f"{field_name} '{value}' is not valid UUID format")
        elif not isinstance(value, UUID):
            pytest.fail(
                f"{field_name} should be UUID or UUID string, got {type(value)}"
            )

    @staticmethod
    def _validate_timestamp_field(value: Any) -> None:
        """Validate field is valid ISO 8601 timestamp."""
        if isinstance(value, str):
            # Try parsing as ISO 8601
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pytest.fail(f"timestamp '{value}' is not valid ISO 8601 format")
        elif not isinstance(value, datetime):
            pytest.fail(
                f"timestamp should be datetime or ISO string, got {type(value)}"
            )


# Convenience functions for common assertion patterns


def assert_circuit_breaker_error(
    exception: Exception, expected_message_contains: str = "Circuit breaker is OPEN"
) -> None:
    """
    Validate circuit breaker error.

    Args:
        exception: Exception from circuit breaker
        expected_message_contains: Expected substring in error message
    """
    ErrorAssertions.assert_exception_handling(
        exception,
        expected_exception_type=Exception,
        expected_message_contains=expected_message_contains,
    )


def assert_service_unavailable_error(exception: Exception, service_name: str) -> None:
    """
    Validate service unavailable error.

    Args:
        exception: Exception from unavailable service
        service_name: Name of the unavailable service
    """
    ErrorAssertions.assert_exception_handling(
        exception,
        expected_exception_type=Exception,
        expected_message_contains=f"{service_name} service is unavailable",
    )


def assert_api_error_with_detail(
    response: Any, expected_status: int, detail_contains: str
) -> None:
    """
    Validate API error response with detail field.

    Args:
        response: HTTP response object
        expected_status: Expected HTTP status code
        detail_contains: Substring expected in detail field
    """
    ErrorAssertions.assert_api_error_response(
        response,
        expected_status_code=expected_status,
        expected_error_message_contains=detail_contains,
    )


def assert_rollback_event(
    event: dict[str, Any],
    expected_item_id: Optional[str] = None,
    expected_rollback_reason: Optional[str] = None,
    should_have_original_state: bool = False,
) -> None:
    """
    Validate rollback event structure for optimistic update failures.

    Convenience wrapper for ErrorAssertions.assert_rollback_event.

    Args:
        event: Rollback event dictionary
        expected_item_id: Expected item ID being rolled back
        expected_rollback_reason: Expected reason for rollback
        should_have_original_state: Whether event should include original state
    """
    ErrorAssertions.assert_rollback_event(
        event,
        expected_item_id=expected_item_id,
        expected_rollback_reason=expected_rollback_reason,
        should_have_original_state=should_have_original_state,
    )
