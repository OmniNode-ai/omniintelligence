# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""ModelCrawlTickRequest — request for a scheduled crawl tick.

Input to ``HandlerCrawlTick.handle()``.  Carries the per-call data for one
scheduler tick; collaborators (debounce state, config, Kafka publisher) are
passed to the handler constructor.

Reference: OMN-2384
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_crawl_scheduler_effect.models.enum_crawler_type import (
    CrawlerType,
)


class ModelCrawlTickRequest(BaseModel):
    """Per-call data for a scheduled crawl tick."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    crawl_type: CrawlerType = Field(
        ...,
        description="Crawler type for the tick.",
    )
    crawl_scope: str = Field(
        ...,
        description="Logical scope for the crawl.",
    )
    source_ref: str = Field(
        ...,
        description="Canonical source identifier.",
    )
    now: datetime | None = Field(
        default=None,
        description=(
            "Current UTC datetime.  Defaults to ``datetime.now(UTC)`` when "
            "None.  Injected for testability."
        ),
    )


__all__ = ["ModelCrawlTickRequest"]
