# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request model for the code crawler's file walk."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_code_crawler_effect.models.model_crawl_config import (
    ModelCrawlConfig,
)


class ModelCrawlFilesRequest(BaseModel):
    """One file-walk request: the crawl configuration and its per-run options."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    config: ModelCrawlConfig
    crawl_id: str | None = None
    repo_filter: str | None = None


__all__ = ["ModelCrawlFilesRequest"]
