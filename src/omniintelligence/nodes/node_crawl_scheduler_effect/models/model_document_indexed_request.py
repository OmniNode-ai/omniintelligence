# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""ModelDocumentIndexedRequest — request to reset a debounce window.

Input to ``HandlerDocumentIndexed.handle()``.  Built from a
``document-indexed.v1`` event; the debounce state manager is passed to the
handler constructor.

Reference: OMN-2384
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_crawl_scheduler_effect.models.enum_crawler_type import (
    CrawlerType,
)


class ModelDocumentIndexedRequest(BaseModel):
    """Key of the debounce entry to clear after a successful crawl."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    source_ref: str = Field(
        ...,
        description="Canonical source identifier from the indexed event.",
    )
    crawler_type: CrawlerType = Field(
        ...,
        description="Crawler type from the indexed event.",
    )


__all__ = ["ModelDocumentIndexedRequest"]
