# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Protocol definitions for LinearCrawlerEffect.

Defines:
  - ModelLinearStateEntry: a single row in omnimemory_linear_state
  - ProtocolLinearStateStore: persistence interface for crawl state
  - ProtocolLinearClient: thin abstraction over the Linear MCP API

These protocols allow the handler to be tested without a real Linear
connection or database.

Ticket: OMN-2388
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class ModelLinearStateEntry:
    """A single row from omnimemory_linear_state.

    Attributes:
        crawl_scope: Logical scope this entry belongs to.
        source_ref: Linear identifier (e.g., "OMN-1234") or document ID.
        source_version: Last-known ``updatedAt`` ISO timestamp.
        content_fingerprint: Last-known SHA-256 of the formatted content.
    """

    crawl_scope: str
    source_ref: str
    source_version: str
    content_fingerprint: str


@dataclass
class ModelLinearItemSummary:
    """Lightweight summary returned by the cheap list phase.

    Contains only what is needed to decide whether a full fetch is required.

    Attributes:
        source_ref: Linear identifier (e.g., "OMN-1234") or document ID.
        updated_at: ISO timestamp of the last update from Linear.
        item_type: "issue" or "document".
        project_id: Optional project ID for scope resolution.
    """

    source_ref: str
    updated_at: str
    item_type: str  # "issue" | "document"
    project_id: str | None = field(default=None)


@dataclass
class ModelLinearItemContent:
    """Full content of a Linear issue or document.

    Attributes:
        source_ref: Linear identifier or document ID.
        updated_at: ISO timestamp from Linear (used as source_version).
        markdown: Formatted markdown content of the issue or document.
        project_id: Optional project ID for scope resolution.
    """

    source_ref: str
    updated_at: str
    markdown: str
    project_id: str | None = field(default=None)


@runtime_checkable
class ProtocolLinearStateStore(Protocol):
    """Persistence interface for omnimemory_linear_state.

    All methods are async and keyed on (crawl_scope, source_ref).
    """

    async def get_all_entries(self, crawl_scope: str) -> list[ModelLinearStateEntry]:
        """Return all crawl-state entries for the given scope."""
        ...

    async def get_entry(
        self, crawl_scope: str, source_ref: str
    ) -> ModelLinearStateEntry | None:
        """Return the crawl-state entry for a specific item, or None."""
        ...

    async def upsert_entry(self, entry: ModelLinearStateEntry) -> None:
        """Insert or update a crawl-state entry."""
        ...

    async def delete_entry(self, crawl_scope: str, source_ref: str) -> None:
        """Remove a crawl-state entry (item removed from Linear)."""
        ...


@runtime_checkable
class ProtocolLinearClient(Protocol):
    """Thin abstraction over the Linear MCP API.

    Allows the handler to be tested with in-memory mock implementations
    without a live Linear connection.
    """

    async def list_issues(
        self,
        team_id: str,
        project_id: str | None = None,
    ) -> list[ModelLinearItemSummary]:
        """Return lightweight summaries for all issues in the given team/project.

        Returns only source_ref and updated_at for each issue — this is the
        cheap phase of the two-phase fetch pattern.
        """
        ...

    async def list_documents(
        self,
        team_id: str,
        project_id: str | None = None,
    ) -> list[ModelLinearItemSummary]:
        """Return lightweight summaries for all documents in the given team/project.

        Returns only source_ref and updated_at for each document — cheap phase.
        """
        ...

    async def get_issue(self, source_ref: str) -> ModelLinearItemContent:
        """Fetch full content for a single Linear issue.

        This is the expensive phase — called only when updatedAt changed.

        Raises:
            RuntimeError: If the issue cannot be fetched (e.g., rate limit,
                not found).
        """
        ...

    async def get_document(self, source_ref: str) -> ModelLinearItemContent:
        """Fetch full content for a single Linear document.

        This is the expensive phase — called only when updatedAt changed.

        Raises:
            RuntimeError: If the document cannot be fetched (e.g., rate limit,
                not found).
        """
        ...


__all__ = [
    "ModelLinearItemContent",
    "ModelLinearItemSummary",
    "ModelLinearStateEntry",
    "ProtocolLinearClient",
    "ProtocolLinearStateStore",
]
