"""Exceptions for pattern compliance handlers.

Domain-specific exceptions for pattern compliance evaluation operations.
Follows the ONEX pattern of explicit, typed error handling.

Ticket: OMN-2256
"""

from __future__ import annotations


class ComplianceValidationError(Exception):
    """Raised when input validation fails for compliance evaluation.

    Indicates that the input to a compliance function is invalid
    (e.g., empty content, no patterns provided, unsupported language).
    """


class ComplianceLlmError(Exception):
    """Raised when the LLM call fails during compliance evaluation.

    Indicates an error during the LLM inference call itself
    (e.g., timeout, connection error, malformed response).
    """


class ComplianceParseError(Exception):
    """Raised when parsing the LLM response fails.

    Indicates that the LLM returned a response that could not be
    parsed into the expected violation structure.
    """


__all__ = [
    "ComplianceLlmError",
    "ComplianceParseError",
    "ComplianceValidationError",
]
