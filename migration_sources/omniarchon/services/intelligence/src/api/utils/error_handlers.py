"""
Shared error handling utilities for API endpoints.

Provides consistent error handling, logging, and exception management
across analytics and intelligence API routers.

Key Features:
- Consistent error handling via decorator pattern
- Structured logging with context
- HTTP status code standardization
- Response format standardization
- Timeout handling support

Usage Examples:

    # Basic error handling decorator
    @api_error_handler("get_pattern_analytics")
    async def get_pattern_analytics(pattern_id: str):
        result = await service.analyze_pattern(pattern_id)
        return standardize_success_response(result)

    # With custom context
    @api_error_handler("create_snapshot", {"project_id": project_id})
    async def create_snapshot(project_id: str):
        await service.create_snapshot(project_id)
        return standardize_success_response({"created": True})

    # Manual error handling
    try:
        result = await service.get_data(id)
        if not result:
            raise handle_not_found("pattern", id)
        return result
    except Exception as e:
        return standardize_error_response(e, operation="get_data")
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar, Union

from fastapi import HTTPException
from pydantic import ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ============================================================================
# Decorator for Comprehensive Error Handling
# ============================================================================


def api_error_handler(
    operation_name: str,
    logger_context: Optional[Dict[str, Any]] = None,
    reraise_http_exceptions: bool = True,
    timeout_seconds: Optional[float] = None,
    correlation_id: Optional[str] = None,
):
    """
    Decorator for consistent API error handling.

    Provides:
    - Automatic exception handling and logging
    - Structured logging with context
    - HTTP status code mapping
    - Timeout support
    - Performance timing
    - Correlation ID for distributed tracing

    Args:
        operation_name: Name of the operation for logging and error messages
        logger_context: Additional context for structured logging (optional)
        reraise_http_exceptions: Whether to re-raise HTTPException (default: True)
        timeout_seconds: Optional timeout in seconds for async operations
        correlation_id: Optional correlation ID for distributed tracing (auto-generated if not provided)

    Returns:
        Decorated function with error handling

    Usage:
        @api_error_handler("pattern_matching", {"project_id": project_id})
        async def match_pattern(pattern_id: str):
            result = await service.match_pattern(pattern_id)
            return standardize_success_response(result)

    Example with timeout:
        @api_error_handler("slow_operation", timeout_seconds=30.0)
        async def slow_operation():
            result = await expensive_computation()
            return result

    Example with correlation_id:
        @api_error_handler("get_pattern", correlation_id=request.headers.get("X-Correlation-ID"))
        async def get_pattern(pattern_id: str):
            return await service.get_pattern(pattern_id)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            start_time = time.time()
            # Generate correlation_id if not provided
            request_correlation_id = correlation_id or str(uuid.uuid4())

            context = logger_context or {}
            context["operation"] = operation_name
            context["correlation_id"] = request_correlation_id
            context["timestamp"] = datetime.now(timezone.utc).isoformat()

            try:
                logger.info(f"Starting {operation_name}", extra=context)

                # Execute with optional timeout
                if timeout_seconds:
                    try:
                        result = await asyncio.wait_for(
                            func(*args, **kwargs), timeout=timeout_seconds
                        )
                    except asyncio.TimeoutError:
                        processing_time_ms = (time.time() - start_time) * 1000
                        logger.error(
                            f"Timeout in {operation_name} after {timeout_seconds}s",
                            extra={**context, "processing_time_ms": processing_time_ms},
                        )
                        raise HTTPException(
                            status_code=504,
                            detail={
                                "error": f"{operation_name} timed out after {timeout_seconds}s",
                                "correlation_id": request_correlation_id,
                            },
                        )
                else:
                    result = await func(*args, **kwargs)

                processing_time_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"Completed {operation_name}",
                    extra={**context, "processing_time_ms": processing_time_ms},
                )
                return result

            except ValidationError as e:
                processing_time_ms = (time.time() - start_time) * 1000
                logger.warning(
                    f"Validation error in {operation_name}: {e}",
                    extra={
                        **context,
                        "error_type": "validation",
                        "processing_time_ms": processing_time_ms,
                    },
                )
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": f"Validation error in {operation_name}: {str(e)}",
                        "correlation_id": request_correlation_id,
                    },
                )

            except ValueError as e:
                processing_time_ms = (time.time() - start_time) * 1000
                logger.warning(
                    f"Value error in {operation_name}: {e}",
                    extra={
                        **context,
                        "error_type": "value_error",
                        "processing_time_ms": processing_time_ms,
                    },
                )
                raise HTTPException(
                    status_code=400,
                    detail={"error": str(e), "correlation_id": request_correlation_id},
                )

            except HTTPException:
                # Re-raise HTTP exceptions without wrapping (if enabled)
                if reraise_http_exceptions:
                    raise
                else:
                    processing_time_ms = (time.time() - start_time) * 1000
                    logger.warning(
                        f"HTTP exception in {operation_name}",
                        extra={**context, "processing_time_ms": processing_time_ms},
                    )
                    raise

            except Exception as e:
                processing_time_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"Unexpected error in {operation_name}: {e}",
                    extra={
                        **context,
                        "error_type": "unexpected",
                        "processing_time_ms": processing_time_ms,
                    },
                    exc_info=True,
                )

                # Check for database-related errors
                error_str = str(e).lower()
                if any(
                    keyword in error_str
                    for keyword in ["database", "connection", "pool", "postgres"]
                ):
                    raise HTTPException(
                        status_code=503,
                        detail={
                            "error": f"Database error in {operation_name}: Service temporarily unavailable",
                            "correlation_id": request_correlation_id,
                        },
                    )

                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": f"Internal server error in {operation_name}",
                        "correlation_id": request_correlation_id,
                    },
                )

        return wrapper

    return decorator


# ============================================================================
# Specialized Error Handlers
# ============================================================================


def handle_not_found(
    resource_type: str,
    resource_id: str,
    detail: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> HTTPException:
    """
    Create standardized 404 error.

    Args:
        resource_type: Type of resource (pattern, project, file, etc.)
        resource_id: ID of the resource
        detail: Optional custom detail message
        correlation_id: Optional correlation ID for distributed tracing

    Returns:
        HTTPException with 404 status

    Usage:
        result = await service.get_pattern(pattern_id)
        if not result:
            raise handle_not_found("pattern", pattern_id, correlation_id=request_correlation_id)
    """
    request_correlation_id = correlation_id or str(uuid.uuid4())
    message = detail or f"{resource_type} not found: {resource_id}"

    logger.warning(
        f"Resource not found: {resource_type}",
        extra={
            "resource_type": resource_type,
            "resource_id": resource_id,
            "correlation_id": request_correlation_id,
        },
    )

    return HTTPException(
        status_code=404,
        detail={"error": message, "correlation_id": request_correlation_id},
    )


def handle_database_error(
    operation_name: str,
    error: Exception,
    detail: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> HTTPException:
    """
    Create standardized database error response.

    Args:
        operation_name: Name of the operation that failed
        error: The original exception
        detail: Optional custom detail message
        correlation_id: Optional correlation ID for distributed tracing

    Returns:
        HTTPException with 503 status

    Usage:
        try:
            await db_operation()
        except Exception as e:
            raise handle_database_error("save_pattern", e, correlation_id=request_correlation_id)
    """
    request_correlation_id = correlation_id or str(uuid.uuid4())
    message = (
        detail or f"Database error in {operation_name}: Service temporarily unavailable"
    )

    logger.error(
        f"Database error in {operation_name}: {error}",
        extra={
            "operation": operation_name,
            "error_type": "database",
            "correlation_id": request_correlation_id,
        },
        exc_info=True,
    )

    return HTTPException(
        status_code=503,
        detail={"error": message, "correlation_id": request_correlation_id},
    )


# ============================================================================
# Structured Logging Utilities
# ============================================================================


def log_with_context(
    message: str, level: str = "info", correlation_id: Optional[str] = None, **context
) -> None:
    """
    Log with structured context.

    Args:
        message: Log message
        level: Log level (info, warning, error, debug)
        correlation_id: Optional correlation ID for distributed tracing
        **context: Additional context fields

    Usage:
        log_with_context(
            "Processing pattern",
            level="info",
            correlation_id=request_correlation_id,
            pattern_id=pattern_id,
            operation="analyze"
        )
    """
    context["timestamp"] = datetime.now(timezone.utc).isoformat()
    context["correlation_id"] = correlation_id or str(uuid.uuid4())

    log_func = getattr(logger, level.lower(), logger.info)
    log_func(message, extra=context)


# ============================================================================
# Response Standardization Utilities
# ============================================================================


def standardize_success_response(
    data: Any,
    message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    processing_time_ms: Optional[float] = None,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Standardize success response format.

    Args:
        data: Response data (can be dict, list, or any JSON-serializable type)
        message: Optional success message
        metadata: Optional metadata dictionary
        processing_time_ms: Optional processing time in milliseconds
        correlation_id: Optional correlation ID for distributed tracing

    Returns:
        Standardized response dictionary

    Usage:
        result = await service.get_patterns()
        return standardize_success_response(
            data=result,
            message="Patterns retrieved successfully",
            processing_time_ms=123.45,
            correlation_id=request_correlation_id
        )
    """
    response = {"success": True, "data": data}

    if message:
        response["message"] = message

    # Build metadata
    meta = metadata.copy() if metadata else {}

    if processing_time_ms is not None:
        meta["processing_time_ms"] = round(processing_time_ms, 2)

    if correlation_id:
        meta["correlation_id"] = correlation_id

    if meta:
        response["metadata"] = meta

    return response


def standardize_error_response(
    error: Union[Exception, str],
    operation: Optional[str] = None,
    status_code: int = 500,
    metadata: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Standardize error response format.

    Args:
        error: Error message or exception
        operation: Optional operation name
        status_code: HTTP status code (default: 500)
        metadata: Optional metadata dictionary
        correlation_id: Optional correlation ID for distributed tracing

    Returns:
        Standardized error response dictionary

    Usage:
        try:
            result = await service.process()
        except Exception as e:
            return standardize_error_response(
                e,
                operation="process_data",
                correlation_id=request_correlation_id
            )
    """
    error_message = str(error) if not isinstance(error, str) else error
    request_correlation_id = correlation_id or str(uuid.uuid4())

    response = {
        "success": False,
        "error": error_message,
        "status_code": status_code,
        "correlation_id": request_correlation_id,
    }

    if operation:
        response["operation"] = operation

    if metadata:
        response["metadata"] = metadata

    response["timestamp"] = datetime.now(timezone.utc).isoformat()

    return response


# ============================================================================
# Validation Utilities
# ============================================================================


def validate_required_fields(
    data: Dict[str, Any],
    required_fields: list[str],
    operation_name: Optional[str] = None,
) -> None:
    """
    Validate that required fields are present in data.

    Args:
        data: Data dictionary to validate
        required_fields: List of required field names
        operation_name: Optional operation name for error message

    Raises:
        HTTPException: If any required fields are missing

    Usage:
        validate_required_fields(
            request_data,
            ["project_id", "file_path"],
            operation_name="create_snapshot"
        )
    """
    missing_fields = [
        field for field in required_fields if field not in data or data[field] is None
    ]

    if missing_fields:
        operation_msg = f" in {operation_name}" if operation_name else ""
        raise HTTPException(
            status_code=400,
            detail=f"Missing required fields{operation_msg}: {', '.join(missing_fields)}",
        )


def validate_range(
    value: Union[int, float],
    min_value: Optional[Union[int, float]] = None,
    max_value: Optional[Union[int, float]] = None,
    field_name: str = "value",
    operation_name: Optional[str] = None,
) -> None:
    """
    Validate that a numeric value is within a specified range.

    Args:
        value: Value to validate
        min_value: Optional minimum value (inclusive)
        max_value: Optional maximum value (inclusive)
        field_name: Name of the field for error message
        operation_name: Optional operation name for error message

    Raises:
        HTTPException: If value is out of range

    Usage:
        validate_range(limit, min_value=1, max_value=200, field_name="limit")
    """
    operation_msg = f" in {operation_name}" if operation_name else ""

    if min_value is not None and value < min_value:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name}{operation_msg} must be >= {min_value}, got {value}",
        )

    if max_value is not None and value > max_value:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name}{operation_msg} must be <= {max_value}, got {value}",
        )


# ============================================================================
# Retry Utilities
# ============================================================================


async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_multiplier: float = 2.0,
    operation_name: Optional[str] = None,
) -> Any:
    """
    Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        backoff_multiplier: Multiplier for exponential backoff
        operation_name: Optional operation name for logging

    Returns:
        Result from the function

    Raises:
        Exception: If all retries are exhausted

    Usage:
        result = await retry_with_backoff(
            lambda: service.unstable_operation(),
            max_retries=3,
            operation_name="fetch_data"
        )
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                op_name = operation_name or "operation"
                logger.warning(
                    f"Retry {attempt + 1}/{max_retries} for {op_name} after error: {e}",
                    extra={
                        "operation": operation_name,
                        "attempt": attempt + 1,
                        "delay": delay,
                    },
                )
                await asyncio.sleep(delay)
                delay *= backoff_multiplier
            else:
                logger.error(
                    f"All {max_retries} retries exhausted for {op_name}",
                    extra={"operation": operation_name},
                    exc_info=True,
                )

    # If we get here, all retries failed
    raise last_exception
