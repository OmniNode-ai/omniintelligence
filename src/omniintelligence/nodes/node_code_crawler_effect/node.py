# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Code Crawler Effect Node — thin shell delegating to handler."""

from __future__ import annotations

from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_file_discovered_event import (
    ModelCodeFileDiscoveredEvent,
)
from omniintelligence.nodes.node_code_crawler_effect.handlers.handler_crawl_files import (
    crawl_files,
)
from omniintelligence.nodes.node_code_crawler_effect.models.model_crawl_config import (
    ModelCrawlConfig,
)

__all__ = [
    "ModelCrawlConfig",
    "ModelCodeFileDiscoveredEvent",
    "crawl_files",
]
