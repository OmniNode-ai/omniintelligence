# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Input model for GitRepoCrawlerEffect.

Defines the crawl request payload consumed from crawl-requested.v1.

Ticket: OMN-2387
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelGitRepoCrawlInput(BaseModel):
    """Input for a git repo crawl request.

    Consumed from the crawl-requested.v1 Kafka topic.
    Produced by CrawlSchedulerEffect or a post-commit git hook.

    Attributes:
        repo_path: Absolute path to the local git repository root.
        trigger_source: Origin of the crawl request.
            "scheduler" — periodic tick from CrawlSchedulerEffect.
            "git_hook"  — post-commit hook on the repo.
        correlation_id: Optional tracing ID propagated from the trigger.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    repo_path: str = Field(
        description="Absolute path to the local git repository root."
    )
    trigger_source: str = Field(
        default="scheduler",
        description=("Origin of the crawl request: 'scheduler' or 'git_hook'."),
    )
    correlation_id: str | None = Field(
        default=None,
        description="Optional correlation ID for distributed tracing.",
    )


__all__ = ["ModelGitRepoCrawlInput"]
