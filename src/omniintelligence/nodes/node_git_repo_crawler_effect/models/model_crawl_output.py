# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Output models for GitRepoCrawlerEffect.

Defines the three document lifecycle events emitted by the crawler:
  - ModelDocumentDiscoveredEvent  — new file not in crawl_state
  - ModelDocumentChangedEvent     — content hash differs from stored fingerprint
  - ModelDocumentRemovedEvent     — file no longer exists in the git tree

Also defines the aggregate crawl output summary.

Ticket: OMN-2387
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelDocumentDiscoveredEvent(BaseModel):
    """Emitted when a .md file is found that has no entry in crawl_state.

    Attributes:
        repo_path: Root path of the repository.
        file_path: Repo-relative path to the file (e.g. "docs/README.md").
        source_version: File-level commit SHA of the most recent commit
            that modified this file (from ``git log -1 --format=%H``).
        content_fingerprint: SHA-256 of the file content at crawl time.
        correlation_id: Tracing ID from the originating crawl request.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    event_type: str = Field(default="document.discovered.v1")
    repo_path: str
    file_path: str
    source_version: str = Field(description="File-level commit SHA (not HEAD).")
    content_fingerprint: str = Field(
        description="SHA-256 hex digest of the file content."
    )
    correlation_id: str | None = None


class ModelDocumentChangedEvent(BaseModel):
    """Emitted when a .md file exists in crawl_state but its content has changed.

    The ``content_fingerprint`` field carries the NEW hash after the change.
    Consumers should use ``previous_source_version`` to determine the diff range.

    Attributes:
        repo_path: Root path of the repository.
        file_path: Repo-relative path to the file.
        source_version: NEW file-level commit SHA.
        previous_source_version: Previous file-level commit SHA stored in crawl_state.
        content_fingerprint: NEW SHA-256 of the file content.
        correlation_id: Tracing ID from the originating crawl request.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    event_type: str = Field(default="document.changed.v1")
    repo_path: str
    file_path: str
    source_version: str = Field(description="New file-level commit SHA (not HEAD).")
    previous_source_version: str = Field(
        description="Previous file-level commit SHA from crawl_state."
    )
    content_fingerprint: str = Field(
        description="New SHA-256 hex digest of the file content."
    )
    correlation_id: str | None = None


class ModelDocumentRemovedEvent(BaseModel):
    """Emitted when a file previously tracked in crawl_state is no longer present.

    Attributes:
        repo_path: Root path of the repository.
        file_path: Repo-relative path that was removed.
        last_source_version: Last known file-level commit SHA from crawl_state.
        correlation_id: Tracing ID from the originating crawl request.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    event_type: str = Field(default="document.removed.v1")
    repo_path: str
    file_path: str
    last_source_version: str = Field(
        description="Last file-level commit SHA stored in crawl_state."
    )
    correlation_id: str | None = None


class ModelGitRepoCrawlOutput(BaseModel):
    """Aggregate result returned by handle_git_repo_crawl.

    Attributes:
        repo_path: Repository that was crawled.
        head_sha: HEAD SHA at the time of the crawl.
        skipped: True if the repo was skipped because HEAD SHA was unchanged.
        discovered: Files found for the first time.
        changed: Files whose content fingerprint changed.
        removed: Files tracked in crawl_state but no longer present.
        errors: Per-file error messages for files that could not be processed.
    """

    model_config = {"extra": "ignore"}

    repo_path: str
    head_sha: str
    skipped: bool = False
    discovered: list[ModelDocumentDiscoveredEvent] = Field(default_factory=list)
    changed: list[ModelDocumentChangedEvent] = Field(default_factory=list)
    removed: list[ModelDocumentRemovedEvent] = Field(default_factory=list)
    errors: dict[str, str] = Field(default_factory=dict)


__all__ = [
    "ModelDocumentChangedEvent",
    "ModelDocumentDiscoveredEvent",
    "ModelDocumentRemovedEvent",
    "ModelGitRepoCrawlOutput",
]
