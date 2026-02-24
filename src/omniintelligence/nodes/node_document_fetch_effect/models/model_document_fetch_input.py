# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Input model for DocumentFetchEffect.

Defines the fetch request constructed from document.discovered.v1 or
document.changed.v1 events consumed from Kafka.

Ticket: OMN-2389
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ModelDocumentFetchInput(BaseModel):
    """Input for a document fetch request.

    Constructed from document.discovered.v1 or document.changed.v1 events.
    The ``crawler_type`` field determines which fetch path is used.

    Attributes:
        source_ref: Canonical document identifier.
            - FILESYSTEM / WATCHDOG: absolute path to the file on disk.
            - GIT_REPO: repo-relative file path (e.g., "docs/README.md").
            - LINEAR: Linear identifier (e.g., "OMN-1234") or document ID.
        crawler_type: Origin crawler that produced the event. Determines
            which fetch strategy is used.
        repo_path: Root path of the git repository. Required when
            ``crawler_type`` is "git_repo". Ignored otherwise.
        crawl_scope: Logical scope of the document
            (e.g., "omninode/omniintelligence").
        event_type: Discriminates between "discovered" and "changed" triggers.
            Propagated to the output for downstream routing.
        correlation_id: Optional tracing ID from the originating event.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    source_ref: str = Field(
        description=(
            "Canonical document identifier: absolute path, git relative path, "
            "or Linear identifier."
        )
    )
    crawler_type: Literal["filesystem", "git_repo", "linear", "watchdog"] = Field(
        description=(
            "Origin crawler type: 'filesystem', 'git_repo', 'linear', or 'watchdog'."
        )
    )
    repo_path: str | None = Field(
        default=None,
        description=(
            "Absolute path to the git repo root. Required for crawler_type='git_repo'."
        ),
    )
    crawl_scope: str = Field(
        description="Logical scope of the document (e.g., 'omninode/omniintelligence')."
    )
    event_type: Literal["document.discovered.v1", "document.changed.v1"] = Field(
        default="document.discovered.v1",
        description="Type of the triggering document lifecycle event.",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Optional correlation ID for distributed tracing.",
    )


__all__ = ["ModelDocumentFetchInput"]
