# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Output models for LinearCrawlerEffect.

Defines the three document lifecycle events emitted by the Linear crawler:
  - ModelDocumentDiscoveredEvent  — new issue/doc not in linear_state
  - ModelDocumentChangedEvent     — content hash differs from stored fingerprint
  - ModelDocumentRemovedEvent     — issue/doc no longer returned by Linear API

Also defines the aggregate crawl output summary.

Note: The document event models here mirror the interface from
node_git_repo_crawler_effect.models.model_crawl_output but are intentionally
defined separately — the two crawlers are independent components and may
diverge in event shape over time.

Ticket: OMN-2388
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelDocumentDiscoveredEvent(BaseModel):
    """Emitted when a Linear issue or document is seen for the first time.

    Attributes:
        crawl_scope: Logical scope this document belongs to
            (e.g., "omninode/omniintelligence").
        source_ref: Linear identifier for the issue (e.g., "OMN-1234") or
            document ID.
        source_version: Linear ``updatedAt`` ISO timestamp at crawl time.
        content_fingerprint: SHA-256 of the formatted markdown content.
        correlation_id: Tracing ID from the originating crawl request.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    event_type: str = Field(default="document.discovered.v1")
    crawl_scope: str
    source_ref: str = Field(
        description="Linear identifier (e.g., 'OMN-1234') or document ID."
    )
    source_version: str = Field(
        description="Linear updatedAt ISO timestamp (not a commit SHA)."
    )
    content_fingerprint: str = Field(
        description="SHA-256 hex digest of the formatted markdown content."
    )
    correlation_id: str | None = None


class ModelDocumentChangedEvent(BaseModel):
    """Emitted when a Linear issue or document has new content.

    The ``content_fingerprint`` carries the NEW hash. The ``source_version``
    carries the NEW updatedAt timestamp.

    Attributes:
        crawl_scope: Logical scope this document belongs to.
        source_ref: Linear identifier or document ID.
        source_version: NEW Linear updatedAt ISO timestamp.
        previous_source_version: Previous updatedAt from linear_state.
        content_fingerprint: NEW SHA-256 of the formatted markdown content.
        correlation_id: Tracing ID from the originating crawl request.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    event_type: str = Field(default="document.changed.v1")
    crawl_scope: str
    source_ref: str
    source_version: str = Field(description="New Linear updatedAt ISO timestamp.")
    previous_source_version: str = Field(
        description="Previous updatedAt ISO timestamp from linear_state."
    )
    content_fingerprint: str = Field(
        description="New SHA-256 hex digest of the formatted markdown content."
    )
    correlation_id: str | None = None


class ModelDocumentRemovedEvent(BaseModel):
    """Emitted when a tracked Linear issue or document is no longer returned.

    Attributes:
        crawl_scope: Logical scope this document belonged to.
        source_ref: Linear identifier or document ID that was removed.
        last_source_version: Last known updatedAt from linear_state.
        correlation_id: Tracing ID from the originating crawl request.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    event_type: str = Field(default="document.removed.v1")
    crawl_scope: str
    source_ref: str
    last_source_version: str = Field(
        description="Last updatedAt ISO timestamp stored in linear_state."
    )
    correlation_id: str | None = None


class ModelLinearCrawlOutput(BaseModel):
    """Aggregate result returned by handle_linear_crawl.

    Attributes:
        team_id: Linear team that was crawled.
        crawl_scope: Logical scope for the crawl.
        discovered: Issues/docs found for the first time.
        changed: Issues/docs whose content changed.
        removed: Issues/docs no longer returned by Linear.
        skipped: Count of items skipped (updatedAt unchanged).
        errors: Per-ref error messages for items that could not be processed.
    """

    model_config = {"extra": "ignore"}

    team_id: str
    crawl_scope: str
    discovered: list[ModelDocumentDiscoveredEvent] = Field(default_factory=list)
    changed: list[ModelDocumentChangedEvent] = Field(default_factory=list)
    removed: list[ModelDocumentRemovedEvent] = Field(default_factory=list)
    skipped: int = 0
    errors: dict[str, str] = Field(default_factory=dict)


__all__ = [
    "ModelDocumentChangedEvent",
    "ModelDocumentDiscoveredEvent",
    "ModelDocumentRemovedEvent",
    "ModelLinearCrawlOutput",
]
