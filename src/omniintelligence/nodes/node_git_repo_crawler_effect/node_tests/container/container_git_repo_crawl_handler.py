# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Binding site for HandlerGitRepoCrawl in the node_git_repo_crawler_effect tests.

The handler is built here, the one binding site, and the tests resolve it
through ``resolve_git_repo_crawl_handler`` instead of constructing it
(OMN-21679).
"""

from __future__ import annotations

from omniintelligence.nodes.node_git_repo_crawler_effect.handlers.handler_git_repo_crawl import (
    HandlerGitRepoCrawl,
)
from omniintelligence.nodes.node_git_repo_crawler_effect.handlers.protocol_crawl_state import (
    ProtocolCrawlStateStore,
)


def resolve_git_repo_crawl_handler(
    crawl_state: ProtocolCrawlStateStore,
) -> HandlerGitRepoCrawl:
    """Resolve the HandlerGitRepoCrawl bound to ``crawl_state``."""
    return HandlerGitRepoCrawl(crawl_state=crawl_state)


__all__ = ["resolve_git_repo_crawl_handler"]
