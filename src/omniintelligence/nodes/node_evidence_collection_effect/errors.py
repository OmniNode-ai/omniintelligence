# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Error types for the evidence collection effect node (OMN-2578).

Defines hard errors that are raised when the evidence collection pipeline
encounters disallowed input. These errors are NOT suppressed — they indicate
a programming error (free-text evidence injection), not a runtime failure.
"""

__all__ = ["DisallowedEvidenceSourceError"]


class DisallowedEvidenceSourceError(ValueError):
    """Raised when a caller attempts to inject evidence from a disallowed source.

    Free-text sources (chat logs, model confidence text, unstructured summaries)
    are explicitly disallowed in the evidence pipeline. This error is raised
    when such a source is provided programmatically.

    Per the OMN-2578 spec:
        - If evidence collection returns no items, silently skip evaluation.
        - If free-text is injected programmatically, raise this error (hard fail).

    The distinction is important:
        - Missing evidence → graceful skip (non-blocking).
        - Injected free-text → hard error (programming contract violation).

    Example:
        >>> raise DisallowedEvidenceSourceError(
        ...     source="chat_log",
        ...     reason="Free-text sources are structurally disallowed.",
        ... )
    """

    def __init__(self, *, source: str, reason: str) -> None:
        """Initialize with the disallowed source and reason.

        Args:
            source: The source string that was rejected.
            reason: Human-readable reason for rejection.
        """
        self.source = source
        self.reason = reason
        super().__init__(
            f"Disallowed evidence source '{source}': {reason}. "
            "Only structured, ledger-backed evidence sources are permitted."
        )
