# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""ModelCrawlTickCommand — the output command published to crawl-tick.v1.

Design doc:
    omni_save/design/DESIGN_OMNIMEMORY_DOCUMENT_INGESTION_PIPELINE.md §4

Reference: OMN-2384
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_crawl_scheduler_effect.models.enum_crawler_type import (
    CrawlerType,
)
from omniintelligence.nodes.node_crawl_scheduler_effect.models.enum_trigger_source import (
    EnumTriggerSource,
)


class ModelCrawlTickCommand(BaseModel):
    """Command published to ``{env}.onex.cmd.omnimemory.crawl-tick.v1``.

    Emitted by CrawlSchedulerEffect after passing the per-source debounce
    guard.  Downstream crawler effect nodes (FilesystemCrawlerEffect,
    GitRepoCrawlerEffect, LinearCrawlerEffect) consume this topic and execute
    their respective crawl logic.

    Frozen because commands are immutable once emitted.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    event_type: Literal["CrawlTickRequested"] = Field(
        default="CrawlTickRequested",
        description="Always 'CrawlTickRequested' — type discriminator.",
    )
    crawl_type: CrawlerType = Field(
        ...,
        description="Crawler type that should execute this tick.",
    )
    crawl_scope: str = Field(
        ...,
        description=(
            "Logical scope for the crawl.  Examples: "
            "'omninode/omniintelligence', 'omninode/shared/global-standards'."
        ),
    )
    source_ref: str = Field(
        ...,
        description=(
            "Canonical identifier for the document source being crawled.  "
            "For FilesystemCrawler this is an absolute path; for GitRepoCrawler "
            "a repo root path; for LinearCrawler a team/project slug."
        ),
    )
    correlation_id: UUID = Field(
        default_factory=uuid4,
        description="Correlation ID for distributed tracing.",
    )
    triggered_at_utc: str = Field(
        ...,
        description="ISO-8601 UTC timestamp of when the trigger arrived.",
    )
    trigger_source: EnumTriggerSource = Field(
        ...,
        description="Origin of the crawl trigger (scheduled, manual, git_hook, filesystem_watch).",
    )


__all__ = ["ModelCrawlTickCommand"]
