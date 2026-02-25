# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Node LinearCrawlerEffect — Linear ticket and document ingestion.

This node follows the ONEX declarative pattern:
    - DECLARATIVE effect driven by contract.yaml
    - Zero custom routing logic — all behavior from handler_routing
    - Lightweight shell that delegates to handlers via container resolution
    - Pattern: "Contract-driven, handlers wired externally"

Extends NodeEffect from omnibase_core for infrastructure I/O operations.

Responsibilities:
    - Consume crawl-tick.v1 events with crawl_type=LINEAR
    - Two-phase fetch: list (cheap id+updatedAt) then full content only on change
    - Emit document.discovered.v1, document.changed.v1, document.removed.v1
    - Update omnimemory_linear_state after each successful crawl

Design Decisions:
    - ``source_version`` = updatedAt ISO timestamp (not content hash).
      Skip full fetch when updatedAt unchanged (95%+ hit rate on steady-state).
    - SHA-256 content hash used as secondary filter: metadata-only updates
      that don't change rendered content do not emit a changed event.
    - Rate limiting handled via exponential backoff in the handler.

Related:
    - OMN-2388: This node implementation
    - OMN-2387: GitRepoCrawlerEffect (companion node, git-based change detection)
    - DESIGN_OMNIMEMORY_DOCUMENT_INGESTION_PIPELINE.md §5
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodeLinearCrawlerEffect(NodeEffect):
    """Declarative effect node for Linear ticket and document ingestion.

    This node is a pure declarative shell. All handler dispatch is defined
    in contract.yaml via ``handler_routing``. The node itself contains NO
    custom routing code.

    Supported Operations (defined in contract.yaml handler_routing):
        - crawl_linear: Fetch Linear issues/docs and emit document lifecycle events

    Dependency Injection:
        The ``handle_linear_crawl`` handler accepts a ``ProtocolLinearStateStore``
        instance and a ``ProtocolLinearClient`` instance. These are resolved
        by the caller or RuntimeHostProcess.

    Example:
        ```python
        from omniintelligence.nodes.node_linear_crawler_effect import (
            NodeLinearCrawlerEffect,
            handle_linear_crawl,
        )

        result = await handle_linear_crawl(
            ModelLinearCrawlInput(team_id="omninode", crawl_scope="omninode/shared"),
            linear_state=my_state_store,
            linear_client=my_linear_client,
        )
        ```
    """

    # Pure declarative shell — all behavior defined in contract.yaml


__all__ = ["NodeLinearCrawlerEffect"]
