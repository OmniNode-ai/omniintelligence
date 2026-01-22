"""Exceptions for semantic analysis handlers.

This module defines domain-specific exceptions for semantic analysis operations.
All exceptions follow the ONEX pattern of explicit, typed error handling.
"""

from __future__ import annotations


class SemanticAnalysisValidationError(Exception):
    """Raised when input validation fails.

    This exception indicates that the input to an analysis function
    is invalid (e.g., empty content, invalid language, unsupported format).

    Attributes:
        message: Human-readable error description.

    Example:
        >>> raise SemanticAnalysisValidationError("Content cannot be empty")
        SemanticAnalysisValidationError: Content cannot be empty
    """

    pass


class SemanticAnalysisParseError(Exception):
    """Raised when AST parsing fails.

    This exception indicates that the code could not be parsed into
    an Abstract Syntax Tree (e.g., syntax errors, unsupported language features).

    Attributes:
        message: Human-readable error description.

    Example:
        >>> raise SemanticAnalysisParseError("Failed to parse: invalid syntax at line 5")
        SemanticAnalysisParseError: Failed to parse: invalid syntax at line 5
    """

    pass


class SemanticAnalysisComputeError(Exception):
    """Raised when semantic analysis computation fails.

    This exception indicates an error during the analysis computation
    itself (e.g., entity extraction failure, relationship detection error).

    Attributes:
        message: Human-readable error description.

    Example:
        >>> raise SemanticAnalysisComputeError("Failed to extract entities")
        SemanticAnalysisComputeError: Failed to extract entities
    """

    pass


__all__ = [
    "SemanticAnalysisComputeError",
    "SemanticAnalysisParseError",
    "SemanticAnalysisValidationError",
]
