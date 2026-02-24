# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Exceptions for quality scoring handlers.

This module defines domain-specific exceptions for quality scoring operations.
All exceptions follow the ONEX pattern of explicit, typed error handling.
"""

from __future__ import annotations


class QualityScoringValidationError(Exception):
    """Raised when input validation fails.

    This exception indicates that the input to a scoring function
    is invalid (e.g., empty content, invalid language).

    Attributes:
        message: Human-readable error description.

    Example:
        >>> raise QualityScoringValidationError("Content cannot be empty")
        QualityScoringValidationError: Content cannot be empty
    """

    pass


class QualityScoringComputeError(Exception):
    """Raised when scoring computation fails.

    This exception indicates an error during the scoring computation
    itself (e.g., AST parsing failure, unexpected content format).

    Attributes:
        message: Human-readable error description.

    Example:
        >>> raise QualityScoringComputeError("Failed to parse AST: syntax error")
        QualityScoringComputeError: Failed to parse AST: syntax error
    """

    pass


__all__ = ["QualityScoringComputeError", "QualityScoringValidationError"]
