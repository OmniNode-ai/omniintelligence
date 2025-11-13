"""
ONEX Error classes - Stub Implementation
"""

from enum import Enum
from typing import Any, Optional


class CoreErrorCode(Enum):
    """Core error codes for ONEX system."""

    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    AUTHORIZATION_FAILED = "AUTHORIZATION_FAILED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INVALID_REQUEST = "INVALID_REQUEST"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"


class OnexError(Exception):
    """Base ONEX error class."""

    def __init__(
        self,
        message: str,
        error_code: CoreErrorCode,
        details: Optional[dict[str, Any]] = None,
        status_code: int = 500,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary."""
        return {
            "message": self.message,
            "error_code": self.error_code.value,
            "details": self.details,
            "status_code": self.status_code,
        }
