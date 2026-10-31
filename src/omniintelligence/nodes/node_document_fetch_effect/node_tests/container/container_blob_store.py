# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""In-memory ProtocolBlobStore for the node_document_fetch_effect tests.

The in-memory implementation is built here, the one binding site, and the test
fixtures resolve it through ``default_blob_store`` instead of constructing it (OMN-21680).
"""

from __future__ import annotations

from omniintelligence.nodes.node_document_fetch_effect.handlers.protocol_blob_store import (
    ProtocolBlobStore,
)


class InMemoryBlobStore:
    """In-memory blob store for testing the LINEAR fetch path."""

    def __init__(self) -> None:
        self._blobs: dict[str, str] = {}
        assert isinstance(self, ProtocolBlobStore)

    def put(self, source_ref: str, content: str) -> None:
        """Store content by source_ref."""
        self._blobs[source_ref] = content

    async def get(self, source_ref: str) -> str:
        if source_ref not in self._blobs:
            raise KeyError(f"Blob not found: {source_ref}")
        return self._blobs[source_ref]


def default_blob_store() -> InMemoryBlobStore:
    """Resolve the default InMemoryBlobStore the node tests run against."""
    return InMemoryBlobStore()
