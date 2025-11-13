"""
Unit tests for API error handling utilities.

Tests cover:
- api_error_handler decorator with various exception types
- Timeout handling
- Response standardization
- Not found error handling
- Structured logging
- Validation utilities
- Retry with backoff

Run with: pytest tests/unit/api/utils/test_error_handlers.py -v
"""

import asyncio
import time
from unittest.mock import patch

import pytest
from api.utils.error_handlers import (
    api_error_handler,
    handle_database_error,
    handle_not_found,
    log_with_context,
    retry_with_backoff,
    standardize_error_response,
    standardize_success_response,
    validate_range,
    validate_required_fields,
)
from fastapi import HTTPException
from pydantic import ValidationError

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_logger():
    """Mock logger for testing log calls."""
    with patch("src.api.utils.error_handlers.logger") as mock_log:
        yield mock_log


# ============================================================================
# Test api_error_handler Decorator
# ============================================================================


class TestApiErrorHandler:
    """Test suite for api_error_handler decorator."""

    @pytest.mark.asyncio
    async def test_successful_execution(self, mock_logger):
        """Test decorator with successful function execution."""

        @api_error_handler("test_operation")
        async def successful_func():
            return {"result": "success"}

        result = await successful_func()

        assert result == {"result": "success"}
        assert mock_logger.info.call_count == 2  # Start and completion logs
        assert "Starting test_operation" in str(mock_logger.info.call_args_list[0])
        assert "Completed test_operation" in str(mock_logger.info.call_args_list[1])

    @pytest.mark.asyncio
    async def test_validation_error_handling(self, mock_logger):
        """Test decorator handling ValidationError."""

        @api_error_handler("validation_test")
        async def func_with_validation_error():
            raise ValidationError.from_exception_data("test", [])

        with pytest.raises(HTTPException) as exc_info:
            await func_with_validation_error()

        assert exc_info.value.status_code == 422
        assert isinstance(exc_info.value.detail, dict)
        assert "Validation error" in exc_info.value.detail["error"]
        assert "correlation_id" in exc_info.value.detail
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_value_error_handling(self, mock_logger):
        """Test decorator handling ValueError."""

        @api_error_handler("value_error_test")
        async def func_with_value_error():
            raise ValueError("Invalid input value")

        with pytest.raises(HTTPException) as exc_info:
            await func_with_value_error()

        assert exc_info.value.status_code == 400
        assert isinstance(exc_info.value.detail, dict)
        assert "Invalid input value" in exc_info.value.detail["error"]
        assert "correlation_id" in exc_info.value.detail
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_http_exception_reraising(self, mock_logger):
        """Test decorator re-raises HTTPException by default."""

        @api_error_handler("http_exception_test")
        async def func_with_http_exception():
            raise HTTPException(status_code=404, detail="Not found")

        with pytest.raises(HTTPException) as exc_info:
            await func_with_http_exception()

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Not found"

    @pytest.mark.asyncio
    async def test_http_exception_no_reraise(self, mock_logger):
        """Test decorator with reraise_http_exceptions=False."""

        @api_error_handler("http_exception_test", reraise_http_exceptions=False)
        async def func_with_http_exception():
            raise HTTPException(status_code=404, detail="Not found")

        with pytest.raises(HTTPException) as exc_info:
            await func_with_http_exception()

        assert exc_info.value.status_code == 404
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_database_error_handling(self, mock_logger):
        """Test decorator handling database errors."""

        @api_error_handler("db_error_test")
        async def func_with_db_error():
            raise Exception("Database connection failed")

        with pytest.raises(HTTPException) as exc_info:
            await func_with_db_error()

        assert exc_info.value.status_code == 503
        assert isinstance(exc_info.value.detail, dict)
        assert "Service temporarily unavailable" in exc_info.value.detail["error"]
        assert "correlation_id" in exc_info.value.detail
        mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_generic_exception_handling(self, mock_logger):
        """Test decorator handling generic exceptions."""

        @api_error_handler("generic_error_test")
        async def func_with_generic_error():
            raise Exception("Something went wrong")

        with pytest.raises(HTTPException) as exc_info:
            await func_with_generic_error()

        assert exc_info.value.status_code == 500
        assert isinstance(exc_info.value.detail, dict)
        assert "Internal server error" in exc_info.value.detail["error"]
        assert "correlation_id" in exc_info.value.detail
        mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_timeout_handling(self, mock_logger):
        """Test decorator with timeout."""

        @api_error_handler("timeout_test", timeout_seconds=0.1)
        async def slow_func():
            await asyncio.sleep(1.0)  # Sleep longer than timeout
            return {"result": "done"}

        with pytest.raises(HTTPException) as exc_info:
            await slow_func()

        assert exc_info.value.status_code == 504
        assert isinstance(exc_info.value.detail, dict)
        assert "timed out" in exc_info.value.detail["error"]
        assert "correlation_id" in exc_info.value.detail
        mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_timeout_success(self, mock_logger):
        """Test decorator with timeout that completes in time."""

        @api_error_handler("timeout_success_test", timeout_seconds=1.0)
        async def fast_func():
            await asyncio.sleep(0.01)  # Sleep less than timeout
            return {"result": "done"}

        result = await fast_func()

        assert result == {"result": "done"}
        assert mock_logger.info.call_count == 2

    @pytest.mark.asyncio
    async def test_with_logger_context(self, mock_logger):
        """Test decorator with custom logger context."""

        @api_error_handler(
            "context_test", logger_context={"user_id": "123", "project": "test"}
        )
        async def func_with_context():
            return {"result": "success"}

        result = await func_with_context()

        assert result == {"result": "success"}
        # Verify context was included in logs
        call_args = mock_logger.info.call_args_list[0]
        assert call_args.kwargs["extra"]["user_id"] == "123"
        assert call_args.kwargs["extra"]["project"] == "test"

    @pytest.mark.asyncio
    async def test_correlation_id_auto_generation(self, mock_logger):
        """Test decorator auto-generates correlation_id when not provided."""

        @api_error_handler("auto_correlation_test")
        async def func_without_correlation():
            return {"result": "success"}

        result = await func_without_correlation()

        assert result == {"result": "success"}
        # Verify correlation_id was auto-generated in logs
        call_args = mock_logger.info.call_args_list[0]
        assert "correlation_id" in call_args.kwargs["extra"]
        # Should be a valid UUID
        correlation_id = call_args.kwargs["extra"]["correlation_id"]
        assert len(correlation_id) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_correlation_id_provided(self, mock_logger):
        """Test decorator uses provided correlation_id."""
        test_correlation_id = "test-correlation-123"

        @api_error_handler(
            "provided_correlation_test", correlation_id=test_correlation_id
        )
        async def func_with_correlation():
            return {"result": "success"}

        result = await func_with_correlation()

        assert result == {"result": "success"}
        # Verify provided correlation_id was used
        call_args = mock_logger.info.call_args_list[0]
        assert call_args.kwargs["extra"]["correlation_id"] == test_correlation_id

    @pytest.mark.asyncio
    async def test_correlation_id_in_error_response(self, mock_logger):
        """Test correlation_id is included in error responses."""

        @api_error_handler("error_correlation_test")
        async def func_with_error():
            raise ValueError("Test error")

        with pytest.raises(HTTPException) as exc_info:
            await func_with_error()

        assert exc_info.value.status_code == 400
        # Error detail should be a dict with correlation_id
        assert isinstance(exc_info.value.detail, dict)
        assert "correlation_id" in exc_info.value.detail
        assert "error" in exc_info.value.detail


# ============================================================================
# Test Specialized Error Handlers
# ============================================================================


class TestSpecializedErrorHandlers:
    """Test suite for specialized error handler functions."""

    def test_handle_not_found(self, mock_logger):
        """Test handle_not_found creates correct HTTPException."""
        exception = handle_not_found("pattern", "pattern_123")

        assert exception.status_code == 404
        assert isinstance(exception.detail, dict)
        assert "pattern not found: pattern_123" in exception.detail["error"]
        assert "correlation_id" in exception.detail
        mock_logger.warning.assert_called_once()

    def test_handle_not_found_custom_detail(self, mock_logger):
        """Test handle_not_found with custom detail message."""
        exception = handle_not_found(
            "file", "file_abc", detail="Custom not found message"
        )

        assert exception.status_code == 404
        assert isinstance(exception.detail, dict)
        assert exception.detail["error"] == "Custom not found message"
        assert "correlation_id" in exception.detail

    def test_handle_not_found_with_correlation_id(self, mock_logger):
        """Test handle_not_found with provided correlation_id."""
        test_correlation_id = "test-correlation-456"
        exception = handle_not_found(
            "pattern", "pattern_123", correlation_id=test_correlation_id
        )

        assert exception.status_code == 404
        assert exception.detail["correlation_id"] == test_correlation_id
        # Verify correlation_id was logged
        call_args = mock_logger.warning.call_args
        assert call_args.kwargs["extra"]["correlation_id"] == test_correlation_id

    def test_handle_database_error(self, mock_logger):
        """Test handle_database_error creates correct HTTPException."""
        original_error = Exception("Connection pool exhausted")
        exception = handle_database_error("save_pattern", original_error)

        assert exception.status_code == 503
        assert isinstance(exception.detail, dict)
        assert "Database error" in exception.detail["error"]
        assert "Service temporarily unavailable" in exception.detail["error"]
        assert "correlation_id" in exception.detail
        mock_logger.error.assert_called_once()

    def test_handle_database_error_with_correlation_id(self, mock_logger):
        """Test handle_database_error with provided correlation_id."""
        test_correlation_id = "db-error-correlation-789"
        original_error = Exception("Connection pool exhausted")
        exception = handle_database_error(
            "save_pattern", original_error, correlation_id=test_correlation_id
        )

        assert exception.status_code == 503
        assert exception.detail["correlation_id"] == test_correlation_id
        # Verify correlation_id was logged
        call_args = mock_logger.error.call_args
        assert call_args.kwargs["extra"]["correlation_id"] == test_correlation_id


# ============================================================================
# Test Response Standardization
# ============================================================================


class TestResponseStandardization:
    """Test suite for response standardization utilities."""

    def test_standardize_success_response_basic(self):
        """Test basic success response standardization."""
        response = standardize_success_response({"key": "value"})

        assert response["success"] is True
        assert response["data"] == {"key": "value"}

    def test_standardize_success_response_with_message(self):
        """Test success response with message."""
        response = standardize_success_response(
            data={"result": "ok"}, message="Operation completed successfully"
        )

        assert response["success"] is True
        assert response["data"] == {"result": "ok"}
        assert response["message"] == "Operation completed successfully"

    def test_standardize_success_response_with_metadata(self):
        """Test success response with metadata."""
        metadata = {"count": 10, "page": 1}
        response = standardize_success_response(data={"items": []}, metadata=metadata)

        assert response["success"] is True
        assert response["metadata"] == metadata

    def test_standardize_success_response_with_timing(self):
        """Test success response with processing time."""
        response = standardize_success_response(
            data={"result": "ok"}, processing_time_ms=123.456
        )

        assert response["success"] is True
        assert response["metadata"]["processing_time_ms"] == 123.46

    def test_standardize_success_response_with_correlation_id(self):
        """Test success response with correlation_id."""
        test_correlation_id = "success-correlation-123"
        response = standardize_success_response(
            data={"result": "ok"}, correlation_id=test_correlation_id
        )

        assert response["success"] is True
        assert response["metadata"]["correlation_id"] == test_correlation_id

    def test_standardize_success_response_with_all_fields(self):
        """Test success response with all optional fields."""
        test_correlation_id = "full-response-456"
        response = standardize_success_response(
            data={"result": "ok"},
            message="Operation completed",
            processing_time_ms=123.456,
            correlation_id=test_correlation_id,
            metadata={"custom_field": "value"},
        )

        assert response["success"] is True
        assert response["message"] == "Operation completed"
        assert response["metadata"]["processing_time_ms"] == 123.46
        assert response["metadata"]["correlation_id"] == test_correlation_id
        assert response["metadata"]["custom_field"] == "value"

    def test_standardize_error_response_basic(self):
        """Test basic error response standardization."""
        response = standardize_error_response("Something went wrong")

        assert response["success"] is False
        assert response["error"] == "Something went wrong"
        assert response["status_code"] == 500
        assert "timestamp" in response
        assert "correlation_id" in response  # Auto-generated

    def test_standardize_error_response_with_exception(self):
        """Test error response with exception object."""
        error = ValueError("Invalid input")
        response = standardize_error_response(
            error, operation="validate_input", status_code=400
        )

        assert response["success"] is False
        assert response["error"] == "Invalid input"
        assert response["operation"] == "validate_input"
        assert response["status_code"] == 400

    def test_standardize_error_response_with_metadata(self):
        """Test error response with metadata."""
        metadata = {"retry_after": 60}
        response = standardize_error_response(
            "Rate limit exceeded", metadata=metadata, status_code=429
        )

        assert response["success"] is False
        assert response["metadata"] == metadata

    def test_standardize_error_response_with_correlation_id(self):
        """Test error response with provided correlation_id."""
        test_correlation_id = "error-correlation-999"
        response = standardize_error_response(
            "Something went wrong", correlation_id=test_correlation_id
        )

        assert response["success"] is False
        assert response["correlation_id"] == test_correlation_id


# ============================================================================
# Test Structured Logging
# ============================================================================


class TestStructuredLogging:
    """Test suite for structured logging utilities."""

    def test_log_with_context_info(self, mock_logger):
        """Test log_with_context with info level."""
        log_with_context("Test message", level="info", user_id="123", operation="test")

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args.args[0] == "Test message"
        assert call_args.kwargs["extra"]["user_id"] == "123"
        assert call_args.kwargs["extra"]["operation"] == "test"
        assert "timestamp" in call_args.kwargs["extra"]
        assert "correlation_id" in call_args.kwargs["extra"]  # Auto-generated

    def test_log_with_context_warning(self, mock_logger):
        """Test log_with_context with warning level."""
        log_with_context("Warning message", level="warning", error_code="ERR_001")

        mock_logger.warning.assert_called_once()

    def test_log_with_context_error(self, mock_logger):
        """Test log_with_context with error level."""
        log_with_context("Error message", level="error", exception="ValueError")

        mock_logger.error.assert_called_once()

    def test_log_with_context_correlation_id(self, mock_logger):
        """Test log_with_context with provided correlation_id."""
        test_correlation_id = "log-correlation-777"
        log_with_context(
            "Test message",
            level="info",
            correlation_id=test_correlation_id,
            operation="test",
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args.kwargs["extra"]["correlation_id"] == test_correlation_id


# ============================================================================
# Test Validation Utilities
# ============================================================================


class TestValidationUtilities:
    """Test suite for validation utility functions."""

    def test_validate_required_fields_success(self):
        """Test validate_required_fields with all fields present."""
        data = {"field1": "value1", "field2": "value2", "field3": "value3"}
        # Should not raise exception
        validate_required_fields(data, ["field1", "field2"])

    def test_validate_required_fields_missing(self):
        """Test validate_required_fields with missing fields."""
        data = {"field1": "value1"}

        with pytest.raises(HTTPException) as exc_info:
            validate_required_fields(data, ["field1", "field2", "field3"])

        assert exc_info.value.status_code == 400
        assert "Missing required fields" in exc_info.value.detail
        assert "field2" in exc_info.value.detail
        assert "field3" in exc_info.value.detail

    def test_validate_required_fields_none_value(self):
        """Test validate_required_fields with None values."""
        data = {"field1": "value1", "field2": None}

        with pytest.raises(HTTPException) as exc_info:
            validate_required_fields(data, ["field1", "field2"])

        assert exc_info.value.status_code == 400
        assert "field2" in exc_info.value.detail

    def test_validate_range_success(self):
        """Test validate_range with value in range."""
        # Should not raise exception
        validate_range(50, min_value=1, max_value=100)
        validate_range(1, min_value=1, max_value=100)  # Boundary
        validate_range(100, min_value=1, max_value=100)  # Boundary

    def test_validate_range_below_minimum(self):
        """Test validate_range with value below minimum."""
        with pytest.raises(HTTPException) as exc_info:
            validate_range(0, min_value=1, max_value=100, field_name="limit")

        assert exc_info.value.status_code == 400
        assert "limit" in exc_info.value.detail
        assert ">= 1" in exc_info.value.detail

    def test_validate_range_above_maximum(self):
        """Test validate_range with value above maximum."""
        with pytest.raises(HTTPException) as exc_info:
            validate_range(150, min_value=1, max_value=100, field_name="page_size")

        assert exc_info.value.status_code == 400
        assert "page_size" in exc_info.value.detail
        assert "<= 100" in exc_info.value.detail

    def test_validate_range_no_bounds(self):
        """Test validate_range without bounds."""
        # Should not raise exception
        validate_range(999999)
        validate_range(-999999)


# ============================================================================
# Test Retry with Backoff
# ============================================================================


class TestRetryWithBackoff:
    """Test suite for retry_with_backoff utility."""

    @pytest.mark.asyncio
    async def test_retry_success_first_attempt(self, mock_logger):
        """Test retry succeeds on first attempt."""

        async def successful_func():
            return "success"

        result = await retry_with_backoff(successful_func, operation_name="test_op")

        assert result == "success"
        # No warning logs since it succeeded immediately
        mock_logger.warning.assert_not_called()

    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self, mock_logger):
        """Test retry succeeds after some failures."""
        call_count = 0

        async def intermittent_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"

        result = await retry_with_backoff(
            intermittent_func,
            max_retries=3,
            initial_delay=0.01,  # Fast for testing
            operation_name="test_op",
        )

        assert result == "success"
        assert call_count == 3
        # Should have 2 warning logs (for first 2 failures)
        assert mock_logger.warning.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_exhausted(self, mock_logger):
        """Test retry exhausts all attempts."""

        async def always_fails():
            raise ValueError("Persistent failure")

        with pytest.raises(ValueError) as exc_info:
            await retry_with_backoff(
                always_fails,
                max_retries=3,
                initial_delay=0.01,
                operation_name="test_op",
            )

        assert "Persistent failure" in str(exc_info.value)
        # Should have 2 warning logs and 1 error log
        assert mock_logger.warning.call_count == 2
        assert mock_logger.error.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_backoff_timing(self):
        """Test retry exponential backoff timing."""
        attempts = []

        async def tracking_func():
            attempts.append(time.time())
            if len(attempts) < 3:
                raise Exception("Not yet")
            return "done"

        await retry_with_backoff(
            tracking_func, max_retries=3, initial_delay=0.1, backoff_multiplier=2.0
        )

        # Verify exponential backoff
        assert len(attempts) == 3
        # Delays should be approximately: 0.1s, 0.2s
        if len(attempts) >= 2:
            delay1 = attempts[1] - attempts[0]
            delay2 = attempts[2] - attempts[1]
            assert 0.08 < delay1 < 0.15  # ~0.1s with tolerance
            assert 0.18 < delay2 < 0.25  # ~0.2s with tolerance


# ============================================================================
# Integration Tests
# ============================================================================


class TestErrorHandlerIntegration:
    """Integration tests for error handlers with realistic scenarios."""

    @pytest.mark.asyncio
    async def test_complete_endpoint_simulation(self, mock_logger):
        """Simulate a complete API endpoint with error handling."""

        @api_error_handler("get_pattern_data", timeout_seconds=1.0)
        async def get_pattern_data(pattern_id: str):
            # Simulate validation
            validate_required_fields({"pattern_id": pattern_id}, ["pattern_id"])

            # Simulate service call
            await asyncio.sleep(0.01)

            if pattern_id == "not_found":
                raise handle_not_found("pattern", pattern_id)

            if pattern_id == "error":
                raise Exception("Service error")

            return standardize_success_response(
                data={"pattern_id": pattern_id, "data": "mock_data"},
                message="Pattern retrieved successfully",
                processing_time_ms=10.0,
            )

        # Test success case
        result = await get_pattern_data("valid_id")
        assert result["success"] is True
        assert result["data"]["pattern_id"] == "valid_id"
        assert "message" in result

        # Test not found case
        with pytest.raises(HTTPException) as exc_info:
            await get_pattern_data("not_found")
        assert exc_info.value.status_code == 404

        # Test error case
        with pytest.raises(HTTPException) as exc_info:
            await get_pattern_data("error")
        assert exc_info.value.status_code == 500
