# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Exceptions for pattern learning handlers.

This module defines domain-specific exceptions for pattern learning operations.
All exceptions follow the ONEX pattern of explicit, typed error handling with
error codes matching the contract.yaml error_handling section.

Error Codes:
    - PATLEARN_001: Input validation failed (non-recoverable)
    - PATLEARN_002: Computation error during pattern learning (recoverable with retry)
"""

from __future__ import annotations


class PatternLearningValidationError(Exception):
    """Raised when input validation fails.

    Error code: PATLEARN_001 - Input validation failed (non-recoverable).

    This exception indicates that the input to a pattern learning function
    is invalid (e.g., empty training data, invalid language, malformed parameters).
    This is a non-recoverable error - retrying with the same input will fail.

    Attributes:
        message: Human-readable error description.

    Example:
        >>> raise PatternLearningValidationError("Training data cannot be empty")
        PatternLearningValidationError: Training data cannot be empty
    """

    pass


class PatternLearningComputeError(Exception):
    """Raised when pattern learning computation fails.

    Error code: PATLEARN_002 - Computation error during pattern learning (recoverable).

    This exception indicates an error during the pattern learning computation
    itself (e.g., AST parsing failure, clustering error, unexpected data format).
    This may be recoverable with retry using immediate_retry strategy.

    Attributes:
        message: Human-readable error description.

    Example:
        >>> raise PatternLearningComputeError("Failed to parse AST: syntax error at line 42")
        PatternLearningComputeError: Failed to parse AST: syntax error at line 42
    """

    pass


__all__ = ["PatternLearningComputeError", "PatternLearningValidationError"]
