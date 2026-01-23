"""Exceptions for intent classification handlers.

This module defines domain-specific exceptions for intent classification operations.
All exceptions follow the ONEX pattern of explicit, typed error handling with
contract-defined error codes for traceability.

Error Codes (from contract.yaml):
    - INTENT_001: Input validation failed (non-recoverable)
    - INTENT_002: Classification computation error (recoverable, immediate retry)
"""

from __future__ import annotations


class IntentClassificationError(Exception):
    """Base exception for intent classification errors.

    Provides a common interface for all intent classification errors,
    including an error code for structured error handling and logging.

    Attributes:
        message: Human-readable error description.
        code: Error code from contract (e.g., INTENT_001, INTENT_002).

    Example:
        >>> try:
        ...     raise IntentClassificationError("Something failed", code="INTENT_999")
        ... except IntentClassificationError as e:
        ...     print(f"Error {e.code}: {e.message}")
        Error INTENT_999: Something failed
    """

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class IntentClassificationValidationError(IntentClassificationError):
    """Raised when input validation fails.

    This exception indicates that the input to a classification function
    is invalid (e.g., empty content, missing required fields, invalid format).

    Contract Error Code: INTENT_001
    Recoverable: False (invalid input cannot be retried without modification)
    Retry Strategy: None

    Attributes:
        message: Human-readable error description.
        code: Always "INTENT_001".

    Example:
        >>> raise IntentClassificationValidationError("Content cannot be empty")
        IntentClassificationValidationError: Content cannot be empty
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, code="INTENT_001")


class IntentClassificationComputeError(IntentClassificationError):
    """Raised when intent classification computation fails.

    This exception indicates an error during the classification computation
    itself (e.g., model inference failure, feature extraction error, timeout).

    Contract Error Code: INTENT_002
    Recoverable: True (transient errors may succeed on retry)
    Retry Strategy: Immediate retry

    Attributes:
        message: Human-readable error description.
        code: Always "INTENT_002".

    Example:
        >>> raise IntentClassificationComputeError("Failed to compute embeddings")
        IntentClassificationComputeError: Failed to compute embeddings
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, code="INTENT_002")


__all__ = [
    "IntentClassificationComputeError",
    "IntentClassificationError",
    "IntentClassificationValidationError",
]
