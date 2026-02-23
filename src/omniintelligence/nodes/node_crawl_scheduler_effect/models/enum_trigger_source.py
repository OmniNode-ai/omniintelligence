# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""TriggerSource enum for crawl tick commands.

Identifies how a crawl was triggered — used in ModelCrawlTickCommand
to give downstream crawlers context about the origin of a tick.

Reference: OMN-2384
"""

from enum import Enum


class EnumTriggerSource(str, Enum):
    """Source that triggered a crawl tick.

    Values match the Literal union defined in the design doc:
        omni_save/design/DESIGN_OMNIMEMORY_DOCUMENT_INGESTION_PIPELINE.md §4
    """

    SCHEDULED = "scheduled"
    MANUAL = "manual"
    GIT_HOOK = "git_hook"
    FILESYSTEM_WATCH = "filesystem_watch"


__all__ = ["EnumTriggerSource"]
