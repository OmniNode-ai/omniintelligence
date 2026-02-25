# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Protocol and state-entry model for omnimemory_crawl_state persistence.

ProtocolCrawlStateStore abstracts the persistence layer so the handler
can be tested without a real database.

Ticket: OMN-2387
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class ModelCrawlStateEntry:
    """A single row from omnimemory_crawl_state.

    Attributes:
        repo_path: Root path of the repository this entry belongs to.
        file_path: Repo-relative path to the tracked file.
        source_version: Last-known file-level commit SHA.
        content_fingerprint: Last-known SHA-256 of file content.
        head_sha: HEAD SHA of the repo at the last successful crawl.
    """

    repo_path: str
    file_path: str
    source_version: str
    content_fingerprint: str
    head_sha: str


@runtime_checkable
class ProtocolCrawlStateStore(Protocol):
    """Persistence interface for omnimemory_crawl_state.

    All methods are async and keyed on (repo_path, file_path).
    Implementations must be safe to call concurrently from multiple
    asyncio tasks on the same event loop.
    """

    async def get_head_sha(self, repo_path: str) -> str | None:
        """Return the HEAD SHA stored from the last successful crawl.

        Returns None if the repo has never been crawled.
        """
        ...

    async def get_all_entries(self, repo_path: str) -> list[ModelCrawlStateEntry]:
        """Return all crawl-state entries for the given repository."""
        ...

    async def get_entry(
        self, repo_path: str, file_path: str
    ) -> ModelCrawlStateEntry | None:
        """Return the crawl-state entry for a specific file, or None."""
        ...

    async def upsert_entry(self, entry: ModelCrawlStateEntry) -> None:
        """Insert or update a crawl-state entry."""
        ...

    async def delete_entry(self, repo_path: str, file_path: str) -> None:
        """Remove a crawl-state entry (called when a file is removed)."""
        ...

    async def update_head_sha(self, repo_path: str, head_sha: str) -> None:
        """Persist the new HEAD SHA after a successful crawl."""
        ...


__all__ = [
    "ModelCrawlStateEntry",
    "ProtocolCrawlStateStore",
]
