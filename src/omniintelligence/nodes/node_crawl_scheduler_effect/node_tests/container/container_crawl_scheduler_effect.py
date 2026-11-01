# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Binding site for NodeCrawlSchedulerEffect in the node_crawl_scheduler_effect tests.

The node is built here, the one binding site, and the tests resolve it through
``resolve_crawl_scheduler_effect`` instead of constructing it (OMN-21679).
"""

from __future__ import annotations

from omnibase_core.models.container.model_onex_container import ModelONEXContainer

from omniintelligence.nodes.node_crawl_scheduler_effect.node import (
    NodeCrawlSchedulerEffect,
)


def resolve_crawl_scheduler_effect(
    container: ModelONEXContainer,
) -> NodeCrawlSchedulerEffect:
    """Resolve the NodeCrawlSchedulerEffect bound to ``container``."""
    return NodeCrawlSchedulerEffect(container)


__all__ = ["resolve_crawl_scheduler_effect"]
