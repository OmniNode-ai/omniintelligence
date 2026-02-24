# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Exceptions for pattern compliance handlers.

Domain-specific exceptions for pattern compliance evaluation operations.
Follows the ONEX pattern of explicit, typed error handling.

LLM and parse errors are handled via structured error output (not exceptions),
following the ONEX convention that domain/expected errors are data, not exceptions.
Only invariant violations (ComplianceValidationError) use exception classes.

Ticket: OMN-2256
"""

from __future__ import annotations


class ComplianceValidationError(Exception):
    """Raised when input validation fails for compliance evaluation.

    Indicates that the input to a compliance function is invalid
    (e.g., empty content, no patterns provided, unsupported language).
    This is an invariant violation that must halt orchestration.
    """


__all__ = [
    "ComplianceValidationError",
]
