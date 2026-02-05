"""Exceptions for pattern matching handlers.

This module defines domain-specific exceptions for pattern matching operations.
All exceptions follow the ONEX pattern of explicit, typed error handling.

Error codes map to contract.yaml error_handling configuration:
    - PATMATCH_001: Validation errors (not recoverable)
    - PATMATCH_002: Compute errors (recoverable via retry)
"""

from __future__ import annotations


class PatternMatchingValidationError(Exception):
    """Raised when input validation fails.

    This exception indicates that the input to a matching function
    is invalid (e.g., empty code snippet, invalid pattern format).

    Error Code: PATMATCH_001
    Recoverable: No
    Retry Strategy: None

    Attributes:
        message: Human-readable error description.

    Example:
        >>> raise PatternMatchingValidationError("Code snippet cannot be empty")
        PatternMatchingValidationError: Code snippet cannot be empty
    """

    pass


class PatternMatchingComputeError(Exception):
    """Raised when pattern matching computation fails.

    This exception indicates an error during the matching computation
    itself (e.g., regex compilation failure, unexpected pattern format).

    Error Code: PATMATCH_002
    Recoverable: Yes
    Retry Strategy: Immediate retry

    Attributes:
        message: Human-readable error description.

    Example:
        >>> raise PatternMatchingComputeError("Failed to compile regex: invalid pattern")
        PatternMatchingComputeError: Failed to compile regex: invalid pattern
    """

    pass


__all__ = ["PatternMatchingComputeError", "PatternMatchingValidationError"]
