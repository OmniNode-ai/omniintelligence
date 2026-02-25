# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Pattern extraction compute exceptions with contract-defined error codes.

This module defines domain-specific exceptions for pattern extraction operations.
All exceptions follow the ONEX pattern of explicit, typed error handling with
contract-defined error codes for traceability.

Error Codes (from contract.yaml):
    - PATTERN_001: Input validation failed (non-recoverable)
    - PATTERN_002: Pattern extraction computation error (recoverable, immediate retry)
"""

from __future__ import annotations


class PatternExtractionError(Exception):
    """Base exception for pattern extraction errors.

    Provides a common interface for all pattern extraction errors,
    including an error code for structured error handling and logging.

    Attributes:
        message: Human-readable error description.
        code: Error code from contract (e.g., PATTERN_001, PATTERN_002).

    Example:
        >>> try:
        ...     raise PatternExtractionError("Something failed", code="PATTERN_999")
        ... except PatternExtractionError as e:
        ...     print(f"Error {e.code}: {e.message}")
        Error PATTERN_999: Something failed
    """

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class PatternExtractionValidationError(PatternExtractionError):
    """Raised when input validation fails.

    This exception indicates that the input to a pattern extraction function
    is invalid (e.g., empty session data, missing required fields, invalid format).

    Contract Error Code: PATTERN_001
    Recoverable: False (invalid input cannot be retried without modification)
    Retry Strategy: None

    Attributes:
        message: Human-readable error description.
        code: Always "PATTERN_001".

    Example:
        >>> raise PatternExtractionValidationError("Session data cannot be empty")
        PatternExtractionValidationError: Session data cannot be empty
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, code="PATTERN_001")


class PatternExtractionComputeError(PatternExtractionError):
    """Raised when pattern extraction computation fails.

    This exception indicates an error during the extraction computation
    itself (e.g., pattern analysis failure, feature extraction error, timeout).

    Contract Error Code: PATTERN_002
    Recoverable: True (transient errors may succeed on retry)
    Retry Strategy: Immediate retry

    Attributes:
        message: Human-readable error description.
        code: Always "PATTERN_002".

    Example:
        >>> raise PatternExtractionComputeError("Failed to extract patterns from trace")
        PatternExtractionComputeError: Failed to extract patterns from trace
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, code="PATTERN_002")


__all__ = [
    "PatternExtractionComputeError",
    "PatternExtractionError",
    "PatternExtractionValidationError",
]
