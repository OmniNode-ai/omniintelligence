# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""ModelCrawlSchedulerResult — output of a single crawl scheduling operation.

Reference: OMN-2384
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_crawl_scheduler_effect.models.enum_crawl_scheduler_status import (
    EnumCrawlSchedulerStatus,
)
from omniintelligence.nodes.node_crawl_scheduler_effect.models.enum_crawler_type import (
    CrawlerType,
)
from omniintelligence.nodes.node_crawl_scheduler_effect.models.enum_trigger_source import (
    EnumTriggerSource,
)


class ModelCrawlSchedulerResult(BaseModel):
    """Result of processing a single crawl trigger through CrawlSchedulerEffect.

    Returned by both:
      - ``schedule_crawl_tick()`` — scheduler tick handler
      - ``handle_crawl_requested()`` — manual/external trigger handler

    The ``status`` field is the primary outcome discriminator.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    status: EnumCrawlSchedulerStatus = Field(
        ...,
        description="Outcome: EMITTED, DEBOUNCED, or ERROR.",
    )
    crawl_type: CrawlerType = Field(
        ...,
        description="Crawler type that was requested.",
    )
    source_ref: str = Field(
        ...,
        description="Source reference that was requested.",
    )
    crawl_scope: str = Field(
        ...,
        description="Logical crawl scope.",
    )
    trigger_source: EnumTriggerSource = Field(
        ...,
        description="Origin of the trigger.",
    )
    correlation_id: UUID = Field(
        ...,
        description="Correlation ID for distributed tracing.",
    )
    processed_at: datetime = Field(
        ...,
        description="Timestamp when the trigger was processed by the scheduler.",
    )
    debounce_window_seconds: int | None = Field(
        default=None,
        description=(
            "Active debounce window in seconds for this (source_ref, crawler_type).  "
            "Present when status=DEBOUNCED to explain the drop duration."
        ),
    )
    error_message: str | None = Field(
        default=None,
        description="Error details when status=ERROR.",
    )


__all__ = ["ModelCrawlSchedulerResult"]
