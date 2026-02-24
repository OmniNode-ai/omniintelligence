# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Protocol for blob store access in DocumentFetchEffect.

The blob store is used to retrieve pre-fetched content for LINEAR documents.
The Linear crawler stores formatted markdown in the blob store; this effect
retrieves it by source_ref.

Ticket: OMN-2389
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ProtocolBlobStore(Protocol):
    """Abstraction over the blob store used for LINEAR document content.

    LINEAR documents have their content pre-fetched by the LinearCrawlerEffect
    and stored in a blob store keyed by source_ref. DocumentFetchEffect
    retrieves content from this store rather than calling the Linear API again.

    Implementations must handle transient failures with exponential backoff
    internally (or surface RuntimeError for the handler to catch).
    """

    async def get(self, source_ref: str) -> str:
        """Retrieve the markdown content for a Linear item by source_ref.

        Args:
            source_ref: Linear identifier (e.g., "OMN-1234") or document ID.

        Returns:
            Markdown content as a string.

        Raises:
            RuntimeError: If the content cannot be retrieved after retries.
            KeyError: If the source_ref is not found in the blob store.
        """
        ...


__all__ = ["ProtocolBlobStore"]
