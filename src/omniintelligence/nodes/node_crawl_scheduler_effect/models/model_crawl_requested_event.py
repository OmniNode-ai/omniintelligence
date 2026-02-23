# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""ModelCrawlRequestedEvent — input event from crawl-requested.v1.

This is the manual trigger input consumed by CrawlSchedulerEffect from
``{env}.onex.cmd.omnimemory.crawl-requested.v1``.

Reference: OMN-2384
"""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_crawl_scheduler_effect.models.enum_crawler_type import (
    CrawlerType,
)
from omniintelligence.nodes.node_crawl_scheduler_effect.models.enum_trigger_source import (
    EnumTriggerSource,
)


class ModelCrawlRequestedEvent(BaseModel):
    """Manual crawl trigger event consumed from ``crawl-requested.v1``.

    Published by:
      - MCP tool invocations (manual trigger)
      - CLI commands (manual trigger)
      - ``post-commit`` git hooks (git_hook trigger)
      - WatchdogEffect (filesystem_watch trigger)

    All trigger sources funnel through this model before the debounce
    guard in CrawlSchedulerEffect decides whether to emit a crawl-tick.
    """

    model_config = ConfigDict(frozen=True, extra="ignore", from_attributes=True)

    crawl_type: CrawlerType = Field(
        ...,
        description="Crawler type being requested.",
    )
    crawl_scope: str = Field(
        ...,
        description="Logical scope for the crawl.",
    )
    source_ref: str = Field(
        ...,
        description="Source reference being crawled (path, repo root, or team slug).",
    )
    correlation_id: UUID = Field(
        default_factory=uuid4,
        description="Correlation ID for distributed tracing.",
    )
    requested_at_utc: str = Field(
        ...,
        description="ISO-8601 UTC timestamp of when the request was emitted.",
    )
    trigger_source: EnumTriggerSource = Field(
        default=EnumTriggerSource.MANUAL,
        description="Origin of the crawl request.",
    )


__all__ = ["ModelCrawlRequestedEvent"]
