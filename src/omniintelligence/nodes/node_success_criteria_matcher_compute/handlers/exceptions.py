"""Exceptions for success criteria matching handlers.

This module defines domain-specific exceptions for criteria matching operations.
All exceptions follow the ONEX pattern of explicit, typed error handling.
"""

from __future__ import annotations


class CriteriaMatchingValidationError(Exception):
    """Raised when input validation fails.

    This exception indicates that the input to a matching function
    is invalid (e.g., invalid operator, duplicate criterion IDs,
    invalid regex pattern, negative weight).

    Example:
        >>> raise CriteriaMatchingValidationError("Duplicate criterion_id: 'test_1'")
        CriteriaMatchingValidationError: Duplicate criterion_id: 'test_1'
    """

    pass


class CriteriaMatchingComputeError(Exception):
    """Raised when matching computation fails unexpectedly.

    This exception indicates an error during the matching computation
    itself (e.g., unexpected type comparison failure, internal error).

    Example:
        >>> raise CriteriaMatchingComputeError("Failed to compare values: type mismatch")
        CriteriaMatchingComputeError: Failed to compare values: type mismatch
    """

    pass


__all__ = ["CriteriaMatchingComputeError", "CriteriaMatchingValidationError"]
