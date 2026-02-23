# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""CrawlerType enum for the crawl scheduler.

Matches the design doc definition in:
    omni_save/design/DESIGN_OMNIMEMORY_DOCUMENT_INGESTION_PIPELINE.md §4

Reference: OMN-2384
"""

from enum import Enum


class CrawlerType(str, Enum):
    """Type of crawler that initiated a crawl request.

    Each crawler type has a distinct per-source debounce window:
      - FILESYSTEM: 30 seconds
      - GIT_REPO:   5 minutes
      - LINEAR:     60 minutes
      - WATCHDOG:   (not subject to scheduler debounce — watchdog-triggered
                    crawl requests pass through as FILESYSTEM)
    """

    FILESYSTEM = "filesystem"
    GIT_REPO = "git_repo"
    LINEAR = "linear"
    WATCHDOG = "watchdog"


__all__ = ["CrawlerType"]
