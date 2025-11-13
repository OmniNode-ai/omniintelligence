"""
API utility modules.

Provides reusable utilities for API endpoints including error handling,
logging, validation, and response formatting.
"""

# Error handlers (comprehensive error handling utilities)
from src.api.utils.error_handlers import (
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

# Response formatters (new standardized formatters)
from src.api.utils.response_formatters import (
    APIResponse,
    ErrorResponse,
    HealthCheckResponse,
    PaginatedResponse,
    PaginationMetadata,
    PaginationParams,
    SuccessResponse,
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

__all__ = [
    # Error handlers
    "api_error_handler",
    "handle_not_found",
    "handle_database_error",
    "log_with_context",
    "standardize_success_response",
    "standardize_error_response",
    "validate_required_fields",
    "validate_range",
    "retry_with_backoff",
    # Response formatters
    "success_response",
    "paginated_response",
    "analytics_response",
    "health_response",
    "list_response",
    "error_response",
    "created_response",
    "updated_response",
    "deleted_response",
    "processing_time_metadata",
    # Pydantic models
    "PaginationParams",
    "PaginationMetadata",
    "APIResponse",
    "SuccessResponse",
    "PaginatedResponse",
    "HealthCheckResponse",
    "ErrorResponse",
]
