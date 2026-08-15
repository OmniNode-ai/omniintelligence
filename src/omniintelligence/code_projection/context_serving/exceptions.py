# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Closed failure vocabulary for explicit code-context serving."""

from __future__ import annotations


class CodeContextError(RuntimeError):
    """Base class for failures safe to surface without request content."""


class CodeContextRequestError(CodeContextError):
    """The canonical request contract is invalid or ambiguous."""


class CodeContextAuthorizationError(CodeContextError):
    """The principal is not authorized for the requested projection scope."""


class CodeContextIntegrityError(CodeContextError):
    """A search hit does not match authoritative promoted artifacts."""


class CodeContextSearchError(CodeContextError):
    """The injected metadata-search dependency did not complete safely."""


class CodeContextTimeoutError(CodeContextError):
    """The bounded serving operation exceeded its hard deadline."""


class CodeContextCandidateBudgetError(CodeContextError):
    """One authorized candidate cannot fit within the request byte ceiling."""


__all__ = [
    "CodeContextAuthorizationError",
    "CodeContextCandidateBudgetError",
    "CodeContextError",
    "CodeContextIntegrityError",
    "CodeContextRequestError",
    "CodeContextSearchError",
    "CodeContextTimeoutError",
]
