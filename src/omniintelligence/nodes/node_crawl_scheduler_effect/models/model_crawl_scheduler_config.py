# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""ModelCrawlSchedulerConfig — configurable debounce windows per crawler type.

All debounce windows are configurable (not hardcoded) per the ticket DoD.
Default values match the design doc:
    omni_save/design/DESIGN_OMNIMEMORY_DOCUMENT_INGESTION_PIPELINE.md §4

Reference: OMN-2384
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_crawl_scheduler_effect.models.enum_crawler_type import (
    CrawlerType,
)

# Default debounce windows in seconds (from design doc §4)
_DEFAULT_FILESYSTEM_DEBOUNCE_S: int = 30  # 30 seconds
_DEFAULT_GIT_REPO_DEBOUNCE_S: int = 300  # 5 minutes
_DEFAULT_LINEAR_DEBOUNCE_S: int = 3600  # 60 minutes
_DEFAULT_WATCHDOG_DEBOUNCE_S: int = 30  # same as filesystem


class ModelCrawlSchedulerConfig(BaseModel):
    """Configuration for CrawlSchedulerEffect debounce windows.

    Debounce windows specify how long (in seconds) a source_ref must be
    quiet after the first trigger before another crawl-tick is permitted
    for the same ``(source_ref, crawler_type)`` key.

    All windows are configurable to support test overrides and future
    tuning without code changes.  Default values follow the design doc.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    debounce_windows_seconds: dict[CrawlerType, int] = Field(
        default_factory=lambda: {
            CrawlerType.FILESYSTEM: _DEFAULT_FILESYSTEM_DEBOUNCE_S,
            CrawlerType.GIT_REPO: _DEFAULT_GIT_REPO_DEBOUNCE_S,
            CrawlerType.LINEAR: _DEFAULT_LINEAR_DEBOUNCE_S,
            CrawlerType.WATCHDOG: _DEFAULT_WATCHDOG_DEBOUNCE_S,
        },
        description=(
            "Per-crawler-type debounce window in seconds.  "
            "A trigger for a given (source_ref, crawler_type) is dropped "
            "silently if the window has not yet expired."
        ),
    )

    def get_window_seconds(self, crawler_type: CrawlerType) -> int:
        """Return debounce window in seconds for the given crawler type.

        Falls back to the FILESYSTEM window if the crawler type is not
        explicitly configured (defensive default).
        """
        return self.debounce_windows_seconds.get(
            crawler_type,
            _DEFAULT_FILESYSTEM_DEBOUNCE_S,
        )


__all__ = ["ModelCrawlSchedulerConfig"]
